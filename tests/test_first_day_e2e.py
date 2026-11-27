"""The first day on Home: what the product is for, the message that starts teaching, the three stages. Opt-in: `pytest -m web`."""

import pytest
from test_editor_safety_e2e import CONTRAST
from test_home_e2e import BUTTONS, FOCUSED, NO_SIDEWAYS_SCROLL, at_home, chore, home, on_the_flow_screen, tab_to

from workflow_factory import save_step

from fake_desktop import step

pytestmark = pytest.mark.web

SENTENCE = "Show it a computer chore once. Then it does the chore for you."
MESSAGE = "I want to teach you a chore: [what you want done, and in which program]"
# the page's clipboard is replaced: nothing here may reach the person's own clipboard
STAND_IN_CLIPBOARD = """window.__copied = []
Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (text) => { window.__copied.push(text) } } })"""


def first_day(page):
    page.add_init_script(STAND_IN_CLIPBOARD)
    page.reload()
    page.get_by_test_id("first-day").wait_for()


def test_with_nothing_learned_home_says_what_it_is_for_and_how_to_start(tmp_path):
    with home(tmp_path) as (page, _):
        first_day(page)
        page.get_by_role("heading", name=SENTENCE).wait_for()
        assert page.get_by_test_id("chat-text").inner_text() == MESSAGE
        stages = page.get_by_test_id("stages").locator("li")
        assert [s.split("\n")[0] for s in stages.all_inner_texts()] == ["1. Teach", "2. Put in order", "3. Let it repeat"]
        assert page.get_by_test_id("new-chore").count() == 0 and page.get_by_test_id("no-chores").count() == 0


def test_copy_this_message_copies_it_and_starts_nothing(tmp_path):
    with home(tmp_path) as (page, desktop):
        first_day(page)
        sent = []
        page.on("request", lambda request: sent.append(request.method))
        page.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert page.evaluate("() => window.__copied") == [MESSAGE]
        assert set(sent) <= {"GET"} and not desktop.clicks


def test_the_first_day_works_with_the_keyboard_alone(tmp_path):
    with home(tmp_path) as (page, _):
        first_day(page)
        tab_to(page, "tab-home")
        for _ in range(10):  # the screens' buttons come first, then the message's own button
            page.keyboard.press("Tab")
            if page.evaluate("() => document.activeElement.textContent.includes('Copy this message')"):
                break
        else:
            raise AssertionError("Copy this message cannot be reached with Tab")
        page.keyboard.press("Enter")
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert page.evaluate("() => window.__copied") == [MESSAGE]


def test_with_actions_learned_and_no_chore_new_chore_is_the_main_button(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    with home(tmp_path) as (page, _):
        page.get_by_test_id("no-chores").wait_for()
        assert page.get_by_test_id("first-day").count() == 0
        button = page.get_by_test_id("new-chore")
        assert button.count() == 1 and "primary" in button.get_attribute("class")
        button.focus()
        page.keyboard.press("Enter")
        on_the_flow_screen(page, "My flow", 0)


def test_an_action_of_the_factory_counts_as_learned(tmp_path):
    save_step(tmp_path / "factory.db", step("open-menu", "Alpha", origin="factory"))
    with home(tmp_path) as (page, _):
        page.get_by_test_id("new-chore").wait_for()
        assert page.get_by_test_id("first-day").count() == 0


def test_the_first_day_gives_way_when_an_action_is_learned_in_another_window(tmp_path):
    with home(tmp_path) as (page, _):
        page.get_by_test_id("first-day").wait_for()
        save_step(tmp_path / "user.db", step("open-menu", "Alpha"))  # the tutor, in a chat
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        page.get_by_test_id("new-chore").wait_for()
        assert page.get_by_test_id("first-day").count() == 0


def test_a_person_with_chores_sees_neither_the_first_day_nor_the_empty_state(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    chore(tmp_path, "morning", "Morning report", "open-menu")
    with home(tmp_path) as (page, _):
        page.get_by_test_id("chore-morning").wait_for()
        assert page.get_by_test_id("first-day").count() == 0 and page.get_by_test_id("no-chores").count() == 0
        assert page.get_by_test_id("new-chore").count() == 1
        at_home(page)


@pytest.mark.parametrize("width,height", [(1280, 800), (683, 384), (390, 740)])
@pytest.mark.parametrize("learned", [False, True])
def test_the_first_day_fits_a_narrow_window_and_stays_readable(tmp_path, width, height, learned):
    if learned:
        save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    with home(tmp_path) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        page.get_by_test_id("no-chores" if learned else "first-day").wait_for()
        assert page.evaluate(NO_SIDEWAYS_SCROLL)
        assert page.evaluate(BUTTONS, width) == []
        assert page.evaluate(CONTRAST) == []
        assert page.evaluate(FOCUSED) in (None, "")  # nothing grabbed the focus
