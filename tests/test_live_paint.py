"""Live smoke test: real agent-desktop against Windows Paint. Opt-in: `pytest -m live`.

Paint must already be running on the secondary monitor (see the live-testing skill:
desktop-window.ps1 launch + place). This test never launches or moves windows.
"""

import sqlite3
from contextlib import closing

import pytest
from workflow_factory import Effect, Flow, Locator, Node, run_flow
from workflow_factory.agent_desktop import AgentDesktop, AgentDesktopError

pytestmark = pytest.mark.live


def test_click_paint_open_settings_through_run_flow_stores_a_measured_effect(tmp_path):
    desktop = AgentDesktop("mspaint.exe")
    try:
        desktop.snapshot()
    except AgentDesktopError as error:
        pytest.fail(f"Paint must be running on the secondary monitor first: {error}")
    flow = Flow(nodes=[Node(id="open-settings", locator=Locator(
        role="button", name="Open settings", automation_id="SettingsButton"))])
    db_path = tmp_path / "user.db"

    result = run_flow(flow, desktop=desktop, user_db=db_path)

    assert result.effects["open-settings"] == Effect.REVEALED
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT count(*) FROM node_results").fetchone() == (1,)
