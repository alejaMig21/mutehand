"""A person names a flow with any words and it remembers its app, driven in the built editor. Opt-in: `pytest -m web`."""

import re
from contextlib import contextmanager

import pytest
from fake_scheduler import FakeScheduler
from test_editor_e2e import DIST, open_page
from test_editor_safety_e2e import CONTRAST

from workflow_factory import Flow, Node, load_flow, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.flows import flow_summaries

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


@pytest.fixture(autouse=True)
def not_the_first_run(monkeypatch):
    monkeypatch.setattr("workflow_factory.api.seen_before", lambda data_dir: True)


@contextmanager
def editor(tmp_path, desktop=None):
    """A page on the built editor: (page, apps) where apps lists every app the server asked a desktop for."""
    from playwright.sync_api import sync_playwright

    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta")])
    apps = []
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: apps.append(app) or desktop,
                       token="e2e-token", web_dir=DIST, schedule_runner=FakeScheduler())
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.set_default_timeout(8_000)
            yield page, apps
            browser.close()
    finally:
        server.stop()


def flows(tmp_path):
    return {f["id"]: (f["title"], f["app"]) for f in flow_summaries(tmp_path / "user.db", None)}


def steps_of_two_apps(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("open-menu", "Alpha", app="word.exe"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))


def save(page):
    page.get_by_test_id("save").click()
    page.get_by_test_id("run-status").filter(has_text=re.compile("^Saved$")).wait_for()


def open_flow(page, flow_id):
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id(f"flow-{flow_id}").click()
    page.locator('.react-flow__node[data-id="a"]').wait_for()


def new_flow(page):
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("new-flow").click()


def test_a_flow_takes_any_words_as_its_name_and_keeps_its_app_after_a_reload_and_a_run(tmp_path):
    steps_of_two_apps(tmp_path)
    with editor(tmp_path) as (page, apps):
        page.get_by_test_id("palette-open-menu").first.click()
        assert page.get_by_test_id("flow-title").input_value() == "My flow"
        page.get_by_test_id("flow-title").fill("Morning report: ¿ventas? 50% / week #1")
        page.get_by_test_id("app-name").select_option("word.exe")
        save(page)
        assert flows(tmp_path) == {"morning-report-ventas-50-week-1": ("Morning report: ¿ventas? 50% / week #1", "word.exe")}

        page.reload()
        page.locator(".react-flow__node").first.wait_for()
        assert page.get_by_test_id("flow-title").input_value() == "Morning report: ¿ventas? 50% / week #1"
        assert page.get_by_test_id("app-name").input_value() == "word.exe"
        page.get_by_test_id("open-flows").click()
        entry = page.get_by_test_id("flow-morning-report-ventas-50-week-1")
        entry.filter(has_text="Morning report: ¿ventas? 50% / week #1").wait_for()
        page.keyboard.press("Escape")

        apps.clear()
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for()
        assert apps and set(apps) == {"word.exe"}

        page.get_by_test_id("flow-title").fill("Evening report")  # a rename keeps the flow, its history and its app
        page.get_by_test_id("app-name").select_option("paint.exe")
        page.get_by_test_id("run-status").filter(has_text="Unsaved changes").wait_for()
        save(page)
        assert flows(tmp_path) == {"morning-report-ventas-50-week-1": ("Evening report", "paint.exe")}


def test_a_flow_saved_before_names_opens_under_its_identifier_with_the_app_of_its_steps(tmp_path):
    steps_of_two_apps(tmp_path)
    save_step(tmp_path / "user.db", step("close", "Alpha", app="word.exe"))
    save_flow(tmp_path / "user.db", Flow(id="old-one", nodes=[Node("a", "open-menu"), Node("b", "close")]))
    with editor(tmp_path) as (page, apps):
        open_flow(page, "old-one")

        assert page.get_by_test_id("flow-title").input_value() == "old-one"
        assert page.get_by_test_id("app-name").input_value() == "word.exe"
        page.get_by_test_id("run-status").filter(has_text=re.compile("^Saved$")).wait_for()


def test_an_app_remembered_in_another_spelling_is_the_taught_one_and_is_listed_once(tmp_path):
    steps_of_two_apps(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="old-one", nodes=[Node("a", "open-menu")]), "Morning", "Word")
    with editor(tmp_path) as (page, apps):
        open_flow(page, "old-one")
        chooser = page.get_by_test_id("app-name")
        assert chooser.input_value() == "word.exe"
        assert chooser.locator("option").all_inner_texts() == ["Paint", "Word"]
        page.get_by_test_id("run-status").filter(has_text=re.compile("^Saved$")).wait_for()
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for()
        assert set(apps) == {"word.exe"}

        page.get_by_test_id("tab-schedules").click()
        page.get_by_test_id("schedule-flow").select_option("old-one")
        scheduled = page.get_by_test_id("schedule-app")
        page.wait_for_function("() => document.querySelector('[data-testid=schedule-app]').value === 'word.exe'")
        assert scheduled.locator("option").all_inner_texts() == ["Paint", "Word"]


def test_a_flow_opened_before_the_steps_arrive_has_nothing_unsaved_once_they_do(tmp_path):
    steps_of_two_apps(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="old-one", nodes=[Node("a", "open-menu")]), "Morning", "Word")
    with editor(tmp_path) as (page, _):
        held = []
        page.route("**/api/steps", lambda route: held.append(route))  # the steps are slow to come
        page.reload()
        open_flow(page, "old-one")
        for route in held:
            route.continue_()

        page.wait_for_function("() => document.querySelector('[data-testid=app-name]').value === 'word.exe'")
        assert page.get_by_test_id("run-status").inner_text() == "Saved"


def test_two_flows_with_the_same_name_stay_two_flows_and_can_be_told_apart(tmp_path):
    steps_of_two_apps(tmp_path)
    with editor(tmp_path) as (page, _):
        asked = []
        page.on("dialog", lambda dialog: (asked.append(dialog.message), dialog.dismiss()))
        page.get_by_test_id("palette-open-menu").first.click()
        page.get_by_test_id("flow-title").fill("Morning")
        save(page)
        new_flow(page)
        page.get_by_test_id("palette-save-file").click()
        page.get_by_test_id("flow-title").fill("Morning")
        save(page)

        assert [n.step for n in load_flow(tmp_path / "user.db", None, "morning").nodes] == ["open-menu"]
        assert [n.step for n in load_flow(tmp_path / "user.db", None, "morning-2").nodes] == ["save-file"]
        assert asked == []
        page.get_by_test_id("open-flows").click()
        for flow_id in ("morning", "morning-2"):
            page.get_by_test_id(f"flow-{flow_id}").filter(has_text=f"Morning ({flow_id})").wait_for()
        page.get_by_test_id("new-flow").click()
        page.get_by_test_id("flow-title").fill("My flow")
        page.get_by_test_id("palette-save-file").click()
        save(page)
        page.get_by_test_id("open-flows").click()
        page.get_by_test_id("flow-my-flow").wait_for()  # the list is read again after a save
        page.get_by_test_id("new-flow").click()
        assert page.get_by_test_id("flow-title").input_value() == "My flow 2"  # a new flow starts with a free name


def test_a_blank_name_is_refused_in_words_and_a_change_made_elsewhere_is_never_replaced_unasked(tmp_path):
    steps_of_two_apps(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="old-one", nodes=[Node("a", "open-menu")]), "Morning")
    with editor(tmp_path) as (page, _):
        accept, asked = {"now": False}, []
        page.on("dialog", lambda d: (asked.append(d.message), d.accept() if accept["now"] else d.dismiss()))
        open_flow(page, "old-one")
        page.get_by_test_id("flow-title").fill("   ")
        page.get_by_test_id("save").click()
        assert "name" in page.get_by_test_id("error").inner_text().lower()
        assert flows(tmp_path)["old-one"][0] == "Morning"

        save_flow(tmp_path / "user.db", Flow(id="old-one", nodes=[Node("a", "save-file")]), "Renamed elsewhere")
        page.get_by_test_id("flow-title").fill("Mine")
        page.get_by_test_id("save").click()
        page.wait_for_timeout(600)
        assert "'Renamed elsewhere' was changed" in asked[-1] and flows(tmp_path)["old-one"][0] == "Renamed elsewhere"
        accept["now"] = True
        save(page)
        assert flows(tmp_path)["old-one"][0] == "Mine"
        assert [n.step for n in load_flow(tmp_path / "user.db", None, "old-one").nodes] == ["open-menu"]


def test_a_box_of_a_flow_never_saved_can_be_tested(tmp_path):
    steps_of_two_apps(tmp_path)
    with editor(tmp_path) as (page, apps):
        page.get_by_test_id("palette-open-menu").first.click()
        page.get_by_test_id("app-name").select_option("paint.exe")
        page.locator('.react-flow__node[data-id="n1"]').dblclick()
        page.get_by_test_id("test-node").click()
        page.get_by_test_id("confirm-test").click()
        page.get_by_test_id("test-result").filter(has_text=re.compile("worked|passed|finished", re.IGNORECASE)).wait_for()

        assert list(flows(tmp_path)) == ["my-flow"] and set(apps) == {"paint.exe"}


def stopped_flow(tmp_path, flow_id="m-1", title="Morning sales report"):
    """A stored flow that stopped once: it leaves a history row and an open question."""
    steps_of_two_apps(tmp_path)
    flow = Flow(id=flow_id, nodes=[Node("a", "open-menu"), Node("b", "save-file")])
    save_flow(tmp_path / "user.db", flow, title, "paint.exe")
    run_flow(flow, desktop=FakeDesktop(controls=[button("Alpha")]), user_db=tmp_path / "user.db")


def test_the_history_the_tutor_queue_and_the_schedules_show_the_name(tmp_path):
    stopped_flow(tmp_path)
    with editor(tmp_path) as (page, _):
        asked = []
        page.on("dialog", lambda dialog: (asked.append(dialog.message), dialog.accept()))
        for tab, row in (("history", "run-1"), ("queue", "doubt-1")):
            page.get_by_test_id(f"tab-{tab}").click()
            page.get_by_test_id(row).filter(has_text="Morning sales report").wait_for()
            assert "m-1" not in page.get_by_test_id(row).inner_text()

        page.get_by_test_id("tab-schedules").click()
        page.get_by_test_id("schedule-flow").select_option(label="Morning sales report")
        page.wait_for_function("() => document.querySelector('[data-testid=schedule-app]').value === 'paint.exe'")
        page.get_by_test_id("schedule-add").click()
        row = page.get_by_test_id("schedule-row-m-1 daily 0900")
        row.filter(has_text="Morning sales report").wait_for()
        assert "m-1" not in row.inner_text()
        page.get_by_test_id("announce").filter(has_text="'Morning sales report' will run").wait_for()
        remove = page.get_by_role("button", name="Remove the daily run of Morning sales report at 09:00")
        remove.click()
        page.get_by_test_id("no-schedules").wait_for()
        assert "'Morning sales report'" in asked[-1]


def test_a_flow_running_elsewhere_is_named_by_its_name(tmp_path):
    steps_of_two_apps(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="m-1", nodes=[Node("a", "open-menu"), Node("b", "save-file")]),
              "Morning sales report", "paint.exe")
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.5
    with editor(tmp_path, desktop) as (page, _):
        open_flow(page, "m-1")
        page.get_by_test_id("run").click()
        page.get_by_test_id("stop").wait_for()
        new_flow(page)
        page.get_by_test_id("running-elsewhere").filter(has_text="Morning sales report is running").wait_for()


def test_naming_saving_and_reopening_work_with_the_keyboard_alone(tmp_path):
    steps_of_two_apps(tmp_path)
    with editor(tmp_path) as (page, _):
        page.get_by_test_id("palette-open-menu").first.press("Enter")
        page.get_by_role("textbox", name="Flow name").press("ControlOrMeta+a")
        page.keyboard.type("Typed by hand")
        page.get_by_test_id("save").press("Enter")
        page.get_by_test_id("run-status").filter(has_text=re.compile("^Saved$")).wait_for()
        new_flow(page)
        page.get_by_test_id("open-flows").press("Enter")
        page.get_by_role("button", name="Typed by hand").press("Enter")
        page.locator('.react-flow__node[data-id="n1"]').wait_for()
        assert page.get_by_test_id("flow-title").input_value() == "Typed by hand"


@pytest.mark.parametrize("width,height", [(1280, 800), (683, 384), (390, 740)])
def test_long_names_fit_a_narrow_window_and_stay_readable(tmp_path, width, height):
    long = "Weekly-report-" + "x" * 80
    stopped_flow(tmp_path, "long-1", long)
    save_flow(tmp_path / "user.db", Flow(id="long-2", nodes=[Node("a", "open-menu")]), long)

    def fits(locator):
        box = locator.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width, (locator, box)

    def no_sideways_scroll():
        assert page.evaluate("() => [document.documentElement, document.querySelector('main')]"
                             ".every((el) => el.scrollWidth <= el.clientWidth)")
        assert page.evaluate(CONTRAST) == []

    with editor(tmp_path) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        open_flow(page, "long-1")
        for test_id in ("flow-title", "app-name", "open-flows", "save", "run"):
            fits(page.get_by_test_id(test_id))
        no_sideways_scroll()
        page.get_by_test_id("open-flows").click()
        for test_id in ("new-flow", "flow-long-1", "flow-long-2"):
            fits(page.get_by_test_id(test_id))
        mark = page.get_by_test_id("flow-long-1").locator("small").bounding_box()
        assert mark["height"] < 24, "the word beside a long name stays on one line"
        no_sideways_scroll()
        page.keyboard.press("Escape")

        page.get_by_test_id("tab-history").click()
        page.get_by_test_id("run-1").filter(has_text=long).wait_for()
        no_sideways_scroll()
        page.get_by_test_id("tab-queue").click()
        page.get_by_test_id("doubt-1").filter(has_text=long).wait_for()
        no_sideways_scroll()
        page.get_by_test_id("tab-schedules").click()
        page.get_by_test_id("schedule-flow").select_option("long-1")
        page.wait_for_function("() => !document.querySelector('[data-testid=schedule-add]').disabled")
        page.get_by_test_id("schedule-add").click()
        page.get_by_test_id("schedule-row-long-1 daily 0900").filter(has_text=long).wait_for()
        for test_id in ("schedule-flow", "schedule-app", "schedule-add", "schedule-remove-long-1 daily 0900"):
            fits(page.get_by_test_id(test_id))
        no_sideways_scroll()
