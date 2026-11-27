"""A chore's daily time, set from its row on Home or from the first box of its flow screen. Driven in the built editor
against the real API with the stand-in desktop and scheduler. Opt-in: `pytest -m web`."""

import subprocess
from contextlib import contextmanager

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_editor_e2e import DIST, open_page
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import (
    BUTTONS,
    FOCUSED,
    NO_SIDEWAYS_SCROLL,
    at_home,
    chore,
    chores,
    on_the_flow_screen,
    row,
    run_button,
    says,
    tab_to,
)

from workflow_factory import Flow, Node, load_flow, save_flow
from workflow_factory.api import ApiServer
from workflow_factory.schedule import create_schedule

from fake_desktop import FakeDesktop, button

pytestmark = pytest.mark.web

TASK = "\\Workflow factory - morning daily "


@contextmanager
def served(tmp_path, scheduler=None, desktop=None):
    """(page, scheduler, desktop) on Home of the built editor."""
    from playwright.sync_api import sync_playwright

    scheduler = scheduler or FakeScheduler()
    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop, token="e2e-token",
                       web_dir=DIST, schedule_runner=scheduler)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server, screen=None)
            page.set_default_timeout(8_000)
            yield page, scheduler, desktop
            browser.close()
    finally:
        server.stop()


def mine(scheduler):
    return sorted(name for name in scheduler.tasks if name.startswith("\\Workflow factory - "))


def set_on_home(page, flow_id, at):
    page.get_by_test_id(f"daily-{flow_id}").click()
    page.get_by_test_id(f"daily-time-{flow_id}").fill(at)
    page.get_by_test_id(f"daily-set-{flow_id}").click()


def start_box(page):
    return page.locator('.react-flow__node:has([data-testid="daily-change"])')


def test_a_time_set_on_home_makes_the_windows_task_and_shows_on_the_first_box(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        assert "Run every day" in page.get_by_test_id("daily-morning").inner_text()

        set_on_home(page, "morning", "07:30")

        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:30 AM").wait_for()
        assert mine(scheduler) == [TASK + "0730"] and FOREIGN in scheduler.tasks
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 3)  # the two boxes and the start box
        start_box(page).filter(has_text="Start: every day at 07:30").wait_for()


def test_changing_the_time_on_home_leaves_one_task_and_stopping_removes_it_and_the_first_box(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        set_on_home(page, "morning", "07:30")
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:30 AM").wait_for()

        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-time-morning").fill("08:15")
        page.get_by_test_id("daily-set-morning").click()
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 8:15 AM").wait_for()
        assert mine(scheduler) == [TASK + "0815"]

        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-stop-morning").click()
        page.get_by_test_id("daily-morning").filter(has_text="Run every day").wait_for()
        assert mine(scheduler) == [] and FOREIGN in scheduler.tasks
        flow = load_flow(tmp_path / "user.db", None, "morning")
        assert [n.id for n in flow.nodes] == ["n1", "n2"]
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 2)


def test_a_time_set_on_the_first_box_shows_on_home_and_can_be_changed_and_stopped_there(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("daily-add").wait_for()

        page.get_by_test_id("daily-add").click()
        page.get_by_test_id("daily-time").fill("06:45")
        page.get_by_test_id("daily-set").click()
        on_the_flow_screen(page, "Morning report", 3)
        page.get_by_test_id("daily-add").filter(has_text="Every day at 06:45").wait_for()  # said, not drawn
        assert start_box(page).count() == 0  # opening the chore never rewrote it
        assert mine(scheduler) == [TASK + "0645"]

        page.get_by_test_id("daily-change").click()
        page.get_by_test_id("daily-time").fill("07:10")
        page.get_by_test_id("daily-set").click()
        start_box(page).filter(has_text="Start: every day at 07:10").wait_for()
        assert mine(scheduler) == [TASK + "0710"]

        page.get_by_test_id("back-home").click()
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:10 AM").wait_for()
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 3)
        page.get_by_test_id("daily-change").click()
        page.get_by_test_id("daily-stop").click()
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("daily-add").wait_for()
        assert mine(scheduler) == []


def test_a_scheduler_that_refuses_is_explained_and_leaves_the_chore_as_it_was(tmp_path):
    chores(tmp_path)
    scheduler = FakeScheduler()

    def refusing(args, **kwargs):
        if args[1] == "/Create":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ERROR: Access is denied.")
        return scheduler(args, **kwargs)

    with served(tmp_path, scheduler=refusing) as (page, _, _):
        at_home(page)
        set_on_home(page, "morning", "07:30")

        alert = row(page, "morning").get_by_role("alert").filter(has_text="Access is denied")
        alert.wait_for()
        assert "nothing was changed" in alert.inner_text().lower()
        assert mine(scheduler) == [] and len(load_flow(tmp_path / "user.db", None, "morning").nodes) == 2
        page.get_by_test_id("daily-morning").filter(has_text="Run every day").wait_for()


def test_run_now_starts_a_chore_with_or_without_a_daily_time(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, desktop):
        at_home(page)
        run_button(page, "morning").click()
        says(page, "morning", "Worked")
        assert [c.name for c in desktop.clicks] == ["Alpha", "Beta"]

        set_on_home(page, "morning", "07:30")
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:30 AM").wait_for()
        run_button(page, "morning").click()
        page.wait_for_function("() => document.querySelector('[data-testid=run-now-morning]').innerText.includes('Run now')")
        page.wait_for_timeout(300)
        assert [c.name for c in desktop.clicks] == ["Alpha", "Beta", "Alpha", "Beta"]


def test_a_schedule_made_before_shows_on_its_chore_and_on_the_canvas_without_rewriting_it(tmp_path):
    chores(tmp_path)
    scheduler = FakeScheduler()
    # a task made by the old Schedules screen, which put no start box on the flow
    create_schedule("morning daily 0645", "morning", "paint.exe", "06:45", ["--user-db", str(tmp_path / "user.db")],
                    runner=scheduler)
    with served(tmp_path, scheduler=scheduler) as (page, _, _):
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 6:45 AM").wait_for()
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 3)
        page.get_by_test_id("daily-add").filter(has_text="Every day at 06:45").wait_for()  # said, not drawn
        assert start_box(page).count() == 0  # opening the chore never rewrote it


def test_the_daily_time_works_with_the_keyboard_alone(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        page.get_by_test_id("chore-morning").wait_for()  # the heading is there while the list still loads
        tab_to(page, "daily-morning")
        page.keyboard.press("Enter")
        assert page.evaluate(FOCUSED) == "daily-time-morning"  # the form opens with the time field ready
        page.get_by_test_id("daily-time-morning").fill("07:30")
        page.keyboard.press("Enter")  # sets it
        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:30 AM").wait_for()
        assert mine(scheduler) == [TASK + "0730"]
        page.wait_for_function("() => document.activeElement.dataset.testid === 'daily-morning'")  # focus came back
        page.keyboard.press("Enter")
        page.keyboard.press("Escape")  # closes without changing
        page.wait_for_function("() => document.activeElement.dataset.testid === 'daily-morning'")
        assert page.get_by_test_id("daily-time-morning").count() == 0
        page.keyboard.press("Enter")
        tab_to(page, "daily-stop-morning")
        page.keyboard.press("Enter")
        page.get_by_test_id("daily-morning").filter(has_text="Run every day").wait_for()
        assert mine(scheduler) == []


def test_the_first_box_daily_time_works_with_the_keyboard_alone(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        tab_to(page, "daily-add")
        page.keyboard.press("Enter")
        assert page.evaluate(FOCUSED) == "daily-time"
        page.get_by_test_id("daily-time").fill("07:30")
        page.keyboard.press("Enter")
        on_the_flow_screen(page, "Morning report", 3)
        assert mine(scheduler) == [TASK + "0730"]
        page.wait_for_function("() => document.activeElement.dataset.testid === 'daily-change'")


@pytest.mark.parametrize("width,height", [(1280, 800), (683, 384), (390, 740)])
def test_the_daily_time_fits_a_narrow_window_and_stays_readable(tmp_path, width, height):
    chores(tmp_path)
    chore(tmp_path, "long-1", "Weekly-report-" + "x" * 80, "open-menu", "save-file")

    def fine():
        assert page.evaluate(NO_SIDEWAYS_SCROLL)
        assert page.evaluate(BUTTONS, width) == []
        assert page.evaluate(CONTRAST) == []

    with served(tmp_path) as (page, _, _):
        page.set_viewport_size({"width": width, "height": height})
        at_home(page)
        fine()
        page.get_by_test_id("daily-long-1").click()
        fine()
        page.get_by_test_id("daily-time-long-1").fill("07:30")
        page.get_by_test_id("daily-set-long-1").click()
        page.get_by_test_id("daily-long-1").filter(has_text="Every day at 7:30 AM").wait_for()
        fine()
        page.get_by_test_id("daily-long-1").click()
        fine()
        page.get_by_test_id("daily-cancel-long-1").click()
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        for test_id in ("daily-add",):
            box = page.get_by_test_id(test_id).bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width and box["height"] >= 44
        page.get_by_test_id("daily-add").click()
        page.get_by_test_id("daily-set").click()
        on_the_flow_screen(page, "Morning report", 3)
        box = page.get_by_test_id("daily-change").bounding_box()  # drawn at the canvas zoom: its own height is checked
        assert box["x"] >= 0 and box["x"] + box["width"] <= width
        assert page.get_by_test_id("daily-change").evaluate("(b) => b.offsetHeight") >= 44
        page.get_by_test_id("daily-change").click()
        assert page.evaluate(CONTRAST) == []
        for test_id in ("daily-time", "daily-set", "daily-stop", "daily-cancel"):
            box = page.get_by_test_id(test_id).bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width and box["height"] >= 44, test_id


def test_a_template_chore_cannot_be_given_a_time_and_says_why(tmp_path):
    from workflow_factory import save_step

    from fake_desktop import step

    save_step(tmp_path / "factory.db", step("open-menu", "Alpha", origin="factory", factory_successes=50))
    save_flow(tmp_path / "factory.db", Flow(id="template", nodes=[Node("a", "open-menu")]), "Template", "paint.exe")
    with served(tmp_path) as (page, scheduler, _):
        at_home(page)
        set_on_home(page, "template", "07:30")
        row(page, "template").get_by_role("alert").filter(has_text="copy").wait_for()
        assert mine(scheduler) == []
