"""A flow has no program of its own: each step node names the technology it acts on, and the API never asks for one."""

import json
import time

import pytest
from fake_scheduler import FakeScheduler
from test_api import call

from workflow_factory import save_step
from workflow_factory.api import ApiServer
from workflow_factory.queue import list_doubts
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, button, step


@pytest.fixture
def served(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    save_step(db, step("print", "Print", app="excel.exe"))
    desktops = {"excel.exe": FakeDesktop(controls=[button("Save workbook"), button("Print")], app="excel.exe"),
                "paint.exe": FakeDesktop(controls=[button("Save picture")], app="paint.exe")}
    server = ApiServer(db, None, desktops.__getitem__, token="secret-token", schedule_runner=FakeScheduler())
    server.start()
    yield server, desktops, db
    server.stop()


def finished(server, run_id):
    for _ in range(200):
        view = call(server, f"/api/runs/{run_id}")[1]
        if view["status"] != "running":
            return view
        time.sleep(0.05)


MIXED = {"nodes": [{"id": "a", "step": "save", "technology": "excel.exe"},
                   {"id": "b", "step": "save", "technology": "paint.exe"}], "edges": [["a", "b"]]}


def test_a_flow_keeps_the_technology_of_each_node_and_no_program_of_its_own(served):
    server, _, _ = served

    saved = call(server, "/api/flows/mixed", "PUT", {**MIXED, "title": "Mixed"})
    loaded = call(server, "/api/flows/mixed")[1]

    assert saved[0] == 200 and "app" not in loaded
    assert [n["technology"] for n in loaded["nodes"]] == ["excel.exe", "paint.exe"]
    assert call(server, "/api/flows")[1] == [{"id": "mixed", "origin": "local", "title": "Mixed"}]
    assert all("app" not in entry for entry in call(server, "/api/flow-overview")[1])


def test_a_run_needs_no_program_in_its_request_and_each_node_acts_on_its_own(served):
    server, desktops, _ = served
    call(server, "/api/flows/mixed", "PUT", MIXED)

    code, started, _ = call(server, "/api/flows/mixed/run", "POST", {"context": {}})
    view = finished(server, started["run_id"])

    assert code == 202 and view["status"] == "finished"
    assert [c.name for c in desktops["excel.exe"].clicks] == ["Save workbook"]
    assert [c.name for c in desktops["paint.exe"].clicks] == ["Save picture"]


def test_a_flow_with_a_node_whose_step_is_not_learned_there_is_refused_and_nothing_is_touched(served):
    server, desktops, _ = served
    body = {"nodes": [*MIXED["nodes"], {"id": "c", "step": "print", "technology": "paint.exe"}], "edges": [["a", "b"], ["b", "c"]]}
    call(server, "/api/flows/mixed", "PUT", body)

    code, answer, _ = call(server, "/api/flows/mixed/run", "POST", {})

    assert code == 400 and "'print' for paint" in answer["error"]
    assert all(d.calls == [] for d in desktops.values())
    assert call(server, "/api/flow-overview")[1][0]["blocked"] == {
        "why": "not_learned", "steps": ["print"], "by_technology": {"paint.exe": ["print"]}}


def test_a_node_test_needs_no_program_either(served):
    server, desktops, _ = served
    call(server, "/api/flows/mixed", "PUT", MIXED)

    code, started, _ = call(server, "/api/flows/mixed/nodes/b/test", "POST", {})

    assert code == 202 and finished(server, started["run_id"])["status"] == "finished"
    assert desktops["excel.exe"].clicks == [] and len(desktops["paint.exe"].clicks) == 1


def test_a_stop_on_a_node_leaves_a_doubt_that_names_its_technology(served):
    server, desktops, db = served
    call(server, "/api/flows/mixed", "PUT", MIXED)
    desktops["paint.exe"]._controls.clear()  # the picture program shows nothing to press

    _, started, _ = call(server, "/api/flows/mixed/run", "POST", {})
    view = finished(server, started["run_id"])

    assert view["status"] == "stopped" and view["stopped"] == "b"
    [doubt] = list_doubts(db, "open")
    assert (doubt.node_id, doubt.step, doubt.technology) == ("b", "save", "paint.exe")
    assert call(server, "/api/doubts")[1][0]["technology"] == "paint.exe"
    [card] = [i for i in call(server, "/api/attention")[1] if i["kind"] == "stopped"]
    assert card["app"] == "paint.exe" and card["node"] == "b"


def test_the_step_list_shows_no_control_name_of_a_private_technology_and_search_cannot_find_it(served):
    server, _, db = served
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    mark_private(db, "telegram.exe")

    everything = call(server, "/api/steps")[1]
    [private] = [row for row in everything if row["name"] == "open-chat"]
    [public] = [row for row in everything if row["name"] == "print"]

    assert "Ana" not in json.dumps(private) and private["locator"] == {"role": "button"}
    assert private["technologies"] == [] and public["locator"]["name"] == "Print"  # others keep their locator
    assert call(server, "/api/steps?q=ana")[1] == []
