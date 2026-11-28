"""A flow has no program of its own: Home and the editor work from the technology each node records. Opt-in: `pytest -m web`."""

import json
import sqlite3
from contextlib import closing

import pytest
from test_home_e2e import home, row, run_button, says

from workflow_factory import Flow, Node, load_flow, save_flow, save_step

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


def two_programs(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    save_flow(db, Flow(id="both", nodes=[Node("a", "save", technology="excel.exe"), Node("b", "save", technology="paint.exe")]),
              "Both programs")
    return {"excel.exe": FakeDesktop(controls=[button("Save workbook")], app="excel.exe"),
            "paint.exe": FakeDesktop(controls=[button("Save picture")], app="paint.exe")}


def test_home_runs_a_flow_of_two_programs_without_asking_for_one(tmp_path):
    desktops = two_programs(tmp_path)
    with home(tmp_path, desktop_for=desktops.__getitem__) as (page, _):
        bodies = []
        page.on("request", lambda r: bodies.append(r.post_data) if r.method == "POST" and r.url.endswith("/run") else None)
        text = row(page, "both").inner_text()
        assert "Excel" in text and "Paint" in text  # each node's program, none of the flow's own
        run_button(page, "both").click()
        says(page, "both", "Worked")
        assert [json.loads(body) for body in bodies] == [{"context": {}}]
    assert [c.name for c in desktops["excel.exe"].clicks] == ["Save workbook"]
    assert [c.name for c in desktops["paint.exe"].clicks] == ["Save picture"]


def test_home_says_which_program_has_not_learned_a_step_and_touches_nothing(tmp_path):
    desktops = two_programs(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="both", nodes=[
        Node("a", "save", technology="excel.exe"), Node("b", "save", technology="word.exe")]), "Both programs")
    with home(tmp_path, desktop_for=desktops.__getitem__) as (page, _):
        button_ = run_button(page, "both")
        button_.filter(has_text="Not ready yet").wait_for()
        assert page.get_by_test_id("flow-why-both").inner_text().strip() == "“save” is not learned for Word yet."
        assert button_.is_disabled()
    assert all(d.calls == [] for d in desktops.values())


def test_a_step_added_in_the_editor_is_kept_with_the_program_it_was_taught_on(tmp_path):
    from playwright.sync_api import sync_playwright
    from test_editor_e2e import DIST, open_page

    from workflow_factory.api import ApiServer

    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    server = ApiServer(db, None, lambda tech: FakeDesktop(controls=[], app=tech), token="e2e-token", web_dir=DIST)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("flow-title").fill("kept")
            page.get_by_test_id("palette-save").click()
            page.get_by_test_id("technology-excel.exe").click()  # a step of two programs asks which
            page.get_by_test_id("node-n1").wait_for()
            open_technology(page, "n1").select_option("paint.exe")
            page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
            browser.close()
    finally:
        server.stop()

    flow = load_flow(db, None, "kept")
    assert [n.technology for n in flow.nodes] == ["paint.exe"]
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT app FROM flow_info").fetchall() == [(None,)]  # nothing of a program stays on the flow


def open_technology(page, node_id):
    """The technology chooser in the detail of a node."""
    if not page.get_by_test_id("detail").is_visible():
        page.get_by_test_id(f"node-{node_id}").dblclick()
    return page.get_by_test_id("node-technology")


def serve_two_programs(tmp_path, size=(1280, 860)):
    from playwright.sync_api import sync_playwright
    from test_editor_e2e import DIST, open_page

    from workflow_factory.api import ApiServer

    two_programs(tmp_path)
    save_step(tmp_path / "user.db", step("only-excel", "Only Excel", app="excel.exe"))
    server = ApiServer(tmp_path / "user.db", None, lambda tech: FakeDesktop(controls=[], app=tech), token="e2e-token", web_dir=DIST)
    server.start()
    playwright = sync_playwright().start()
    browser, page = open_page(playwright, server)
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.set_default_timeout(8_000)
    return server, playwright, browser, page


@pytest.fixture
def two(tmp_path):
    server, playwright, browser, page = serve_two_programs(tmp_path)
    yield page, tmp_path
    browser.close()
    playwright.stop()
    server.stop()


def test_the_flow_screen_has_no_program_selector_and_the_panel_lists_steps_by_name_once(two):
    page, _ = two
    page.get_by_test_id("palette-save").wait_for()
    assert page.get_by_test_id("app-name").count() == 0
    assert page.get_by_test_id("palette-save").count() == 1  # learned for two programs, offered once
    assert page.get_by_test_id("palette-only-excel").count() == 1
    page.get_by_test_id("search").fill("paint")  # the search box still finds by program
    page.get_by_test_id("palette-save").wait_for()
    assert page.get_by_test_id("palette-only-excel").count() == 0


def test_a_node_says_its_program_and_offers_only_the_programs_its_step_is_learned_for(two):
    page, _ = two
    page.get_by_test_id("palette-only-excel").click()
    page.get_by_test_id("palette-save").click()
    page.get_by_test_id("technology-excel.exe").click()  # a step of two programs asks which
    assert "Excel" in page.get_by_test_id("node-n1").inner_text()
    chooser = open_technology(page, "n1")
    assert [o.inner_text() for o in chooser.locator("option").all()] == ["Excel"]
    page.get_by_test_id("close-detail").click()
    chooser = open_technology(page, "n2")
    assert sorted(o.inner_text() for o in chooser.locator("option").all()) == ["Excel", "Paint"]
    assert page.get_by_test_id("detail").inner_text().count("Excel") >= 1


def test_the_changed_technology_is_kept_after_a_reload_and_undo_takes_it_back(two):
    page, tmp_path = two
    page.get_by_test_id("flow-title").fill("changed")
    page.get_by_test_id("palette-save").click()
    page.get_by_test_id("technology-excel.exe").click()  # a step of two programs asks which
    page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
    first = load_flow(tmp_path / "user.db", None, "changed").nodes[0].technology
    other = "paint.exe" if first == "excel.exe" else "excel.exe"
    open_technology(page, "n1").select_option(other)
    page.get_by_test_id("close-detail").click()
    page.get_by_test_id("undo").click()  # Undo takes the change back, and the save follows it
    assert open_technology(page, "n1").input_value() == first
    page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
    assert load_flow(tmp_path / "user.db", None, "changed").nodes[0].technology == first
    open_technology(page, "n1").select_option(other)
    page.get_by_test_id("close-detail").click()
    page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
    assert load_flow(tmp_path / "user.db", None, "changed").nodes[0].technology == other
    page.reload()
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-changed").click()
    page.get_by_test_id("node-n1").wait_for()
    assert open_technology(page, "n1").input_value() == other


def test_the_technology_chooser_is_reached_and_changed_from_the_keyboard(two):
    page, _ = two
    page.get_by_test_id("palette-save").click()
    page.get_by_test_id("technology-excel.exe").click()  # a step of two programs asks which
    chooser = open_technology(page, "n1")
    before = chooser.input_value()
    chooser.focus()
    page.keyboard.press("ArrowDown")
    assert before == "excel.exe" and chooser.input_value() == "paint.exe"  # the first program by name is the one added
    page.keyboard.press("ArrowUp")
    assert page.evaluate("document.activeElement.dataset.testid") == "node-technology"


def test_the_chooser_fits_a_narrow_window(tmp_path):
    server, playwright, browser, page = serve_two_programs(tmp_path, size=(390, 800))
    try:
        page.get_by_test_id("palette-save").click()
        page.get_by_test_id("technology-excel.exe").click()  # a step of two programs asks which
        chooser = open_technology(page, "n1")
        box = chooser.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        browser.close()
        playwright.stop()
        server.stop()
