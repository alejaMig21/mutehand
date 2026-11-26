"""Opt-in live check of both text routes on a Word page of our own, read back outside accessibility (Word's own COM interface).

It takes the foreground window (real keys go there) and, for the paste, briefly uses the person's clipboard (backed up and put back).
That disturbs whoever is working, so it never runs by itself: set WF_LIVE_WORD=1 and be away from the keyboard.
Word must not be running: the helper refuses to touch an instance the person already has.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from workflow_factory import Flow, Node, save_step
from workflow_factory.agent_desktop import AgentDesktop
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


@pytest.fixture
def our_word():
    if os.environ.get("WF_LIVE_WORD") != "1":
        pytest.skip("opt-in: set WF_LIVE_WORD=1 (it takes the foreground window and briefly the clipboard)")
    if helper("monitors").stdout.count("primary=False") < 1:
        pytest.skip("no second monitor: the test window would land on the main screen")
    launched = helper("launch", "-Exe", "WINWORD.EXE", "-Arguments", "/w /q")
    if launched.returncode != 0:
        pytest.skip(f"the helper did not start our own Word (exit {launched.returncode}): {launched.stdout.strip()}")
    pid = int(launched.stdout.split()[-1])
    time.sleep(4)
    yield pid
    helper("stop", "-ProcessId", str(pid))


def body_locator(desktop) -> Locator:
    control = next(c for c in desktop.snapshot() if "body" in c.name.lower() or "page 1" in c.name.lower())
    return Locator(control.role, control.name)


@pytest.mark.parametrize("action", ["paste_text", "press_keys"])
def test_both_routes_write_the_text_on_a_word_page_of_our_own(tmp_path, our_word, action):
    desktop = AgentDesktop("winword")
    key = desktop.app_key()
    save_step(tmp_path / "user.db", Step(app=key.process, version=key.version, name="write-page", locator=body_locator(desktop),
                                         action=action))
    flow = Flow(id="f", nodes=[Node("w", "write-page", fields={"text": {"value": "wf live check 42"}})])

    result = run_flow(flow, desktop, tmp_path / "user.db")

    assert result.status == "finished", json.dumps(result.blocked)
    assert "wf live check 42" in document_text().lower()  # lower-cased: Word may capitalise the first letter
