"""A stopped flow (editor rethink, ticket 09): the attention list, trying again, and asking for help. API side."""

import json
import time

import pytest
from fake_scheduler import FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, list_doubts, reject_step, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.queue import answer_doubt, record_run
from workflow_factory.steps import list_steps, step_report
from workflow_factory.tutor import list_open_doubts, mark_private

from fake_desktop import FakeDesktop, button, step

WEEKLY = Flow(id="weekly", nodes=[Node("n1", "open-menu"), Node("n2", "close-message")])


class Setup:
    """A data file with one flow that stops at its second node: Paint does not show the button."""

    def __init__(self, tmp_path, effect="", app="paint.exe"):
        self.db = tmp_path / "user.db"
        self.app = app
        save_step(self.db, step("open-menu", "Alpha", app=app))
        save_step(self.db, step("close-message", "Beta", app=app, effect=effect))
        save_flow(self.db, WEEKLY, "Weekly export", app)
        self.desktop = FakeDesktop(controls=[button("Alpha")], app=app)
        self.server = ApiServer(self.db, None, lambda name: self.desktop, token="secret-token",
                                schedule_runner=FakeScheduler())
        self.server.start()

    def stop_the_flow(self):
        return run_flow(WEEKLY, self.desktop, self.db)

    def attention(self):
        return call(self.server, "/api/attention")[1]

    def try_again(self):
        return call(self.server, "/api/flows/weekly/try-again", "POST", {"app": self.app})

    def finished(self, run_id):
        for _ in range(100):
            view = call(self.server, f"/api/runs/{run_id}")[1]
            if view["status"] != "running":
                return view
            time.sleep(0.05)


@pytest.fixture
def setup(tmp_path):
    made = Setup(tmp_path)
    yield made
    made.server.stop()


def test_nothing_is_listed_while_nothing_has_stopped(setup):
    assert setup.attention() == []


def test_a_stopped_flow_is_listed_with_its_title_node_and_reason(setup):
    setup.stop_the_flow()

    [item] = setup.attention()

    assert item["kind"] == "stopped" and item["flow"] == "weekly" and item["title"] == "Weekly export"
    assert item["node"] == "n2" and item["step"] == "close-message" and item["reason"] == "control_not_found"
    assert item["doubt"] == 1 and item["note"] is None and item["rejected_by_person"] == []


def test_the_list_says_when_the_flow_stopped(setup):
    setup.stop_the_flow()

    [item] = setup.attention()

    assert item["at"].startswith("2026-01-01T")  # when the stopped run ended


def test_a_flow_with_two_open_doubts_is_one_item_and_a_tested_node_is_none(setup):
    save_step(setup.db, step("third", "Gamma"))
    save_flow(setup.db, Flow(id="weekly", nodes=[Node("n1", "open-menu"), Node("n2", "close-message"), Node("n3", "third")],
                             edges=[("n1", "n2"), ("n1", "n3")]))
    run_flow(Flow(id="weekly", nodes=[Node("n1", "open-menu"), Node("n2", "close-message"), Node("n3", "third")],
                  edges=[("n1", "n2"), ("n1", "n3")]), setup.desktop, setup.db)
    run_flow(Flow(nodes=[Node("n9", "close-message")], id="weekly", trial="weekly#test:n2"), setup.desktop, setup.db)

    items = setup.attention()

    assert len(list_doubts(setup.db, "open")) == 3 and [i["flow"] for i in items] == ["weekly"]  # the test's doubt is not listed


def test_a_deleted_flow_raises_no_card(setup):
    setup.stop_the_flow()
    assert call(setup.server, "/api/flows/weekly", "DELETE")[0] == 200

    assert setup.attention() == []


def test_a_private_apps_rejected_actions_are_sent_as_handles_that_still_allow_them_again(tmp_path):
    made = Setup(tmp_path, app="vault.exe")
    try:
        mark_private(made.db, "vault.exe")
        made.stop_the_flow()
        reject_step(made.db, "vault.exe", "close-message")

        [item] = made.attention()
        [handle] = item["rejected_by_person"]

        assert "close-message" not in json.dumps(item) and "Beta" not in json.dumps(item)
        assert call(made.server, f"/api/steps/{handle['app']}/{handle['step']}/restore", "POST")[0] == 200
        assert state_of(made.db, "close-message") != "rejected" and made.attention()[0]["rejected_by_person"] == []
    finally:
        made.server.stop()


def test_a_private_apps_node_is_not_named(tmp_path):
    made = Setup(tmp_path, app="vault.exe")
    try:
        mark_private(made.db, "vault.exe")
        made.stop_the_flow()

        [item] = made.attention()

        assert item["step"] is None and item["private"] is True
        assert "close-message" not in json.dumps(item) and "Beta" not in json.dumps(item)
    finally:
        made.server.stop()


# --- trying again ---------------------------------------------------------------------------

def test_trying_again_closes_the_doubt_as_tried_again_and_resumes_from_where_it_stopped(setup):
    setup.stop_the_flow()
    setup.desktop._controls.append(button("Beta"))  # what was wrong has passed
    before = len(setup.desktop.clicks)

    code, started, _ = setup.try_again()
    view = setup.finished(started["run_id"])

    assert code == 202 and view["status"] == "finished"
    assert [c.name for c in setup.desktop.clicks[before:]] == ["Beta"]  # the first node was not done twice
    [doubt] = list_doubts(setup.db)
    assert (doubt.status, doubt.closed_as) == ("answered", "tried_again")
    assert setup.attention() == []


def test_trying_again_that_stops_again_leaves_a_new_open_doubt(setup):
    setup.stop_the_flow()

    _, started, _ = setup.try_again()
    view = setup.finished(started["run_id"])

    assert view["status"] == "stopped" and view["stopped"] == "n2"
    assert [d.status for d in list_doubts(setup.db)] == ["answered", "open"]
    assert [i["doubt"] for i in setup.attention()] == [2]


def state_of(db, name):
    return step_report(db, next(s for s in list_steps(db, None) if s.name == name))["state"]


def test_trying_again_lifts_a_rejection_a_failed_check_made_and_does_the_node_again(tmp_path):
    made = Setup(tmp_path, effect="closed_dialog")  # taught to close a dialog, but now it reveals something
    try:
        made.desktop._reveals[("button", "Beta")] = [button("New")]
        made.desktop._controls.append(button("Beta"))
        made.stop_the_flow()
        assert state_of(made.db, "close-message") == "rejected"  # one failure rejected it
        [item] = made.attention()
        assert item["reason"] == "effect_mismatch" and item["rejected_by_person"] == []

        code, started, _ = made.try_again()
        view = made.finished(started["run_id"])

        assert code == 202  # a rejected step would have refused to start
        assert [c.name for c in made.desktop.clicks] == ["Alpha", "Beta", "Beta"]  # the action happened again, as said
        assert view["status"] == "stopped"  # and it differed again: the same problem
        assert [(d.status, d.closed_as) for d in list_doubts(made.db)] == [("answered", "tried_again"), ("open", None)]
    finally:
        made.server.stop()


def test_trying_again_never_lifts_a_step_the_person_rejected(setup):
    setup.stop_the_flow()
    reject_step(setup.db, "paint.exe", "close-message")

    code, body, _ = setup.try_again()

    assert code == 400 and "rejected" in body["error"] and "Allow" in body["error"]
    assert state_of(setup.db, "close-message") == "rejected"
    assert [d.status for d in list_doubts(setup.db)] == ["open"]  # nothing was closed
    [item] = setup.attention()
    assert item["rejected_by_person"] == [{"app": "paint.exe", "step": "close-message"}]


def test_a_try_that_cannot_start_leaves_the_doubt_open(setup):
    setup.stop_the_flow()
    setup.server._runs["busy"] = {"flow_id": "weekly", "status": "running", "nodes": {}, "log": []}

    code, _, _ = setup.try_again()

    assert code == 409 and [d.status for d in list_doubts(setup.db)] == ["open"]


def test_trying_again_on_a_flow_nobody_knows_is_a_404(setup):
    assert call(setup.server, "/api/flows/nothing/try-again", "POST", {"app": "paint.exe"})[0] == 404


# --- asking for help -------------------------------------------------------------------------

def test_asking_for_help_keeps_the_note_on_the_doubt_and_leaves_it_open(setup):
    setup.stop_the_flow()

    code, body, _ = call(setup.server, "/api/doubts/1/help", "POST", {"note": "Paint was minimised"})

    assert code == 200 and body == {"doubt": 1, "note": "Paint was minimised"}
    [doubt] = list_doubts(setup.db)
    assert (doubt.status, doubt.note) == ("open", "Paint was minimised")
    assert setup.attention()[0]["note"] == "Paint was minimised"
    assert list_open_doubts(setup.db)[0]["note"] == "Paint was minimised"  # the tutor reads it


def test_a_long_note_is_cut_and_a_closed_doubt_takes_none(setup):
    setup.stop_the_flow()
    call(setup.server, "/api/doubts/1/help", "POST", {"note": "x" * 900})
    assert len(list_doubts(setup.db)[0].note) == 500

    answer_doubt(setup.db, 1)
    assert call(setup.server, "/api/doubts/1/help", "POST", {"note": "late"})[0] == 400
    assert call(setup.server, "/api/doubts/99/help", "POST", {"note": "x"})[0] == 400


def test_a_run_that_is_recorded_as_stopped_is_not_a_card_without_a_doubt(setup):
    record_run(setup.db, "weekly", "2026-01-01T07:00:00Z", "2026-01-01T07:00:01Z", "stopped", "n2", [])

    assert setup.attention() == []


def test_a_run_that_resumes_shows_the_nodes_done_before_as_done(setup):
    setup.stop_the_flow()
    setup.desktop._controls.append(button("Beta"))

    _, started, _ = setup.try_again()
    view = setup.finished(started["run_id"])

    assert view["nodes"] == {"n1": "done", "n2": "done"}  # the first node was done by the run that stopped
