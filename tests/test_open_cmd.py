import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENER = ROOT / "Workflow Factory.cmd"


def test_double_clicking_the_opener_file_starts_the_editor_and_returns_at_once(tmp_path):
    fake_browser = tmp_path / "fake_browser.py"
    called = tmp_path / "browser-called.txt"
    fake_browser.write_text(f"import sys\nopen(r'{called}', 'a').write(sys.argv[1] + chr(10))\n", encoding="utf-8")
    env = dict(os.environ, WORKFLOW_FACTORY_USER_DB=str(tmp_path / "user.db"),
               BROWSER=f'"{sys.executable}" "{fake_browser}" %s')

    started = time.perf_counter()
    # no pipes: a double click has none, and the editor that stays running would keep a pipe open and block run()
    result = subprocess.run(["cmd", "/c", str(OPENER)], cwd=tmp_path, env=env, timeout=30, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert result.returncode == 0
    assert time.perf_counter() - started < 10  # the editor keeps running; the opener does not wait for it

    state = tmp_path / "app.json"
    for _ in range(300):
        if state.exists() and called.exists():
            break
        time.sleep(0.1)
    address = json.loads(state.read_text())["url"]
    try:
        assert called.read_text().strip() == address  # the browser was handed the editor address
        with urllib.request.urlopen(address.split("#")[0], timeout=5) as page:
            assert page.status == 200
    finally:
        request = urllib.request.Request(address.split("#")[0] + "api/quit", method="POST")
        request.add_header("Authorization", "Bearer " + address.split("#token=")[1])
        urllib.request.urlopen(request, timeout=5).close()
        for _ in range(100):
            if not state.exists():
                break
            time.sleep(0.1)
    assert not state.exists()
