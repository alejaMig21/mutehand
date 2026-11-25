import json
import threading
import urllib.request

from workflow_factory import app

from fake_desktop import FakeDesktop


def launch(tmp_path, opened, **kw):
    """Run the launcher in a thread the way the shortcut does; `opened` collects the addresses it opens."""
    thread = threading.Thread(
        target=lambda: app.run(data_dir=tmp_path, open_browser=opened.append, desktop_for=lambda name: FakeDesktop(),
                               hotkey=False, **kw), daemon=True)
    thread.start()
    return thread


def wait_until(condition, seconds=10):
    done = threading.Event()
    for _ in range(int(seconds * 50)):
        if condition():
            return True
        done.wait(0.02)
    return False


def token_of(address):
    return address.split("#token=")[1]


def quit_editor(address):
    base = address.split("#")[0]
    request = urllib.request.Request(base + "api/quit", method="POST")
    request.add_header("Authorization", f"Bearer {token_of(address)}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status


def test_a_launch_opens_the_editor_with_its_token_and_quit_ends_it(tmp_path):
    opened = []
    thread = launch(tmp_path, opened)
    assert wait_until(lambda: opened)

    address = opened[0]
    assert address.startswith("http://127.0.0.1:") and "#token=" in address
    with urllib.request.urlopen(address.split("#")[0], timeout=5) as page:  # the editor page is served
        assert page.status == 200
    assert (tmp_path / "app.json").exists()

    assert quit_editor(address) == 202
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert not (tmp_path / "app.json").exists()  # a quit editor leaves no state behind


def test_a_second_launch_opens_the_running_editor_and_starts_nothing(tmp_path):
    opened = []
    thread = launch(tmp_path, opened)
    assert wait_until(lambda: opened)

    again = []
    app.run(data_dir=tmp_path, open_browser=again.append, desktop_for=lambda name: FakeDesktop(), hotkey=False)

    assert again == [opened[0]]  # same address, same token, returned at once (no second server to wait on)
    quit_editor(opened[0])
    thread.join(timeout=10)


def test_a_leftover_state_file_from_a_crashed_editor_does_not_block_a_new_one(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"url": "http://127.0.0.1:1/#token=dead"}))
    opened = []
    thread = launch(tmp_path, opened)
    assert wait_until(lambda: opened)

    assert opened[0] != "http://127.0.0.1:1/#token=dead"
    quit_editor(opened[0])
    thread.join(timeout=10)


def test_the_launcher_writes_nothing_to_the_console(tmp_path, capsys):
    opened = []
    thread = launch(tmp_path, opened)
    assert wait_until(lambda: opened)
    quit_editor(opened[0])
    thread.join(timeout=10)

    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_the_state_file_holds_only_the_address(tmp_path):
    opened = []
    thread = launch(tmp_path, opened)
    assert wait_until(lambda: opened)

    assert set(json.loads((tmp_path / "app.json").read_text())) == {"url"}
    quit_editor(opened[0])
    thread.join(timeout=10)


def test_another_program_on_the_old_port_is_not_mistaken_for_the_editor(tmp_path):
    import http.server

    class Stranger(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # answers 200 to everything, like many local tools
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"not the editor")

        def log_message(self, *args):
            pass

    stranger = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stranger)
    threading.Thread(target=stranger.serve_forever, daemon=True).start()
    try:
        old = f"http://127.0.0.1:{stranger.server_address[1]}/#token=stale"
        (tmp_path / "app.json").write_text(json.dumps({"url": old}))
        opened = []
        thread = launch(tmp_path, opened)
        assert wait_until(lambda: opened)

        assert opened[0] != old  # it started its own editor instead of opening the stranger
        quit_editor(opened[0])
        thread.join(timeout=10)
    finally:
        stranger.shutdown()
        stranger.server_close()
