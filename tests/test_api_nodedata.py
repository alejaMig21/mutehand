"""The node detail endpoints: the Data of the last run (shapes unless values are asked for) and Test this node."""

import time

import pytest
from test_api import call, make_server

from workflow_factory import Flow, Node, save_flow, save_step

from fake_desktop import FakeDesktop, button, step


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


@pytest.fixture
def server(tmp_path):
    save_step(tmp_path / "user.db", step("press", "Alpha"))
    save_step(tmp_path / "user.db", step("typer", "Notes", action="type_value"))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Notes")], secrets={"vault/token": "hunter2-secret"})
    running = make_server(tmp_path, desktop)
    running.desktop = desktop
    yield running
    running.stop()


def chain():
    return Flow(id="f", nodes=[
        Node("d", kind="data", op="fixed", fields={"value": fixed("hello world")}),
        Node("c", kind="data", op="convert", fields={"value": ref("d", "value"), "to": fixed("text")}),
        Node("p", "press"),
    ])


def finish(server, run_id):
    for _ in range(100):
        _, view, _ = call(server, f"/api/runs/{run_id}")
        if view["status"] != "running":
            return view
        time.sleep(0.05)
    raise AssertionError("the run did not end")


def run_chain(server, tmp_path):
    save_flow(tmp_path / "user.db", chain())
    _, started, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
    return finish(server, started["run_id"])


def test_after_a_run_the_node_data_shows_shapes_and_never_the_values_by_default(server, tmp_path):
    run_chain(server, tmp_path)

    code, body, _ = call(server, "/api/flows/f/data")

    assert code == 200
    assert body["c"] == {"in": {"value": {"type": "text", "size": 11}, "to": {"type": "text", "size": 4}},
                         "out": {"value": {"type": "text", "size": 11}}}
    assert "hello world" not in str(body)


def test_the_values_come_only_when_they_are_asked_for(server, tmp_path):
    run_chain(server, tmp_path)

    _, body, _ = call(server, "/api/flows/f/data?values=1")

    assert body["c"]["out"] == {"value": "hello world"}


def test_a_flow_that_never_ran_has_no_data_yet(server, tmp_path):
    save_flow(tmp_path / "user.db", chain())

    assert call(server, "/api/flows/f/data")[1] == {}
    assert call(server, "/api/flows/ghost/data")[0] == 404


def test_test_this_node_runs_only_that_node_and_updates_its_data(server, tmp_path):
    run_chain(server, tmp_path)
    flow = chain()
    flow = Flow(id="f", nodes=[flow.nodes[0], Node("c", kind="data", op="convert",
                                                   fields={"value": ref("d", "value"), "to": fixed("text")}),
                               Node("m", kind="data", op="math", fields={"a": fixed(1), "b": fixed(2), "operation": fixed("add")})])
    save_flow(tmp_path / "user.db", flow)
    server.desktop.clicks.clear()  # what the first run did is not what the test does

    code, started, _ = call(server, "/api/flows/f/nodes/m/test", "POST", {"app": "paint.exe"})
    view = finish(server, started["run_id"])

    assert code == 202 and view["status"] == "finished" and server.desktop.clicks == []
    assert call(server, "/api/flows/f/data?values=1")[1]["m"]["out"] == {"value": 3}


def test_testing_a_step_acts_on_that_step_alone(server, tmp_path):
    run_chain(server, tmp_path)
    server.desktop.clicks.clear()

    _, started, _ = call(server, "/api/flows/f/nodes/p/test", "POST", {"app": "paint.exe"})
    view = finish(server, started["run_id"])

    assert view["status"] == "finished" and [c.name for c in server.desktop.clicks] == ["Alpha"]


def test_a_node_that_needs_data_from_a_run_that_never_happened_says_so(server, tmp_path):
    save_flow(tmp_path / "user.db", chain())

    code, body, _ = call(server, "/api/flows/f/nodes/c/test", "POST", {"app": "paint.exe"})

    assert code == 400 and "run the flow" in body["error"]


def test_only_steps_and_data_nodes_can_be_tested_and_the_node_must_exist(server, tmp_path):
    save_flow(tmp_path / "user.db", Flow(id="g", nodes=[Node("w", kind="wait", fields={"seconds": fixed(1)})]))

    assert "cannot be tested alone" in call(server, "/api/flows/g/nodes/w/test", "POST", {"app": "paint.exe"})[1]["error"]
    assert call(server, "/api/flows/g/nodes/zzz/test", "POST", {"app": "paint.exe"})[0] == 400
    assert call(server, "/api/flows/ghost/nodes/w/test", "POST", {"app": "paint.exe"})[0] == 404


def test_a_secret_typed_by_a_step_is_in_no_response(server, tmp_path):
    save_step(tmp_path / "user.db", step("login", "Notes", action="type_secret", secret_ref="vault/token",
                                         sensitive="password_field"))
    save_flow(tmp_path / "user.db", Flow(id="s", nodes=[Node("l", "login")]))
    from workflow_factory import grant_consent
    grant_consent(tmp_path / "user.db", "paint.exe", "Notes", "type_secret")

    _, started, _ = call(server, "/api/flows/s/run", "POST", {"app": "paint.exe"})
    view = finish(server, started["run_id"])
    body = str(call(server, "/api/flows/s/data?values=1")[1]) + str(view)

    assert "hunter2-secret" not in body
