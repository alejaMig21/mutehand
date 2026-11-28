"""Other things that need the person (editor rethink, ticket 10): actions to learn again by app, a rejected action that
blocks a flow, and a missing piece of setup. API side: the attention list."""

import json

import pytest
from fake_scheduler import FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, reject_step, run_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.steps import revalidate_changed_versions
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, button, save_flow_on, step

MISSING = {"id": "agent-desktop", "title": "Desktop control (agent-desktop)", "why": "It is how the apprentice sees and acts on apps.",
           "ok": False, "fix": "Install it with npm: npm install -g agent-desktop", "optional": False}
FINE = {**MISSING, "ok": True, "fix": None}
OPTIONAL = {**MISSING, "id": "second-monitor", "optional": True}


class Setup:
    def __init__(self, tmp_path, app="paint.exe"):
        self.db = tmp_path / "user.db"
        self.app = app
        save_step(self.db, step("open-menu", "Alpha", app=app))
        save_step(self.db, step("save-file", "Beta", app=app))
        save_flow_on(self.db, Flow(id="morning", nodes=[Node("a", "open-menu"), Node("b", "save-file")]), "Morning report", app)
        save_flow_on(self.db, Flow(id="evening", nodes=[Node("a", "open-menu")]), "Evening report", app)
        self.server = ApiServer(self.db, None, lambda name: FakeDesktop(controls=[button("Alpha")], app=app), token="secret-token",
                                schedule_runner=FakeScheduler())
        self.server.start()

    def items(self):
        return call(self.server, "/api/attention")[1]


@pytest.fixture
def setup(tmp_path):
    made = Setup(tmp_path)
    yield made
    made.server.stop()


def test_an_updated_app_is_one_item_naming_the_app_and_every_flow_it_blocks(setup):
    revalidate_changed_versions(setup.db, "paint.exe", "2.0")

    [item] = setup.items()

    assert item["kind"] == "relearn" and item["app"] == "paint.exe" and item["private"] is False
    assert item["steps"] == ["open-menu", "save-file"]
    assert item["flows"] == [{"id": "evening", "title": "Evening report"}, {"id": "morning", "title": "Morning report"}]


def test_an_updated_app_that_blocks_no_flow_raises_nothing(setup):
    for flow in ("morning", "evening"):
        call(setup.server, f"/api/flows/{flow}", "DELETE")
    revalidate_changed_versions(setup.db, "paint.exe", "2.0")

    assert setup.items() == []


def test_a_private_apps_actions_are_not_named(tmp_path):
    made = Setup(tmp_path, app="vault.exe")
    try:
        mark_private(made.db, "vault.exe")
        revalidate_changed_versions(made.db, "vault.exe", "2.0")

        [item] = made.items()

        assert item["private"] is True and item["steps"] == []
        assert "open-menu" not in json.dumps(item) and "save-file" not in json.dumps(item) and "Alpha" not in json.dumps(item)
    finally:
        made.server.stop()


def test_a_rejected_action_that_blocks_a_flow_says_why_and_which_flows(setup):
    reject_step(setup.db, "paint.exe", "save-file")

    [item] = setup.items()

    assert item["kind"] == "rejected" and item["app"] == "paint.exe" and item["step"] == "save-file"
    assert item["why"] == {"kind": "person"}
    assert item["flows"] == [{"id": "morning", "title": "Morning report"}]


def test_a_rejected_action_that_no_flow_uses_raises_no_item(setup):
    save_step(setup.db, step("unused", "Gamma"))
    reject_step(setup.db, "paint.exe", "unused")

    assert setup.items() == []


def test_allowing_a_rejected_action_again_removes_its_item(setup):
    reject_step(setup.db, "paint.exe", "save-file")

    assert call(setup.server, "/api/steps/paint.exe/save-file/restore", "POST")[0] == 200

    assert setup.items() == []


def test_a_rejected_action_of_a_stopped_flow_is_left_to_that_flows_card(setup):
    run_flow(Flow(id="morning", nodes=[Node("a", "open-menu"), Node("b", "save-file")]), FakeDesktop(controls=[button("Alpha")]), setup.db)
    reject_step(setup.db, "paint.exe", "save-file")

    assert [item["kind"] for item in setup.items()] == ["stopped"]


def test_a_private_apps_rejected_action_is_not_described(tmp_path):
    made = Setup(tmp_path, app="vault.exe")
    try:
        mark_private(made.db, "vault.exe")
        reject_step(made.db, "vault.exe", "save-file")

        [item] = made.items()

        assert item["private"] is True and item["why"] == {"kind": "person"}
        assert "save-file" not in json.dumps(item) and "Beta" not in json.dumps(item)  # an opaque handle, not the name
        assert call(made.server, f"/api/steps/vault.exe/{item['step']}/restore", "POST")[0] == 200  # and it still allows it again
        assert made.items() == []
    finally:
        made.server.stop()


@pytest.mark.parametrize("checks, kinds", [([MISSING], ["setup"]), ([FINE], []), ([OPTIONAL], []), ([], [])])
def test_only_a_missing_required_setup_piece_is_listed(setup, monkeypatch, checks, kinds):
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: checks)

    assert [item["kind"] for item in setup.items()] == kinds


def test_a_missing_setup_piece_says_what_it_is_for_and_how_to_fix_it(setup, monkeypatch):
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [MISSING])

    [item] = setup.items()

    assert item == {"kind": "setup", "id": "agent-desktop", "title": MISSING["title"], "why": MISSING["why"], "fix": MISSING["fix"]}
