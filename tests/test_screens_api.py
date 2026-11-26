import json
import time

from test_api import call, make_server

from workflow_factory import (
    Flow,
    Node,
    Sensitivity,
    grant_consent,
    list_runs,
    run_flow,
    save_flow,
    save_step,
)

from fake_desktop import FakeDesktop, button, step


def run_and_wait(server, flow_id, context=None):
    _, started, _ = call(server, f"/api/flows/{flow_id}/run", "POST", {"app": "paint.exe", "context": context or {}})
    for _ in range(100):
        _, view, _ = call(server, f"/api/runs/{started['run_id']}")
        if view["status"] != "running":
            return view
        time.sleep(0.05)


# --- step library ----------------------------------------------------------------------------

def test_the_library_shows_origin_state_and_the_numbers_behind_the_confidence(tmp_path):
    save_step(tmp_path / "factory.db", step("open-menu", "Menu", origin="factory", factory_successes=50))
    save_step(tmp_path / "user.db", step("save-file", "Save"))
    server = make_server(tmp_path)
    try:
        status, library, _ = call(server, "/api/library")
    finally:
        server.stop()

    by_name = {item["name"]: item for item in library}
    assert status == 200
    assert by_name["open-menu"]["origin"] == "factory" and by_name["open-menu"]["state"] == "suspect"
    assert (by_name["open-menu"]["successes"], by_name["open-menu"]["failures"]) == (50, 0)
    assert by_name["open-menu"]["confidence"] == 0.98  # 51 / 52: high, but not trusted until it has own successes
    assert by_name["save-file"]["origin"] == "local" and by_name["save-file"]["confidence"] == 0.5


def test_a_person_can_reject_a_step_and_restore_it_even_a_factory_one(tmp_path):
    save_step(tmp_path / "factory.db", step("open-menu", "Menu", origin="factory"))
    server = make_server(tmp_path)
    try:
        rejected = call(server, "/api/steps/paint.exe/open-menu/reject", "POST", {})
        after_reject = {i["name"]: i["state"] for i in call(server, "/api/library")[1]}
        restored = call(server, "/api/steps/paint.exe/open-menu/restore", "POST", {})
        after_restore = {i["name"]: i["state"] for i in call(server, "/api/library")[1]}
    finally:
        server.stop()

    assert rejected[0] == restored[0] == 200
    assert after_reject["open-menu"] == "rejected" and after_restore["open-menu"] == "suspect"


def test_a_step_whose_name_has_spaces_can_be_rejected_and_restored_as_the_browser_asks(tmp_path):
    save_step(tmp_path / "user.db", step("Select cell A1", "Menu"))
    server = make_server(tmp_path)
    try:  # the browser percent-encodes the path; the playbook names steps "Verb object", with spaces
        rejected = call(server, "/api/steps/paint.exe/Select%20cell%20A1/reject", "POST", {})
        restored = call(server, "/api/steps/paint.exe/Select%20cell%20A1/restore", "POST", {})
        state = {i["name"]: i["state"] for i in call(server, "/api/library")[1]}
    finally:
        server.stop()

    assert (rejected[0], restored[0]) == (200, 200) and restored[1]["step"] == "Select cell A1"
    assert state["Select cell A1"] == "suspect"


# --- consents: revoke only ---------------------------------------------------------------------

def test_the_consents_screen_lists_scopes_and_can_revoke_but_never_grant(tmp_path):
    grant_consent(tmp_path / "user.db", app="paint.exe", control="Send", action="click")
    server = make_server(tmp_path)
    scope = {"app": "paint.exe", "control": "Send", "action": "click"}
    try:
        listed = call(server, "/api/consents")
        granted = call(server, "/api/consents", "POST", scope)  # there is no grant route
        revoked = call(server, "/api/consents", "DELETE", scope)
        after = call(server, "/api/consents")
    finally:
        server.stop()

    assert listed[1] == [scope]
    assert granted[0] == 404
    assert revoked[0] == 200 and after[1] == []


# --- tutor queue ---------------------------------------------------------------------------------

def test_the_queue_screen_lists_open_doubts_and_records_a_human_answer(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Missing"))
    run_flow(Flow(id="morning", nodes=[Node("a", "open-menu")]), desktop=FakeDesktop(controls=[button("Other")]),
             user_db=tmp_path / "user.db")
    server = make_server(tmp_path)
    try:
        _, open_doubts, _ = call(server, "/api/doubts?status=open")
        answered = call(server, f"/api/doubts/{open_doubts[0]['id']}/answer", "POST", {})
        after = call(server, "/api/doubts?status=open")[1]
        everything = call(server, "/api/doubts")[1]
        unknown = call(server, "/api/doubts/999/answer", "POST", {})
    finally:
        server.stop()

    assert open_doubts[0]["reason"] == "control_not_found" and open_doubts[0]["capture"] == {"button": 1}
    assert answered[0] == 200 and after == [] and everything[0]["status"] == "answered"
    assert unknown[0] == 400


# --- run history ---------------------------------------------------------------------------------

def test_run_history_tells_what_ran_what_stopped_and_why_without_any_data_values(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("send", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(tmp_path / "user.db", step("typer", "Alpha", action="type_value"))
    save_flow(tmp_path / "user.db", Flow(id="ok", nodes=[Node("a", "open-menu")]))
    save_flow(tmp_path / "user.db", Flow(id="stuck", nodes=[Node("a", "open-menu"), Node("s", "send")]))
    save_flow(tmp_path / "user.db", Flow(id="typing", nodes=[Node("t", "typer", inputs=(("text", "str"),))]))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Send")])
    server = make_server(tmp_path, desktop=desktop)
    try:
        run_and_wait(server, "ok")
        run_and_wait(server, "stuck")
        run_and_wait(server, "typing", {"text": "hunter2"})
        status, history, _ = call(server, "/api/history")
        only_stuck = call(server, "/api/history?flow=stuck")[1]
    finally:
        server.stop()

    assert status == 200 and [run["flow_id"] for run in history] == ["typing", "stuck", "ok"]  # newest first
    stuck = next(run for run in history if run["flow_id"] == "stuck")
    assert stuck["status"] == "stopped" and stuck["stopped_node"] == "s"
    assert {n["node_id"]: (n["status"], n["reason"]) for n in stuck["nodes"]} == {
        "a": ("done", None), "s": ("blocked", "no_consent")}
    assert [run["flow_id"] for run in only_stuck] == ["stuck"]
    assert "hunter2" not in json.dumps(history)  # values never reach the history


def test_the_engine_records_one_history_row_per_executed_run(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    run_flow(Flow(id="f", nodes=[Node("a", "open-menu")]), desktop=FakeDesktop(controls=[button("Alpha")]),
             user_db=tmp_path / "user.db")

    (run,) = list_runs(tmp_path / "user.db")

    assert run["status"] == "finished" and run["started_at"] <= run["finished_at"]
    assert run["nodes"] == [{"node_id": "a", "status": "done", "reason": None, "effect": "no_change",
                              "step": "open-menu", "kind": "step", "op": None}]


def test_rejecting_an_unknown_step_is_a_404(tmp_path):
    server = make_server(tmp_path)
    try:
        status, body, _ = call(server, "/api/steps/paint.exe/never-taught/reject", "POST", {})
    finally:
        server.stop()

    assert status == 404 and "no such step" in body["error"]


def test_a_doubt_can_be_dismissed_from_the_queue_screen(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Missing"))
    run_flow(Flow(id="f", nodes=[Node("a", "open-menu")]), desktop=FakeDesktop(controls=[]),
             user_db=tmp_path / "user.db")
    server = make_server(tmp_path)
    try:
        dismissed = call(server, "/api/doubts/1/dismiss", "POST", {})
        statuses = [d["status"] for d in call(server, "/api/doubts")[1]]
    finally:
        server.stop()

    assert dismissed[0] == 200 and statuses == ["dismissed"]


def test_revoking_with_an_incomplete_body_is_a_400_not_a_crash(tmp_path):
    server = make_server(tmp_path)
    try:
        status, body, _ = call(server, "/api/consents", "DELETE", {"app": "paint.exe"})
    finally:
        server.stop()

    assert status == 400


def test_the_library_shows_to_revalidate_for_every_step_once_a_run_saw_a_newer_app_version(tmp_path):
    save_step(tmp_path / "factory.db", step("open-menu", "Menu", origin="factory", version="1.0"))
    save_step(tmp_path / "user.db", step("save-file", "Save", version="1.0"))
    save_step(tmp_path / "user.db", step("other", "Other", version="2.0"))
    run_flow(Flow(id="f", nodes=[Node("a", "other")]),
             desktop=FakeDesktop(controls=[button("Other")], version="2.0"), user_db=tmp_path / "user.db")
    server = make_server(tmp_path)
    try:
        library = {item["name"]: item["state"] for item in call(server, "/api/library")[1]}
    finally:
        server.stop()

    assert library == {"open-menu": "to_revalidate", "save-file": "to_revalidate", "other": "suspect"}


def test_a_human_answer_keeps_the_note_the_person_wrote(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Missing"))
    run_flow(Flow(id="f", nodes=[Node("a", "open-menu")]), desktop=FakeDesktop(controls=[]),
             user_db=tmp_path / "user.db")
    server = make_server(tmp_path)
    try:
        call(server, "/api/doubts/1/answer", "POST", {"note": "the button is now called Main menu"})
        doubts = call(server, "/api/doubts?status=answered")[1]
    finally:
        server.stop()

    assert doubts[0]["note"] == "the button is now called Main menu"


def test_an_unexpected_failure_still_leaves_a_run_in_the_history_as_an_error(tmp_path):
    import pytest

    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))

    class Broken(FakeDesktop):
        def snapshot(self):
            raise RuntimeError("a bug, not a desktop failure")

    with pytest.raises(RuntimeError):
        run_flow(Flow(id="f", nodes=[Node("a", "open-menu")]), desktop=Broken(controls=[button("Alpha")]),
                 user_db=tmp_path / "user.db")

    (run,) = list_runs(tmp_path / "user.db")
    assert run["status"] == "error" and run["flow_id"] == "f"


def test_revoking_a_consent_that_does_not_exist_is_a_404(tmp_path):
    server = make_server(tmp_path)
    try:
        status, _, _ = call(server, "/api/consents", "DELETE",
                            {"app": "paint.exe", "control": "Send", "action": "click"})
    finally:
        server.stop()

    assert status == 404


def test_the_history_keeps_only_the_most_recent_runs(tmp_path):
    from workflow_factory.queue import record_run

    for n in range(4):
        record_run(tmp_path / "user.db", f"f{n}", "t0", "t1", "finished", None,
                   [{"node_id": "a", "status": "done"}], keep=2)

    assert [run["flow_id"] for run in list_runs(tmp_path / "user.db")] == ["f3", "f2"]
