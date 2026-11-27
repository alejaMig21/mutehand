"""Editor rethink, ticket 13: only Home, Apps and the flow screen remain. Each ability of the six old screens (Steps, Tutor
queue, Run history, Schedules, Consents, Setup check) is proven where it lives now, and the program can be closed from
the navigation. Driven in the built editor against the real API with the stand-in desktop and Windows scheduler.
Opt-in: `pytest -m web`."""

import re
import time
from contextlib import contextmanager

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_canvas_e2e import stub_clipboard
from test_editor_e2e import DIST, open_page
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import NO_SIDEWAYS_SCROLL, at_home, chore, chores, on_the_flow_screen, row, run_button, says, tab_to

from workflow_factory import Sensitivity, grant_consent, reject_step, run_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.consent import consents
from workflow_factory.queue import list_doubts
from workflow_factory.steps import list_steps, step_report

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web

MISSING = {"id": "agent-desktop", "title": "Desktop control (agent-desktop)", "why": "It is how the apprentice sees and acts on apps.",
           "ok": False, "fix": "Install it with npm: npm install -g agent-desktop", "optional": False}
TASK = "\\Workflow factory - morning daily "


@contextmanager
def served(tmp_path, desktop=None, width=None):
    """(page, server, scheduler, desktop) on Home of the built editor."""
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
            if width:
                page.set_viewport_size({"width": width, "height": 800})
            yield page, server, scheduler, desktop
            browser.close()
    finally:
        server.stop()


def state_of(db, name):
    return step_report(db, next(s for s in list_steps(db, None) if s.name == name))["state"]


def a_stopped_chore(tmp_path):
    """"weekly" stopped at its second box: a doubt and a history row are left."""
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_step(db, step("close-message", "Missing"))
    flow = chore(tmp_path, "weekly", "Weekly export", "open-menu", "close-message")
    run_flow(flow, desktop=FakeDesktop(controls=[button("Alpha")]), user_db=db)
    return db


# --- navigation -----------------------------------------------------------------------------------------------------

def test_the_navigation_is_home_apps_and_close_the_program_and_none_of_the_old_screens_is_reachable(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        at_home(page)
        shown = page.locator("nav[aria-label=screens] button:visible, nav[aria-label=screens] summary")
        names = [b.inner_text().strip() for b in shown.all()]
        assert names == ["Home", "Apps", "More"]  # closing the program is inside More
        page.get_by_test_id("app-more-toggle").click()
        assert page.get_by_test_id("quit").inner_text().strip() == "Close the program"
        page.get_by_test_id("app-more-toggle").click()
        for old in ("library", "queue", "history", "schedules", "consents", "checks", "editor"):
            assert page.get_by_test_id(f"tab-{old}").count() == 0
        page.get_by_test_id("open-chore-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        assert page.get_by_test_id("tab-home").get_attribute("aria-current") == "page"  # the flow screen belongs to Home
        page.reload()  # a reload brings back the flow screen with the same chore
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("back-home").click()
        at_home(page)


def test_a_screen_title_names_only_home_or_apps(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        at_home(page)
        assert page.title() == "Home · Workflow Factory"
        page.get_by_test_id("tab-apps").click()
        page.wait_for_function("() => document.title.startsWith('Apps')")
        assert page.get_by_test_id("tab-apps").get_attribute("aria-current") == "page"


@pytest.mark.parametrize("width", [683, 390])
def test_the_navigation_fits_a_narrow_window_is_readable_and_works_from_the_keyboard(tmp_path, width):
    chores(tmp_path)
    with served(tmp_path, width=width) as (page, _, _, _):
        at_home(page)
        assert page.evaluate(NO_SIDEWAYS_SCROLL) and page.evaluate(CONTRAST) == []
        page.get_by_test_id("app-more-toggle").click()
        for test_id in ("tab-home", "tab-apps", "app-more-toggle", "quit"):
            box = page.get_by_test_id(test_id).bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width and box["height"] >= 44, test_id
        tab_to(page, "tab-apps")
        page.keyboard.press("Enter")
        page.get_by_role("heading", name="Programs it knows").wait_for()
        assert page.evaluate(NO_SIDEWAYS_SCROLL)


# --- close the program ----------------------------------------------------------------------------------------------

def test_closing_with_nothing_to_lose_does_not_ask_and_the_closed_page_says_how_to_open_it_again(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, server, _, _):
        asked = []
        page.on("dialog", lambda dialog: (asked.append(dialog.message), dialog.dismiss()))
        at_home(page)
        assert not page.get_by_test_id("quit").is_visible()  # it is not at hand: a tap near the tabs cannot reach it
        tab_to(page, "app-more-toggle")
        page.keyboard.press("Enter")
        assert "uv run workflow-factory" in page.get_by_test_id("quit").get_attribute("title")  # the control says it too

        tab_to(page, "quit")
        page.keyboard.press("Enter")

        closed = page.get_by_test_id("closed")
        closed.wait_for()
        assert asked == [] and server.quit_requested.is_set()
        assert "uv run workflow-factory" in closed.inner_text()


def test_closing_while_a_chore_runs_asks_first_says_what_is_lost_and_how_to_open_it_again(tmp_path):
    chores(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.5
    with served(tmp_path, desktop) as (page, server, _, _):
        asked, accept = [], {"now": False}
        page.on("dialog", lambda d: (asked.append(d.message), d.accept() if accept["now"] else d.dismiss()))
        run_button(page, "morning").click()
        page.get_by_test_id("run-now-morning").filter(has_text="Stop").wait_for()

        page.get_by_test_id("app-more-toggle").click()
        page.get_by_test_id("quit").click()
        page.wait_for_timeout(400)
        assert len(asked) == 1 and not server.quit_requested.is_set()  # asked, and "cancel" changed nothing
        assert "running will be stopped" in asked[0] and "uv run workflow-factory" in asked[0]

        accept["now"] = True
        page.get_by_test_id("quit").click()  # the menu is still open after a cancelled close
        page.get_by_test_id("closed").wait_for()
        assert server.quit_requested.is_set()


def test_closing_with_a_change_that_is_not_kept_asks_first(tmp_path):
    from workflow_factory import build_factory

    build_factory(tmp_path / "factory.db", {"version": 1, "steps": [], "flows": [
        {"id": "template", "nodes": [{"id": "n1", "step": "open-menu"}], "edges": None}]})
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    with served(tmp_path) as (page, server, _, _):
        asked = []
        page.on("dialog", lambda d: (asked.append(d.message), d.dismiss()))
        page.get_by_test_id("open-chore-template").click()  # a built-in template cannot be kept as it is edited
        page.locator('.react-flow__node[data-id="n1"]').wait_for()
        page.get_by_test_id("search").fill("wait")
        page.get_by_test_id("system-wait").click()
        page.get_by_test_id("run-status").filter(has_text="Not kept").wait_for()

        page.get_by_test_id("app-more-toggle").click()
        page.get_by_test_id("quit").click()

        page.wait_for_timeout(300)
        assert len(asked) == 1 and "not saved" in asked[0] and not server.quit_requested.is_set()


# --- Steps: the actions of an app, what is wrong with them, Allow again -----------------------------------------------

def test_the_actions_of_an_app_are_listed_by_name_and_a_rejected_one_says_why_and_is_allowed_again_from_apps_and_home(tmp_path):
    db = tmp_path / "user.db"
    chores(tmp_path)
    save_step(db, step("factory-only", "Gamma", origin="factory"))
    reject_step(db, "paint.exe", "save-file")  # the person rejected it themselves
    with served(tmp_path) as (page, _, _, _):
        says(page, "morning", "Cannot run yet")
        page.get_by_test_id("attention-allow-again-paint.exe-save-file").wait_for()  # Home: the chore it blocks
        page.get_by_test_id("tab-apps").click()
        page.get_by_test_id("app-row-paint.exe").click()
        card = page.get_by_test_id("app-card-paint.exe")
        card.get_by_test_id("app-problem-save-file").wait_for()
        assert "3 actions" in card.inner_text()
        assert {"open-menu", "factory-only"} <= {a.inner_text() for a in card.locator("[data-testid^=app-action-]").all()}
        assert "You rejected it." in card.get_by_test_id("app-problem-save-file").inner_text()

        card.get_by_test_id("app-allow-again-save-file").click()

        card.get_by_test_id("app-problem-save-file").wait_for(state="detached")
        assert state_of(db, "save-file") != "rejected"
        page.get_by_test_id("tab-home").click()
        says(page, "morning", "Never run")


# --- Consents: what it may do, taking it back ------------------------------------------------------------------------

def test_a_permission_is_listed_in_its_app_taken_back_after_asking_and_never_granted_there(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Send it", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(db, "mail.exe", "Send", "click")
    with served(tmp_path) as (page, _, _, _):
        page.get_by_test_id("tab-apps").click()
        page.get_by_test_id("app-row-mail.exe").click()
        card = page.get_by_test_id("app-card-mail.exe")
        permission = card.get_by_test_id("app-permission-Send-click")
        assert "Press “Send”" in permission.inner_text()
        assert page.get_by_role("button", name=re.compile("Grant|Allow always", re.I)).count() == 0  # taking back only

        permission.get_by_role("button", name="Take back").click()
        card.get_by_test_id("take-back-ask").wait_for()
        assert len(consents(db)) == 1  # asking changed nothing
        card.get_by_test_id("take-back-yes").click()

        permission.wait_for(state="detached")
        assert consents(db) == []


# --- Tutor queue: why a chore stopped, a note for the helper, nothing dismissed -------------------------------------

def test_a_stopped_chore_names_its_box_and_reason_keeps_the_persons_note_on_the_doubt_and_offers_no_dismiss(tmp_path):
    db = a_stopped_chore(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        stub_clipboard(page)
        card = page.get_by_test_id("attention-weekly")
        card.wait_for()
        text = card.inner_text()
        assert "“Weekly export” stopped" in text and "“close-message”" in text and "not on the screen" in text
        assert "_" not in text.replace("close-message", "")  # words, never codes

        card.get_by_test_id("attention-ask-help-weekly").click()
        card.get_by_test_id("attention-note-weekly").fill("the button is called Main menu now")
        card.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()

        [doubt] = list_doubts(db)
        assert doubt.status == "open" and doubt.note == "the button is called Main menu now"  # it stays open, for the tutor
        words = " ".join(b.inner_text() for b in page.get_by_role("button").all()).lower()
        assert "dismiss" not in words and "save answer" not in words


def test_a_half_typed_note_survives_leaving_home_and_a_reload_until_it_is_kept(tmp_path):
    db = a_stopped_chore(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        stub_clipboard(page)
        card = page.get_by_test_id("attention-weekly")
        card.get_by_test_id("attention-ask-help-weekly").click()
        card.get_by_test_id("attention-note-weekly").fill("half an answer")

        page.get_by_test_id("tab-apps").click()
        page.get_by_role("heading", name="Programs it knows").wait_for()
        page.get_by_test_id("tab-home").click()
        card.get_by_test_id("attention-ask-help-weekly").click()
        assert card.get_by_test_id("attention-note-weekly").input_value() == "half an answer"

        page.reload()
        card.get_by_test_id("attention-ask-help-weekly").click()
        assert card.get_by_test_id("attention-note-weekly").input_value() == "half an answer"
        assert list_doubts(db)[0].note is None  # nothing was sent anywhere: it is only remembered on this screen


# --- Run history: in each chore -------------------------------------------------------------------------------------

def test_the_history_of_a_chore_is_read_where_the_chore_is_with_what_stopped_it(tmp_path):
    a_stopped_chore(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        row(page, "weekly").wait_for()
        page.get_by_test_id("more-weekly").click()
        page.get_by_test_id("more-history-weekly").click()
        run = page.locator('[data-testid^="history-run-"]').first
        run.wait_for()
        text = run.inner_text()
        assert text.startswith("Stopped") and "open-menu: done" in text and "close-message: stopped" in text
        assert page.get_by_test_id("tab-history").count() == 0


# --- Schedules: add, see, change, stop, other tasks stay hidden -------------------------------------------------------

def test_a_daily_run_is_added_seen_and_stopped_on_the_chore_and_no_other_task_is_shown_or_touched(tmp_path):
    chores(tmp_path)
    with served(tmp_path) as (page, _, scheduler, _):
        at_home(page)
        assert "Run every day" in page.get_by_test_id("daily-morning").inner_text()
        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-time-morning").fill("07:45")
        page.get_by_test_id("daily-set-morning").click()

        page.get_by_test_id("daily-morning").filter(has_text="Every day at 7:45 AM").wait_for()
        created = next(task for name, task in scheduler.tasks.items() if name != FOREIGN)
        assert "--app paint.exe" in created["arguments"]  # it runs on the app the chore remembers
        assert "Defrag" not in page.locator("body").inner_text()

        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-stop-morning").click()
        page.get_by_test_id("daily-morning").filter(has_text="Run every day").wait_for()
        assert list(scheduler.tasks) == [FOREIGN]


# --- Setup check: only when something is missing --------------------------------------------------------------------

def test_a_missing_piece_of_setup_is_a_card_with_its_fix_on_home_and_nothing_jumps_to_another_screen(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [MISSING])
    chores(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        card = page.get_by_test_id("attention-setup-agent-desktop")
        card.wait_for()
        assert "Desktop control (agent-desktop): missing" in card.inner_text()
        assert "To fix: Install it with npm" in card.inner_text()
        page.reload()
        card.wait_for()
        at_home(page)  # still Home, as before: a reload never lands on a screen of its own
        assert page.get_by_test_id("tab-checks").count() == 0


def test_a_working_setup_raises_nothing_and_an_optional_gap_is_not_shown(tmp_path, monkeypatch):
    monkeypatch.setattr("workflow_factory.attention.run_checks",
                        lambda data_dir: [{**MISSING, "ok": True, "fix": None}, {**MISSING, "id": "second-monitor", "optional": True}])
    chores(tmp_path)
    with served(tmp_path) as (page, _, _, _):
        says(page, "morning", "Never run")
        page.wait_for_timeout(400)
        assert page.get_by_test_id("attention").count() == 0


# --- A paused run says why wherever it is shown ---------------------------------------------------------------------

def a_run_that_waits_for_the_person():
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 0.5
    desktop.on_action = [desktop.user_acts]
    desktop.on_sleep = [lambda: time.sleep(4)]  # the fake clock's wait takes real time, long enough to be seen on a loaded machine
    return desktop


def test_a_paused_run_says_why_on_the_flow_screen_on_its_box_and_when_it_is_seen_from_another_chore(tmp_path):
    chores(tmp_path)
    chore(tmp_path, "evening", "Evening report", "open-menu")
    with served(tmp_path, a_run_that_waits_for_the_person()) as (page, _, _, _):
        run_button(page, "morning").click()
        says(page, "morning", "Paused: you moved the mouse")  # Home

        page.get_by_test_id("open-chore-evening").click()  # the other chore: the paused one is seen from here
        elsewhere = page.get_by_test_id("running-elsewhere")
        elsewhere.wait_for()
        assert "Paused: you moved the mouse" in elsewhere.inner_text()

        elsewhere.get_by_role("button", name="Show it").click()
        page.get_by_test_id("paused").wait_for()
        assert "you moved the mouse" in page.get_by_test_id("paused").inner_text()
        assert "Paused: you moved the mouse" in page.locator('[data-testid^="node-"]').filter(has_text="Paused").first.inner_text()
