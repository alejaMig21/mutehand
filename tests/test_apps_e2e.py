"""The Apps screen (editor rethink, ticket 11): programs it knows, a search across them, one app opened with its actions,
problems first, its permissions with "Take back", and the message to teach another. Driven in the built editor against the
real API, with the stand-in desktop and Windows scheduler. Opt-in: `pytest -m web`."""

import pytest
from test_canvas_e2e import stub_clipboard
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import NO_SIDEWAYS_SCROLL, home, put_flow, put_flows

from workflow_factory import Sensitivity, grant_consent, load_flow, reject_step, run_flow, save_step
from workflow_factory.consent import consents
from workflow_factory.steps import list_steps, record_app_name, revalidate_changed_versions, step_report
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


def apps_screen(page):
    page.get_by_test_id("tab-apps").click()
    page.get_by_role("heading", name="Programs it knows").wait_for()


def app_row(page, app):
    return page.get_by_test_id(f"app-row-{app}")


def twenty_five(db):
    for n in range(25):
        save_step(db, step("open", "Alpha", app=f"program{n:02}.exe"))


def state_of(db, name):
    return step_report(db, next(s for s in list_steps(db, None) if s.name == name))["state"]


def test_with_25_apps_the_first_rows_show_and_show_more_adds_the_rest(tmp_path):
    twenty_five(tmp_path / "user.db")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        assert page.title() == "Apps · Mutehand"
        app_row(page, "program00.exe").wait_for()
        assert page.locator("[data-testid^=app-row-]").count() == 14
        assert "1 step" in app_row(page, "program00.exe").inner_text()
        more = page.get_by_test_id("apps-show-more")
        assert more.inner_text().strip() == "Show 11 more programs"

        more.click()

        assert page.locator("[data-testid^=app-row-]").count() == 25
        more.wait_for(state="detached")


def test_a_search_by_words_finds_actions_in_every_app_and_opens_the_app_that_has_one(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Save spreadsheet", "A", app="excel.exe"))
    save_step(db, step("Open file", "A", app="excel.exe"))
    save_step(db, step("Save picture", "A", app="paint.exe"))
    save_step(db, step("Print", "A", app="word.exe"))
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "word.exe").wait_for()
        page.get_by_test_id("apps-search").fill("save")
        page.get_by_test_id("apps-search").press("Enter")

        app_row(page, "word.exe").wait_for(state="detached")
        assert "Save spreadsheet" in app_row(page, "excel.exe").inner_text()
        assert "Save picture" in app_row(page, "paint.exe").inner_text()
        assert "Open file" not in app_row(page, "excel.exe").inner_text()

        app_row(page, "paint.exe").click()
        page.get_by_test_id("app-card-paint.exe").wait_for()

        page.get_by_test_id("apps-search").fill("zzz nothing")
        page.get_by_test_id("apps-search-go").click()
        page.get_by_test_id("apps-none").wait_for()
        assert "zzz nothing" in page.get_by_test_id("apps-none").inner_text()


def test_an_app_opens_with_its_actions_problems_first_each_with_its_button(tmp_path):
    db = tmp_path / "user.db"
    for name in ("Write in a cell", "Open file", "Add a chart", "New spreadsheet", "Save"):
        save_step(db, step(name, "Alpha", app="excel.exe"))
    reject_step(db, "excel.exe", "Save")
    save_step(db, step("Add a chart", "Alpha", app="excel.exe", version="0.9"))
    revalidate_changed_versions(db, "excel.exe", "1.0")  # it was learned on 0.9
    record_app_name(db, FakeDesktop(controls=[], app="excel.exe", product_name="Microsoft Excel").app_key())
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        apps_screen(page)
        assert "5 steps" in app_row(page, "excel.exe").inner_text()
        assert "2 need attention" in app_row(page, "excel.exe").inner_text()
        app_row(page, "excel.exe").click()
        card = page.get_by_test_id("app-card-excel.exe")
        card.wait_for()
        assert "Microsoft Excel" in card.inner_text() and ".exe" not in card.inner_text()
        parts = "[data-testid^=app-problem-], [data-testid=app-relearn], [data-testid^=app-step-]"
        order = [p.get_attribute("data-testid") for p in card.locator(parts).all()]
        assert order == ["app-relearn", "app-problem-Save", "app-step-New spreadsheet", "app-step-Open file",
                         "app-step-Write in a cell"]
        assert "learned again" in card.get_by_test_id("app-relearn").inner_text()
        assert "You blocked it." in card.get_by_test_id("app-problem-Save").inner_text()

        card.get_by_test_id("app-message-relearn").click()
        message = card.get_by_test_id("chat-text").inner_text()
        assert "Microsoft Excel was updated" in message and ".exe" not in message

        card.get_by_test_id("app-allow-again-Save").click()
        card.get_by_test_id("app-problem-Save").wait_for(state="detached")
        assert state_of(db, "Save") != "rejected"
        card.get_by_test_id("app-close").click()
        app_row(page, "excel.exe").filter(has_text="1 needs attention").wait_for()


def test_taking_a_permission_back_asks_first_says_what_stops_and_removes_only_that_consent(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Send it", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("Open inbox", "Inbox", app="mail.exe"))
    put_flow(tmp_path, "weekly", "Weekly report", "Open inbox", "Send it", app="mail.exe")
    grant_consent(db, "mail.exe", "Send", "click")
    grant_consent(db, "mail.exe", "Reply", "click")
    grant_consent(db, "word.exe", "Send", "click")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "mail.exe").click()
        card = page.get_by_test_id("app-card-mail.exe")
        permission = card.get_by_test_id("app-permission-Send-click")
        assert "Press “Send”" in permission.inner_text()

        permission.get_by_role("button", name="Take back").click()
        asked = card.get_by_test_id("take-back-ask")
        assert "This flow will stop: “Weekly report”" in asked.inner_text()
        assert "The step “Send it” will not run without it." in asked.inner_text()
        assert len(consents(db)) == 3  # nothing happened yet

        asked.get_by_role("button", name="Keep it").click()
        asked.wait_for(state="detached")
        assert len(consents(db)) == 3

        permission.get_by_role("button", name="Take back").click()
        card.get_by_test_id("take-back-yes").click()

        permission.wait_for(state="detached")
        assert {(c.app, c.control) for c in consents(db)} == {("mail.exe", "Reply"), ("word.exe", "Send")}
        assert "taken back" in page.get_by_test_id("announce").inner_text().lower()
        assert "Weekly report" in page.get_by_test_id("announce").inner_text()
        assert card.get_by_test_id("app-permission-Reply-click").count() == 1


def test_a_flow_stopped_on_an_app_is_noted_on_its_row(tmp_path):
    put_flows(tmp_path)
    db = tmp_path / "user.db"
    run_flow(load_flow(db, None, "morning"), desktop=FakeDesktop(controls=[button("Alpha")]), user_db=db)
    save_step(tmp_path / "user.db", step("calm", "Alpha", app="notes.exe"))
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "paint.exe").filter(has_text="1 stopped").wait_for()
        assert "stopped" not in app_row(page, "notes.exe").inner_text()
        rows = [r.get_attribute("data-testid") for r in page.locator("[data-testid^=app-row-]").all()]
        assert rows == ["app-row-paint.exe", "app-row-notes.exe"]  # what needs the person comes first


def test_the_message_to_teach_another_action_names_the_app_and_copies(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Open file", "A", app="excel.exe"))
    record_app_name(db, FakeDesktop(controls=[], app="excel.exe", product_name="Microsoft Excel").app_key())
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        apps_screen(page)
        app_row(page, "excel.exe").click()
        card = page.get_by_test_id("app-card-excel.exe")
        card.get_by_test_id("app-teach").click()
        message = card.get_by_test_id("chat-text").inner_text()
        assert "teach another step in Microsoft Excel" in message and ".exe" not in message
        card.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert page.evaluate("() => window.copied") == message


def test_everything_works_from_the_keyboard_alone_and_the_focus_goes_where_the_person_is(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Send it", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(db, "mail.exe", "Send", "click")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        page.get_by_test_id("apps-search").focus()
        page.keyboard.type("send")
        page.keyboard.press("Enter")
        app_row(page, "mail.exe").wait_for()
        app_row(page, "mail.exe").focus()
        page.keyboard.press("Enter")
        card = page.get_by_test_id("app-card-mail.exe")
        card.wait_for()
        assert page.evaluate("() => document.activeElement.closest('[data-testid^=app-card-]') !== null")  # the card has the focus
        page.get_by_test_id("app-take-back-Send-click").focus()
        page.keyboard.press("Enter")
        page.get_by_test_id("take-back-yes").focus()
        page.keyboard.press("Enter")
        card.get_by_test_id("app-permission-Send-click").wait_for(state="detached")
        assert consents(db) == []
        page.get_by_test_id("app-close").focus()
        page.keyboard.press("Enter")
        card.wait_for(state="detached")
        assert page.evaluate("() => document.activeElement.dataset.testid") == "app-row-mail.exe"


def test_no_screen_content_of_a_private_app_reaches_the_screen_a_search_or_a_message(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    save_step(db, step("Bank code 4471", "Bank code 4471", app="telegram.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    mark_private(db, "telegram.exe")
    reject_step(db, "telegram.exe", "Bank code 4471")
    revalidate_changed_versions(db, "telegram.exe", "2.0")
    grant_consent(db, "telegram.exe", "Chat with Ana Ruiz", "click")
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        apps_screen(page)
        page.get_by_test_id("apps-search").fill("bank")
        page.get_by_test_id("apps-search").press("Enter")
        page.get_by_test_id("apps-none").wait_for()
        page.get_by_test_id("apps-search").fill("")
        page.get_by_test_id("apps-search").press("Enter")
        app_row(page, "telegram.exe").click()
        card = page.get_by_test_id("app-card-telegram.exe")
        card.wait_for()
        card.get_by_role("button", name="Take back").click()
        card.get_by_test_id("take-back-ask").wait_for()
        card.get_by_role("button", name="Show me the message to copy").first.click()
        words = page.get_by_test_id("app-card-telegram.exe").inner_text() + page.get_by_test_id("chat-text").first.inner_text()
        for secret in ("Ana Ruiz", "4471", "open-chat", "Bank code"):
            assert secret not in words, secret
        assert "Telegram" in words


@pytest.mark.parametrize("width,height", [(683, 384), (390, 740)])
def test_the_screen_fits_a_narrow_window_with_readable_buttons(tmp_path, width, height):
    db = tmp_path / "user.db"
    twenty_five(db)
    save_step(db, step("A very long step name " + "x" * 60, "A", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(db, "mail.exe", "Send", "click")
    reject_step(db, "mail.exe", "A very long step name " + "x" * 60)
    buttons = """(width) => [...document.querySelectorAll('.apps button')].filter((b) => b.offsetParent).map((b) => {
        const rect = b.getBoundingClientRect()
        return [b.innerText.trim(), rect.left >= 0 && rect.right <= width && rect.height >= 44]
      }).filter(([, fits]) => !fits)"""
    with home(tmp_path) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        apps_screen(page)
        app_row(page, "mail.exe").click()
        card = page.get_by_test_id("app-card-mail.exe")
        card.get_by_role("button", name="Take back").click()
        card.get_by_test_id("take-back-ask").wait_for()
        card.get_by_test_id("app-teach").click()
        assert page.evaluate(NO_SIDEWAYS_SCROLL)
        assert page.evaluate(buttons, width) == []
        assert page.evaluate(CONTRAST) == []
