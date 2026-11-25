import json
import re

import pytest

from workflow_factory.agent_desktop import (
    SNAPSHOT_ATTEMPTS,
    AgentDesktop,
    AgentDesktopError,
    read_secret,
    resolve_binary,
    system_frame_fields,
    version_of_pid,
)
from workflow_factory.desktop import AppKey, Control, Desktop, Frame

from fake_desktop import FakeDesktop

FORBIDDEN_FLAGS = {"--force", "--trace", "--trace-strict", "--screenshot", "--debug"}


class FakeRunner:
    """Stands in for the agent-desktop process: records calls, replays canned JSON."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, args, stdin=None):
        assert not FORBIDDEN_FLAGS & set(args), args
        self.calls.append((list(args), stdin))
        return json.dumps(self.replies.pop(0))


def ok(data):
    return {"ok": True, "data": data}


def test_find_builds_exact_query_and_returns_control_with_ref():
    runner = FakeRunner(
        ok({"snapshot_id": "s1", "matches": [
            {"ref_id": "@s1:e5", "role": "button", "name": "Pencil", "states": []}]})
    )

    control = AgentDesktop("mspaint.exe", runner, settle_seconds=0).find("button", "Pencil", "PencilBtn")

    assert control == Control(role="button", name="Pencil", automation_id="PencilBtn")
    assert control.ref == "@s1:e5"
    assert runner.calls == [(
        ["find", "--app", "mspaint.exe", "--role", "button", "--name", "Pencil",
         "--exact", "--native-id", "PencilBtn"], None)]


def test_find_returns_none_when_nothing_matches():
    runner = FakeRunner(ok({"snapshot_id": "s1", "matches": []}))

    assert AgentDesktop("mspaint.exe", runner, settle_seconds=0).find("button", "Nope") is None


def test_click_uses_the_control_ref():
    runner = FakeRunner(ok({}))

    AgentDesktop("mspaint.exe", runner, settle_seconds=0).click(Control("button", "Pencil", ref="@s1:e5"))

    assert runner.calls == [(["click", "@s1:e5"], None)]


def test_cli_failure_surfaces_as_typed_error():
    runner = FakeRunner({"ok": False, "error": {"code": "STALE_REF", "message": "gone"}})

    with pytest.raises(AgentDesktopError) as caught:
        AgentDesktop("mspaint.exe", runner, settle_seconds=0).click(Control("button", "Pencil", ref="@s1:e5"))

    assert caught.value.code == "STALE_REF"


def test_type_text_goes_through_stdin_never_arguments():
    runner = FakeRunner(ok({}))

    AgentDesktop("notepad.exe", runner, settle_seconds=0).type_text(Control("edit", "Body", ref="@s1:e2"), "s3cret")

    args, stdin = runner.calls[0]
    assert args == ["type", "@s1:e2", "--stdin"]
    assert stdin == "s3cret"
    assert all("s3cret" not in a for a in args)


def test_resolve_binary_skips_the_npm_cmd_shim_and_uses_the_real_exe(tmp_path):
    shim = tmp_path / "agent-desktop.CMD"
    shim.write_text("")
    real = tmp_path / "node_modules" / "agent-desktop" / "bin" / "agent-desktop-win32-x64.exe"
    real.parent.mkdir(parents=True)
    real.write_text("")

    assert resolve_binary(which=lambda name: str(shim)) == str(real)


def test_resolve_binary_missing_install_is_a_typed_error():
    with pytest.raises(AgentDesktopError) as caught:
        resolve_binary(which=lambda name: None)

    assert caught.value.code == "NOT_INSTALLED"


def test_snapshot_retries_while_the_window_is_transiently_ambiguous():
    transient = {"ok": False, "error": {"code": "AMBIGUOUS_TARGET", "message": "2 windows"}}
    runner = FakeRunner(transient, ok({"snapshot_id": "s1", "tree": {"role": "window"}}))

    controls = AgentDesktop("mspaint.exe", runner, settle_seconds=0).snapshot()

    assert controls == (Control("window", ""),)
    assert len(runner.calls) == 2


def test_snapshot_gives_up_with_typed_error_after_bounded_retries():
    transient = {"ok": False, "error": {"code": "AMBIGUOUS_TARGET", "message": "2 windows"}}
    runner = FakeRunner(*[transient] * 10)

    with pytest.raises(AgentDesktopError) as caught:
        AgentDesktop("mspaint.exe", runner, settle_seconds=0).snapshot()

    assert caught.value.code == "AMBIGUOUS_TARGET"
    assert len(runner.calls) == SNAPSHOT_ATTEMPTS


def test_snapshot_reads_native_id_published_as_kind_value_object():
    tree = {"role": "window", "children": [
        {"role": "button", "name": "Save", "ref_id": "@s1:e1",
         "native_id": {"kind": "automation_id", "value": "Save"}}]}
    runner = FakeRunner(ok({"snapshot_id": "s1", "tree": tree}))

    controls = AgentDesktop("mspaint.exe", runner, settle_seconds=0).snapshot()

    assert Control("button", "Save", "Save") in controls


def test_snapshot_flattens_tree_into_controls():
    tree = {"role": "window", "children": [
        {"role": "toolbar", "children": [
            {"role": "button", "name": "Pencil", "native_id": "PencilBtn", "ref_id": "@s1:e5"},
            {"role": "button", "name": "Fill", "ref_id": "@s1:e6"}]}]}
    runner = FakeRunner(ok({"snapshot_id": "s1", "tree": tree}))

    controls = AgentDesktop("mspaint.exe", runner, settle_seconds=0).snapshot()

    assert Control("button", "Pencil", "PencilBtn") in controls
    assert Control("button", "Fill") in controls
    assert runner.calls[0][0][:3] == ["snapshot", "--app", "mspaint.exe"]


def test_non_json_output_surfaces_as_typed_error():
    with pytest.raises(AgentDesktopError) as caught:
        AgentDesktop("mspaint.exe", lambda args, stdin=None: "", settle_seconds=0).find("button", "x")

    assert caught.value.code == "INVALID_RESPONSE"


def test_reply_missing_expected_fields_surfaces_as_typed_error():
    runner = FakeRunner(ok({"snapshot_id": "s1"}))

    with pytest.raises(AgentDesktopError) as caught:
        AgentDesktop("mspaint.exe", runner, settle_seconds=0).snapshot()

    assert caught.value.code == "INVALID_RESPONSE"


def test_process_that_cannot_start_surfaces_as_typed_error():
    def broken(args, stdin=None):
        raise FileNotFoundError("agent-desktop.exe")

    with pytest.raises(AgentDesktopError) as caught:
        AgentDesktop("mspaint.exe", broken, settle_seconds=0).click(Control("button", "x", ref="@a:e1"))

    assert caught.value.code == "CLI_UNAVAILABLE"


def test_real_adapter_and_fake_both_satisfy_the_desktop_port():
    assert isinstance(AgentDesktop("mspaint.exe", FakeRunner()), Desktop)
    assert isinstance(FakeDesktop(controls=[]), Desktop)


def test_find_reports_the_native_id_of_the_matched_control():
    runner = FakeRunner(ok({"snapshot_id": "s1", "matches": [
        {"ref_id": "@s1:e5", "role": "button", "name": "Save",
         "native_id": {"kind": "automation_id", "value": "Save"}}]}))

    control = AgentDesktop("mspaint.exe", runner, settle_seconds=0).find("button", "Save")

    assert control == Control("button", "Save", "Save")


def test_executable_version_of_a_running_process_has_four_numeric_parts():
    import os

    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version_of_pid(os.getpid()))


def test_app_key_is_process_name_plus_executable_version():
    runner = FakeRunner(ok({"apps": [
        {"name": "other.exe", "pid": 1}, {"name": "mspaint.exe", "pid": 42}]}))
    desktop = AgentDesktop("mspaint.exe", runner, settle_seconds=0, version_of=lambda pid: f"v{pid}")

    assert desktop.app_key() == AppKey("mspaint.exe", "v42")
    assert runner.calls == [(["list-apps"], None)]


def test_app_name_matches_regardless_of_case():
    runner = FakeRunner(ok({"apps": [{"name": "MSPaint.exe", "pid": 7}]}))
    desktop = AgentDesktop("mspaint.exe", runner, settle_seconds=0, version_of=lambda pid: "1.0")

    assert desktop.app_key() == AppKey("mspaint.exe", "1.0")


@pytest.mark.live
def test_system_frame_fields_reads_resolution_scale_language_and_theme():
    context = system_frame_fields()

    assert context["resolution_width"] >= 800 and context["resolution_height"] >= 600
    assert context["scale"] >= 1.0
    assert context["theme"] in ("light", "dark")
    assert re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]+)*", context["language"])


def test_frame_combines_window_geometry_from_the_cli_with_system_frame_fields():
    windows = ok([  # the real CLI answers list-windows with a bare list
        {"app_name": "other.exe", "bounds": {"x": 0, "y": 0, "width": 1, "height": 1}, "minimized": False},
        {"app_name": "mspaint.exe", "bounds": {"x": 5, "y": 6, "width": 800, "height": 600}, "minimized": False},
    ])
    context = {"resolution_width": 1920, "resolution_height": 1080, "scale": 1.25,
               "language": "es-AR", "theme": "dark"}
    desktop = AgentDesktop("mspaint.exe", FakeRunner(windows), settle_seconds=0,
                           system_frame_fields=lambda: context)

    assert desktop.frame() == Frame(
        window_state="normal", window_width=800, window_height=600, resolution_width=1920,
        resolution_height=1080, scale=1.25, language="es-AR", theme="dark")


def test_minimized_and_full_screen_windows_report_their_window_state():
    context = {"resolution_width": 1920, "resolution_height": 1080, "scale": 1.0,
               "language": "en-US", "theme": "light"}

    def frame_of(window):
        runner = FakeRunner(ok([{"app_name": "mspaint.exe", **window}]))
        return AgentDesktop("mspaint.exe", runner, system_frame_fields=lambda: context).frame()

    assert frame_of({"bounds": {"x": 0, "y": 0, "width": 1920, "height": 1040}, "minimized": False}).window_state == "maximized"
    assert frame_of({"bounds": {"x": 0, "y": 0, "width": 300, "height": 200}, "minimized": True}).window_state == "minimized"


def test_type_secret_reads_the_credential_store_and_pipes_the_value_through_stdin():
    runner = FakeRunner(ok({}))
    desktop = AgentDesktop("mspaint.exe", runner, settle_seconds=0, read_secret=lambda ref: f"value-of-{ref}")

    desktop.type_secret(Control("textfield", "Password", ref="@s1:e2"), "login")

    args, stdin = runner.calls[0]
    assert args == ["type", "@s1:e2", "--stdin"]
    assert stdin == "value-of-login"
    assert all("value-of-login" not in a for a in args)


def test_find_reports_a_secure_control_as_secure_but_still_readable():
    runner = FakeRunner(ok({"snapshot_id": "s1", "matches": [
        {"ref_id": "@s1:e5", "role": "textfield", "name": "Password", "states": ["enabled", "secure"]}]}))

    control = AgentDesktop("mspaint.exe", runner, settle_seconds=0).find("textfield", "Password")

    assert control.secure is True and control.readable is True


@pytest.mark.live
def test_credential_store_round_trip_keeps_the_value_out_of_the_reference():
    import uuid

    ref = f"dwf-live-test-{uuid.uuid4().hex}"
    _credential_write(ref, "s3cret-value")
    try:
        assert read_secret(ref) == "s3cret-value"
    finally:
        _credential_delete(ref)
    with pytest.raises(AgentDesktopError) as caught:
        read_secret(ref)
    assert caught.value.code == "SECRET_NOT_FOUND"


@pytest.mark.live
def test_real_cli_accepts_text_on_stdin_and_reports_a_stale_ref_as_typed_error():
    desktop = AgentDesktop("mspaint.exe", settle_seconds=0)

    with pytest.raises(AgentDesktopError) as caught:
        desktop.type_text(Control("textfield", "x", ref="@sdeadbeef000000:e1"), "plain text on stdin")

    assert caught.value.code != "INVALID_ARGS"


def _credential_write(ref, value):
    import ctypes
    from ctypes import wintypes

    class Credential(ctypes.Structure):
        _fields_ = [("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                    ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR)]

    blob = value.encode("utf-16-le")
    buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    credential = Credential(Type=1, TargetName=ref, CredentialBlobSize=len(blob),
                            CredentialBlob=buffer, Persist=1, UserName="dwf-live-test")
    assert ctypes.windll.advapi32.CredWriteW(ctypes.byref(credential), 0)


def _credential_delete(ref):
    import ctypes

    ctypes.windll.advapi32.CredDeleteW(ref, 1, 0)


def test_a_cli_error_while_typing_a_secret_never_repeats_the_cli_message():
    leaky = {"ok": False, "error": {"code": "ACTION_FAILED", "message": "could not type hunter2"}}
    desktop = AgentDesktop("mspaint.exe", FakeRunner(leaky), settle_seconds=0,
                           read_secret=lambda ref: "hunter2")

    with pytest.raises(AgentDesktopError) as caught:
        desktop.type_secret(Control("textfield", "Password", ref="@s1:e2"), "login")

    assert caught.value.code == "ACTION_FAILED"
    assert "hunter2" not in str(caught.value)


def test_click_at_turns_a_fraction_of_the_anchor_into_a_physical_click_inside_it():
    bounds = ok({"value": {"x": 2620.0, "y": 75.0, "width": 32.0, "height": 32.0}})
    runner = FakeRunner(bounds, ok({}))

    path = []
    AgentDesktop("mspaint.exe", runner, settle_seconds=0, move_cursor=path.append,
                 cursor_position=lambda: (0, 0), glide_pause=lambda _: None).click_at(
        Control("icon", "Recycle Bin", ref="@s1:e5"), 0.5, 0.25)

    assert path[0] == (0, 0) and path[-1] == (2636, 83)  # the cursor glided from where it was
    assert runner.calls == [
        (["get", "@s1:e5", "--property", "bounds"], None),
        (["--headed", "mouse-click", "--xy", "2636,83"], None),  # 2620 + 16, 75 + 8
    ]


def test_drag_computes_both_ends_from_their_own_anchors_and_centres_when_no_fraction_is_given():
    source = ok({"value": {"x": 100.0, "y": 200.0, "width": 40.0, "height": 20.0}})
    destination = ok({"value": {"x": 1000.0, "y": 500.0, "width": 100.0, "height": 100.0}})
    runner = FakeRunner(source, destination, ok({}))

    path = []
    AgentDesktop("explorer.exe", runner, settle_seconds=0, move_cursor=path.append,
                 cursor_position=lambda: (0, 0), glide_pause=lambda _: None).drag(
        Control("listitem", "Report.docx", ref="@s1:e1"), None,
        Control("pane", "Desktop", ref="@s1:e9"), (0.9, 0.5))

    assert path[-1] == (120, 210)  # it glides to where the drag starts
    assert runner.calls[2] == (
        ["--headed", "drag", "--from-xy", "120,210", "--to-xy", "1090,550"], None)


def test_app_key_process_name_is_lowercased_so_lessons_and_consents_never_split_by_case():
    runner = FakeRunner(ok({"apps": [{"name": "MSPaint.exe", "pid": 7}]}))
    desktop = AgentDesktop("MSPaint.exe", runner, settle_seconds=0, version_of=lambda pid: "1.0")

    assert desktop.app_key() == AppKey("mspaint.exe", "1.0")


@pytest.mark.live
def test_input_detector_reads_cursor_last_input_and_foreground_without_touching_anything():
    desktop = AgentDesktop("mspaint.exe", settle_seconds=0)

    (x, y), last_input = desktop.input_fingerprint()
    foreground = desktop.foreground_app()

    assert isinstance(x, int) and isinstance(y, int) and last_input >= 0
    assert desktop.idle_seconds() >= 0
    assert foreground == foreground.lower() and foreground.endswith(".exe")


@pytest.mark.live
def test_the_emergency_hotkey_listener_calls_back_when_its_hotkey_message_arrives():
    import threading

    from workflow_factory.hotkey import EmergencyHotkey

    pressed = threading.Event()
    hotkey = EmergencyHotkey(pressed.set)
    hotkey.start()
    try:
        hotkey.simulate_press()  # posts the WM_HOTKEY message: no keyboard input is sent
        assert pressed.wait(timeout=3)
    finally:
        hotkey.stop()


@pytest.mark.live
def test_the_cursor_is_read_in_physical_pixels_even_from_a_dpi_unaware_thread():
    import ctypes
    from ctypes import wintypes

    from workflow_factory.agent_desktop import _get_cursor_pos

    user32 = ctypes.windll.user32
    user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    unaware, per_monitor = ctypes.c_void_p(-1), ctypes.c_void_p(-4)

    def raw_read():
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y

    previous = user32.SetThreadDpiAwarenessContext(per_monitor)
    try:
        physical = raw_read()
        user32.SetThreadDpiAwarenessContext(unaware)
        virtualised, through_adapter = raw_read(), _get_cursor_pos()
    finally:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))

    if virtualised == physical:
        pytest.skip("this setup does not virtualise the cursor (100% scale there), nothing to correct")
    assert through_adapter == physical
@pytest.mark.live
def test_pressing_the_emergency_hotkey_stops_a_flow_that_is_about_to_run(tmp_path):
    import threading

    from workflow_factory import EmergencyHotkey, Flow, Node, emergency_stop, run_flow, save_lesson

    from fake_desktop import FakeDesktop, button, lesson

    pressed = threading.Event()

    def on_press():
        emergency_stop()
        pressed.set()

    hotkey = EmergencyHotkey(on_press)
    hotkey.start()
    try:
        hotkey.simulate_press()
        assert pressed.wait(timeout=3)
    finally:
        hotkey.stop()
    save_lesson(tmp_path / "user.db", lesson("a", "Alpha"))
    desktop = FakeDesktop(controls=[button("Alpha")])

    result = run_flow(Flow(id="f", nodes=[Node("a", "a")]), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.emergency is True and desktop.clicks == []


DENIED = {"ok": False, "error": {"code": "POLICY_DENIED", "message": "Target is not actionable: supported_action"}}


def test_a_field_that_only_accepts_a_value_is_filled_with_set_value_through_stdin():
    runner = FakeRunner(DENIED, ok({"property": "value", "value": "abc "}), ok({}))

    AgentDesktop("notepad.exe", runner, settle_seconds=0).type_text(Control("edit", "Body", ref="@s1:e2"), "hello")

    # typing inserts, set-value replaces: the readable content is kept and the text appended
    assert runner.calls == [(["type", "@s1:e2", "--stdin"], "hello"), (["get", "@s1:e2", "--property", "value"], None),
                            (["set-value", "@s1:e2", "--stdin"], "abc hello")]


def test_an_empty_field_that_reports_no_value_is_just_set():
    runner = FakeRunner(DENIED, ok({"property": "value", "value": None}), ok({}))

    AgentDesktop("notepad.exe", runner, settle_seconds=0).type_text(Control("edit", "Body", ref="@s1:e2"), "hello")

    assert runner.calls[-1] == (["set-value", "@s1:e2", "--stdin"], "hello")


def test_a_policy_denial_for_another_reason_is_not_worked_around():
    other = {"ok": False, "error": {"code": "POLICY_DENIED", "message": "application is protected"}}
    runner = FakeRunner(other)

    with pytest.raises(AgentDesktopError) as error:
        AgentDesktop("notepad.exe", runner, settle_seconds=0).type_text(Control("edit", "Body", ref="@s1:e2"), "hello")

    assert error.value.code == "POLICY_DENIED"
    assert len(runner.calls) == 1


def test_a_secret_falls_back_to_set_value_through_stdin_and_never_through_arguments():
    runner = FakeRunner(DENIED, ok({}))

    AgentDesktop("notepad.exe", runner, settle_seconds=0, read_secret=lambda ref: "s3cret").type_secret(
        Control("edit", "", ref="@s1:e3", secure=True), "ref:one")

    assert [call[0] for call in runner.calls] == [["type", "@s1:e3", "--stdin"], ["set-value", "@s1:e3", "--stdin"]]
    assert all(call[1] == "s3cret" for call in runner.calls)
    assert all("s3cret" not in arg for call in runner.calls for arg in call[0])


def test_only_a_policy_denial_triggers_the_set_value_fallback():
    runner = FakeRunner({"ok": False, "error": {"code": "STALE_REF", "message": "gone"}})

    with pytest.raises(AgentDesktopError) as error:
        AgentDesktop("notepad.exe", runner, settle_seconds=0).type_text(Control("edit", "Body", ref="@s1:e2"), "hello")

    assert error.value.code == "STALE_REF"
    assert len(runner.calls) == 1


def test_a_failed_secret_fallback_withholds_the_details():
    runner = FakeRunner(DENIED, {"ok": False, "error": {"code": "ACTION_FAILED", "message": "echo s3cret"}})

    with pytest.raises(AgentDesktopError) as error:
        AgentDesktop("notepad.exe", runner, settle_seconds=0, read_secret=lambda ref: "s3cret").type_secret(
            Control("edit", "", ref="@s1:e3", secure=True), "ref:one")

    assert "s3cret" not in str(error.value)


def test_snapshot_marks_a_password_field_as_secure_and_leaves_a_plain_one_alone():
    tree = {"role": "window", "children": [
        {"role": "textfield", "name": "Plain field", "ref_id": "@s1:e1", "states": ["focused"]},
        {"role": "textfield", "ref_id": "@s1:e2", "states": ["secure"]},
    ]}
    runner = FakeRunner(ok({"snapshot_id": "s1", "tree": tree}))

    controls = AgentDesktop("notepad.exe", runner, settle_seconds=0).snapshot()

    assert [(c.ref, c.secure) for c in controls if c.role == "textfield"] == [("@s1:e1", False), ("@s1:e2", True)]
