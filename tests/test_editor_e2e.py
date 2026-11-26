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


@pytest.fixture(autouse=True)
def not_the_first_run(monkeypatch):
    """Every screen test starts as a later run, so the editor is what shows; the first-run test turns this off."""
    monkeypatch.setattr("workflow_factory.api.seen_before", lambda data_dir: True)
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
    page.wait_for_timeout(400)  # the canvas re-fits (animated) after a node is added
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
        page.get_by_test_id("open-detail").click()
        page.get_by_test_id("add-input").click()
        page.get_by_test_id("close-detail").click()
        page.get_by_test_id("flow-id").fill("e2e-flow")
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()

        saved = load_flow(tmp_path / "user.db", None, "e2e-flow")
        assert [n.step for n in saved.nodes] == ["open-menu", "save-file"]
        assert saved.edges == [("n1", "n2")]
        assert saved.nodes[1].inputs == (("value", "str"),)

        # run it with the typed value and watch the per-node status
        page.get_by_test_id("app-name").fill("paint.exe")
        page.get_by_test_id("run-data").click()
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

        page.get_by_test_id("open-flows").click()
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
        assert "needs consent" in marked.inner_text().lower()
        assert "needs consent" not in page.get_by_test_id("palette-open-menu").inner_text().lower()
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
            page.get_by_test_id("open-flows").click()
            page.get_by_test_id("duplicate-morning-template").click()
            page.locator('.react-flow__node[data-id="n1"]').wait_for()
            assert page.get_by_test_id("flow-id").input_value() == "morning-template-copy"
            page.get_by_test_id("open-flows").click()
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


def test_system_nodes_and_steps_are_added_wired_deleted_saved_and_reopened(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        page.get_by_test_id("system-manual-trigger").click()  # n1
        page.get_by_test_id("palette-open-menu").click()  # n2
        page.get_by_test_id("system-daily-trigger").click()  # n3, deleted again below
        page.get_by_test_id("palette-save-file").click()  # n4
        page.locator('.react-flow__node[data-id="n4"]').wait_for()
        drag_between(page, page.locator('.react-flow__node[data-id="n1"] .react-flow__handle.source'),
                     page.locator('.react-flow__node[data-id="n2"] .react-flow__handle.target'))
        drag_between(page, page.locator('.react-flow__node[data-id="n2"] .react-flow__handle.source'),
                     page.locator('.react-flow__node[data-id="n4"] .react-flow__handle.target'))
        page.locator('.react-flow__node[data-id="n3"]').click()
        page.get_by_test_id("delete-node").click()
        assert page.locator('.react-flow__node[data-id="n3"]').count() == 0
        page.get_by_test_id("flow-id").fill("built")
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()

        saved = load_flow(tmp_path / "user.db", None, "built")
        assert [(n.id, n.kind, n.step) for n in saved.nodes] == [
            ("n1", "trigger", ""), ("n2", "step", "open-menu"), ("n4", "step", "save-file")]
        assert saved.edges == [("n1", "n2"), ("n2", "n4")]

        # start from an empty canvas, then reopen the saved flow
        page.get_by_test_id("open-flows").click()
        page.get_by_test_id("new-flow").click()
        assert page.locator(".react-flow__node").count() == 0
        page.get_by_test_id("open-flows").click()
        page.get_by_test_id("flow-built").click()
        page.locator('.react-flow__node[data-id="n4"]').wait_for()
        assert page.locator(".react-flow__node").count() == 3 and page.locator(".react-flow__edge").count() == 2
        browser.close()


def test_the_search_panel_finds_system_nodes_and_steps_by_name_and_by_app(editor):
    from playwright.sync_api import expect, sync_playwright

    server, _ = editor
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        page.get_by_test_id("palette-open-menu").wait_for()
        search = page.get_by_test_id("search")

        search.fill("wait")
        page.get_by_test_id("system-wait").wait_for()
        expect(page.get_by_test_id("palette-open-menu")).to_have_count(0)  # retried: the panel re-renders after the typing

        search.fill("paint")  # by app: both steps of Paint, no system node
        page.get_by_test_id("palette-open-menu").wait_for()
        expect(page.get_by_test_id("palette-save-file")).to_have_count(1)
        expect(page.get_by_test_id("system-wait")).to_have_count(0)

        search.fill("nothing like this")
        page.get_by_text("Nothing matches").wait_for()
        browser.close()


def test_a_flow_with_an_if_and_a_for_each_keeps_what_the_wires_mean_after_saving(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        page.get_by_test_id("system-foreach").click()  # n1
        page.get_by_test_id("palette-open-menu").click()  # n2: the body
        page.get_by_test_id("palette-save-file").click()  # n3: after the loop
        page.locator('.react-flow__node[data-id="n3"]').wait_for()
        for a, b in (("n1", "n2"), ("n1", "n3")):
            drag_between(page, page.locator(f'.react-flow__node[data-id="{a}"] .react-flow__handle.source'),
                         page.locator(f'.react-flow__node[data-id="{b}"] .react-flow__handle.target'))
        page.get_by_test_id("flow-id").fill("looped")
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()

        saved = load_flow(tmp_path / "user.db", None, "looped")
        assert saved.nodes[0].body == "n2" and saved.edges == [("n1", "n3")]
        browser.close()


def test_nothing_in_the_editor_starts_a_lesson(editor):
    import re

    from playwright.sync_api import sync_playwright

    server, _ = editor
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        page.get_by_test_id("palette-open-menu").wait_for()
        page.get_by_test_id("palette-open-menu").click()
        page.get_by_test_id("open-flows").click()
        page.locator(".react-flow__node").first.click()
        words = page.locator("body").inner_text() + " ".join(
            b.get_attribute("aria-label") or "" for b in page.get_by_role("button").all())
        assert not re.search(r"lesson|teach|learn|study", words, re.IGNORECASE)
        browser.close()


def seed_data_flow(tmp_path):
    from workflow_factory import save_flow

    def fixed(value):
        return {"value": value}

    nodes = [
        Node("d", kind="data", op="fixed", fields={"value": fixed("hello world")}),
        Node("c", kind="data", op="convert", fields={"value": {"ref": {"node": "d", "field": "value"}}, "to": fixed("text")}),
        Node("m", kind="data", op="math", fields={"a": fixed(1), "b": fixed(2), "operation": fixed("add")}),
        Node("p", "open-menu"),
    ]
    save_flow(tmp_path / "user.db", Flow(id="datas", nodes=nodes, edges=[("d", "c"), ("c", "m"), ("m", "p")]))


def open_seeded_flow(page):
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-datas").click()
    page.locator('.react-flow__node[data-id="p"]').wait_for()


def test_the_node_detail_shows_data_hidden_until_asked_and_never_before_a_run(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    seed_data_flow(tmp_path)
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        open_seeded_flow(page)
        page.locator('.react-flow__node[data-id="c"]').dblclick()
        detail = page.get_by_test_id("detail")
        detail.wait_for()
        assert "No data yet" in detail.inner_text()  # nothing ran

        page.get_by_test_id("close-detail").click()
        page.get_by_test_id("app-name").fill("paint.exe")
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="finished").wait_for(timeout=10_000)
        page.locator('.react-flow__node[data-id="c"]').dblclick()
        out = detail.get_by_test_id("data-value")
        out.first.wait_for()
        assert "text · 11 characters" in detail.inner_text() and "hello world" not in detail.inner_text()

        detail.get_by_test_id("show-values").check()
        detail.get_by_text("hello world").first.wait_for()
        detail.get_by_test_id("show-values").uncheck()
        detail.get_by_text("text · 11 characters").first.wait_for()
        assert "hello world" not in detail.inner_text()
        browser.close()


def test_a_field_is_edited_as_a_fixed_value_or_as_a_reference_and_the_node_is_tested_alone(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    seed_data_flow(tmp_path)
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        open_seeded_flow(page)
        page.get_by_test_id("app-name").fill("paint.exe")
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="finished").wait_for(timeout=10_000)

        page.locator('.react-flow__node[data-id="m"]').dblclick()
        detail = page.get_by_test_id("detail")
        detail.get_by_test_id("value-a").fill("10")  # a fixed number
        detail.get_by_test_id("mode-b").select_option("ref")  # b now comes from another node
        assert page.get_by_test_id("ref-b").locator("option").count() >= 2
        detail.get_by_test_id("mode-b").select_option("value")
        detail.get_by_test_id("value-b").fill("5")

        detail.get_by_test_id("test-node").click()  # a data node touches no control: no warning first
        detail.get_by_test_id("test-result").filter(has_text="Test finished").wait_for(timeout=10_000)
        detail.get_by_test_id("show-values").check()
        detail.get_by_text("15").first.wait_for()

        detail.get_by_test_id("close-detail").click()
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()
        saved = load_flow(tmp_path / "user.db", None, "datas")
        math = next(n for n in saved.nodes if n.id == "m")
        assert math.fields["a"] == {"value": 10} and math.fields["b"] == {"value": 5}
        browser.close()


def test_testing_a_step_warns_about_the_mouse_and_keyboard_first_then_runs_only_that_step(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    seed_data_flow(tmp_path)
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        open_seeded_flow(page)
        page.get_by_test_id("app-name").fill("paint.exe")
        page.locator('.react-flow__node[data-id="p"]').dblclick()
        detail = page.get_by_test_id("detail")
        detail.get_by_test_id("test-node").click()
        warning = page.get_by_test_id("test-warning")
        warning.wait_for()
        assert "mouse and keyboard" in warning.inner_text()
        assert page.locator(".react-flow__node.status-done").count() == 0  # nothing ran yet
        page.get_by_test_id("confirm-test").click()
        detail.get_by_test_id("test-result").filter(has_text="Test finished").wait_for(timeout=10_000)
        browser.close()


def test_a_node_takes_a_failure_policy_in_its_settings(editor):
    from playwright.sync_api import sync_playwright

    server, tmp_path = editor
    seed_data_flow(tmp_path)
    with sync_playwright() as playwright:
        browser, page = open_page(playwright, server)
        open_seeded_flow(page)
        page.locator('.react-flow__node[data-id="p"]').dblclick()
        page.get_by_test_id("on-failure").select_option("retry")
        page.get_by_test_id("retries").fill("4")
        page.get_by_test_id("close-detail").click()
        page.get_by_test_id("save").click()
        page.get_by_test_id("run-status").filter(has_text="saved").wait_for()
        node = next(n for n in load_flow(tmp_path / "user.db", None, "datas").nodes if n.id == "p")
        assert (node.on_failure, node.retries) == ("retry", 4)
        browser.close()


def serve(tmp_path, desktop):
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop, token="e2e-token", web_dir=DIST)
    server.start()
    return server


def test_stop_ends_a_run_at_once_and_the_run_button_comes_back(tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import save_flow

    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
    save_flow(tmp_path / "user.db", Flow(id="slow", nodes=[Node("a", "open-menu"), Node("b", "save-file")]))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 0.8
    server = serve(tmp_path, desktop)
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("open-flows").click()
            page.get_by_test_id("flow-slow").click()
            page.locator('.react-flow__node[data-id="b"]').wait_for()
            page.get_by_test_id("app-name").fill("paint.exe")
            page.get_by_test_id("run").click()
            page.get_by_test_id("run-log").wait_for()
            page.get_by_test_id("stop").click()
            page.get_by_test_id("run-status").filter(has_text="emergency").wait_for(timeout=10_000)
            page.get_by_test_id("run").wait_for()
            assert [c.name for c in desktop.clicks] == ["Alpha"]
            assert "open-menu started" in page.get_by_test_id("run-log").inner_text()
            browser.close()
    finally:
        server.stop()


def test_a_flow_with_a_rejected_step_says_which_one_and_cannot_be_started(tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import reject_step, save_flow

    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")
    save_flow(tmp_path / "user.db", Flow(id="blocked", nodes=[Node("a", "open-menu"), Node("b", "save-file")]))
    server = serve(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Beta")]))
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("palette-open-menu").wait_for()
            page.get_by_test_id("open-flows").click()
            page.get_by_test_id("flow-blocked").click()
            note = page.get_by_test_id("cannot-start")
            note.wait_for()
            assert "'save-file' is rejected" in note.inner_text()
            assert page.get_by_test_id("run").is_disabled()
            assert "1 rejected step" in page.get_by_test_id("safety-summary").inner_text()
            assert "Rejected" in page.get_by_test_id("node-b").inner_text()
            browser.close()
    finally:
        server.stop()


def test_cards_say_how_far_a_step_is_trusted_and_doubts_are_counted_but_cannot_be_answered_here(tmp_path):
    from playwright.sync_api import sync_playwright

    from workflow_factory import Sensitivity, grant_consent, save_flow

    save_step(tmp_path / "user.db", step("send", "Send", app="telegram.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(tmp_path / "user.db", step("open-menu", "Alpha", app="telegram.exe"))
    grant_consent(tmp_path / "user.db", "telegram.exe", "Send", "click")
    save_flow(tmp_path / "user.db", Flow(id="chat", nodes=[Node("a", "open-menu"), Node("b", "send")]))
    desktop = FakeDesktop(controls=[button("Alpha")], app="telegram.exe")  # Send is not on screen: b will stop
    server = serve(tmp_path, desktop)
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("palette-send").wait_for()
            page.get_by_test_id("open-flows").click()
            page.get_by_test_id("flow-chat").click()
            page.locator('.react-flow__node[data-id="b"]').wait_for()
            b = page.get_by_test_id("node-b").inner_text()
            assert "On trial" in b and "Consent given" in b and "Private app" in b

            page.get_by_test_id("app-name").fill("telegram.exe")
            page.get_by_test_id("run").click()
            page.get_by_test_id("run-status").filter(has_text="stopped").wait_for(timeout=10_000)
            page.get_by_text("1 doubt").first.wait_for()
            assert "1 doubt" in page.get_by_test_id("node-b").inner_text()
            assert "1 doubt" in page.get_by_test_id("safety-summary").inner_text()
            words = " ".join(button_.inner_text() for button_ in page.get_by_role("button").all())
            assert not any(word in words.lower() for word in ("answer", "dismiss", "resolve"))
            browser.close()
    finally:
        server.stop()


HOLES = [{"hole": "open", "role": "button", "control_name": "Alpha"}, {"hole": "compose", "role": "button", "control_name": "Beta"},
         {"hole": "send", "role": "button", "control_name": "Gamma"}]


def taught_recipe(tmp_path, second_has_compose=True):
    from workflow_factory.recipes import apply_recipe, save_recipe

    save_recipe(tmp_path / "user.db", "send-message", HOLES)
    apply_recipe(tmp_path / "user.db", FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")], app="a.exe"),
                 "send-message")
    names = ["Alpha", "Gamma"] + (["Delta"] if second_has_compose else [])
    fills = {"compose": {"role": "button", "control_name": "Delta"}} if second_has_compose else {}
    apply_recipe(tmp_path / "user.db", FakeDesktop(controls=[button(n) for n in names], app="b.exe"), "send-message", fills)


def test_dropping_a_recipe_adds_its_connected_nodes_and_adapted_steps_say_where_they_came_from(tmp_path):
    from playwright.sync_api import sync_playwright

    taught_recipe(tmp_path)
    server = serve(tmp_path, FakeDesktop(controls=[]))
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            entry = page.get_by_test_id("recipe-send-message")
            entry.wait_for()
            assert "3 steps" in entry.inner_text() and "A" in entry.inner_text()
            page.get_by_test_id("app-name").fill("b.exe")
            entry.click()
            page.locator('.react-flow__node[data-id="n3"]').wait_for()
            assert page.locator(".react-flow__node").count() == 3 and page.locator(".react-flow__edge").count() == 2
            assert "Adapted from A" in page.get_by_test_id("node-n2").inner_text()  # compose was taught for b on its own
            assert page.get_by_test_id("cannot-start").count() == 0 and not page.get_by_test_id("run").is_disabled()

            page.get_by_test_id("app-name").fill("a.exe")  # the original app: nothing is adapted
            assert "Adapted" not in page.get_by_test_id("node-n2").inner_text()
            browser.close()
    finally:
        server.stop()


def test_a_recipe_with_an_unfilled_hole_cannot_run_and_says_which(tmp_path):
    from playwright.sync_api import sync_playwright

    taught_recipe(tmp_path, second_has_compose=False)  # on b the compose control was never found: a hole stays open
    server = serve(tmp_path, FakeDesktop(controls=[]))
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("app-name").fill("b.exe")
            page.get_by_test_id("recipe-send-message").click()
            page.locator('.react-flow__node[data-id="n3"]').wait_for()
            note = page.get_by_test_id("cannot-start")
            note.wait_for()
            assert "the hole 'compose' of the recipe 'send-message'" in note.inner_text()
            assert "the hole 'send'" in note.inner_text()
            assert "Hole not filled: compose" in page.get_by_test_id("node-n2").inner_text()
            assert page.get_by_test_id("run").is_disabled()
            browser.close()
    finally:
        server.stop()


def test_a_schedule_is_added_listed_and_removed_from_the_screen_and_other_tasks_stay_hidden(tmp_path):
    from fake_scheduler import FOREIGN, FakeScheduler
    from playwright.sync_api import sync_playwright

    from workflow_factory import save_flow

    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=[Node("a", "open-menu")]))
    scheduler = FakeScheduler()
    server = ApiServer(tmp_path / "user.db", None, lambda app: None, token="e2e-token", web_dir=DIST, schedule_runner=scheduler)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("tab-schedules").click()
            page.get_by_test_id("no-schedules").wait_for()  # the foreign task is not shown
            page.get_by_test_id("schedule-app").fill("mspaint.exe")
            page.get_by_test_id("schedule-time").fill("07:45")
            page.get_by_test_id("schedule-add").click()
            row = page.get_by_test_id("schedule-row-morning daily 0745")
            row.wait_for()
            assert "morning" in row.inner_text() and "mspaint.exe" in row.inner_text() and "07:45" in row.inner_text()
            page.get_by_test_id("schedule-remove-morning daily 0745").click()
            page.get_by_test_id("no-schedules").wait_for()
            assert list(scheduler.tasks) == [FOREIGN]
            browser.close()
    finally:
        server.stop()


def test_the_first_run_opens_on_the_setup_check_and_it_can_be_reopened_later(tmp_path, monkeypatch):
    from playwright.sync_api import sync_playwright

    from workflow_factory.checks import seen_before

    monkeypatch.setattr("workflow_factory.api.seen_before", seen_before)  # the real one: this is a first run
    server = serve(tmp_path, FakeDesktop(controls=[]))
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            summary = page.get_by_test_id("checks-summary")
            summary.wait_for()
            page.get_by_test_id("check-agent-desktop").wait_for()
            text = page.get_by_test_id("check-data-folder").inner_text()
            assert "Ready" in text or "Missing" in text  # always a word, never colour alone
            assert page.get_by_test_id("palette-open-menu").count() == 0  # the editor is behind it on a first run

            page.reload()  # it was shown once: the next visit opens the editor
            page.get_by_test_id("tab-editor").wait_for()
            page.wait_for_timeout(500)
            assert page.get_by_test_id("checks-summary").count() == 0
            page.get_by_test_id("tab-checks").click()
            page.get_by_test_id("checks-summary").wait_for()
            browser.close()
    finally:
        server.stop()
