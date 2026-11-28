"""What the editor needs from the API so that saving never destroys work and a run is never lost sight of."""

import socket
import sqlite3
import struct
import time

import pytest
from test_api import call, make_server

from workflow_factory import Flow, Node, list_runs, run_flow, save_step, schedule
from workflow_factory.api import MAX_FLOW_NAME_CHARS

from fake_desktop import FakeDesktop, button, save_flow_on, step

ONE = {"nodes": [{"id": "n1", "step": "open-menu"}], "edges": []}
TWO = {"nodes": [{"id": "n1", "step": "open-menu"}, {"id": "n2", "step": "save-file"}], "edges": [["n1", "n2"]]}


def test_where_the_nodes_sit_is_saved_with_the_flow(tmp_path):
    server = make_server(tmp_path)
    try:
        call(server, "/api/flows/placed", "PUT", {**ONE, "positions": {"n1": {"x": 520, "y": 240}}})
        _, loaded, _ = call(server, "/api/flows/placed")
        refused, _, _ = call(server, "/api/flows/placed", "PUT", {**ONE, "positions": {"n1": {"x": "left"}}})
    finally:
        server.stop()

    assert loaded["positions"] == {"n1": {"x": 520, "y": 240}}
    assert refused == 400


def test_a_save_never_silently_replaces_a_flow_the_editor_has_not_seen(tmp_path):
    server = make_server(tmp_path)
    try:
        created, first, _ = call(server, "/api/flows/report", "PUT", {**ONE, "base": None})
        as_new, refusal, _ = call(server, "/api/flows/report", "PUT", {**TWO, "base": None})
        updated, second, _ = call(server, "/api/flows/report", "PUT", {**TWO, "base": first["revision"]})
        stale, _, _ = call(server, "/api/flows/report", "PUT", {**ONE, "base": first["revision"]})
        _, kept, _ = call(server, "/api/flows/report")
        forced, _, _ = call(server, "/api/flows/report", "PUT", ONE)  # no base: the person chose to replace it
    finally:
        server.stop()

    assert (created, as_new, updated, stale, forced) == (200, 409, 200, 409, 200)
    assert "already exists" in refusal["error"]
    assert len(kept["nodes"]) == 2 and kept["revision"] == second["revision"] != first["revision"]


def test_a_flow_name_with_accents_is_saved_as_the_browser_sends_it(tmp_path):
    server = make_server(tmp_path)
    try:
        saved, _, _ = call(server, "/api/flows/ma%C3%B1ana", "PUT", ONE)
        _, listed, _ = call(server, "/api/flows")
        loaded, _, _ = call(server, "/api/flows/ma%C3%B1ana")
        spaced, refusal, _ = call(server, "/api/flows/two%20words", "PUT", ONE)
    finally:
        server.stop()

    assert (saved, loaded) == (200, 200) and listed[0]["id"] == "mañana"
    assert spaced == 400 and "letters, digits" in refusal["error"]


def test_the_runs_in_progress_are_listed_so_a_reloaded_editor_can_stop_them(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    desktop = FakeDesktop(controls=[button("Alpha")])
    desktop.click_seconds = 1.0
    server = make_server(tmp_path, desktop)
    try:
        call(server, "/api/flows/slow", "PUT", {"nodes": [{"id": "n1", "step": "open-menu", "technology": "paint.exe"}], "edges": []})
        _, started, _ = call(server, "/api/flows/slow/run", "POST", {"app": "paint.exe"})
        _, during, _ = call(server, "/api/runs")
        for _ in range(100):
            if call(server, f"/api/runs/{started['run_id']}")[1]["status"] != "running":
                break
            time.sleep(0.05)
        _, after, _ = call(server, "/api/runs")
    finally:
        server.stop()

    assert during == [{"run_id": started["run_id"], "flow_id": "slow"}]
    assert after == []


def test_a_refused_request_says_what_is_wrong_without_showing_the_inside(tmp_path):
    server = make_server(tmp_path)
    try:
        call(server, "/api/flows/report", "PUT", ONE)
        strange = call(server, "/api/flows/odd", "PUT", {"nodes": [{"id": "n1", "step": "x", "surprise": 1}]})
        too_long = call(server, f"/api/flows/{'a' * 101}", "PUT", ONE)
    finally:
        server.stop()

    assert strange[:2] == (400, {"error": "that is not a valid flow"})
    assert too_long[0] == 400 and "100 characters" in too_long[1]["error"]


def test_a_browser_that_leaves_before_the_answer_is_not_an_error(tmp_path, monkeypatch):
    def slow(*databases):
        time.sleep(0.3)
        return []

    monkeypatch.setattr("workflow_factory.api.list_steps", slow)
    server = make_server(tmp_path)
    crashed = []
    server._http.handle_error = lambda request, address: crashed.append(address)  # what would print a traceback
    try:
        with socket.create_connection(server.address) as client:
            client.sendall(f"GET /api/steps HTTP/1.1\r\nHost: 127.0.0.1:{server.address[1]}\r\n"
                           "Authorization: Bearer secret-token\r\n\r\n".encode())
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))  # close at once, hard
        time.sleep(0.8)
    finally:
        server.stop()

    assert crashed == []


def test_no_more_schedules_are_made_than_a_person_could_manage(tmp_path):
    from fake_scheduler import FakeScheduler

    save_flow_on(tmp_path / "user.db", Flow(id="report", nodes=[Node("n1", "open-menu")]), app="paint.exe")
    scheduler = FakeScheduler()
    server = make_server(tmp_path, schedule_runner=scheduler)
    try:
        codes = [call(server, "/api/schedules", "POST", {"flow": "report", "app": "paint.exe", "at": f"{h:02}:00"})[0]
                 for h in range(21)]
        again = call(server, "/api/schedules", "POST", {"flow": "report", "app": "paint.exe", "at": "03:00"})[0]
    finally:
        server.stop()

    assert codes == [201] * 20 + [409] and again == 201  # replacing one that exists is not a new one


def test_listing_many_steps_does_not_open_the_database_once_per_step(tmp_path, monkeypatch):
    for number in range(60):
        save_step(tmp_path / "user.db", step(f"step-{number}", "Alpha"))
    server = make_server(tmp_path)
    opened = []
    real = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: (opened.append(1), real(*a, **kw))[1])
    try:
        counts = []
        for path in ("/api/steps", "/api/apps/paint.exe"):
            opened.clear()
            status, listed, _ = call(server, path)
            counts.append((status, len(listed if isinstance(listed, list) else listed["steps"]), len(opened) < 12))
    finally:
        server.stop()

    assert counts == [(200, 60, True), (200, 60, True)]


def test_the_history_keeps_what_each_node_did_even_after_the_flow_changes(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    run_flow(Flow(id="f", nodes=[Node("n1", "open-menu")]), desktop=FakeDesktop(controls=[button("Alpha")]),
             user_db=tmp_path / "user.db")

    assert list_runs(tmp_path / "user.db")[0]["nodes"][0]["step"] == "open-menu"


@pytest.mark.parametrize("number", [float("nan"), float("inf")])
@pytest.mark.parametrize("where", ["positions", "fields"])
def test_a_number_the_browser_cannot_read_back_is_never_saved(tmp_path, number, where):
    body = ({**ONE, "positions": {"n1": {"x": number, "y": 0}}} if where == "positions" else
            {"nodes": [{"id": "n1", "step": "open-menu", "fields": {"text": {"value": number}}}], "edges": []})
    server = make_server(tmp_path)
    try:
        refused, _, _ = call(server, "/api/flows/bad", "PUT", body)
        loaded, _, _ = call(server, "/api/flows/bad")
    finally:
        server.stop()

    assert (refused, loaded) == (400, 404)


def test_a_fault_inside_the_server_is_not_blamed_on_the_request(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow_factory.api.list_steps", lambda *databases: {}["internal"])
    server = make_server(tmp_path)
    try:
        answer = call(server, "/api/steps")
    finally:
        server.stop()

    assert answer[:2] == (500, {"error": "internal error"})


def test_the_longest_flow_name_the_editor_saves_makes_a_valid_schedule_name():
    assert schedule.full_name(f"{'a' * MAX_FLOW_NAME_CHARS} daily 0900").endswith("daily 0900")
