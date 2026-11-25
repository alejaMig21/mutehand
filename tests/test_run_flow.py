import sqlite3
from contextlib import closing

from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import Flow, Node, run_flow, save_lesson


def one_node_flow():
    return Flow(nodes=[Node(id="n1", lesson="open-menu")])


def taught(db_path, control_name="Open menu"):
    save_lesson(db_path, lesson("open-menu", control_name))
    return db_path


def stored_effects(db_path):
    with closing(sqlite3.connect(db_path)) as db:
        return db.execute("SELECT node_id, effect, finished_at FROM node_results").fetchall()


def test_one_node_flow_clicks_located_control_and_stores_revealed_effect(tmp_path):
    desktop = FakeDesktop(
        controls=[button("Open menu", "menuBtn")],
        reveals={("button", "Open menu"): [button("Save as")]},
    )
    db_path = taught(tmp_path / "user.db")

    result = run_flow(one_node_flow(), desktop=desktop, user_db=db_path)

    assert [c.name for c in desktop.clicks] == ["Open menu"]
    assert result.effects == {"n1": "revealed"}
    assert stored_effects(db_path) == [("n1", "revealed", "2026-01-01T00:00:00Z")]


def test_click_that_removes_a_control_is_stored_as_closed_dialog(tmp_path):
    desktop = FakeDesktop(
        controls=[button("Open menu"), button("Dialog OK")],
        removes={("button", "Open menu"): [button("Dialog OK")]},
    )
    db_path = taught(tmp_path / "user.db")

    run_flow(one_node_flow(), desktop=desktop, user_db=db_path)

    assert [row[1] for row in stored_effects(db_path)] == ["closed_dialog"]


def test_missing_control_stops_the_flow_without_clicking(tmp_path):
    desktop = FakeDesktop(controls=[button("Something else")])
    db_path = taught(tmp_path / "user.db")

    result = run_flow(one_node_flow(), desktop=desktop, user_db=db_path)

    assert desktop.clicks == []
    assert result.stopped == "n1"


def test_click_that_changes_nothing_is_stored_as_no_change(tmp_path):
    desktop = FakeDesktop(controls=[button("Open menu")])
    db_path = taught(tmp_path / "user.db")

    run_flow(one_node_flow(), desktop=desktop, user_db=db_path)

    assert [row[1] for row in stored_effects(db_path)] == ["no_change"]
