import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, suppress

import pytest

from workflow_factory import (
    Flow,
    Node,
    Status,
    answer_doubt,
    find_step,
    list_doubts,
    list_open_doubts,
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
    result = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)
    for doubt in list_doubts(user_db, "open"):  # a stopped flow waits for its answer before the next run
        answer_doubt(user_db, doubt.id)
    return result.statuses["n1"]


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
    (doubt,) = list_doubts(user_db, "open")
    answer_doubt(user_db, doubt.id)  # the stopped flow waits until its doubt is answered
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
    assert result.stopped == "n1"

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


def history(user_db):
    (run,) = list_runs(user_db)
    return {n["node_id"]: (n["status"], n["reason"]) for n in run["nodes"]}


def teach_two(user_db):
    """open-menu expects something new to appear; save-file has nothing taught to compare with."""
    save_step(user_db, step("open-menu", "Menu", effect="revealed"))
    save_step(user_db, step("save-file", "Save"))


def menu_and_save():
    return FakeDesktop(controls=[button("Menu"), button("Save")])


def test_a_step_that_changed_the_screen_differently_stops_the_flow_with_a_doubt(tmp_path):
    user_db = tmp_path / "user.db"
    teach_two(user_db)
    desktop = menu_and_save()
    flow = Flow(id="f", nodes=[Node("a", "open-menu"), Node("b", "save-file")], edges=[("a", "b")])

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert (result.stopped, result.blocked) == ("a", {"a": "effect_mismatch"})
    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert history(user_db) == {"a": ("blocked", "effect_mismatch")}
    (doubt,) = list_doubts(user_db, "open")  # the exact cause travels with the triage reason
    assert (doubt.node_id, doubt.reason, doubt.detail) == ("a", "precondition_not_met", "effect_mismatch")
    assert list_open_doubts(user_db)[0]["detail"] == "effect_mismatch"  # what the tutor reads


def test_a_database_from_before_doubts_kept_the_exact_cause_still_opens(tmp_path):
    user_db = tmp_path / "user.db"
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute("CREATE TABLE doubts (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id TEXT NOT NULL,"
                   " node_id TEXT NOT NULL, step TEXT NOT NULL, reason TEXT NOT NULL, capture TEXT NOT NULL,"
                   " status TEXT NOT NULL DEFAULT 'open', note TEXT)")
        db.execute("INSERT INTO doubts (flow_id, node_id, step, reason, capture)"
                   " VALUES ('f', 'a', 'open-menu', 'precondition_not_met', '{}')")

    (doubt,) = list_doubts(user_db)
    assert (doubt.reason, doubt.detail) == ("precondition_not_met", None)


def test_for_each_stops_at_the_first_item_that_changed_the_screen_differently(tmp_path):
    user_db = tmp_path / "user.db"
    teach_two(user_db)
    desktop = menu_and_save()
    flow = Flow(id="f", nodes=[Node("e", kind="foreach", body="b", fields={"items": {"value": [1, 2]}}),
                               Node("b", "open-menu")])

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.blocked == {"e": "effect_mismatch", "b": "effect_mismatch"}
    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert history(user_db)["b"] == ("blocked", "effect_mismatch")


def test_a_node_told_to_continue_goes_on_and_an_if_can_still_test_what_happened(tmp_path):
    user_db = tmp_path / "user.db"
    teach_two(user_db)
    desktop = menu_and_save()
    flow = Flow(id="f", nodes=[Node("a", "open-menu", on_failure="continue"),
                               Node("choose", kind="if", on="a", equals="no_change", then="b"),
                               Node("b", "save-file")],
                edges=[("a", "choose"), ("choose", "b")])

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.status == "finished" and [c.name for c in desktop.clicks] == ["Menu", "Save"]
    assert history(user_db)["a"] == ("continued", "effect_mismatch")


@pytest.mark.parametrize(("flow", "node_id"), [
    (Flow(id="f", nodes=[Node("e", kind="foreach", body="b", on_failure="continue", fields={"items": {"value": [1]}}),
                         Node("b", "open-menu")]), "b"),
    (Flow(id="f", nodes=[Node("l", "open-menu", kind="loop", max_iterations=1, max_seconds=60,
                              stop_after_failures=3)], edges=[]), "l"),
], ids=["for each told to continue", "loop under its failure limit"])
def test_a_repeated_node_that_goes_on_is_told_in_the_history(tmp_path, flow, node_id):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", effect="revealed"))

    run_flow(flow, desktop=failing_desktop(), user_db=user_db)

    assert history(user_db)[node_id] == ("done", "effect_mismatch")


def each(**kw):
    return Flow(id="f", nodes=[Node("e", kind="foreach", body="b", fields={"items": {"value": [1]}}, **kw),
                               Node("b", "open-menu")])


@pytest.mark.parametrize(("flow", "doubt_node"), [
    (Flow(id="f", nodes=[Node("a", "open-menu", on_failure="retry", retries=3)]), "a"),
    (each(on_failure="retry", retries=3), "b"),
], ids=["step", "for each"])
def test_a_retry_is_not_spent_on_a_step_the_mismatch_just_rejected(tmp_path, flow, doubt_node):
    user_db = tmp_path / "user.db"
    teach_two(user_db)  # never succeeded: one failure rejects it
    desktop = menu_and_save()

    run_flow(flow, desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    (doubt,) = list_doubts(user_db, "open")
    assert (doubt.node_id, doubt.detail) == (doubt_node, "effect_mismatch")  # not the rejection it caused


def test_a_retry_performs_the_action_again_while_the_step_is_still_allowed(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", effect="revealed", factory_successes=40))
    desktop = menu_and_save()

    run_flow(Flow(id="f", nodes=[Node("a", "open-menu", on_failure="retry", retries=2)]),
             desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu"] * 3


@pytest.mark.parametrize(("flow", "node_id"), [
    (Flow(id="f", nodes=[Node("a", "open-menu", on_failure="continue")]), "a"),
    (each(on_failure="continue"), "b"),
], ids=["step", "for each"])
def test_a_mismatch_told_to_continue_still_gives_out_what_the_action_measured(tmp_path, flow, node_id):
    user_db = tmp_path / "user.db"
    teach_two(user_db)

    result = run_flow(flow, desktop=menu_and_save(), user_db=user_db)

    assert result.outputs[node_id] == {"effect": "no_change"}


def test_a_for_each_body_that_reads_a_value_still_gives_it_out(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", action="read_value"))
    desktop = menu_and_save()

    result = run_flow(each(), desktop=desktop, user_db=user_db)

    assert "value" in result.outputs["b"] and result.outputs["b"]["effect"] == "no_change"


def test_an_item_that_succeeds_after_its_doubt_is_not_told_as_a_mismatch(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", effect="revealed", factory_successes=40))
    run_flow(each(), desktop=failing_desktop(), user_db=user_db)
    (doubt,) = list_doubts(user_db, "open")
    answer_doubt(user_db, doubt.id)

    result = run_flow(each(), desktop=working_desktop(), user_db=user_db)

    (run,) = [r for r in list_runs(user_db) if r["id"] == result.run_id]
    assert {n["node_id"]: n["reason"] for n in run["nodes"]}["b"] is None


def test_two_openers_of_an_old_database_both_succeed(tmp_path, monkeypatch):
    user_db = tmp_path / "user.db"
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute("CREATE TABLE doubts (id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id TEXT NOT NULL,"
                   " node_id TEXT NOT NULL, step TEXT NOT NULL, reason TEXT NOT NULL, capture TEXT NOT NULL,"
                   " status TEXT NOT NULL DEFAULT 'open', note TEXT)")
    both_looked = threading.Barrier(2)

    class SameMoment(sqlite3.Connection):
        """Both openers read the columns before either changes the table."""

        def execute(self, sql, *args):
            cursor = super().execute(sql, *args)
            if sql != "PRAGMA table_info(doubts)":
                return cursor
            rows = cursor.fetchall()
            with suppress(threading.BrokenBarrierError):
                both_looked.wait(timeout=1)
            return iter(rows)

    connect = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda path: connect(path, factory=SameMoment))
    with ThreadPoolExecutor(2) as pool:
        assert [f.result() for f in [pool.submit(list_doubts, user_db) for _ in range(2)]] == [[], []]
