"""The built editor in a headless browser, against the real local API. Opt-in: `pytest -m web`.

Needs web/dist (cd web && npm install && npm run build). The browser is this test's own headless
instance: it never opens a window or touches the person's mouse and keyboard.
"""

import glob
import json
import os
from pathlib import Path

import pytest

from workflow_factory import Flow, Node, load_flow, save_step
from workflow_factory.api import ApiServer

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web
DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
HEADLESS_SHELL = glob.glob(os.path.expanduser(
    "~/AppData/Local/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell.exe"))


@pytest.fixture
def editor(tmp_path):
    if not (DIST / "index.html").exists():
        pytest.fail("web/dist is missing: run `npm install && npm run build` in web/")
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
    save_step(tmp_path / "factory.db", step("factory-only", "Gamma", origin="factory"))
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

        # palette: steps from the user and factory layers
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
        assert [n.step for n in saved.nodes] == ["open-menu", "save-file"]
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


def test_a_sensitive_step_is_marked_in_words_in_the_palette_not_only_by_colour(editor, tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import Sensitivity

    server, folder = editor
    save_step(folder / "user.db", step("send-message", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
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


def open_page(playwright, server):
    browser = playwright.chromium.launch(
        headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
    page = browser.new_page()
    page.goto(f"{server.url}/#token=e2e-token")
    return browser, page


def test_the_four_other_screens_show_their_data_and_their_actions_work(tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import grant_consent, run_flow

    if not (DIST / "index.html").exists():
        pytest.fail("web/dist is missing: run `npm install && npm run build` in web/")
    user_db, factory_db = tmp_path / "user.db", tmp_path / "factory.db"
    save_step(factory_db, step("open-menu", "Menu", origin="factory", factory_successes=50))
    save_step(user_db, step("save-file", "Save"))
    grant_consent(user_db, app="paint.exe", control="Send", action="click")
    flow = Flow(id="morning", nodes=[Node("a", "save-file"), Node("b", "open-menu")])
    # Menu is missing on screen: the flow stops at b, leaving a doubt and a history row
    run_flow(flow, desktop=FakeDesktop(controls=[button("Save")]), user_db=user_db, factory_db=factory_db)
    server = ApiServer(user_db, factory_db, lambda app: FakeDesktop(controls=[]), token="e2e-token", web_dir=DIST)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)

            page.get_by_test_id("tab-library").click()
            row = page.get_by_test_id("step-row-open-menu")
            row.wait_for()
            assert "factory" in row.inner_text() and page.get_by_test_id("state-open-menu").inner_text() == "suspect"
            page.get_by_test_id("reject-open-menu").click()
            page.get_by_test_id("restore-open-menu").wait_for()
            assert page.get_by_test_id("state-open-menu").inner_text() == "rejected"
            page.get_by_test_id("restore-open-menu").click()
            page.get_by_test_id("reject-open-menu").wait_for()

            page.get_by_test_id("tab-consents").click()
            page.get_by_test_id("consent").wait_for()
            assert page.get_by_role("button", name="Grant").count() == 0  # revoke only
            page.get_by_test_id("revoke-Send").click()
            page.get_by_test_id("no-consents").wait_for()

            page.get_by_test_id("tab-queue").click()
            page.get_by_test_id("doubt-1").wait_for()
            assert "control_not_found" in page.get_by_test_id("doubt-1").inner_text()
            page.get_by_test_id("note-1").fill("the button is called Main menu now")
            page.get_by_test_id("answer-1").click()
            page.get_by_test_id("no-doubts").wait_for()
            page.get_by_test_id("doubt-filter").select_option("answered")
            page.get_by_test_id("doubt-1").wait_for()
            assert "answer: the button is called Main menu now" in page.get_by_test_id("doubt-1").inner_text()

            page.get_by_test_id("tab-history").click()
            page.get_by_test_id("run-1").wait_for()
            text = page.get_by_test_id("run-1").inner_text()
            assert "stopped" in text and "a: done" in text and "b: blocked (control_not_found)" in text
            browser.close()
    finally:
        server.stop()


def test_a_factory_template_is_duplicated_from_the_editor_and_opens_as_an_editable_copy(tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import build_factory

    if not (DIST / "index.html").exists():
        pytest.fail("web/dist is missing: run `npm install && npm run build` in web/")
    build_factory(tmp_path / "factory.db", {"version": 1, "steps": [], "flows": [
        {"id": "morning-template", "nodes": [{"id": "n1", "step": "open-menu"}], "edges": None}]})
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: None, token="e2e-token", web_dir=DIST)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("duplicate-morning-template").click()
            page.get_by_test_id("flow-morning-template-copy").wait_for()
            page.locator('.react-flow__node[data-id="n1"]').wait_for()
            assert page.get_by_test_id("flow-id").input_value() == "morning-template-copy"
            assert "local" in page.get_by_test_id("flow-morning-template-copy").inner_text()
            assert page.get_by_test_id("duplicate-morning-template-copy").count() == 0  # a copy is not a template
            browser.close()
    finally:
        server.stop()


def test_the_quit_button_asks_first_then_ends_the_server_and_says_so_on_screen(editor):
    from playwright.sync_api import sync_playwright

    server, _ = editor
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, executable_path=HEADLESS_SHELL[0] if HEADLESS_SHELL else None)
        page = browser.new_page()
        asked, accept = [], {"now": False}
        page.on("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept() if accept["now"] else dialog.dismiss()))
        page.goto(server.url + "/#token=e2e-token")

        page.get_by_test_id("quit").click()
        page.wait_for_timeout(500)
        assert len(asked) == 1 and not server.quit_requested.is_set()  # asked, and "cancel" changed nothing

        accept["now"] = True
        page.get_by_test_id("quit").click()
        page.get_by_test_id("closed").wait_for()
        assert server.quit_requested.is_set()
        assert "closed" in page.get_by_test_id("closed").inner_text().lower()
        browser.close()
