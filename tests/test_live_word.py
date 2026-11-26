"""Opt-in live check of both text routes on a Word page of our own, read back outside accessibility (Word's own COM interface).

It takes the foreground window (real keys go there) and, for the paste, briefly uses the person's clipboard (backed up and put back).
That disturbs whoever is working, so it never runs by itself: set WF_LIVE_WORD=1 and be away from the keyboard.
Word must not be running: the helper refuses to touch an instance the person already has.
"""

import ctypes
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from workflow_factory import Flow, Node, save_step
from workflow_factory.agent_desktop import AgentDesktop
from workflow_factory.clipboard import WindowsClipboard, backup
from workflow_factory.flow import run_flow
from workflow_factory.steps import Locator, Step

pytestmark = pytest.mark.live
HELPER = Path.home() / ".claude" / "skills" / "testing" / "live-testing" / "desktop-window.ps1"


def helper(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-File", str(HELPER), *args], capture_output=True, text=True, timeout=120)


def document_text() -> str:
    """The page text, asked of Word itself (COM), which does not depend on accessibility or on focus."""
    script = "$w=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application'); $w.ActiveDocument.Content.Text"
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=60).stdout.strip()


@pytest.fixture(scope="module")
def our_word():
    if os.environ.get("WF_LIVE_WORD") != "1":
        pytest.skip("opt-in: set WF_LIVE_WORD=1 (it takes the foreground window and briefly the clipboard)")
    if helper("monitors").stdout.count("primary=False") < 1:
        pytest.skip("no second monitor: the test window would land on the main screen")
    launched = helper("launch", "-Exe", r'"C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE" /w /q')
    if launched.returncode != 0:
        pytest.skip(f"the helper did not start our own Word (exit {launched.returncode}): {launched.stdout.strip()}")
    pid = int(launched.stdout.split()[-1])
    try:
        hwnd = 0
        for _ in range(30):  # Word takes a while to show its window
            found = helper("window", "-ProcessId", str(pid))
            if found.returncode == 0 and found.stdout.strip().isdigit():
                hwnd = int(found.stdout.strip())
                break
            time.sleep(1)
        assert hwnd, "our Word never showed a window"
        helper("place", "-Hwnd", str(hwnd))  # on the second monitor, no activation
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # restore: the helper starts it minimized
        for _ in range(10):  # Windows may refuse the first tries (foreground lock); keys go to the foreground window
            current = user32.GetForegroundWindow()
            me = ctypes.windll.kernel32.GetCurrentThreadId()
            other = user32.GetWindowThreadProcessId(current, None)
            user32.AttachThreadInput(me, other, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(me, other, False)
            time.sleep(0.5)
            if user32.GetForegroundWindow() == hwnd:
                break
        assert user32.GetForegroundWindow() == hwnd, "could not bring our Word to the foreground"
        yield pid
    finally:  # our own Word never outlives the test, whatever happened
        helper("stop", "-ProcessId", str(pid))


def body_locator(desktop) -> Locator:
    control = next(c for c in desktop.snapshot() if c.name == "Page 1 content")
    return Locator(control.role, control.name)


@pytest.mark.parametrize("action", ["paste_text", "press_keys"])
def test_both_routes_write_the_text_on_a_word_page_of_our_own(tmp_path, our_word, action):
    desktop = AgentDesktop("WINWORD.EXE")
    key = desktop.app_key()
    save_step(tmp_path / "user.db", Step(app=key.process, version=key.version, name="write-page", locator=body_locator(desktop),
                                         action=action))
    flow = Flow(id="f", nodes=[Node("w", "write-page", fields={"text": {"value": "wf live check 42"}})])

    before = backup(WindowsClipboard())
    result = run_flow(flow, desktop, tmp_path / "user.db")
    after = backup(WindowsClipboard())

    assert result.status == "finished", json.dumps(result.blocked)
    assert after.items == before.items, "the person's clipboard did not come back as it was"
    assert "wf live check 42" in document_text().lower()  # lower-cased: Word may capitalise the first letter
