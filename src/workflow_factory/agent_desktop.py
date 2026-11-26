"""Desktop port backed by the real agent-desktop CLI.

Deliberately has no way to pass --force, --trace or screenshot flags (consent
gate, see ADR-0002). Text goes through stdin so it never lands in process args.
"""

import contextlib
import ctypes
import json
import random
import shutil
import subprocess
import time
import winreg
from collections.abc import Callable
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from workflow_factory import clipboard
from workflow_factory.clipboard import WindowsClipboard
from workflow_factory.desktop import AppKey, Control, DesktopError, Frame
from workflow_factory.humanize import glide

Runner = Callable[[list[str], str | None], str]
SNAPSHOT_ATTEMPTS = 5


class AgentDesktopError(DesktopError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def resolve_binary(which=shutil.which) -> str:
    """Path of the real agent-desktop exe. The npm `.cmd` shim is skipped: running it goes
    through cmd.exe, where a control name containing `&` would become a shell command."""
    found = which("agent-desktop")
    if not found:
        raise AgentDesktopError("NOT_INSTALLED", "agent-desktop is not on PATH")
    real = Path(found).parent / "node_modules" / "agent-desktop" / "bin" / "agent-desktop-win32-x64.exe"
    return str(real) if real.exists() else found


def _run_cli(args: list[str], stdin: str | None = None) -> str:
    # exit code 1 still carries a JSON error envelope on stdout, so no check=True
    done = subprocess.run(
        [resolve_binary(), *args], input=stdin, capture_output=True, text=True, encoding="utf-8"
    )
    return done.stdout


def _image_path(pid: int) -> str:
    """Full path of a running process' executable."""
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise AgentDesktopError("PROCESS_UNAVAILABLE", f"cannot open process {pid}")
    try:
        size = ctypes.c_ulong(1024)
        path = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, path, ctypes.byref(size)):
            raise AgentDesktopError("PROCESS_UNAVAILABLE", f"no image path for process {pid}")
        return path.value
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


def version_of_pid(pid: int) -> str:
    """Executable file version (a.b.c.d) of a running process, via the Windows version resource."""
    version, path = ctypes.windll.version, _image_path(pid)
    length = version.GetFileVersionInfoSizeW(path, None)
    block = ctypes.create_string_buffer(length)
    if not length or not version.GetFileVersionInfoW(path, 0, length, block):
        raise AgentDesktopError("VERSION_UNAVAILABLE", f"no version resource in {path}")
    info, info_len = ctypes.c_void_p(), ctypes.c_uint()
    version.VerQueryValueW(block, "\\", ctypes.byref(info), ctypes.byref(info_len))
    ms, ls = ctypes.cast(info.value + 8, ctypes.POINTER(ctypes.c_uint * 2)).contents
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


@contextlib.contextmanager
def _physical_pixels():
    """This thread sees physical screen pixels (per-monitor DPI v2), the same units agent-desktop uses."""
    user32 = ctypes.windll.user32
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        yield
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))


def _get_cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    with _physical_pixels():
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def _set_cursor_pos(point: tuple[int, int]) -> None:
    with _physical_pixels():
        ctypes.windll.user32.SetCursorPos(point[0], point[1])


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _last_input_tick() -> int:
    info = _LastInputInfo(ctypes.sizeof(_LastInputInfo))
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return info.dwTime


def foreground_process_name() -> str:
    """Lower-case executable name of the app that owns the foreground window."""
    user32 = ctypes.windll.user32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
    return Path(_image_path(pid.value)).name.lower()


def system_frame_fields() -> dict:
    """Resolution (physical px), scale, UI language and app theme of this Windows session."""
    user32, gdi32, shcore, kernel = (ctypes.windll.user32, ctypes.windll.gdi32,
                                     ctypes.windll.shcore, ctypes.windll.kernel32)
    hdc = user32.GetDC(0)
    width, height = gdi32.GetDeviceCaps(hdc, 118), gdi32.GetDeviceCaps(hdc, 117)  # DESKTOPHORZRES/VERTRES
    user32.ReleaseDC(0, hdc)
    locale = ctypes.create_unicode_buffer(85)
    kernel.GetUserDefaultLocaleName(locale, 85)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            light = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
    except OSError:
        light = 1  # value absent on older Windows: light is the platform default
    return {
        "resolution_width": width, "resolution_height": height,
        "scale": shcore.GetScaleFactorForDevice(0) / 100,
        "language": locale.value, "theme": "light" if light else "dark",
    }


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def read_secret(ref: str) -> str:
    """Value of a generic Windows Credential Manager entry. Only the adapter ever holds it."""
    pointer = ctypes.POINTER(_Credential)()
    if not ctypes.windll.advapi32.CredReadW(ref, 1, 0, ctypes.byref(pointer)):  # CRED_TYPE_GENERIC
        raise AgentDesktopError("SECRET_NOT_FOUND", ref)
    try:
        credential = pointer.contents
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode("utf-16-le")
    finally:
        ctypes.windll.advapi32.CredFree(pointer)


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def capture_region(x: int, y: int, width: int, height: int) -> np.ndarray:
    """RGB pixels of a screen rectangle (physical px), read with GDI. Reads only, sends no input."""
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    handle = ctypes.c_void_p
    for name, restype in (("GetDC", handle), ("CreateCompatibleDC", handle),
                          ("CreateCompatibleBitmap", handle), ("SelectObject", handle)):
        getattr(user32 if name == "GetDC" else gdi32, name).restype = restype
    user32.SetThreadDpiAwarenessContext.restype = handle
    previous = user32.SetThreadDpiAwarenessContext(handle(-4))  # per-monitor v2: coordinates are physical
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(handle(screen))
    bitmap = gdi32.CreateCompatibleBitmap(handle(screen), width, height)
    try:
        gdi32.SelectObject(handle(memory), handle(bitmap))
        # SRCCOPY | CAPTUREBLT: also captures layered windows
        if not gdi32.BitBlt(handle(memory), 0, 0, width, height, handle(screen), x, y, 0x00CC0020 | 0x40000000):
            raise AgentDesktopError("CAPTURE_FAILED", f"{width}x{height} at {x},{y}")
        header = _BitmapInfoHeader(ctypes.sizeof(_BitmapInfoHeader), width, -height, 1, 32, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(handle(memory), handle(bitmap), 0, height, buffer, ctypes.byref(header), 0)
    finally:
        gdi32.DeleteObject(handle(bitmap))
        gdi32.DeleteDC(handle(memory))
        user32.ReleaseDC(None, handle(screen))
        user32.SetThreadDpiAwarenessContext(previous)
    return np.frombuffer(buffer, np.uint8).reshape(height, width, 4)[:, :, 2::-1].copy()  # BGRA -> RGB


def _native_id(raw) -> str:
    # real CLI publishes {"kind": "automation_id", "value": "Save"}
    return raw.get("value", "") if isinstance(raw, dict) else raw or ""


def _walk(node: dict):
    if node.get("role"):
        yield Control(
            role=node["role"],
            name=node.get("name", ""),
            automation_id=_native_id(node.get("native_id")),
            ref=node.get("ref_id", ""),
            secure="secure" in node.get("states", []),
        )
    for child in node.get("children", []):
        yield from _walk(child)


class AgentDesktop:
    def __init__(
        self, app: str, runner: Runner = _run_cli, settle_seconds: float = 0.5,
        version_of=version_of_pid, system_frame_fields=system_frame_fields,
        read_secret=read_secret, move_cursor=None, cursor_position=None,
        glide_pause=time.sleep, rng=random, clipboard_backend=None,
    ):
        self._board = clipboard_backend  # None: the real Windows clipboard, opened when a paste needs it
        self._app = app
        self._version_of = version_of
        self._system_frame_fields = system_frame_fields
        self._read_secret = read_secret
        self._move_cursor = move_cursor  # None: the real cursor (looked up at call time)
        self._cursor_position = cursor_position or _get_cursor_pos
        self._glide_pause, self._rng = glide_pause, rng
        self._runner = runner
        self._settle = settle_seconds  # ponytail: fixed pause, poll for stability if apps repaint slower

    def _call(self, args: list[str], stdin: str | None = None) -> dict:
        try:
            reply = json.loads(self._runner(args, stdin))
        except OSError as error:
            raise AgentDesktopError("CLI_UNAVAILABLE", str(error)) from error
        except ValueError as error:
            raise AgentDesktopError("INVALID_RESPONSE", "output is not JSON") from error
        if not reply.get("ok"):
            error = reply.get("error", {})
            raise AgentDesktopError(error.get("code", "UNKNOWN"), error.get("message", ""))
        return reply.get("data", {})

    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None:
        args = ["find", "--app", self._app, "--role", role, "--name", name, "--exact"]
        if automation_id:
            args += ["--native-id", automation_id]
        matches = self._call(args).get("matches", [])
        if not matches:
            return None
        match = matches[0]
        return Control(
            role=match.get("role", role),
            name=match.get("name", ""),
            automation_id=_native_id(match.get("native_id")) or automation_id or "",
            ref=match.get("ref_id", ""),
            # research 23: the CLI lists a password field with states ["secure"], hides its name and value
            secure="secure" in match.get("states", []),
        )

    def click(self, control: Control) -> None:
        self._call(["click", control.ref])
        time.sleep(self._settle)  # let the app repaint before the effect is measured

    def _point(self, anchor: Control, fraction: tuple[float, float] | None) -> tuple[int, int]:
        """Screen point at a fraction of the anchor's current bounds (centre when None)."""
        fx, fy = fraction or (0.5, 0.5)
        box = self._call(["get", anchor.ref, "--property", "bounds"])["value"]
        return round(box["x"] + fx * box["width"]), round(box["y"] + fy * box["height"])

    def _glide_to(self, point: tuple[int, int]) -> None:
        """Move the real cursor to the point like a hand would, not in one jump."""
        move = self._move_cursor or _set_cursor_pos
        glide(self._cursor_position(), point, move, rng=self._rng, sleep=self._glide_pause)

    def input_fingerprint(self) -> tuple:
        return self._cursor_position(), _last_input_tick()

    def idle_seconds(self) -> float:
        return ((ctypes.windll.kernel32.GetTickCount() - _last_input_tick()) & 0xFFFFFFFF) / 1000

    def foreground_app(self) -> str:
        return foreground_process_name()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def click_at(self, anchor: Control, fx: float, fy: float) -> None:
        """Physical click inside the anchor (never an absolute point from the caller)."""
        x, y = self._point(anchor, (fx, fy))
        self._glide_to((x, y))
        self._call(["--headed", "mouse-click", "--xy", f"{x},{y}"])
        time.sleep(self._settle)

    def drag(self, source: Control, source_point, destination: Control, destination_point) -> None:
        (x1, y1), (x2, y2) = self._point(source, source_point), self._point(destination, destination_point)
        self._glide_to((x1, y1))
        self._call(["--headed", "drag", "--from-xy", f"{x1},{y1}", "--to-xy", f"{x2},{y2}"])
        time.sleep(self._settle)

    def capture(self, anchor: Control) -> np.ndarray:
        time.sleep(self._settle)  # a retry is only useful if the screen had time to change
        box = self._call(["get", anchor.ref, "--property", "bounds"])["value"]
        return capture_region(round(box["x"]), round(box["y"]), round(box["width"]), round(box["height"]))

    def _enter(self, control: Control, text: str) -> None:
        """Insert text. A field with no semantic insert (only SetValue) is refused without focus: set its value.

        Typing inserts and set-value replaces, so a readable field keeps its content (the text is appended); a
        secure field cannot be read, so it is replaced (a password field is normally empty).
        """
        try:
            self._call(["type", control.ref, "--stdin"], stdin=text)
        except AgentDesktopError as error:
            if error.code != "POLICY_DENIED" or "supported_action" not in str(error):
                raise
            if not control.secure:
                text = (self._call(["get", control.ref, "--property", "value"]).get("value") or "") + text
            self._call(["set-value", control.ref, "--stdin"], stdin=text)  # takes no focus

    def type_text(self, control: Control, text: str) -> None:
        self._enter(control, text)

    def press_key(self, key: str) -> None:
        self._call(["--headed", "press", key])  # real input: it goes to whichever window is in the foreground

    def _clipboard(self):
        try:
            return self._board or WindowsClipboard()
        except (AttributeError, OSError) as error:  # not Windows, or no access to the clipboard
            raise AgentDesktopError("CLIPBOARD_UNAVAILABLE", str(error)) from error

    def clipboard_backup(self):
        try:
            return clipboard.backup(self._clipboard())
        except OSError as error:
            raise AgentDesktopError("CLIPBOARD_UNAVAILABLE", str(error)) from error

    def clipboard_set(self, text: str) -> None:
        try:
            clipboard.set_text(self._clipboard(), text)
        except OSError as error:
            raise AgentDesktopError("CLIPBOARD_UNAVAILABLE", str(error)) from error

    def clipboard_restore(self, saved) -> tuple[str, ...]:
        try:
            return clipboard.restore(self._clipboard(), saved)
        except OSError as error:
            raise AgentDesktopError("CLIPBOARD_UNAVAILABLE", str(error)) from error

    def read_text(self, control: Control) -> str:
        return self._call(["get", control.ref, "--property", "value"]).get("value") or ""  # no focus, no input

    def type_secret(self, control: Control, secret_ref: str) -> None:
        try:
            self._enter(control, self._read_secret(secret_ref))
        except AgentDesktopError as error:
            # the CLI message could echo what was typed: keep the code, drop the text
            raise AgentDesktopError(error.code, "typing a secret failed; details withheld") from None

    def snapshot(self) -> tuple[Control, ...]:
        for attempt in range(1, SNAPSHOT_ATTEMPTS + 1):
            try:
                tree = self._call(["snapshot", "--app", self._app, "-i"]).get("tree")
                if tree is None:
                    raise AgentDesktopError("INVALID_RESPONSE", "snapshot has no tree")
                return tuple(_walk(tree))
            except AgentDesktopError as error:
                # right after an action the app can briefly own two windows
                if error.code != "AMBIGUOUS_TARGET" or attempt == SNAPSHOT_ATTEMPTS:
                    raise
                time.sleep(self._settle)

    def app_key(self) -> AppKey:
        for app in self._call(["list-apps"]).get("apps", []):
            if app.get("name", "").lower() == self._app.lower():  # Windows process names ignore case
                return AppKey(self._app.lower(), self._version_of(app["pid"]))
        raise AgentDesktopError("APP_NOT_FOUND", self._app)

    def frame(self) -> Frame:
        fields = self._system_frame_fields()
        for window in self._call(["list-windows", "--app", self._app]):
            if window.get("app_name", "").lower() == self._app.lower():
                bounds = window["bounds"]
                full = (bounds["width"] >= 0.98 * fields["resolution_width"]
                        and bounds["height"] >= 0.9 * fields["resolution_height"])
                state = "minimized" if window.get("minimized") else "maximized" if full else "normal"
                return Frame(window_state=state, window_width=bounds["width"],
                             window_height=bounds["height"], **fields)
        raise AgentDesktopError("WINDOW_NOT_FOUND", self._app)

    def now(self) -> str:
        return datetime.now(UTC).isoformat()
