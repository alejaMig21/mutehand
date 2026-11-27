"""What the non-technical personas could not do on Home and Apps (editor rethink, ticket 14), each fixed once and kept fixed.
Driven in the built editor. Opt-in: `pytest -m web`."""

import re

import pytest
from acceptance_server import everyday, many_apps
from fake_scheduler import FakeScheduler
from test_apps_e2e import app_row, apps_screen
from test_canvas_e2e import stub_clipboard
from test_editor_e2e import DIST
from test_flow_more_e2e import more, served
from test_home_e2e import home, put_flow, put_flows, rejected, row, run_button, says

from workflow_factory import grant_consent, save_step
from workflow_factory.api import ApiServer
from workflow_factory.consent import consents
from workflow_factory.steps import revalidate_changed_versions

from fake_desktop import step

pytestmark = pytest.mark.web


# --- 1: no screen that is gone is named -------------------------------------------------------------------------------

def test_a_flow_blocked_by_a_rejected_action_points_to_the_allow_again_that_exists(tmp_path):
    put_flows(tmp_path)
    rejected(tmp_path / "user.db")
    with home(tmp_path) as (page, _):
        why = page.get_by_test_id("flow-why-stuck")
        why.wait_for()
        assert "Steps" not in why.inner_text() and "Allow again" in why.inner_text()
        page.get_by_test_id("attention").get_by_role("button", name="Allow again").wait_for()  # it is read apart from the flow
        assert page.get_by_test_id("attention").get_by_role("button", name="Allow again").count() == 1  # what the words point at


# --- 2: nothing that looks like a button does nothing -----------------------------------------------------------------

def test_the_actions_of_an_app_are_plain_labels_and_a_flow_that_cannot_run_says_why_when_pressed(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Open file", "Alpha", app="excel.exe"))
    put_flows(tmp_path)
    rejected(db)
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "excel.exe").click()
        label = page.get_by_test_id("app-step-Open file")
        look = label.evaluate(
            "(e) => { const s = getComputedStyle(e); return [s.backgroundColor, s.borderTopWidth, s.borderTopLeftRadius] }")
        assert look == ["rgba(0, 0, 0, 0)", "0px", "0px"]

        page.get_by_test_id("tab-home").click()
        run_button(page, "stuck").click(force=True)
        assert page.evaluate("() => document.activeElement.id") == "why-stuck"  # the press leads to the reason


# --- 3: permissions are always there ----------------------------------------------------------------------------------

def test_an_open_app_always_shows_its_permissions_with_a_plain_empty_state(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Open file", "Alpha", app="excel.exe"))
    save_step(db, step("Send", "Alpha", app="mail.exe"))
    grant_consent(db, "mail.exe", "Send", "click")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        assert "1 permission" in app_row(page, "mail.exe").inner_text()
        assert "permission" not in app_row(page, "excel.exe").inner_text()

        app_row(page, "excel.exe").click()
        card = page.get_by_test_id("app-card-excel.exe")
        card.get_by_test_id("app-no-permissions").wait_for()
        assert "You have not given it any permission" in card.inner_text()
        assert card.get_by_role("button", name="Take back").count() == 0

        app_row(page, "mail.exe").click()
        mail = page.get_by_test_id("app-card-mail.exe")
        mail.get_by_role("button", name="Take back").wait_for()
        assert mail.get_by_role("button", name="Take back").is_visible()
        assert "You have not given it any permission" not in mail.inner_text()


@pytest.mark.parametrize("data", [everyday, many_apps])
def test_the_persona_data_has_a_permission_to_take_back(tmp_path, data):
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: None, token="t", web_dir=DIST,
                       schedule_runner=FakeScheduler())
    data(tmp_path / "user.db", server)
    assert consents(tmp_path / "user.db")


# --- 4: the banners use the screens' words ----------------------------------------------------------------------------

def test_a_run_started_with_run_now_says_which_flow_worked_in_steps(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "evening", "Evening report", "open-menu")
    with home(tmp_path) as (page, _):
        says(page, "morning", "Never run")
        run_button(page, "morning").click()
        result = page.get_by_test_id("flow-result-morning")
        result.wait_for()
        assert re.fullmatch(r"Worked .+ at \d\d:\d\d\. 2 steps finished\.", result.inner_text().strip())
        assert "Morning report" in row(page, "morning").inner_text()
        assert page.get_by_test_id("flow-result-evening").count() == 0
        run_button(page, "evening").click()
        page.get_by_test_id("flow-result-evening").wait_for()
        assert "1 step finished." in row(page, "evening").inner_text()
        assert "node" not in page.locator("main").inner_text().lower()


# --- 5: the list stays where it is --------------------------------------------------------------------------------------

def test_allowing_again_on_home_does_not_move_the_list_and_answers_where_it_was_pressed(tmp_path):
    put_flows(tmp_path)
    rejected(tmp_path / "user.db")
    with home(tmp_path) as (page, _):
        button = page.get_by_test_id("attention").get_by_role("button", name="Allow again")
        button.wait_for()
        before = row(page, "morning").bounding_box()["y"]
        tapped = button.bounding_box()["y"]

        button.click()

        card = page.get_by_test_id("attention").get_by_text("allowed again")
        card.wait_for()
        assert abs(card.bounding_box()["y"] - tapped) < 160  # next to where the finger was
        page.wait_for_timeout(400)  # the lists are read again by now
        assert abs(row(page, "morning").bounding_box()["y"] - before) <= 2


def test_opening_an_app_keeps_the_row_pressed_where_it_was(tmp_path):
    db = tmp_path / "user.db"
    for n in range(25):
        save_step(db, step("open", "Alpha", app=f"program{n:02}.exe"))
    with home(tmp_path) as (page, _):
        apps_screen(page)
        target = app_row(page, "program08.exe")
        target.scroll_into_view_if_needed()
        page.evaluate("() => window.scrollBy(0, 40)")
        before = target.bounding_box()["y"]

        target.click()

        card = page.get_by_test_id("app-card-program08.exe")
        card.wait_for()
        assert abs(target.bounding_box()["y"] - before) <= 2
        rect = card.bounding_box()
        assert 0 <= rect["y"] < page.viewport_size["height"]  # and what it opened is in view


# --- 6: delete can always be undone ------------------------------------------------------------------------------------

def test_the_undo_notice_takes_the_place_of_the_deleted_flow_and_survives_a_reload(tmp_path):
    put_flows(tmp_path)
    for n in range(8):
        put_flow(tmp_path, f"extra-{n}", f"Extra flow {n}", "open-menu")
    with served(tmp_path) as (page, _, _):
        says(page, "extra-6", "Never run")
        page.get_by_test_id("flow-extra-6").scroll_into_view_if_needed()
        old = page.get_by_test_id("flow-extra-6").bounding_box()["y"]
        more(page, "extra-6")
        page.get_by_test_id("more-delete-extra-6").click()

        notice = page.get_by_test_id("deleted-notice")
        notice.wait_for()
        rect = notice.bounding_box()
        assert 0 <= rect["y"] and rect["y"] + rect["height"] <= page.viewport_size["height"]  # no scrolling to find it
        assert abs(rect["y"] - old) < 130  # where the flow was

        page.reload()
        notice = page.get_by_test_id("deleted-notice")
        notice.wait_for()
        assert "Extra flow 6" in notice.inner_text()
        page.get_by_test_id("undo-delete").click()
        page.get_by_test_id("flow-extra-6").wait_for()
        assert page.get_by_test_id("deleted-notice").count() == 0


# --- 7: no code is ever shown ---------------------------------------------------------------------------------------------

def test_a_pasted_wall_of_text_is_cut_and_a_refused_search_never_shows_a_code(tmp_path):
    save_step(tmp_path / "user.db", step("open", "Alpha", app="excel.exe"))
    with home(tmp_path) as (page, _):
        apps_screen(page)
        field = page.get_by_test_id("apps-search")
        field.fill("x" * 100_000)
        page.get_by_test_id("apps-search-go").click()
        page.wait_for_timeout(500)
        assert len(field.input_value()) <= 200
        assert "HTTP" not in page.locator("main").inner_text()

        page.route("**/api/apps?q=*", lambda route: route.fulfill(status=414, body=""))
        field.fill("anything")
        page.get_by_test_id("apps-search-go").click()
        error = page.get_by_test_id("load-error")
        error.wait_for()
        assert "HTTP" not in error.inner_text() and "414" not in error.inner_text()
        assert error.get_by_role("button", name="Try again").is_visible()


# --- 8: Apps on the first day -------------------------------------------------------------------------------------------

def test_apps_with_nothing_learned_says_how_to_teach_with_a_copy_button(tmp_path):
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        apps_screen(page)
        page.get_by_test_id("apps-empty").wait_for()
        page.get_by_test_id("chat-message").get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert "Claude Code" not in page.locator("main").inner_text()


# --- 9: the daily time is shown as it was typed --------------------------------------------------------------------------

def test_a_daily_time_is_shown_in_the_clock_the_person_typed_it_in_and_saved_is_said(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-time-morning").fill("19:05")  # the field's value is always 24 hours; it shows 7:05 PM
        page.get_by_test_id("daily-set-morning").click()

        saved = page.get_by_test_id("daily-saved-morning")
        saved.wait_for()
        assert "Saved" in saved.inner_text() and "7:05 PM" in saved.inner_text()
        # the row re-reads the schedule after the save, so wait for it instead of reading it at once
        page.get_by_test_id("daily-morning").filter(has_text="7:05 PM").wait_for()
        assert "19:05" not in row(page, "morning").inner_text()


# --- 10: one message per app -----------------------------------------------------------------------------------------------

def test_an_app_with_ten_actions_to_learn_again_offers_one_message_in_plain_words(tmp_path):
    db = tmp_path / "user.db"
    for n in range(10):
        save_step(db, step(f"Step {n}", "Alpha", app="excel.exe", version="0.9"))
    revalidate_changed_versions(db, "excel.exe", "1.0")
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        apps_screen(page)
        app_row(page, "excel.exe").click()
        card = page.get_by_test_id("app-card-excel.exe")
        buttons = card.get_by_role("button", name="Show me what to send")
        buttons.wait_for()
        assert buttons.count() == 1
        buttons.click()
        assert card.get_by_test_id("chat-message").count() == 1
        text = card.get_by_test_id("chat-message").inner_text()
        assert "was updated and its steps have to be learned again" in text
        assert "Claude Code" not in text and "folder" not in text


# --- 11: Run now answers at once -----------------------------------------------------------------------------------------

def test_run_now_shows_running_on_the_row_the_moment_it_is_pressed(tmp_path):
    put_flows(tmp_path)
    held = []
    with home(tmp_path) as (page, _):
        says(page, "morning", "Never run")
        page.route("**/api/flows/morning/run", lambda route: held.append(route))
        run_button(page, "morning").click()

        row(page, "morning").get_by_text("Running now").wait_for()
        assert "Running…" in run_button(page, "morning").inner_text()
        assert run_button(page, "morning").locator("svg").first.evaluate("(e) => getComputedStyle(e).animationName") == "spin"
        held[0].continue_()
        page.get_by_test_id("flow-result-morning").wait_for()
