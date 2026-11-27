import json
import time
import urllib.error
import urllib.request

import pytest

from workflow_factory import Flow, Node, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.steps import add_tags
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, button, step


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
        with error:  # an HTTPError holds the response: close it
            return error.code, json.loads(error.read() or b"null"), dict(error.headers)


@pytest.fixture
def server(tmp_path):
    running = make_server(tmp_path)
    yield running
    running.stop()


def test_requests_without_the_token_or_with_a_wrong_one_are_rejected(server):
    assert call(server, "/api/steps", token=None)[0] == 401
    assert call(server, "/api/steps", token="guess")[0] == 401
    assert call(server, "/api/steps")[0] == 200


def test_the_server_only_binds_to_the_loopback_interface(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        ApiServer(tmp_path / "u.db", None, lambda app: None, host="0.0.0.0")
    server = make_server(tmp_path)
    try:
        assert server.address[0] == "127.0.0.1"
    finally:
        server.stop()


def test_the_editor_never_opens_on_a_port_a_browser_refuses(tmp_path, monkeypatch):
    handed_out, closed = iter([1719, 6667, 50123]), []

    class SystemThatHandsOutBlockedPorts:
        def __init__(self, address, handler):
            self.server_address = (address[0], next(handed_out))

        def server_close(self):
            closed.append(self.server_address[1])

        def serve_forever(self):
            pass

    monkeypatch.setattr("workflow_factory.api.ThreadingHTTPServer", SystemThatHandsOutBlockedPorts)

    server = ApiServer(tmp_path / "u.db", None, lambda app: None)

    assert server.address == ("127.0.0.1", 50123)
    assert closed == [1719, 6667]  # the refused ones are given back


def test_a_request_whose_host_header_is_not_loopback_is_refused_against_dns_rebinding(server):
    status, _, _ = call(server, "/api/steps", host="evil.example.com")

    assert status == 403


def test_the_step_listing_carries_tags_and_technologies_and_filters_with_the_shared_search_rule(tmp_path):
    save_step(tmp_path / "user.db", step("Save", "Save", app="paint.exe"))
    save_step(tmp_path / "user.db", step("Save", "Save", app="notepad.exe"))
    save_step(tmp_path / "user.db", step("Éxport data", "Export", app="vault.exe"))
    add_tags(tmp_path / "user.db", "Save", ["File"])
    mark_private(tmp_path / "user.db", "vault.exe")
    server = make_server(tmp_path)
    try:
        everything = call(server, "/api/steps")[1]
        by_text = call(server, "/api/steps?q=sav")[1]
        by_tag_text = call(server, "/api/steps?q=fil")[1]
        by_tech = call(server, "/api/steps?tech=paint.exe")[1]
        private_text = call(server, "/api/steps?q=export")[1]
    finally:
        server.stop()

    saves = [item for item in everything if item["name"] == "Save"]
    assert len(everything) == 3 and all(item["technologies"] == ["notepad.exe", "paint.exe"] for item in saves)
    assert all(item["tags"] == ["file"] for item in saves)
    assert {item["app"] for item in by_text} == {"paint.exe", "notepad.exe"} == {item["app"] for item in by_tag_text}
    assert [item["app"] for item in by_tech] == ["paint.exe"]
    vault = [item for item in everything if item["app"] == "vault.exe"][0]
    assert vault["tags"] == [] and vault["technologies"] == []  # a private technology adds nothing it could be found by
    assert [item["app"] for item in private_text] == ["vault.exe"]  # its own row still shows, by name, as before


def test_the_api_sends_no_cross_origin_permission(server):
    _, _, headers = call(server, "/api/steps")

    assert not [name for name in headers if name.lower().startswith("access-control-")]


def test_the_palette_lists_steps_from_the_user_and_the_factory_with_the_user_shadowing(tmp_path):
    save_step(tmp_path / "factory.db", step("open-menu", "Factory menu", origin="factory"))
    save_step(tmp_path / "factory.db", step("save-file", "Save", origin="factory"))
    save_step(tmp_path / "user.db", step("open-menu", "My menu"))
    server = make_server(tmp_path)
    try:
        status, steps, _ = call(server, "/api/steps")
    finally:
        server.stop()

    assert status == 200
    by_name = {item["name"]: item for item in steps}
    assert by_name["open-menu"]["origin"] == "local" and by_name["open-menu"]["locator"]["name"] == "My menu"
    assert by_name["save-file"]["origin"] == "factory"
    assert "secret_ref" not in json.dumps(steps)


def test_a_flow_built_in_the_editor_is_saved_to_sqlite_and_listed(server, tmp_path):
    body = {"nodes": [{"id": "a", "step": "open-menu"}, {"id": "b", "step": "save-file"}],
            "edges": [["a", "b"]]}

    assert call(server, "/api/flows/morning", "PUT", body)[0] == 200
    status, flow, _ = call(server, "/api/flows/morning")
    _, listing, _ = call(server, "/api/flows")

    assert status == 200 and [n["id"] for n in flow["nodes"]] == ["a", "b"] and flow["edges"] == [["a", "b"]]
    assert {"id": "morning", "origin": "local", "title": "morning"} in listing


def test_an_invalid_flow_is_refused_with_a_message(server):
    body = {"nodes": [{"id": "a", "step": "x"}, {"id": "b", "step": "y"}], "edges": [["a", "b"], ["b", "a"]]}

    status, error, _ = call(server, "/api/flows/loopy", "PUT", body)

    assert status == 400 and "cycle" in error["error"]


def test_a_flow_runs_and_its_live_per_node_status_can_be_polled(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
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


def test_an_unexpected_failure_is_written_with_its_traceback_to_the_console_but_not_to_the_browser(tmp_path, capsys):
    (tmp_path / "factory.db").write_bytes(b"this is not a sqlite file at all, just text" * 10)
    server = make_server(tmp_path)
    try:
        status, body, _ = call(server, "/api/flows")
    finally:
        server.stop()

    assert status == 500 and body == {"error": "internal error"}
    assert "Traceback" in capsys.readouterr().err  # so a person can tell a lost data folder from a bug


def test_a_negative_content_length_is_refused_instead_of_blocking_a_thread(server):
    import socket

    with socket.create_connection(server.address, timeout=5) as connection:
        connection.sendall(
            (f"PUT /api/flows/x HTTP/1.1\r\nHost: 127.0.0.1:{server.address[1]}\r\n"
             "Authorization: Bearer secret-token\r\nContent-Length: -1\r\n\r\n").encode())
        reply = connection.recv(4096).decode()

    assert reply.startswith("HTTP/1.0 400") or reply.startswith("HTTP/1.1 400")


def test_a_non_ascii_authorization_header_is_a_plain_401(server):
    request = urllib.request.Request(server.url + "/api/steps")
    request.add_header("Authorization", "Bearer caf\u00e9")

    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(request, timeout=5)

    refused.value.close()
    assert refused.value.code == 401


def test_an_ipv6_host_header_is_refused_because_the_server_never_binds_it(server):
    assert call(server, "/api/steps", host=f"[::1]:{server.address[1]}")[0] == 403


def slow_server(tmp_path, flows=1, **kw):
    desktop = FakeDesktop(controls=[button("Alpha")])
    desktop.click_seconds = 0.6  # long enough to still be running when the next request arrives
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
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


def test_a_factory_template_can_be_duplicated_into_the_user_layer_through_the_api(tmp_path):
    from workflow_factory import build_factory

    build_factory(tmp_path / "factory.db", {"version": 1, "steps": [], "flows": [
        {"id": "morning-template", "nodes": [{"id": "a", "step": "open-menu"}], "edges": None}]})
    server = make_server(tmp_path)
    try:
        created = call(server, "/api/flows/morning-template/duplicate", "POST", {"new_id": "mine"})
        again = call(server, "/api/flows/morning-template/duplicate", "POST", {"new_id": "mine"})
        listing = call(server, "/api/flows")[1]
    finally:
        server.stop()

    assert created[0] == 201 and created[1]["id"] == "mine"
    assert again[0] == 400 and "already exists" in again[1]["error"]
    assert [(f["id"], f["origin"]) for f in listing] == [("mine", "local"), ("morning-template", "factory")]


def test_quit_needs_the_token_and_then_flags_the_server_to_stop(server):
    assert call(server, "/api/quit", method="POST", token=None)[0] == 401
    assert not server.quit_requested.is_set()

    assert call(server, "/api/quit", method="POST")[0] == 202
    assert server.quit_requested.is_set()
