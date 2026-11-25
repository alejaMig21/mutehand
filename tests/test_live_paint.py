"""Live smoke test: real agent-desktop against Windows Paint. Opt-in: `pytest -m live`.

Paint must already be running on the secondary monitor (see the live-testing skill:
desktop-window.ps1 launch + place). This test never launches or moves windows.
"""

import sqlite3
from contextlib import closing

import pytest
from workflow_factory import (
    Effect,
    Flow,
    Lesson,
    Locator,
    Node,
    list_doubts,
    run_flow,
    save_lesson,
)
from workflow_factory.agent_desktop import AgentDesktop, AgentDesktopError

pytestmark = pytest.mark.live


def test_click_paint_open_settings_through_run_flow_stores_a_measured_effect(tmp_path):
    desktop = AgentDesktop("mspaint.exe")
    try:
        desktop.snapshot()
    except AgentDesktopError as error:
        pytest.fail(f"Paint must be running on the secondary monitor first: {error}")
    key = desktop.app_key()
    db_path = tmp_path / "user.db"
    save_lesson(db_path, Lesson(
        app=key.process, version=key.version, name="open-settings",
        locator=Locator(role="button", name="Open settings", automation_id="SettingsButton"),
        frame=desktop.frame()))
    flow = Flow(nodes=[Node(id="open-settings", lesson="open-settings")])

    result = run_flow(flow, desktop=desktop, user_db=db_path)

    assert result.effects["open-settings"] == Effect.REVEALED
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT count(*) FROM node_results").fetchone() == (1,)


def test_missing_control_in_real_paint_stops_the_flow_with_a_text_free_doubt(tmp_path):
    desktop = AgentDesktop("mspaint.exe")
    key = desktop.app_key()
    db_path = tmp_path / "user.db"
    save_lesson(db_path, Lesson(app=key.process, version=key.version, name="ghost",
                                locator=Locator(role="button", name="No such control anywhere")))

    result = run_flow(Flow(id="ghost-flow", nodes=[Node(id="n1", lesson="ghost")]),
                      desktop=desktop, user_db=db_path)

    (doubt,) = list_doubts(db_path)
    assert result.stopped == "n1"
    assert doubt.reason == "control_not_found" and doubt.capture.get("button", 0) >= 1
    assert "Open settings" not in repr(doubt) and b"Open settings" not in db_path.read_bytes()
