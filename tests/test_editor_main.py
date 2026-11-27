import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent.parent / "src" / "workflow_factory" / "web"


@pytest.fixture
def editor_process(tmp_path):
    if not (DIST / "index.html").exists():
        pytest.fail("src/workflow_factory/web is missing: run `npm install && npm run build` in web/")
    env = {**os.environ, "WORKFLOW_FACTORY_USER_DB": str(tmp_path / "user.db")}
    process = subprocess.Popen(
        [sys.executable, "-m", "workflow_factory.editor", "--no-hotkey"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
    )
    first_line = process.stdout.readline().strip()
    yield process, first_line
    process.terminate()
    process.wait(timeout=10)


def test_the_editor_command_prints_a_tokened_loopback_url_and_serves_the_built_editor(editor_process):
    _, line = editor_process

    assert line.startswith("Editor: http://127.0.0.1:") and "#token=" in line
    url, token = line.removeprefix("Editor: ").split("#token=")
    with urllib.request.urlopen(url, timeout=5) as page:
        assert b'<div id="root">' in page.read()
    request = urllib.request.Request(url + "api/steps", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert json.loads(response.read()) == []  # an empty user database: nothing taught yet
    with pytest.raises(urllib.error.HTTPError) as refused:
        urllib.request.urlopen(url + "api/steps", timeout=5)
    refused.value.close()
    assert refused.value.code == 401


def test_the_built_editor_lives_inside_the_package_so_an_installed_copy_finds_it():
    import workflow_factory
    from workflow_factory.editor import DEFAULT_WEB_DIR

    assert DEFAULT_WEB_DIR == Path(workflow_factory.__file__).resolve().parent / "web"
    assert (DEFAULT_WEB_DIR / "index.html").is_file()
