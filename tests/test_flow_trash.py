"""Rename, delete with undo, and the history of one flow: the API behind a flow's "More"."""

import json
import sqlite3
import subprocess
from contextlib import closing

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.flows import save_layout
from workflow_factory.queue import acquire_run_lock, list_runs, record_run, release_run_lock, save_checkpoint

from fake_desktop import FakeDesktop, button, step

ONE = {"nodes": [{"id": "n1", "step": "open-menu"}], "edges": []}


@pytest.fixture
def served(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    desktop = FakeDesktop(controls=[button("Alpha")])
    scheduler = FakeScheduler()
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop, token="secret-token",
                       schedule_runner=scheduler)
    server.start()
    call(server, "/api/flows/morning", "PUT", {**ONE, "title": "Morning report", "app": "paint.exe"})
    yield server, scheduler, tmp_path
    server.stop()


def daily(server, flow="morning", at="09:30"):
    assert call(server, "/api/schedules", "POST", {"flow": flow, "app": "paint.exe", "at": at})[0] == 201


def test_renaming_changes_the_title_only_and_history_schedule_and_checkpoint_stay(served):
    server, scheduler, tmp_path = served
    db = tmp_path / "user.db"
    daily(server)
    run_flow(Flow(id="morning", nodes=[Node("n1", "open-menu")]), FakeDesktop(controls=[button("Alpha")]), db)
    save_checkpoint(db, "morning", {"done": ["n1"]}, "definition")  # a stopped run's, left after the finished one
    before = (list_runs(db, "morning"), dict(scheduler.tasks))

    code, view, _ = call(server, "/api/flows/morning/rename", "POST", {"title": "  Daily   sales  "})

    assert code == 200 and view["title"] == "Daily sales" and view["id"] == "morning"
    assert call(server, "/api/flows/morning")[1]["title"] == "Daily sales"
    assert (list_runs(db, "morning"), dict(scheduler.tasks)) == before
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT state FROM checkpoints WHERE flow_id = 'morning'").fetchone() == ('{"done": ["n1"]}',)


@pytest.mark.parametrize("title", ["", "   ", "x" * 101, 7, "a\x00b"])
def test_a_title_that_cannot_be_shown_is_refused_and_changes_nothing(served, title):
    server, _, _ = served

    assert call(server, "/api/flows/morning/rename", "POST", {"title": title})[0] == 400
    assert call(server, "/api/flows/morning")[1]["title"] == "Morning report"


def test_renaming_a_flow_that_does_not_exist_is_a_404(served):
    assert call(served[0], "/api/flows/nope/rename", "POST", {"title": "x"})[0] == 404


def test_deleting_removes_the_flow_and_its_daily_run_and_undo_restores_both(served):
    server, scheduler, tmp_path = served
    daily(server)
    save_layout(tmp_path / "user.db", "morning", {"n1": {"x": 5, "y": 7}})
    save_checkpoint(tmp_path / "user.db", "morning", {"done": []}, "definition")
    view = call(server, "/api/flows/morning")[1]

    assert call(server, "/api/flows/morning", "DELETE")[0] == 200

    assert call(server, "/api/flows")[1] == [] and call(server, "/api/flows/morning")[0] == 404
    assert call(server, "/api/schedules")[1] == [] and list(scheduler.tasks) == [FOREIGN]  # the foreign task stays

    code, back, _ = call(server, "/api/flows/morning/restore", "POST")

    assert code == 200 and back == view  # words, app, nodes, places and revision as they were
    assert call(server, "/api/schedules")[1] == [
        {"name": "morning daily 0930", "flow": "morning", "app": "paint.exe", "at": "09:30"}]
    with closing(sqlite3.connect(tmp_path / "user.db")) as con:
        assert con.execute("SELECT count(*) FROM checkpoints WHERE flow_id = 'morning'").fetchone() == (1,)


def test_a_flow_that_runs_cannot_be_deleted_until_it_stops(served):
    server, _, tmp_path = served
    assert acquire_run_lock(tmp_path / "user.db", "morning")  # a run, maybe a scheduled one in another process
    try:
        code, body, _ = call(server, "/api/flows/morning", "DELETE")
        assert code == 409 and "running" in body["error"] and "Stop" in body["error"]
        assert call(server, "/api/flows/morning")[0] == 200
    finally:
        release_run_lock(tmp_path / "user.db", "morning")
    assert call(server, "/api/flows/morning", "DELETE")[0] == 200


def test_a_flow_followed_in_this_editor_cannot_be_deleted_either(served):
    server, _, _ = served
    server._runs["r1"] = {"flow_id": "morning#test:n1", "status": "running", "nodes": {}, "log": []}

    assert call(server, "/api/flows/morning", "DELETE")[0] == 409


def test_deleting_a_flow_that_is_not_there_or_is_built_in_is_refused_in_words(served):
    server, _, tmp_path = served
    save_flow(tmp_path / "factory.db", Flow(id="template", nodes=[Node("n1", "open-menu")]))

    assert call(server, "/api/flows/nope", "DELETE")[0] == 404
    code, body, _ = call(server, "/api/flows/template", "DELETE")
    assert code == 400 and "built-in" in body["error"]
    assert call(server, "/api/flows/template")[0] == 200


def test_deleting_a_copy_that_shadows_a_built_in_flow_shows_the_built_in_one(served):
    server, _, tmp_path = served
    save_flow(tmp_path / "factory.db", Flow(id="template", nodes=[Node("n1", "open-menu")]), "Factory words")
    call(server, "/api/flows/template", "PUT", {**ONE, "title": "My words"})

    assert call(server, "/api/flows/template", "DELETE")[0] == 200
    assert call(server, "/api/flows/template")[1]["title"] == "Factory words"

    assert call(server, "/api/flows/template/restore", "POST")[0] == 200
    assert call(server, "/api/flows/template")[1]["title"] == "My words"


def test_a_deleted_identifier_is_not_given_to_a_new_flow(served):
    server, _, _ = served
    call(server, "/api/flows/morning", "DELETE")

    code, made, _ = call(server, "/api/flows", "POST", {**ONE, "title": "Morning report"})

    assert code == 201 and made["id"] != "morning"
    assert call(server, "/api/flows/morning", "PUT", ONE)[0] == 409  # the old history and questions are not inherited


def test_undo_needs_a_deleted_flow_and_a_free_identifier(served):
    server, _, _ = served
    assert call(server, "/api/flows/morning/restore", "POST")[0] == 404  # nothing was deleted
    call(server, "/api/flows/morning", "DELETE")
    assert call(server, "/api/flows/morning/restore", "POST")[0] == 200
    assert call(server, "/api/flows/morning/restore", "POST")[0] == 404  # only once


def test_a_refused_removal_of_the_daily_run_leaves_the_flow_where_it_is(served):
    server, scheduler, _ = served
    daily(server)
    real = scheduler.__class__.__call__

    def stubborn(args, **kwargs):
        if args[1] == "/Delete":
            return scheduler._done(args, 1, err="access denied")
        return real(scheduler, args, **kwargs)

    server.schedule_runner = stubborn
    code, body, _ = call(server, "/api/flows/morning", "DELETE")

    assert code == 502 and "daily run" in body["error"]
    assert call(server, "/api/flows/morning")[0] == 200


def test_the_history_of_a_flow_keeps_each_nodes_name_after_the_flow_changes(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    flow = Flow(id="morning", nodes=[
        Node("n1", kind="wait", fields={"seconds": {"value": 1}}), Node("n2", "open-menu")])
    run_flow(flow, FakeDesktop(controls=[button("Alpha")]), db)

    [run] = list_runs(db, "morning")
    # the flow is rebuilt later and reuses the node ids: the history still says what ran
    names = {n["node_id"]: (n["kind"], n["op"], n["step"]) for n in run["nodes"]}

    assert names == {"n1": ("wait", None, None), "n2": ("step", None, "open-menu")}


def test_a_run_that_crashes_still_names_the_nodes_that_finished(tmp_path, monkeypatch):
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    flow = Flow(id="morning", nodes=[Node("n1", kind="wait", fields={"seconds": {"value": 1}}), Node("n2", "open-menu")])
    monkeypatch.setattr("workflow_factory.flow._run_step", lambda *a: (_ for _ in ()).throw(RuntimeError("bug")))

    with pytest.raises(RuntimeError):
        run_flow(flow, FakeDesktop(controls=[button("Alpha")]), db)

    [run] = list_runs(db, "morning")
    assert run["status"] == "error" and [(n["node_id"], n["kind"]) for n in run["nodes"]] == [("n1", "wait")]


def test_the_history_endpoint_lists_one_flow_newest_first_without_its_tests(served):
    server, _, tmp_path = served
    db = tmp_path / "user.db"
    flow = Flow(id="morning", nodes=[Node("n1", "open-menu")])
    for _ in range(2):
        run_flow(flow, FakeDesktop(controls=[button("Alpha")]), db)
    record_run(db, "morning#test:n1", "2026-01-01T07:00:00Z", "2026-01-01T07:00:01Z", "finished", None, [])
    record_run(db, "other", "2026-01-01T07:00:00Z", "2026-01-01T07:00:01Z", "finished", None, [])

    runs = call(server, "/api/history?flow=morning")[1]

    assert [r["flow_id"] for r in runs] == ["morning", "morning"] and runs[0]["id"] > runs[1]["id"]
    assert all(n["kind"] == "step" and n["step"] == "open-menu" for r in runs for n in r["nodes"])
    assert json.dumps(runs).count("Alpha") == 0  # no screen content


def test_a_flow_deleted_a_moment_ago_is_listed_so_a_reload_can_still_undo_it(served):
    server, scheduler, tmp_path = served
    daily(server)
    assert call(server, "/api/deleted")[1] == []
    call(server, "/api/flows/morning", "DELETE")

    assert call(server, "/api/deleted")[1] == [{"id": "morning", "title": "Morning report", "daily_runs": 1}]

    call(server, "/api/flows/morning/restore", "POST")
    assert call(server, "/api/deleted")[1] == []


def test_a_flow_deleted_long_ago_is_no_longer_offered_but_stays_restorable(served):
    server, _, tmp_path = served
    call(server, "/api/flows/morning", "DELETE")
    with closing(sqlite3.connect(tmp_path / "user.db")) as db, db:
        db.execute("UPDATE flow_trash SET deleted_at = '2020-01-01T00:00:00+00:00'")

    assert call(server, "/api/deleted")[1] == []
    assert call(server, "/api/flows/morning/restore", "POST")[0] == 200


def test_a_trash_made_before_deletions_were_dated_still_works(served):
    server, _, tmp_path = served
    with closing(sqlite3.connect(tmp_path / "user.db")) as db, db:
        db.execute("DROP TABLE IF EXISTS flow_trash")
        db.execute("CREATE TABLE flow_trash (id TEXT PRIMARY KEY, definition TEXT NOT NULL, positions TEXT, "
                   "title TEXT, app TEXT, schedules TEXT NOT NULL)")
    assert call(server, "/api/flows/morning", "DELETE")[0] == 200
    assert call(server, "/api/deleted")[1][0]["id"] == "morning"


def test_undo_that_cannot_set_the_daily_run_again_does_not_keep_a_daily_node_without_a_task(served):
    server, scheduler, _ = served
    daily = {"id": "t", "kind": "trigger", "fields": {"mode": {"value": "daily"}, "at": {"value": "09:30"}}}
    assert call(server, "/api/flows/morning", "PUT", {"nodes": [daily, *ONE["nodes"]], "edges": None, "app": "paint.exe"})[0] == 200
    assert len(call(server, "/api/schedules")[1]) == 1  # saving the node made the task
    call(server, "/api/flows/morning", "DELETE")
    taken = server.schedule_runner

    def refusing(args, **kwargs):
        if args[1] == "/Create":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ERROR: Access is denied.")
        return taken(args, **kwargs)

    server.schedule_runner = refusing
    code, back, _ = call(server, "/api/flows/morning/restore", "POST")

    assert code == 200 and back["daily_run_lost"] and back["daily_node_removed"] is True
    assert [n["kind"] for n in back["nodes"]] == ["step"] and call(server, "/api/schedules")[1] == []
    assert [n["kind"] for n in call(server, "/api/flows/morning")[1]["nodes"]] == ["step"]
