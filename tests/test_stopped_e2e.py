"""A stopped chore: it comes first on Home, and Try again and Ask for help sit beside it and under its red box (editor
rethink, ticket 09). Driven in the built editor against the real API, with the stand-in desktop and Windows scheduler.
Opt-in: `pytest -m web`."""

import re

import pytest
from test_canvas_e2e import node, stub_clipboard
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import NO_SIDEWAYS_SCROLL, chore, chores, home, row, says

from workflow_factory import list_doubts, reject_step, run_flow, save_step
from workflow_factory.tutor import list_open_doubts, mark_private

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


@pytest.fixture(autouse=True)
def not_the_first_run(monkeypatch):
    monkeypatch.setattr("workflow_factory.api.seen_before", lambda data_dir: True)


def stopped(tmp_path, title="Weekly export", *, third=False):
    """A chore that did its first box and stopped at its second: Paint did not show the button."""
    db = tmp_path / "user.db"
    names = ["open-menu", "close-message"] + (["save-picture"] if third else [])
    for name, control in zip(names, ("Alpha", "Beta", "Gamma"), strict=False):
        save_step(db, step(name, control))
    flow = chore(tmp_path, "weekly", title, *names)
    run_flow(flow, desktop=FakeDesktop(controls=[button("Alpha")]), user_db=db)
    return db


def card(page, flow_id="weekly"):
    return page.get_by_test_id(f"attention-{flow_id}")


def try_again(page, flow_id="weekly"):
    return page.get_by_test_id(f"attention-try-again-{flow_id}")


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def test_a_stopped_chore_comes_first_on_home_with_a_count_and_says_which_box_and_why_in_plain_words(tmp_path):
    stopped(tmp_path)
    chores(tmp_path)
    with home(tmp_path) as (page, _):
        card(page).wait_for()
        assert "Needs your attention (1)" in page.get_by_test_id("attention").inner_text()
        text = card(page).inner_text()
        assert re.search(r"“Weekly export” stopped .+ at \d\d:\d\d", text)
        assert "“close-message”: The button or field this step uses is not on the screen." in text
        assert "Paint" in text and "control_not_found" not in text and ".exe" not in text
        above = page.get_by_test_id("attention").bounding_box()["y"]
        assert above < page.get_by_role("heading", name="Your chores").bounding_box()["y"]  # first on the screen
        assert "See above" in row(page, "weekly").inner_text()
        assert row(page, "weekly").get_by_test_id("run-now-weekly").inner_text().strip() == "Try again"
        assert row(page, "morning").get_by_test_id("run-now-morning").inner_text().strip() == "Run now"


def test_the_attention_section_is_absent_when_nothing_has_stopped_and_counts_every_stopped_chore(tmp_path):
    chores(tmp_path)
    with home(tmp_path) as (page, _):
        says(page, "morning", "Never run")
        assert page.get_by_test_id("attention").count() == 0 and "attention" not in page.inner_text("body").lower()
    stopped(tmp_path)
    save_step(tmp_path / "user.db", step("print-it", "Gamma"))
    other = chore(tmp_path, "other", "Other chore", "print-it")
    run_flow(other, desktop=FakeDesktop(controls=[]), user_db=tmp_path / "user.db")
    with home(tmp_path) as (page, _):
        page.get_by_test_id("attention").wait_for()
        assert "Needs your attention (2)" in page.get_by_test_id("attention").inner_text()


def test_try_again_closes_the_doubt_goes_on_from_where_it_stopped_and_says_it_is_fixed(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        card(page).wait_for()
        try_again(page).click()

        fixed = page.get_by_test_id("tried-weekly")
        fixed.filter(has_text="Fixed: “Weekly export” ran to the end just now.").wait_for()
        assert "2 boxes finished." in fixed.inner_text()  # the one done before counts too
        assert clicked(desktop) == ["Beta"]  # the first box was not done again
        assert [(d.status, d.closed_as) for d in list_doubts(db)] == [("answered", "tried_again")]
        assert page.get_by_test_id("attention").count() == 0
        says(page, "weekly", r"Worked .+ at \d\d:\d\d")
        assert row(page, "weekly").get_by_test_id("run-now-weekly").inner_text().strip() == "Run now"

        fixed.get_by_role("button", name="Hide").click()
        assert page.get_by_test_id("tried-weekly").count() == 0


def test_trying_again_that_stops_for_the_same_reason_says_so_and_the_card_stays(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path, FakeDesktop(controls=[button("Alpha")])) as (page, _):
        card(page).wait_for()
        try_again(page).click()

        page.get_by_test_id("tried-weekly").filter(has_text="Still stopped").wait_for()
        card(page).wait_for()
        assert [d.status for d in list_doubts(db)] == ["answered", "open"]


def test_trying_again_that_stops_somewhere_else_says_it_is_a_new_problem(tmp_path):
    stopped(tmp_path, third=True)
    with home(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Beta")])) as (page, _):  # Gamma is missing
        card(page).wait_for()
        try_again(page).click()

        page.get_by_test_id("tried-weekly").filter(has_text="A new problem: “Weekly export” stopped again.").wait_for()
        assert "“save-picture”" in page.get_by_test_id("tried-weekly").inner_text()
        assert "“save-picture”" in card(page).inner_text()


def test_a_step_the_person_rejected_offers_allow_again_instead_and_trying_again_never_lifts_it(tmp_path):
    db = stopped(tmp_path)
    reject_step(db, "paint.exe", "close-message")
    with home(tmp_path) as (page, desktop):
        card(page).wait_for()
        assert try_again(page).count() == 0
        posts = []
        page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)

        page.get_by_test_id("attention-allow-again-weekly").click()
        try_again(page).wait_for()  # allowed again: now it can be tried
        assert page.get_by_test_id("attention-allow-again-weekly").count() == 0
        assert [p for p in posts if "try-again" in p] == []

        try_again(page).click()
        page.get_by_test_id("tried-weekly").filter(has_text="Fixed").wait_for()
        assert clicked(desktop) == ["Beta"]


def test_ask_for_help_shows_the_message_copies_it_and_keeps_the_note_on_the_open_doubt(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        stub_clipboard(page)
        card(page).wait_for()
        posts = []
        page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)

        page.get_by_test_id("attention-ask-help-weekly").click()
        message = page.get_by_test_id("attention-help-weekly").get_by_test_id("chat-text")
        for part in ("“Weekly export”", "“close-message”", "The button or field this step uses is not on the screen.", "open question 1"):
            assert part in message.inner_text()
        assert "control_not_found" not in message.inner_text()

        page.get_by_test_id("attention-note-weekly").fill("It only happens when Paint is minimised")
        assert "My note: “It only happens when Paint is minimised”." in message.inner_text()
        page.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()

        assert "My note: “It only happens when Paint is minimised”." in page.evaluate("() => window.copied")
        [doubt] = list_doubts(db)
        assert (doubt.status, doubt.note) == ("open", "It only happens when Paint is minimised")
        assert list_open_doubts(db)[0]["note"] == "It only happens when Paint is minimised"
        card(page).wait_for()  # still there: help was asked for, nothing was answered
        assert not [p for p in posts if "/answer" in p or "/dismiss" in p or "try-again" in p] and clicked(desktop) == []


def test_giving_the_chore_a_daily_time_after_it_stopped_does_not_send_it_back_to_the_start(tmp_path):
    stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        card(page).wait_for()
        page.get_by_test_id("daily-weekly").click()
        page.get_by_test_id("daily-time-weekly").fill("07:30")
        page.get_by_test_id("daily-set-weekly").click()
        row(page, "weekly").filter(has_text="07:30").wait_for()

        try_again(page).click()
        page.get_by_test_id("tried-weekly").filter(has_text="Fixed").wait_for()
        assert clicked(desktop) == ["Beta"]  # Alpha was done before the stop and is not done twice


def test_the_stopped_box_is_red_and_chosen_on_the_flow_screen_with_the_reason_and_the_same_two_buttons(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        page.get_by_test_id("open-chore-weekly").click()
        strip = page.get_by_role("region", name="About the chosen box")
        strip.get_by_test_id("strip-reason").wait_for()

        assert "status-blocked" in node(page, "n2").get_attribute("class") and "Stopped here" in node(page, "n2").inner_text()
        assert "selected" in node(page, "n2").locator(".card").get_attribute("class")
        assert strip.get_by_role("heading").inner_text() == "close-message"
        assert "The button or field this step uses is not on the screen." in strip.get_by_test_id("strip-reason").inner_text()

        strip.get_by_test_id("strip-try-again").click()
        page.get_by_test_id("tried-weekly").filter(has_text="Fixed: “Weekly export” ran to the end just now.").wait_for()
        assert clicked(desktop) == ["Beta"]
        assert "status-done" in node(page, "n2").get_attribute("class") and "status-done" in node(page, "n1").get_attribute("class")
        assert [(d.status, d.closed_as) for d in list_doubts(db)] == [("answered", "tried_again")]
        assert page.get_by_test_id("strip-reason").count() == 0


def test_asking_for_help_from_the_flow_screen_keeps_the_note_and_changes_nothing(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        stub_clipboard(page)
        page.get_by_test_id("open-chore-weekly").click()
        page.get_by_test_id("strip-ask-help").click()
        page.get_by_test_id("strip-note").fill("Paint was behind another window")
        page.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()

        assert "Paint was behind another window" in page.evaluate("() => window.copied")
        assert [(d.status, d.note) for d in list_doubts(db)] == [("open", "Paint was behind another window")]
        assert clicked(desktop) == []


def test_pressing_run_on_a_stopped_chore_points_to_the_stopped_box_instead_of_a_queue(tmp_path):
    stopped(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_test_id("open-chore-weekly").click()
        page.get_by_test_id("strip-reason").wait_for()
        node(page, "n1").click()  # looking at another box
        assert page.get_by_test_id("strip-reason").count() == 0

        page.get_by_test_id("run").click()
        outcome = page.get_by_test_id("run-outcome")
        outcome.filter(has_text="stopped earlier").wait_for()
        assert "Tutor queue" not in outcome.inner_text()
        outcome.get_by_role("button", name="Show the stopped box").click()
        page.get_by_test_id("strip-reason").wait_for()


def test_trying_again_and_asking_for_help_work_from_the_keyboard_alone(tmp_path):
    db = stopped(tmp_path)
    with home(tmp_path) as (page, desktop):
        stub_clipboard(page)
        card(page).wait_for()
        page.get_by_test_id("attention-ask-help-weekly").focus()
        page.keyboard.press("Enter")
        assert page.evaluate("() => document.activeElement.tagName") == "TEXTAREA"  # the note is ready to type in
        page.keyboard.type("hello")
        page.keyboard.press("Tab")
        page.keyboard.press("Enter")
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert list_doubts(db)[0].note == "hello"

        try_again(page).focus()
        page.keyboard.press("Enter")
        page.get_by_test_id("tried-weekly").filter(has_text="Fixed").wait_for()
        assert clicked(desktop) == ["Beta"]


def test_no_screen_content_of_a_private_app_reaches_a_stopped_card_or_its_message(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    flow = chore(tmp_path, "greet", "Say hello", "open-chat", app="telegram.exe")
    mark_private(db, "telegram.exe")
    run_flow(flow, desktop=FakeDesktop(controls=[button("Bank code 4471")], app="telegram.exe"), user_db=db)
    with home(tmp_path, FakeDesktop(controls=[], app="telegram.exe")) as (page, _):
        said = []
        page.on("response", lambda r: said.append(r) if "/api/attention" in r.url else None)
        page.get_by_test_id("attention-greet").wait_for()
        assert "one of its boxes" in card(page, "greet").inner_text()
        page.get_by_test_id("attention-ask-help-greet").click()
        message = page.get_by_test_id("attention-help-greet").inner_text()
        shown = page.content() + message + "".join(r.text() for r in said)
        assert "Ana Ruiz" not in shown and "4471" not in shown and "open-chat" not in shown and "one of its boxes" in message


@pytest.mark.parametrize("width,height", [(683, 384), (390, 740)])
def test_the_stopped_chore_fits_a_narrow_window_on_home_and_on_the_flow_screen_with_readable_buttons(tmp_path, width, height):
    stopped(tmp_path, "Weekly-export-" + "x" * 70)
    chores(tmp_path)
    buttons = """(width) => [...document.querySelectorAll('.attention button, .tried button, .strip button, .strip-reason button')]
      .filter((b) => b.offsetParent).map((b) => {
        const box = b.getBoundingClientRect()
        return [b.innerText.trim(), box.left >= 0 && box.right <= width && box.height >= 44 && b.scrollWidth <= b.clientWidth]
      }).filter(([, fits]) => !fits)"""
    with home(tmp_path) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        card(page).wait_for()
        page.get_by_test_id("attention-ask-help-weekly").click()
        assert page.evaluate(NO_SIDEWAYS_SCROLL) and page.evaluate(buttons, width) == [] and page.evaluate(CONTRAST) == []
        shown = try_again(page).bounding_box()
        assert shown["x"] >= 0 and shown["x"] + shown["width"] <= width
        try_again(page).click()
        page.get_by_test_id("tried-weekly").wait_for()
        assert page.evaluate(NO_SIDEWAYS_SCROLL) and page.evaluate(buttons, width) == [] and page.evaluate(CONTRAST) == []

    stopped_again = tmp_path / "again"
    stopped_again.mkdir()
    stopped(stopped_again)
    with home(stopped_again) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        page.get_by_test_id("open-chore-weekly").click()
        strip = page.get_by_test_id("strip-reason")
        strip.wait_for()
        page.get_by_test_id("strip-ask-help").click()
        for name in ("Try again", "Ask for help"):
            shown = page.get_by_role("region", name="About the chosen box").get_by_role("button", name=re.compile(name)).bounding_box()
            assert shown["height"] >= 44 and shown["x"] >= 0 and shown["x"] + shown["width"] <= width
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        assert page.evaluate(CONTRAST) == []
