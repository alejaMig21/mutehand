"""A chore's "More": rename it, delete it with an undo, read its history. Driven in the built editor. Opt-in: `pytest -m web`."""

import re
import sqlite3
from contextlib import closing, contextmanager

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_editor_e2e import DIST, open_page
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import BUTTONS, NO_SIDEWAYS_SCROLL, chore, chores, row, run_button, says

from workflow_factory import Flow, Node, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.queue import save_checkpoint

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web
FOCUSED = "() => document.activeElement.dataset.testid"


@pytest.fixture(autouse=True)
def not_the_first_run(monkeypatch):
    monkeypatch.setattr("workflow_factory.api.seen_before", lambda data_dir: True)


@contextmanager
def served(tmp_path, desktop=None):
    """(page, desktop, scheduler) on Home, with the stand-in desktop and the stand-in Windows scheduler."""
    from playwright.sync_api import sync_playwright

    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta")])
    scheduler = FakeScheduler()
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop, token="e2e-token",
                       web_dir=DIST, schedule_runner=scheduler)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server, screen=None)
            page.set_default_timeout(8_000)
            yield page, desktop, scheduler
            browser.close()
    finally:
        server.stop()


def more(page, flow_id):
    page.get_by_test_id(f"more-{flow_id}").click()
    page.get_by_test_id(f"more-rename-{flow_id}").wait_for()


def daily(scheduler, flow_id="morning", at="09:30"):
    exe = "C:\\py\\pythonw.exe"
    scheduler.tasks[f"\\Workflow factory - {flow_id} daily {at.replace(':', '')}"] = {
        "command": exe, "arguments": f"-m workflow_factory.workday --flow {flow_id} --app paint.exe --fired daily", "at": at}


def ours(scheduler):
    return [name for name in scheduler.tasks if name != FOREIGN]


def test_more_opens_and_closes_from_the_keyboard_and_the_focus_returns(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, _):
        says(page, "morning", "Never run")
        page.get_by_test_id("more-morning").focus()
        assert page.get_by_test_id("more-morning").get_attribute("aria-expanded") == "false"
        page.keyboard.press("Enter")
        page.get_by_test_id("more-rename-morning").wait_for()
        assert page.get_by_test_id("more-morning").get_attribute("aria-expanded") == "true"
        page.keyboard.press("Tab")
        assert page.evaluate(FOCUSED) == "more-rename-morning"
        page.keyboard.press("Escape")
        page.get_by_test_id("more-rename-morning").wait_for(state="detached")
        assert page.evaluate(FOCUSED) == "more-morning"


def test_renaming_by_keyboard_changes_the_title_only(tmp_path):
    db = tmp_path / "user.db"
    morning = chores(tmp_path)
    run_flow(morning, FakeDesktop(controls=[button("Alpha"), button("Beta")]), db)
    save_checkpoint(db, "morning", {"done": []}, "definition")
    with served(tmp_path) as (page, _, scheduler):
        daily(scheduler)
        says(page, "morning", "Worked")
        more(page, "morning")
        page.get_by_test_id("more-rename-morning").press("Enter")
        field = page.get_by_test_id("rename-input-morning")
        assert page.evaluate(FOCUSED) == "rename-input-morning" and field.input_value() == "Morning report"
        field.fill("Evening: ¿sales?  report")
        field.press("Enter")

        says(page, "morning", "Evening: ¿sales\\? report")
        says(page, "morning", "Worked")  # its history stays with it
        assert page.evaluate(FOCUSED) == "more-morning"
        assert ours(scheduler) == ["\\Workflow factory - morning daily 0930"]
        with closing(sqlite3.connect(db)) as con:
            assert con.execute("SELECT count(*) FROM checkpoints WHERE flow_id = 'morning'").fetchone() == (1,)
            assert con.execute("SELECT count(*) FROM run_history WHERE flow_id = 'morning'").fetchone() == (1,)


def test_a_name_that_cannot_be_kept_is_said_in_words_and_escape_leaves_the_old_one(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, _):
        more(page, "morning")
        page.get_by_test_id("more-rename-morning").click()
        field = page.get_by_test_id("rename-input-morning")
        field.fill("   ")
        field.press("Enter")
        page.get_by_role("alert").filter(has_text="needs 1 to 100 characters").wait_for()
        assert "Morning report" in row(page, "morning").inner_text()
        field.fill("Another")
        field.press("Escape")
        page.get_by_test_id("rename-input-morning").wait_for(state="detached")
        assert "Morning report" in row(page, "morning").inner_text() and page.evaluate(FOCUSED) == "more-rename-morning"


def test_deleting_removes_the_chore_and_its_daily_run_and_undo_brings_both_back(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, scheduler):
        daily(scheduler)
        says(page, "morning", "Never run")
        more(page, "morning")
        page.get_by_test_id("more-delete-morning").click()

        notice = page.get_by_test_id("deleted-notice")
        notice.wait_for()
        assert "Morning report" in notice.inner_text() and "daily run" in notice.inner_text()
        page.get_by_test_id("chore-morning").wait_for(state="detached")
        assert ours(scheduler) == []
        assert page.evaluate(FOCUSED) == "undo-delete"  # the row that had the focus is gone

        page.keyboard.press("Enter")
        says(page, "morning", "Morning report")
        assert page.get_by_test_id("deleted-notice").count() == 0
        assert ours(scheduler) == ["\\Workflow factory - morning daily 0930"]
        assert page.evaluate(FOCUSED) == "open-chore-morning"


def test_a_running_chore_cannot_be_deleted_until_it_is_stopped(tmp_path):
    chores(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.5
    with served(tmp_path, desktop) as (page, _, scheduler):
        daily(scheduler)
        run_button(page, "morning").click()
        says(page, "morning", "Running now")
        more(page, "morning")
        page.get_by_test_id("more-delete-morning").click()

        page.get_by_role("alert").filter(has_text="Stop it first").wait_for()
        assert page.get_by_test_id("chore-morning").count() == 1 and len(ours(scheduler)) == 1
        assert page.get_by_test_id("deleted-notice").count() == 0

        run_button(page, "morning").filter(has_text="Stop").click()
        says(page, "morning", "You stopped it")
        page.get_by_test_id("more-delete-morning").click()
        page.get_by_test_id("deleted-notice").wait_for()
        page.get_by_test_id("chore-morning").wait_for(state="detached")
        assert ours(scheduler) == []


def test_history_reads_newest_first_in_plain_words_with_box_names_after_the_flow_changed(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_step(db, step("save-file", "Missing"))
    first = Flow(id="morning", nodes=[Node("n1", "open-menu"), Node("n2", kind="wait", fields={"seconds": {"value": 1}})])
    run_flow(first, FakeDesktop(controls=[button("Alpha")]), db)
    # the flow is rebuilt: n2 is now another box, and the old run must still say what it ran
    second = Flow(id="morning", nodes=[Node("n1", "open-menu"), Node("n2", "save-file")])
    save_flow(db, second, "Morning report", "paint.exe")
    run_flow(second, FakeDesktop(controls=[button("Alpha")]), db)

    with served(tmp_path) as (page, _, _):
        says(page, "morning", "Stopped")
        more(page, "morning")
        page.get_by_test_id("more-history-morning").click()
        runs = page.locator('[data-testid^="history-run-"]')
        runs.nth(1).wait_for()
        assert runs.count() == 2
        newest, oldest = runs.nth(0).inner_text(), runs.nth(1).inner_text()
        assert re.search(r"Stopped .+ at \d\d:\d\d", newest) and "save-file" in newest and "stopped" in newest
        assert "The button or field this step uses is not on the screen." in newest
        assert re.search(r"Worked .+ at \d\d:\d\d", oldest) and "Wait a while: done" in oldest and "open-menu: done" in oldest
        assert "save-file" not in oldest and ".exe" not in newest + oldest and "Alpha" not in newest + oldest
        page.get_by_test_id("more-history-morning").click()  # a second press hides it
        page.get_by_test_id("history-morning").wait_for(state="detached")


def test_a_chore_that_never_ran_says_so_in_its_history(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, _):
        more(page, "morning")
        page.get_by_test_id("more-history-morning").click()
        page.get_by_test_id("history-morning").filter(has_text="has not run yet").wait_for()


@pytest.mark.parametrize("width,height", [(1280, 800), (683, 384), (390, 740)])
def test_more_fits_a_narrow_window_and_stays_readable(tmp_path, width, height):
    db = tmp_path / "user.db"
    chores(tmp_path)
    long = "Weekly-report-" + "x" * 80
    chore(tmp_path, "long-1", long, "open-menu", "save-file")
    run_flow(Flow(id="long-1", nodes=[Node("n1", "open-menu"), Node("n2", "save-file")]), FakeDesktop(controls=[button("Alpha")]), db)

    def fine():
        assert page.evaluate(NO_SIDEWAYS_SCROLL)
        assert page.evaluate(BUTTONS, width) == []
        assert page.evaluate(CONTRAST) == []

    with served(tmp_path) as (page, _, _):
        page.set_viewport_size({"width": width, "height": height})
        says(page, "long-1", "Stopped")
        more(page, "long-1")
        fine()
        page.get_by_test_id("more-rename-long-1").click()
        page.get_by_test_id("rename-input-long-1").wait_for()
        fine()
        page.get_by_test_id("rename-input-long-1").press("Escape")
        page.get_by_test_id("more-history-long-1").click()
        page.get_by_test_id("history-long-1").wait_for()
        fine()
        page.get_by_test_id("more-delete-long-1").click()
        page.get_by_test_id("deleted-notice").wait_for()
        fine()
        notice = page.get_by_test_id("deleted-notice").bounding_box()
        assert notice["x"] >= 0 and notice["x"] + notice["width"] <= width
