"""Steps that put text into an app that refuses set-value (Word): by paste, or by keys one at a time.

Both send real keys to the foreground window, so they run alone under the input lock, refuse when the foreground window is not
the app's, and a paste backs up the person's clipboard first and puts it back, saying what it could not.
"""

import pytest
from fake_clipboard import CF_BITMAP, CF_UNICODETEXT, HTML_FORMAT

from workflow_factory import Flow, Node, find_step, run_flow, save_step
from workflow_factory.desktop import DesktopError
from workflow_factory.flow import emergency_stop

from fake_desktop import FakeDesktop, button, step


def text_bytes(value: str) -> bytes:
    return value.encode("utf-16-le") + b"\x00\x00"


def word():
    desktop = FakeDesktop(controls=[button("Body")], app="word.exe")
    desktop.foreground = "word.exe"
    return desktop


def teach(user_db, action):
    save_step(user_db, step("write-page", "Body", action=action, app="word.exe"))


def flow_text(text):
    return Flow(id="f", nodes=[Node("w", "write-page", fields={"text": {"value": text}})])


def run(tmp_path, desktop, action, the_flow=None):
    teach(tmp_path / "user.db", action)
    return run_flow(the_flow or flow_text("Hello Word"), desktop=desktop, user_db=tmp_path / "user.db")


# --- paste -----------------------------------------------------------------------------------------------

def test_a_paste_puts_the_text_on_the_page_and_the_persons_clipboard_comes_back(tmp_path):
    desktop = word()
    desktop.board.items = {CF_UNICODETEXT: text_bytes("what the person copied"), HTML_FORMAT: b"<b>copied</b>"}
    before = dict(desktop.board.items)

    result = run(tmp_path, desktop, "paste_text")

    assert result.status == "finished" and desktop.page == "Hello Word"
    assert desktop.board.items == before and result.outputs["w"]["not_restored"] == []
    assert [c[0] for c in desktop.calls if c[0].startswith(("clipboard", "press"))] == [
        "clipboard_backup", "clipboard_set", "press_key", "clipboard_restore"]


def test_the_step_says_which_clipboard_formats_it_could_not_put_back(tmp_path):
    desktop = word()
    desktop.board.items = {CF_UNICODETEXT: text_bytes("x"), CF_BITMAP: b"handle"}
    desktop.board.unreadable = {CF_BITMAP}

    result = run(tmp_path, desktop, "paste_text")

    assert result.outputs["w"]["not_restored"] == ["bitmap handle"]


def test_a_paste_into_a_window_that_is_not_the_app_sends_nothing_and_leaves_the_clipboard_alone(tmp_path):
    desktop = word()
    desktop.foreground = "chrome.exe"  # the person switched windows
    desktop.board.items = {CF_UNICODETEXT: text_bytes("private")}

    result = run(tmp_path, desktop, "paste_text")

    assert result.status == "stopped" and result.blocked == {"w": "wrong_window"}
    assert desktop.pressed == [] and desktop.elsewhere == "" and desktop.board.writes == 0


def test_the_clipboard_is_put_back_even_when_the_paste_itself_fails(tmp_path):
    desktop = word()
    desktop.board.items = {CF_UNICODETEXT: text_bytes("keep me")}

    def refuse(key):
        raise DesktopError("keys refused")

    desktop.press_key = refuse

    result = run(tmp_path, desktop, "paste_text")

    assert result.status == "stopped" and result.blocked == {"w": "action_failed"}
    assert desktop.board.items == {CF_UNICODETEXT: text_bytes("keep me")}


def test_a_paste_that_loses_the_window_between_setting_the_clipboard_and_pasting_pastes_nothing(tmp_path):
    desktop = word()
    desktop.board.items = {CF_UNICODETEXT: text_bytes("mine")}
    original = desktop.clipboard_set

    def set_then_switch(text):
        original(text)
        desktop.foreground = "chrome.exe"

    desktop.clipboard_set = set_then_switch

    result = run(tmp_path, desktop, "paste_text")

    assert result.blocked == {"w": "wrong_window"} and desktop.pressed == [] and desktop.board.text() == "mine"


# --- keys ------------------------------------------------------------------------------------------------

def test_keys_type_the_text_one_press_at_a_time_with_a_new_line_as_enter(tmp_path):
    desktop = word()

    result = run(tmp_path, desktop, "press_keys", flow_text("Hi\nyou"))

    assert result.status == "finished" and desktop.page == "Hi\nyou"
    assert [k for k, _ in desktop.pressed] == ["shift+h", "i", "return", "y", "o", "u"]
    assert not [c for c in desktop.calls if c[0].startswith("clipboard")]  # the clipboard is not involved


def test_keys_stop_the_moment_the_foreground_window_stops_being_the_app(tmp_path):
    desktop = word()
    desktop.on_action.append(lambda: setattr(desktop, "foreground", "chrome.exe") if len(desktop.pressed) == 3 else None)

    result = run(tmp_path, desktop, "press_keys", flow_text("abcdef"))

    assert result.status == "stopped" and result.blocked == {"w": "wrong_window"}
    assert desktop.page == "abc" and desktop.elsewhere == ""  # nothing reached the other window


def test_text_that_cannot_be_sent_as_keys_is_refused_before_any_key_is_sent(tmp_path):
    desktop = word()

    result = run(tmp_path, desktop, "press_keys", flow_text("naïve 😀"))

    assert result.blocked == {"w": "unsendable_text"} and desktop.pressed == []


def test_the_emergency_stop_ends_the_typing_at_once(tmp_path):
    desktop = word()
    desktop.on_action.append(lambda: emergency_stop() if len(desktop.pressed) == 2 else None)

    result = run(tmp_path, desktop, "press_keys", flow_text("abcdef"))

    assert result.status == "emergency" and desktop.page == "ab"


# --- both ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["paste_text", "press_keys"])
def test_a_step_that_writes_text_needs_a_text_to_write(tmp_path, action):
    desktop = word()

    result = run(tmp_path, desktop, action, Flow(id="f", nodes=[Node("w", "write-page")]))

    assert result.blocked == {"w": "missing_input"} and desktop.pressed == []


@pytest.mark.parametrize("action", ["paste_text", "press_keys"])
def test_the_text_never_reaches_what_the_run_gives_out(tmp_path, action):
    desktop = word()

    result = run(tmp_path, desktop, action)

    assert "Hello Word" not in str(result.outputs) and "Hello Word" not in str(result.effects)


@pytest.mark.parametrize("action", ["paste_text", "press_keys"])
def test_both_routes_take_the_input_lock_like_every_physical_step(tmp_path, action):
    teach(tmp_path / "user.db", action)

    assert find_step(tmp_path / "user.db", None, "word.exe", "write-page").uses_physical_input
