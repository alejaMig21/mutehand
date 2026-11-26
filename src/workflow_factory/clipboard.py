"""Back up the person's clipboard, put text on it for a paste, and put the person's own content back.

The logic is plain and takes a backend with four calls (`formats`, `get`, `set_all`, `name`), so it is tested without touching the
real clipboard. `WindowsClipboard` is the real backend. Every format whose bytes can be read is copied as it is and written back as
it was, including the copy or cut flag of copied files and rich text; a format that gives no bytes (a bitmap handle, a delayed
rendering) cannot be put back, and its name is reported instead of being lost without a word.
"""

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

CF_UNICODETEXT = 13


class Backend(Protocol):
    def formats(self) -> list[int]: ...
    def get(self, fmt: int) -> bytes | None: ...
    def set_all(self, items: dict[int, bytes]) -> None: ...
    def name(self, fmt: int) -> str: ...


@dataclass(frozen=True)
class Backup:
    items: dict[int, bytes]
    lost: tuple[str, ...]  # formats that could not be copied, by name


def backup(board: Backend) -> Backup:
    items: dict[int, bytes] = {}
    lost = []
    for fmt in board.formats():
        data = board.get(fmt)
        if data is None:
            lost.append(board.name(fmt))
        else:
            items[fmt] = data
    return Backup(items, tuple(lost))


def set_text(board: Backend, text: str) -> None:
    """Replace everything on the clipboard with this text, so nothing older can be pasted by mistake."""
    board.set_all({CF_UNICODETEXT: text.encode("utf-16-le") + b"\x00\x00"})


def restore(board: Backend, saved: Backup) -> tuple[str, ...]:
    """Put the saved content back. Returns the names of the formats that could not be put back."""
    board.set_all(saved.items)
    return saved.lost


# --- the real clipboard ---------------------------------------------------------------------------------

GMEM_MOVEABLE = 0x0002
_STANDARD = {1: "text (ANSI)", 2: "bitmap handle", 3: "metafile handle", 7: "OEM text", 8: "image", 9: "palette handle", 13: "text",
             14: "enhanced metafile handle", 15: "files", 16: "locale", 17: "image (v5)"}


class WindowsClipboard:
    """The Windows clipboard through user32 and kernel32. Opening it can fail while another program holds it: it retries."""

    def __init__(self, attempts: int = 20, pause: float = 0.05):
        self._user, self._kernel = ctypes.windll.user32, ctypes.windll.kernel32
        self._user.GetClipboardData.restype = wintypes.HANDLE
        self._user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        self._kernel.GlobalAlloc.restype = wintypes.HANDLE
        self._kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        self._kernel.GlobalLock.restype = ctypes.c_void_p
        self._kernel.GlobalLock.argtypes = [wintypes.HANDLE]
        self._kernel.GlobalUnlock.argtypes = [wintypes.HANDLE]
        self._kernel.GlobalSize.restype = ctypes.c_size_t
        self._kernel.GlobalSize.argtypes = [wintypes.HANDLE]
        self._attempts, self._pause = attempts, pause

    def _open(self) -> None:
        for _ in range(self._attempts):
            if self._user.OpenClipboard(None):
                return
            time.sleep(self._pause)
        raise OSError("the clipboard is held by another program")

    def formats(self) -> list[int]:
        self._open()
        try:
            found, fmt = [], 0
            while True:
                fmt = self._user.EnumClipboardFormats(fmt)
                if not fmt:
                    return found
                found.append(fmt)
        finally:
            self._user.CloseClipboard()

    def get(self, fmt: int) -> bytes | None:
        self._open()
        try:
            handle = self._user.GetClipboardData(fmt)
            if not handle or fmt in (2, 3, 9, 14):  # GDI handles are not memory blocks
                return None
            size = self._kernel.GlobalSize(handle)
            pointer = self._kernel.GlobalLock(handle)
            if not pointer or not size:
                return None
            try:
                return ctypes.string_at(pointer, size)
            finally:
                self._kernel.GlobalUnlock(handle)
        finally:
            self._user.CloseClipboard()

    def set_all(self, items: dict[int, bytes]) -> None:
        self._open()
        try:
            self._user.EmptyClipboard()
            for fmt, data in items.items():
                handle = self._kernel.GlobalAlloc(GMEM_MOVEABLE, len(data))
                pointer = self._kernel.GlobalLock(handle)
                ctypes.memmove(pointer, data, len(data))
                self._kernel.GlobalUnlock(handle)
                self._user.SetClipboardData(fmt, handle)  # the clipboard owns the block from here
        finally:
            self._user.CloseClipboard()

    def name(self, fmt: int) -> str:
        if fmt in _STANDARD:
            return _STANDARD[fmt]
        buffer = ctypes.create_unicode_buffer(128)
        return buffer.value if self._user.GetClipboardFormatNameW(fmt, buffer, 128) else f"format {fmt}"
