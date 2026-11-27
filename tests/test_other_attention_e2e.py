"""Other things that need the person (editor rethink, ticket 10): actions to learn again after an app update, a rejected
action that blocks a chore, and a missing piece of setup. Driven in the built editor against the real API, with the
stand-in desktop and Windows scheduler. Opt-in: `pytest -m web`."""

import pytest
from test_canvas_e2e import stub_clipboard
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import NO_SIDEWAYS_SCROLL, chore, chores, home, row, says

from workflow_factory import reject_step, save_step
from workflow_factory.steps import list_steps, revalidate_changed_versions, step_report
from workflow_factory.tutor import mark_private

from fake_desktop import step

pytestmark = pytest.mark.web

MISSING = {"id": "agent-desktop", "title": "Desktop control (agent-desktop)", "why": "It is how the apprentice sees and acts on apps.",
           "ok": False, "fix": "Install it with npm: npm install -g agent-desktop", "optional": False}


@pytest.fixture(autouse=True)
def not_the_first_run(monkeypatch):
    monkeypatch.setattr("workflow_factory.api.seen_before", lambda data_dir: True)


def attention(page):
    return page.get_by_test_id("attention")


def state_of(db, name):
    return step_report(db, next(s for s in list_steps(db, None) if s.name == name))["state"]


def an_updated_app(tmp_path):
    chores(tmp_path)
    chore(tmp_path, "evening", "Evening report", "open-menu")
    revalidate_changed_versions(tmp_path / "user.db", "paint.exe", "2.0")  # what a run records when it meets another version


def test_an_app_update_is_one_card_naming_the_app_and_the_blocked_chores_with_the_message_to_send(tmp_path):
    an_updated_app(tmp_path)
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        card = page.get_by_test_id("attention-relearn-paint.exe")
        card.wait_for()
        assert "Needs your attention (1)" in attention(page).inner_text()
        text = card.inner_text()
        assert "Paint was updated" in text and "“Evening report”" in text and "“Morning report”" in text and ".exe" not in text

        page.get_by_test_id("attention-message-relearn-paint.exe").click()
        message = card.get_by_test_id("chat-text").inner_text()
        assert "Paint" in message and "learned again" in message and "“Morning report”" in message and ".exe" not in message
        card.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert page.evaluate("() => window.copied") == message


def test_an_action_that_blocks_no_chore_raises_no_card(tmp_path):
    chores(tmp_path)
    save_step(tmp_path / "user.db", step("unused", "Gamma"))
    reject_step(tmp_path / "user.db", "paint.exe", "unused")
    with home(tmp_path) as (page, _):
        says(page, "morning", "Never run")
        page.wait_for_timeout(400)
        assert attention(page).count() == 0


def test_a_rejected_action_that_blocks_a_chore_says_why_and_allow_again_lifts_it(tmp_path):
    chores(tmp_path)
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")
    with home(tmp_path) as (page, _):
        card = page.get_by_test_id("attention-rejected-paint.exe-save-file")
        card.wait_for()
        text = card.inner_text()
        assert "“save-file” is rejected" in text and "You rejected it." in text and "“Morning report”" in text
        assert "Cannot run yet" in row(page, "morning").inner_text()

        card.get_by_role("button", name="Allow again").click()

        attention(page).wait_for(state="detached")
        assert state_of(tmp_path / "user.db", "save-file") != "rejected"
        assert row(page, "morning").get_by_test_id("run-now-morning").inner_text().strip() == "Run now"


def test_a_missing_required_setup_piece_shows_how_to_fix_it_and_a_working_setup_shows_nothing(tmp_path, monkeypatch):
    chores(tmp_path)
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [MISSING])
    with home(tmp_path) as (page, _):
        card = page.get_by_test_id("attention-setup-agent-desktop")
        card.wait_for()
        text = card.inner_text()
        assert "Desktop control (agent-desktop)" in text and "It is how the apprentice sees and acts on apps." in text
        assert "To fix: Install it with npm: npm install -g agent-desktop" in text
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [{**MISSING, "ok": True, "fix": None}])
    with home(tmp_path) as (page, _):
        says(page, "morning", "Never run")
        page.wait_for_timeout(400)
        assert attention(page).count() == 0


def test_the_cards_work_from_the_keyboard_alone(tmp_path):
    chores(tmp_path)
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")
    with home(tmp_path) as (page, _):
        page.get_by_test_id("attention-rejected-paint.exe-save-file").wait_for()
        page.get_by_test_id("attention-allow-again-paint.exe-save-file").focus()
        page.keyboard.press("Enter")
        attention(page).wait_for(state="detached")
        assert state_of(tmp_path / "user.db", "save-file") != "rejected"
    revalidate_changed_versions(tmp_path / "user.db", "paint.exe", "2.0")
    with home(tmp_path) as (page, _):
        stub_clipboard(page)
        page.get_by_test_id("attention-message-relearn-paint.exe").focus()
        page.keyboard.press("Enter")
        assert page.get_by_test_id("chat-text").is_visible()
        page.keyboard.press("Tab")
        page.keyboard.press("Enter")
        page.get_by_text("Copied. Paste it in the chat.").wait_for()


def test_no_screen_content_of_a_private_app_reaches_these_cards_or_their_message(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    save_step(db, step("send-it", "Bank code 4471", app="telegram.exe"))
    chore(tmp_path, "greet", "Say hello", "open-chat", app="telegram.exe")
    chore(tmp_path, "pay", "Pay", "send-it", app="telegram.exe")
    mark_private(db, "telegram.exe")
    reject_step(db, "telegram.exe", "send-it")
    revalidate_changed_versions(db, "telegram.exe", "2.0")
    with home(tmp_path) as (page, _):
        said = []
        page.on("response", lambda r: said.append(r) if "/api/attention" in r.url else None)
        page.get_by_test_id("attention-relearn-telegram.exe").wait_for()
        page.get_by_test_id("attention-message-relearn-telegram.exe").click()
        assert page.get_by_test_id("attention-rejected-telegram.exe-send-it").count() == 1
        words = attention(page).inner_text() + page.get_by_test_id("chat-text").inner_text()
        for secret in ("Ana Ruiz", "4471", "open-chat", "send-it"):
            assert secret not in words, secret
        assert "Ana Ruiz" not in "".join(r.text() for r in said) and "4471" not in "".join(r.text() for r in said)


@pytest.mark.parametrize("width,height", [(683, 384), (390, 740)])
def test_the_cards_fit_a_narrow_window_with_readable_buttons(tmp_path, width, height, monkeypatch):
    chores(tmp_path)
    chore(tmp_path, "evening", "Evening-report-" + "x" * 60, "open-menu")
    save_step(tmp_path / "user.db", step("print-it", "Gamma", app="notes.exe"))
    chore(tmp_path, "notes", "Notes", "print-it", app="notes.exe")
    reject_step(tmp_path / "user.db", "notes.exe", "print-it")
    revalidate_changed_versions(tmp_path / "user.db", "paint.exe", "2.0")
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [MISSING])
    buttons = """(width) => [...document.querySelectorAll('.attention button')].filter((b) => b.offsetParent).map((b) => {
        const box = b.getBoundingClientRect()
        return [b.innerText.trim(), box.left >= 0 && box.right <= width && box.height >= 44 && b.scrollWidth <= b.clientWidth]
      }).filter(([, fits]) => !fits)"""
    with home(tmp_path) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        page.get_by_test_id("attention-setup-agent-desktop").wait_for()
        page.get_by_test_id("attention-message-relearn-paint.exe").click()
        assert "Needs your attention (3)" in attention(page).inner_text()
        assert page.evaluate(NO_SIDEWAYS_SCROLL) and page.evaluate(buttons, width) == [] and page.evaluate(CONTRAST) == []
