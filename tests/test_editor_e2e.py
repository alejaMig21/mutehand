"""The built editor in a headless browser, against the real local API. Opt-in: `pytest -m web`.

Needs web/dist (cd web && npm install && npm run build). The browser is this test's own headless
instance: it never opens a window or touches the person's mouse and keyboard.
"""

import glob
import json
import os
from pathlib import Path

import pytest
from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import Flow, Node, load_flow, save_lesson
from workflow_factory.api import ApiServer

pytestmark = pytest.mark.web
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
HEADLESS_SHELL = glob.glob(os.path.expanduser(
    "~/AppData/Local/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell.exe"))


@pytest.fixture
def editor(tmp_path):
    if not (DIST / "index.html").exists():
        pytest.fail("web/dist is missing: run `npm install && npm run build` in web/")
    save_lesson(tmp_path / "user.db", lesson("open-menu", "Alpha"))
    save_lesson(tmp_path / "user.db", lesson("save-file", "Beta"))
    save_lesson(tmp_path / "factory.db", lesson("factory-only", "Gamma", origin="factory"))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop,
                       token="e2e-token", web_dir=DIST)
    server.start()
    yield server, tmp_path
    server.stop()


def drag_between(page, source, target):
    a, b = source.bounding_box(), target.bounding_box()
    page.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
    page.mouse.down()
    page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=12)
    page.mouse.up()


def test_the_editor_builds_saves_runs_and_shows_live_status_against_the_real_api(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
        page = browser.new_page()
        page.goto(f"{server.url}/#token=e2e-token")

        # palette: lessons from the user and factory layers
        for name in ("open-menu", "save-file", "factory-only"):
            page.get_by_test_id(f"palette-{name}").wait_for()
        page.get_by_test_id("palette-open-menu").click()
        page.get_by_test_id("palette-save-file").click()
        page.locator('.react-flow__node[data-id="n1"]').wait_for()
        page.locator('.react-flow__node[data-id="n2"]').wait_for()

        # connect n1 -> n2, then configure a typed input and save
        drag_between(page, page.locator('.react-flow__node[data-id="n1"] .react-flow__handle.source'),
                     page.locator('.react-flow__node[data-id="n2"] .react-flow__handle.target'))
        page.locator('.react-flow__node[data-id="n2"]').click()
        page.get_by_test_id("add-input").click()
        page.get_by_test_id("flow-id").fill("e2e-flow")
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()

        saved = load_flow(tmp_path / "user.db", None, "e2e-flow")
        assert [n.lesson for n in saved.nodes] == ["open-menu", "save-file"]
        assert saved.edges == [("n1", "n2")]
        assert saved.nodes[1].inputs == (("value", "str"),)

        # run it with the typed value and watch the per-node status
        page.get_by_test_id("app-name").fill("paint.exe")
        page.get_by_test_id("context").fill(json.dumps({"value": "hello"}))
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="finished").wait_for(timeout=10_000)
        assert page.locator('.react-flow__node[data-id="n1"].status-done').count() == 1
        assert page.locator('.react-flow__node[data-id="n2"].status-done').count() == 1
        browser.close()


def test_the_editor_without_the_token_cannot_read_anything(editor):
    from playwright.sync_api import sync_playwright

    server, _ = editor
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
        page = browser.new_page()
        page.goto(server.url + "/")  # no #token fragment
        page.get_by_test_id("error").wait_for()
        assert page.get_by_test_id("palette-open-menu").count() == 0
        browser.close()


def test_a_loaded_flow_keeps_unique_node_ids_and_drops_the_previous_run_colours(editor):
    from playwright.sync_api import sync_playwright
    from workflow_factory import save_flow

    server, tmp_path = editor
    save_flow(tmp_path / "user.db", Flow(id="gappy", nodes=[Node("n1", "open-menu"), Node("n3", "save-file")],
                                         edges=[]))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
        page = browser.new_page()
        page.goto(f"{server.url}/#token=e2e-token")
        page.get_by_test_id("palette-open-menu").click()  # n1 on a fresh canvas
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()
        page.get_by_test_id("app-name").fill("paint.exe")
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="finished").wait_for(timeout=10_000)
        assert page.locator(".react-flow__node.status-done").count() == 1

        page.get_by_test_id("flow-gappy").click()  # a different flow whose node ids are n1 and n3
        page.locator('.react-flow__node[data-id="n3"]').wait_for()
        assert page.locator(".react-flow__node.status-done").count() == 0  # no colours from the old run

        page.get_by_test_id("palette-save-file").click()  # the new node must not reuse n3
        page.locator(".react-flow__node").nth(2).wait_for()
        ids = [node.get_attribute("data-id") for node in page.locator(".react-flow__node").all()]
        assert len(ids) == len(set(ids)) == 3
        browser.close()


def test_the_pure_javascript_of_the_editor_passes_its_own_tests():
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the editor's JavaScript tests")
    done = subprocess.run([node, "--test"], cwd=DIST.parent, capture_output=True, text=True, timeout=60)

    assert done.returncode == 0, done.stdout + done.stderr


def test_a_sensitive_lesson_is_marked_in_words_in_the_palette_not_only_by_colour(editor, tmp_path):
    from playwright.sync_api import sync_playwright
    from workflow_factory import Sensitivity

    server, folder = editor
    save_lesson(folder / "user.db", lesson("send-message", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
        page = browser.new_page()
        page.goto(f"{server.url}/#token=e2e-token")
        marked = page.get_by_test_id("palette-send-message")
        marked.wait_for()
        assert "needs consent" in marked.inner_text()
        assert "needs consent" not in page.get_by_test_id("palette-open-menu").inner_text()
        browser.close()
