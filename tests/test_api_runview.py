"""The run view's API side: stop at once, the run log, safety marks on steps, a flow with a rejected step refusing to start."""

import time

import pytest
from test_api import call, wait_until_finished

from workflow_factory import Flow, Node, Sensitivity, grant_consent, reject_step, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.flow import EMERGENCY_STOP

from fake_desktop import FakeDesktop, button, step


def make(tmp_path, nodes, **desktop_kw):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")], **desktop_kw)
    save_flow(tmp_path / "user.db", Flow(id="f", nodes=nodes))
    server = ApiServer(tmp_path / "user.db", None, lambda app: desktop, token="secret-token")
    server.start()
    return server, desktop


@pytest.fixture
def two(tmp_path):
    server, desktop = make(tmp_path, [Node("a", "open-menu"), Node("b", "save-file")])
    yield server, desktop
    server.stop()


def test_a_run_keeps_a_log_of_what_each_node_did_in_order(two):
    server, _ = two
    _, started, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
    wait_until_finished(server, started["run_id"])

    view = call(server, f"/api/runs/{started['run_id']}")[1]

    assert [(e["node"], e["status"]) for e in view["log"]] == [
        ("a", "running"), ("a", "done"), ("b", "running"), ("b", "done")]
    assert all(len(e["at"]) == 8 and e["at"][2] == ":" for e in view["log"])  # HH:MM:SS


def test_stop_ends_the_run_at_once_and_the_next_run_is_not_blocked_by_it(tmp_path):
    server, desktop = make(tmp_path, [Node("a", "open-menu"), Node("b", "save-file")])
    desktop.click_seconds = 0.5
    try:
        _, started, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
        time.sleep(0.15)
        code, _, _ = call(server, f"/api/runs/{started['run_id']}/stop", "POST")
        wait_until_finished(server, started["run_id"])
        view = call(server, f"/api/runs/{started['run_id']}")[1]

        assert code == 202 and view["status"] == "emergency"
        assert [c.name for c in desktop.clicks] == ["Alpha"]  # b never acted
        assert not EMERGENCY_STOP.is_set()  # cleared once nothing is running, or the next run would refuse to start
        desktop.click_seconds = 0
        again = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
        wait_until_finished(server, again[1]["run_id"])
        assert again[0] == 202 and call(server, f"/api/runs/{again[1]['run_id']}")[1]["status"] in ("finished", "stopped")
    finally:
        server.stop()


def test_stopping_a_run_that_is_not_running_or_does_not_exist_is_refused(two):
    server, _ = two
    _, started, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
    wait_until_finished(server, started["run_id"])

    assert call(server, f"/api/runs/{started['run_id']}/stop", "POST")[0] == 409
    assert call(server, "/api/runs/nope/stop", "POST")[0] == 404


def test_a_flow_with_a_rejected_step_is_refused_with_the_step_named(tmp_path):
    server, desktop = make(tmp_path, [Node("a", "open-menu"), Node("b", "save-file")])
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")
    try:
        code, body, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
    finally:
        server.stop()

    assert code == 400 and "save-file" in body["error"] and "rejected" in body["error"]
    assert desktop.clicks == []


def test_a_step_says_how_far_it_is_trusted_whether_its_app_is_private_and_whether_consent_is_given(tmp_path):
    save_step(tmp_path / "user.db", step("send", "Send", app="telegram.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(tmp_path / "user.db", step("plain", "Alpha"))
    save_step(tmp_path / "user.db", step("gone", "Beta"))
    reject_step(tmp_path / "user.db", "paint.exe", "gone")
    server = ApiServer(tmp_path / "user.db", None, lambda app: None, token="secret-token")
    server.start()
    try:
        by_name = {s["name"]: s for s in call(server, "/api/steps")[1]}
        grant_consent(tmp_path / "user.db", "telegram.exe", "Send", "click")
        after = {s["name"]: s for s in call(server, "/api/steps")[1]}
    finally:
        server.stop()

    assert (by_name["plain"]["state"], by_name["plain"]["private"], by_name["plain"]["consent"]) == ("suspect", False, "none")
    assert by_name["gone"]["state"] == "rejected"
    assert (by_name["send"]["private"], by_name["send"]["consent"]) == (True, "missing")
    assert after["send"]["consent"] == "given"


def test_open_doubts_are_listed_by_flow_and_node_so_the_editor_can_count_them(tmp_path):
    server, desktop = make(tmp_path, [Node("a", "open-menu"), Node("b", "save-file")])
    desktop._controls = [button("Alpha")]  # Beta is missing: b stops with a doubt
    try:
        _, started, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
        wait_until_finished(server, started["run_id"])
        doubts = call(server, "/api/doubts?status=open")[1]
    finally:
        server.stop()

    assert [(d["flow_id"], d["node_id"]) for d in doubts] == [("f", "b")]


def test_the_recipes_are_listed_with_the_apps_they_were_taught_on_and_their_adapted_steps_say_so(tmp_path):
    from workflow_factory.recipes import apply_recipe, save_recipe

    holes = [{"hole": "open", "role": "button", "control_name": "Alpha"}, {"hole": "go", "role": "button", "control_name": "Beta"}]
    save_recipe(tmp_path / "user.db", "launch", holes)
    apply_recipe(tmp_path / "user.db", FakeDesktop(controls=[button("Alpha"), button("Beta")], app="a.exe"), "launch")
    apply_recipe(tmp_path / "user.db", FakeDesktop(controls=[button("Alpha"), button("Gamma")], app="b.exe"), "launch",
                 {"go": {"role": "button", "control_name": "Gamma"}})
    server = ApiServer(tmp_path / "user.db", None, lambda app: None, token="secret-token")
    server.start()
    try:
        (recipe,) = call(server, "/api/recipes")[1]
        steps = {(s["app"], s["name"]): s for s in call(server, "/api/steps")[1]}
    finally:
        server.stop()

    assert recipe["name"] == "launch" and recipe["origin"] == "a.exe" and set(recipe["apps"]) == {"a.exe", "b.exe"}
    assert steps[("b.exe", "launch-go")]["adapted_from"] == "a.exe"
    assert steps[("a.exe", "launch-go")]["adapted_from"] is None


def test_a_flow_that_names_a_step_not_taught_for_the_app_is_refused_with_the_step_named(tmp_path):
    server, desktop = make(tmp_path, [Node("a", "open-menu"), Node("b", "launch-go")])
    try:
        code, body, _ = call(server, "/api/flows/f/run", "POST", {"app": "paint.exe"})
    finally:
        server.stop()

    assert code == 400 and "'launch-go'" in body["error"] and "not been taught" in body["error"]
    assert desktop.clicks == []
