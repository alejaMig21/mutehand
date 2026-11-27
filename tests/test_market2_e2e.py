"""The second market test (non-technical personas on the finished app): what they could not read, find or tell had worked.
Each defect is fixed once and kept fixed. Driven in the built editor. Opt-in: `pytest -m web`."""

import re

import pytest
from test_apps_e2e import app_row, apps_screen
from test_flow_more_e2e import more, served
from test_home_e2e import home, put_flow, put_flows, row, run_button, says
from test_stopped_e2e import card, stopped, try_again

from workflow_factory import grant_consent, reject_step, run_flow, save_step

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web
INK = "rgb(228, 236, 246)"
REFUSING_CLIPBOARD = """Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { throw new Error('no') } } })"""
KEPT_CLIPBOARD = """window.__copied = []
Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (t) => { window.__copied.push(t) } } })"""
AT_CENTRE = """(b) => { const r = b.getBoundingClientRect()
  return b.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)) }"""


def more_menu(page):
    return page.locator("details.app-more")


def reread(page, endpoint):
    """Make the screen read its lists again (the window gets focus back) and wait until the answer has been drawn."""
    with page.expect_response(lambda response: endpoint in response.url):
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
    page.evaluate("() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))")


# --- 1: the More menu of the tab bar closes by itself ----------------------------------------------------------------

@pytest.mark.parametrize("how", ["tab", "escape", "outside"])
def test_the_more_menu_closes_when_a_tab_is_chosen_escape_is_pressed_or_the_page_is_clicked(tmp_path, how):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_test_id("tab-apps").click()
        page.get_by_test_id("app-more-toggle").click()
        assert more_menu(page).evaluate("(d) => d.open")
        if how == "tab":
            page.get_by_test_id("tab-home").click()
        elif how == "escape":
            page.keyboard.press("Escape")
        else:
            page.mouse.click(300, 400)
        assert not more_menu(page).evaluate("(d) => d.open")

        page.get_by_test_id("tab-home").click()
        new = page.get_by_test_id("new-flow")
        new.wait_for()
        assert new.evaluate(AT_CENTRE)  # nothing is over the button


def test_the_close_button_inside_the_more_menu_still_works(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_test_id("app-more-toggle").click()
        page.get_by_test_id("quit").click()
        page.get_by_test_id("closed").wait_for()


# --- 2: the first day says what is what in plain words ---------------------------------------------------------------

def test_the_three_stages_are_plain_words_that_are_not_tappable(tmp_path):
    with home(tmp_path) as (page, _):
        page.get_by_test_id("first-day").wait_for()
        stages = page.get_by_test_id("stages")
        text = page.get_by_test_id("first-day").inner_text()
        assert "Put in order" not in text and "join up by themselves" not in text
        assert page.get_by_role("heading", name="How it works").is_visible()
        assert stages.locator("li b").all_inner_texts() == ["Teach", "Choose the steps", "Let it repeat"]
        for stage in stages.locator("li").all():
            assert stage.evaluate("(e) => getComputedStyle(e).cursor") == "default"
        assert stages.locator("button, a, [role=button], [tabindex]").count() == 0


def test_the_teach_card_on_apps_is_one_clear_message_not_a_switched_off_node(tmp_path):
    with home(tmp_path) as (page, _):
        page.get_by_test_id("tab-apps").click()
        empty = page.get_by_test_id("apps-empty")
        empty.wait_for()
        assert empty.evaluate("(e) => getComputedStyle(e).color") == INK
        assert empty.evaluate("(e) => getComputedStyle(e).borderTopStyle") == "none"
        assert empty.get_by_role("heading", name="Teach it your first flow").evaluate("(e) => getComputedStyle(e).color") == INK
        assert empty.get_by_role("button", name="Copy this message").is_enabled()


# --- 3: Copy this message answers at once ----------------------------------------------------------------------------

def test_copy_this_message_changes_the_button_at_once(tmp_path):
    with home(tmp_path) as (page, _):
        page.add_init_script(KEPT_CLIPBOARD)
        page.reload()
        page.get_by_test_id("first-day").wait_for()
        copy = page.get_by_test_id("chat-message").get_by_role("button").first
        copy.click()
        copy.filter(has_text="Copied").wait_for()
        assert copy.locator("svg").count() == 1
        assert "Copy this message" not in copy.inner_text()
        assert len(page.evaluate("() => window.__copied")) == 1


def test_when_the_browser_refuses_to_copy_the_message_is_selected_and_the_words_say_to_press_ctrl_c(tmp_path):
    with home(tmp_path) as (page, _):
        page.add_init_script(REFUSING_CLIPBOARD)
        page.reload()
        page.get_by_test_id("first-day").wait_for()
        page.get_by_test_id("chat-message").get_by_role("button", name="Copy this message").click()
        page.get_by_test_id("chat-message").get_by_role("status").filter(has_text="Ctrl+C").wait_for()
        selected = page.evaluate("() => window.getSelection().toString()")
        assert selected.strip() == page.get_by_test_id("chat-text").inner_text().strip()


# --- 4: the search example finds something ---------------------------------------------------------------------------

def test_the_example_in_the_search_node_finds_a_program_that_has_a_save_action(tmp_path):
    save_step(tmp_path / "user.db", step("Save", "Alpha", app="excel.exe"))
    save_step(tmp_path / "user.db", step("Print", "Alpha", app="word.exe"))
    with home(tmp_path) as (page, _):
        apps_screen(page)
        field = page.get_by_test_id("apps-search")
        field.fill(field.get_attribute("placeholder").removeprefix("for example: "))
        page.get_by_test_id("apps-search-go").click()
        app_row(page, "excel.exe").wait_for()
        assert page.get_by_test_id("apps-none").count() == 0
        assert app_row(page, "word.exe").count() == 0


# --- 5: one honest line after Run now ---------------------------------------------------------------------------------

def test_after_run_now_the_row_has_one_line_about_the_last_run(tmp_path):
    db = tmp_path / "user.db"
    morning = put_flows(tmp_path)
    run_flow(morning, desktop=FakeDesktop(controls=[button("Alpha"), button("Beta")]), user_db=db)  # an older, good run
    with home(tmp_path) as (page, _):
        says(page, "morning", r"Worked .+ at \d\d:\d\d")
        run_button(page, "morning").click()
        result = page.get_by_test_id("flow-result-morning")
        result.wait_for()
        assert re.fullmatch(r"Worked .+ at \d\d:\d\d\. 2 steps finished\.", result.inner_text().strip())
        reread(page, "/api/flow-overview")  # the list is read again: still one line
        assert len(re.findall(r"orked", row(page, "morning").inner_text())) == 1


# --- 6: Try again keeps the list steady and says how it went where the finger was -------------------------------------

def test_try_again_answers_in_place_of_the_card_and_the_list_below_stays_put(tmp_path):
    stopped(tmp_path)
    put_flow(tmp_path, "evening", "Evening report", "open-menu")
    with home(tmp_path) as (page, _):
        card(page).wait_for()
        before = row(page, "evening").bounding_box()["y"]
        tapped = try_again(page).bounding_box()["y"]

        try_again(page).click()

        fixed = page.get_by_test_id("tried-weekly")
        fixed.filter(has_text="Fixed").wait_for()
        assert page.get_by_test_id("attention").is_visible()  # the red node did not just disappear
        assert abs(fixed.bounding_box()["y"] - tapped) < 200  # next to where the finger was
        reread(page, "/api/flow-overview")
        assert abs(row(page, "evening").bounding_box()["y"] - before) <= 60
        fixed.get_by_role("button", name="Hide").click()
        page.get_by_test_id("tried-weekly").wait_for(state="detached")


# --- 7: plain words on Take back, and a steady order of programs --------------------------------------------------------

def test_take_back_does_not_talk_about_teaching_in_a_chat_in_words_nobody_heard(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Send", "Alpha", app="mail.exe"))
    grant_consent(db, "mail.exe", "Send", "click")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "mail.exe").click()
        page.get_by_role("button", name="Take back").click()
        words = page.get_by_test_id("take-back-ask").inner_text()
        assert "while teaching" not in words and "chat" in words


def test_the_programs_keep_their_order_after_something_is_fixed(tmp_path):
    db = tmp_path / "user.db"
    for app in ("alpha.exe", "beta.exe", "zeta.exe"):
        save_step(db, step("Open", "Alpha", app=app))
    reject_step(db, "zeta.exe", "Open")
    order = "() => [...document.querySelectorAll('[data-testid^=app-row-]')].map((e) => e.dataset.testid)"
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "zeta.exe").wait_for()
        first = page.evaluate(order)
        assert first[0] == "app-row-zeta.exe"
        app_row(page, "zeta.exe").click()
        page.get_by_role("button", name="Allow again").click()
        page.get_by_test_id("app-allowed-Open").wait_for()
        reread(page, "/api/apps")
        assert page.evaluate(order) == first


# --- 8: the screens say flow, node and step, never chore, box, action or draft ----------------------------------------------

JARGON = re.compile(r"\bchores?\b|\bbox(?:es)?\b|\bactions?\b|\bdraft\b", re.IGNORECASE)
LABELS = """() => [...document.querySelectorAll('[aria-label], [title], [placeholder]')]
  .flatMap((e) => ['aria-label', 'title', 'placeholder'].map((a) => e.getAttribute(a)).filter(Boolean))"""


def test_the_screens_never_say_flow_node_action_or_draft(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_test_id("new-flow").click()
        page.get_by_test_id("flow-title").wait_for()
        assert page.get_by_test_id("flow-title").input_value() == "New flow"
        assert not JARGON.search(page.title())
        page.get_by_test_id("open-flows").click()
        page.get_by_test_id("new-flow").wait_for()
        assert page.get_by_test_id("new-flow").inner_text().strip() == "New flow"
        assert page.get_by_test_id("open-flows").inner_text().strip() == "Flows"
        everything = page.locator("body").inner_text() + " ".join(page.evaluate(LABELS))
        everything = everything.replace("React Flow", "")  # the library's credit in the canvas corner stays as it is
        assert not JARGON.search(everything), JARGON.findall(everything)
        page.get_by_test_id("open-flows").click()
        assert page.get_by_role("button", name="Run now").count() == 1


# --- 9: rename says it worked --------------------------------------------------------------------------------------------

def test_rename_says_renamed_in_the_row(tmp_path):
    put_flows(tmp_path)
    with served(tmp_path) as (page, _, _):
        says(page, "morning", "Never run")
        more(page, "morning")
        page.get_by_test_id("more-rename-morning").click()
        page.get_by_test_id("rename-input-morning").fill("Morning numbers")
        page.get_by_test_id("rename-save-morning").click()
        note = page.get_by_test_id("renamed-morning")
        note.wait_for()
        assert "Renamed" in note.inner_text()
        assert row(page, "morning").get_by_test_id("renamed-morning").is_visible()
