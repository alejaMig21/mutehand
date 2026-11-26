import sqlite3
from contextlib import closing

import pytest

from workflow_factory import (
    Flow,
    Node,
    Status,
    answer_doubt,
    find_step,
    list_runs,
    reject_step,
    restore_step,
    run_flow,
    save_step,
    step_report,
)

from fake_desktop import FakeDesktop, button, step

FLOW = Flow(nodes=[Node(id="n1", step="open-menu")])


def working_desktop():
    """Click reveals a control, matching the step's taught effect."""
    return FakeDesktop(controls=[button("Menu")], reveals={("button", "Menu"): [button("Next")]})


def failing_desktop():
    """Click changes nothing: measured effect is no_change, not the taught 'revealed'."""
    return FakeDesktop(controls=[button("Menu")])


def teach_factory(factory_db, **counters):
    save_step(factory_db, step("open-menu", "Menu", origin="factory", effect="revealed", **counters))


def status_after_run(desktop, user_db, factory_db):
    return run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db).statuses["n1"]


def test_factory_step_with_high_counters_needs_two_own_successes_to_be_trusted(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=50)

    first = status_after_run(working_desktop(), user_db, factory_db)
    second = status_after_run(working_desktop(), user_db, factory_db)

    assert (first, second) == (Status.SUSPECT, Status.TRUSTED)


def test_failures_move_a_step_from_suspect_to_rejected_and_rejected_is_not_replayed(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=3)

    statuses = [status_after_run(failing_desktop(), user_db, factory_db) for _ in range(3)]
    desktop = working_desktop()
    result = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert statuses == [Status.SUSPECT, Status.SUSPECT, Status.REJECTED]
    assert desktop.clicks == []
    assert result.blocked == {"n1": "rejected"}


def test_only_an_explicit_human_restore_lets_a_rejected_step_run_again(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=3)
    for _ in range(3):
        status_after_run(failing_desktop(), user_db, factory_db)
    # re-teaching or a version bump is not a restore
    save_step(user_db, step("open-menu", "Menu", effect="revealed", version="1.0"))
    still_blocked = run_flow(FLOW, desktop=working_desktop(), user_db=user_db, factory_db=factory_db)

    restore_step(user_db, app="paint.exe", name="open-menu")
    answer_doubt(user_db, 1)  # the stopped flow waits until its doubt is answered
    desktop = working_desktop()
    restored = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert still_blocked.blocked == {"n1": "rejected"}
    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert restored.statuses == {"n1": Status.SUSPECT}


def test_a_factory_step_rejected_by_its_shipped_counters_can_be_restored_by_a_human(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_failures=2)  # confidence 1/8 = 0.125, rejected on arrival
    blocked = run_flow(FLOW, desktop=working_desktop(), user_db=user_db, factory_db=factory_db)

    restore_step(user_db, app="paint.exe", name="open-menu")
    answer_doubt(user_db, 1)  # the stopped flow waits until its doubt is answered
    desktop = working_desktop()
    run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert blocked.blocked == {"n1": "rejected"}
    assert [c.name for c in desktop.clicks] == ["Menu"]


def report(user_db, name="open-menu"):
    return step_report(user_db, find_step(user_db, None, "paint.exe", name))


def test_a_rejected_step_remembers_why_until_a_person_restores_it(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", effect="revealed"))

    result = run_flow(FLOW, desktop=failing_desktop(), user_db=user_db)

    why = report(user_db)["why"]
    assert (why["kind"], why["expected"], why["got"]) == ("different_effect", "revealed", "no_change") and why["at"]
    assert result.stopped is None  # the node itself finished: the history has to say what went wrong
    (run,) = list_runs(user_db)
    assert run["nodes"][0]["status"] == "done" and run["nodes"][0]["reason"] == "effect_mismatch"

    restore_step(user_db, "paint.exe", "open-menu")
    assert report(user_db)["why"] is None
    reject_step(user_db, "paint.exe", "open-menu")
    assert report(user_db)["why"] == {"kind": "person"}


def test_a_database_from_before_reasons_were_kept_still_opens(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute("CREATE TABLE step_state (app TEXT NOT NULL, name TEXT NOT NULL, local_successes INTEGER NOT NULL DEFAULT 0,"
                   " local_failures INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0,"
                   " restored INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (app, name))")
        db.execute("INSERT INTO step_state (app, name, local_failures, rejected) VALUES ('paint.exe', 'open-menu', 1, 1)")

    assert report(user_db) == {"state": "rejected", "successes": 0, "failures": 1, "confidence": 0.2, "why": None}


@pytest.mark.parametrize(("flow", "node_id"), [
    (Flow(id="f", nodes=[Node("e", kind="foreach", body="b", fields={"items": {"value": [1]}}), Node("b", "open-menu")]), "b"),
    (Flow(id="f", nodes=[Node("l", "open-menu", kind="loop", max_iterations=1, max_seconds=60,
                              stop_after_failures=3)], edges=[]), "l"),
], ids=["for each", "loop"])
def test_a_repeated_node_that_changed_the_screen_differently_is_told_in_the_history(tmp_path, flow, node_id):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", effect="revealed"))

    run_flow(flow, desktop=failing_desktop(), user_db=user_db)

    (run,) = list_runs(user_db)
    node = {n["node_id"]: n for n in run["nodes"]}[node_id]
    assert (node["status"], node["reason"]) == ("done", "effect_mismatch")
