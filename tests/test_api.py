import json
import time
import urllib.error
import urllib.request

import pytest
from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import Flow, Node, save_flow, save_lesson
from workflow_factory.api import ApiServer


def make_server(tmp_path, desktop=None, **kw):
    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop,
                       token="secret-token", **kw)
    server.start()
    return server


def call(server, path, method="GET", body=None, token="secret-token", host=None):
    request = urllib.request.Request(server.url + path, method=method)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if host:
        request.add_header("Host", host)
    data = json.dumps(body).encode() if body is not None else None
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, data=data, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null"), dict(error.headers)


@pytest.fixture
def server(tmp_path):
    running = make_server(tmp_path)
    yield running
    running.stop()


def test_requests_without_the_token_or_with_a_wrong_one_are_rejected(server):
    assert call(server, "/api/lessons", token=None)[0] == 401
    assert call(server, "/api/lessons", token="guess")[0] == 401
    assert call(server, "/api/lessons")[0] == 200


def test_the_server_only_binds_to_the_loopback_interface(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        ApiServer(tmp_path / "u.db", None, lambda app: None, host="0.0.0.0")
    server = make_server(tmp_path)
    try:
        assert server.address[0] == "127.0.0.1"
    finally:
        server.stop()


def test_a_request_whose_host_header_is_not_loopback_is_refused_against_dns_rebinding(server):
    status, _, _ = call(server, "/api/lessons", host="evil.example.com")

    assert status == 403


def test_the_api_sends_no_cross_origin_permission(server):
    _, _, headers = call(server, "/api/lessons")

    assert not [name for name in headers if name.lower().startswith("access-control-")]


def test_the_palette_lists_lessons_from_the_user_and_the_factory_with_the_user_shadowing(tmp_path):
    save_lesson(tmp_path / "factory.db", lesson("open-menu", "Factory menu", origin="factory"))
    save_lesson(tmp_path / "factory.db", lesson("save-file", "Save", origin="factory"))
    save_lesson(tmp_path / "user.db", lesson("open-menu", "My menu"))
    server = make_server(tmp_path)
    try:
        status, lessons, _ = call(server, "/api/lessons")
    finally:
        server.stop()

    assert status == 200
    by_name = {item["name"]: item for item in lessons}
    assert by_name["open-menu"]["origin"] == "local" and by_name["open-menu"]["locator"]["name"] == "My menu"
    assert by_name["save-file"]["origin"] == "factory"
    assert "secret_ref" not in json.dumps(lessons)


def test_a_flow_built_in_the_editor_is_saved_to_sqlite_and_listed(server, tmp_path):
    body = {"nodes": [{"id": "a", "lesson": "open-menu"}, {"id": "b", "lesson": "save-file"}],
            "edges": [["a", "b"]]}

    assert call(server, "/api/flows/morning", "PUT", body)[0] == 200
    status, flow, _ = call(server, "/api/flows/morning")
    _, listing, _ = call(server, "/api/flows")

    assert status == 200 and [n["id"] for n in flow["nodes"]] == ["a", "b"] and flow["edges"] == [["a", "b"]]
    assert {"id": "morning", "origin": "local"} in listing


def test_an_invalid_flow_is_refused_with_a_message(server):
    body = {"nodes": [{"id": "a", "lesson": "x"}, {"id": "b", "lesson": "y"}], "edges": [["a", "b"], ["b", "a"]]}

    status, error, _ = call(server, "/api/flows/loopy", "PUT", body)

    assert status == 400 and "cycle" in error["error"]


def test_a_flow_runs_and_its_live_per_node_status_can_be_polled(tmp_path):
    save_lesson(tmp_path / "user.db", lesson("open-menu", "Alpha"))
    save_lesson(tmp_path / "user.db", lesson("save-file", "Beta"))
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=[Node("a", "open-menu"), Node("b", "save-file")]))
    server = make_server(tmp_path)
    try:
        status, started, _ = call(server, "/api/flows/morning/run", "POST", {"app": "paint.exe"})
        run_id, final = started["run_id"], None
        for _ in range(100):
            _, final, _ = call(server, f"/api/runs/{run_id}")
            if final["status"] != "running":
                break
            time.sleep(0.05)
    finally:
        server.stop()

    assert status == 202 and final["status"] == "finished"
    assert final["nodes"] == {"a": "done", "b": "done"}


def test_the_built_editor_is_served_without_a_token_because_it_holds_no_data(tmp_path):
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<title>editor</title>")
    server = make_server(tmp_path, web_dir=web)
    try:
        with urllib.request.urlopen(server.url + "/", timeout=5) as response:
            page = response.read().decode()
    finally:
        server.stop()

    assert "<title>editor</title>" in page


def test_an_unexpected_failure_is_a_json_500_without_details(tmp_path):
    (tmp_path / "factory.db").write_bytes(b"this is not a sqlite file at all, just text" * 10)
    server = make_server(tmp_path)
    try:
        status, body, _ = call(server, "/api/flows")
    finally:
        server.stop()

    assert status == 500 and body == {"error": "internal error"}


def test_a_negative_content_length_is_refused_instead_of_blocking_a_thread(server):
    import socket

    with socket.create_connection(server.address, timeout=5) as connection:
        connection.sendall(
            (f"PUT /api/flows/x HTTP/1.1\r\nHost: 127.0.0.1:{server.address[1]}\r\n"
             "Authorization: Bearer secret-token\r\nContent-Length: -1\r\n\r\n").encode())
        reply = connection.recv(4096).decode()

    assert reply.startswith("HTTP/1.0 400") or reply.startswith("HTTP/1.1 400")


def test_a_non_ascii_authorization_header_is_a_plain_401(server):
    request = urllib.request.Request(server.url + "/api/lessons")
    request.add_header("Authorization", "Bearer caf\u00e9")

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=5)

    assert refused.value.code == 401


def test_an_ipv6_host_header_is_refused_because_the_server_never_binds_it(server):
    assert call(server, "/api/lessons", host=f"[::1]:{server.address[1]}")[0] == 403


def slow_server(tmp_path, flows=1, **kw):
    desktop = FakeDesktop(controls=[button("Alpha")])
    desktop.click_seconds = 0.6  # long enough to still be running when the next request arrives
    save_lesson(tmp_path / "user.db", lesson("open-menu", "Alpha"))
    for number in range(flows):
        save_flow(tmp_path / "user.db", Flow(id=f"f{number}", nodes=[Node("a", "open-menu")]))
    server = ApiServer(tmp_path / "user.db", None, lambda app: desktop, token="secret-token", **kw)
    server.start()
    return server


def wait_until_finished(server, run_id):
    for _ in range(200):
        if call(server, f"/api/runs/{run_id}")[1]["status"] != "running":
            return
        time.sleep(0.05)


def test_a_flow_that_is_already_running_cannot_be_started_again(tmp_path):
    server = slow_server(tmp_path)
    try:
        first = call(server, "/api/flows/f0/run", "POST", {"app": "paint.exe"})
        second = call(server, "/api/flows/f0/run", "POST", {"app": "paint.exe"})
        wait_until_finished(server, first[1]["run_id"])
        third = call(server, "/api/flows/f0/run", "POST", {"app": "paint.exe"})
        wait_until_finished(server, third[1]["run_id"])
    finally:
        server.stop()

    assert (first[0], second[0], third[0]) == (202, 409, 202)


def test_the_number_of_runs_at_the_same_time_is_capped(tmp_path):
    server = slow_server(tmp_path, flows=3, max_active_runs=2)
    try:
        codes = [call(server, f"/api/flows/f{n}/run", "POST", {"app": "paint.exe"})[0] for n in range(3)]
        time.sleep(1.2)
    finally:
        server.stop()

    assert codes == [202, 202, 429]


def test_only_the_most_recent_finished_runs_are_kept(tmp_path):
    server = slow_server(tmp_path, flows=3, max_kept_runs=2)
    server_ids = []
    try:
        for n in range(3):
            _, started, _ = call(server, f"/api/flows/f{n}/run", "POST", {"app": "paint.exe"})
            server_ids.append(started["run_id"])
            wait_until_finished(server, started["run_id"])
        statuses = [call(server, f"/api/runs/{run_id}")[0] for run_id in server_ids]
    finally:
        server.stop()

    assert statuses == [404, 200, 200]
