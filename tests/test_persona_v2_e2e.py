"""What the non-technical personas could not do on the finished model v2 (mutehand-v2 ticket 10), each fixed once and kept fixed.
Driven in the built editor. Opt-in: `pytest -m web`."""

import pytest
from test_apps_e2e import app_row, apps_screen
from test_canvas_e2e import editor
from test_flow_more_e2e import more, served
from test_home_e2e import home, put_flow, put_flows, says

from workflow_factory import grant_consent, save_step
from workflow_factory.consent import consents

from fake_desktop import step

pytestmark = pytest.mark.web


# --- 2: every flow deleted lately has its own Undo ---------------------------------------------------------------------

def test_two_deleted_flows_each_keep_their_undo_and_both_survive_a_reload(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    with served(tmp_path) as (page, _, _):
        says(page, "weekly", "Never run")
        for flow in ("morning", "weekly"):
            more(page, flow)
            page.get_by_test_id(f"more-delete-{flow}").click()
            page.get_by_test_id(f"flow-{flow}").wait_for(state="detached")
        notices = page.get_by_test_id("deleted-notice")
        notices.nth(1).wait_for()
        assert notices.count() == 2
        page.reload()
        notices.nth(1).wait_for()
        assert notices.count() == 2
        notices.filter(has_text="Morning report").get_by_role("button", name="Undo").click()
        page.get_by_test_id("flow-morning").wait_for()
        assert notices.count() == 1 and "Weekly export" in notices.inner_text()
        notices.get_by_role("button", name="Undo").click()
        page.get_by_test_id("flow-weekly").wait_for()
        assert notices.count() == 0


# --- 3: a confirmation never moves the row's buttons -------------------------------------------------------------------

def spots(page, flow):
    """Where the row's buttons are, so that a second tap lands on the same thing."""
    return {name: page.get_by_test_id(f"{name}-{flow}").bounding_box() for name in ("run-now", "daily", "more")}


@pytest.mark.parametrize("width,height", [(1280, 800), (390, 740)])
def test_saving_a_daily_time_or_a_new_name_leaves_the_rows_buttons_where_they_were(tmp_path, width, height):
    put_flows(tmp_path)
    with served(tmp_path) as (page, _, _):
        page.set_viewport_size({"width": width, "height": height})
        says(page, "morning", "Never run")
        before = spots(page, "morning")

        page.get_by_test_id("daily-morning").click()
        page.get_by_test_id("daily-set-morning").click()
        page.get_by_test_id("daily-saved-morning").wait_for()
        page.get_by_test_id("daily-set-morning").wait_for(state="detached")
        after = spots(page, "morning")
        assert after["more"]["y"] == before["more"]["y"] and after["run-now"] == before["run-now"]
        assert abs(after["more"]["x"] - before["more"]["x"]) <= 1

        more(page, "morning")
        page.get_by_test_id("more-rename-morning").click()
        page.get_by_test_id("rename-input-morning").fill("Morning")
        page.get_by_test_id("rename-save-morning").click()
        page.get_by_test_id("renamed-morning").wait_for()
        now = spots(page, "morning")
        assert all(abs(after[n][axis] - now[n][axis]) <= 1 for n in after for axis in ("x", "y"))


# --- 4: Run now in a flow with nothing in it says why it cannot run -----------------------------------------------------------

def test_run_now_in_a_new_empty_flow_says_it_has_nothing_to_run_and_looks_unavailable(tmp_path):
    many_programs(tmp_path, 1)
    with editor(tmp_path, size=(390, 740)) as page:
        run = page.get_by_test_id("run")
        run.wait_for()
        assert run.is_disabled() and "Nothing to run yet" in run.inner_text()
        assert run.evaluate("(b) => getComputedStyle(b).borderStyle") == "dashed"  # not the filled look of a button that can be pressed
        assert "Add your first node" in page.locator(".empty-canvas").inner_text()  # what to do is on the screen, not in a tooltip


# --- 5: Escape backs out of the take-back question, and a pasted wall of text stays on the screen ---------------------------

def test_escape_leaves_the_take_back_question_without_taking_anything_back(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("Send it", "Send", app="mail.exe"))
    grant_consent(db, "mail.exe", "Send", "click")
    with home(tmp_path) as (page, _):
        apps_screen(page)
        app_row(page, "mail.exe").click()
        card = page.get_by_test_id("app-card-mail.exe")
        card.get_by_role("button", name="Take back").click()
        card.get_by_test_id("take-back-ask").wait_for()
        page.keyboard.press("Escape")
        card.get_by_test_id("take-back-ask").wait_for(state="detached")
        assert len(consents(db)) == 1
        assert page.evaluate("document.activeElement.dataset.testid") == "app-take-back-Send-click"  # the focus is where it was


def test_a_pasted_wall_of_text_echoed_in_no_results_stays_inside_the_screen(tmp_path):
    save_step(tmp_path / "user.db", step("open", "Alpha", app="excel.exe"))
    with home(tmp_path) as (page, _):
        page.set_viewport_size({"width": 390, "height": 740})
        apps_screen(page)
        page.get_by_test_id("apps-search").fill("x" * 100_000)
        page.get_by_test_id("apps-search-go").click()
        page.get_by_test_id("apps-none").wait_for()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.get_by_test_id("apps-none").evaluate("(e) => e.scrollWidth <= e.clientWidth")  # the text wraps inside its box
        assert page.locator("main").evaluate("(e) => e.scrollWidth <= e.clientWidth")  # and the screen does not scroll sideways


# --- 7: the name at the top leads Home ---------------------------------------------------------------------------------------

def test_the_name_at_the_top_left_goes_home_from_every_screen(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        brand = page.get_by_role("button", name="Mutehand", exact=False).first
        apps_screen(page)
        brand.click()
        page.get_by_role("heading", name="Your flows").wait_for()
        assert page.get_by_test_id("tab-home").get_attribute("aria-current") == "page"
        page.get_by_test_id("open-flow-morning").click()
        page.get_by_test_id("flow-title").wait_for()
        brand.click()
        page.get_by_role("heading", name="Your flows").wait_for()


# --- 8: New flow makes no flow until it has a node ---------------------------------------------------------------------------

def test_tapping_new_flow_twice_leaves_no_empty_flow_in_the_list(tmp_path):
    put_flows(tmp_path)
    with served(tmp_path) as (page, _, _):
        says(page, "morning", "Never run")
        for _ in range(2):
            page.get_by_test_id("new-flow").click()
            page.get_by_test_id("flow-title").wait_for()
            page.get_by_test_id("back-home").click()
            page.get_by_role("heading", name="Your flows").wait_for()
        page.get_by_test_id("new-flow").dblclick()  # two quick taps on the same button
        page.get_by_test_id("flow-title").wait_for()
        page.get_by_test_id("back-home").click()
        page.get_by_role("heading", name="Your flows").wait_for()
        says(page, "morning", "Never run")
        assert page.locator('[data-testid^="open-flow-"]').count() == 1  # only Morning report exists


def test_an_empty_flow_exists_only_when_a_node_was_added_and_then_removed(tmp_path):
    """The one way to get "New flow" in the list with nothing in it: its first node made it, and the person took the node out."""
    put_flows(tmp_path)
    with served(tmp_path) as (page, _, _):
        says(page, "morning", "Never run")
        page.get_by_test_id("new-flow").click()
        page.get_by_test_id("search").fill("wait")
        page.get_by_test_id("system-wait").click()
        page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
        page.locator(".react-flow__node").first.click()
        page.get_by_test_id("delete-node").click()
        page.get_by_test_id("removed-notice").wait_for()
        page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
        page.get_by_test_id("back-home").click()
        says(page, "new-flow", "Never run")  # kept by the earlier decision: a flow is made by its first node


# --- 1: a step learned for many programs stays short on its card, and asking which one stays on the screen -------------------

def many_programs(tmp_path, count=30):
    db = tmp_path / "user.db"
    for n in range(count):
        save_step(db, step("Save", f"Save {n}", app=f"program{n:02}.exe"))


def test_a_step_card_names_three_programs_and_counts_the_rest(tmp_path):
    many_programs(tmp_path)
    with editor(tmp_path) as page:
        card = page.get_by_test_id("palette-Save")
        card.wait_for()
        hint = card.locator("small")
        assert "+27 more" in hint.inner_text() and hint.inner_text().count(",") == 2
        assert hint.get_attribute("title").count(",") == 29  # the whole list is one hover or one read away


@pytest.mark.parametrize("how", ["outside", "escape-elsewhere"])
def test_the_which_program_question_fits_a_phone_keeps_cancel_in_view_and_closes_by_itself(tmp_path, how):
    many_programs(tmp_path)
    with editor(tmp_path, size=(390, 740)) as page:
        page.get_by_test_id("palette-Save").click()
        chooser = page.get_by_test_id("technology-chooser")
        chooser.wait_for()
        cancel = chooser.get_by_role("button", name="Cancel")
        box = cancel.bounding_box()
        assert 0 <= box["y"] and box["y"] + box["height"] <= page.viewport_size["height"]  # Cancel is on the screen
        assert chooser.bounding_box()["height"] <= page.viewport_size["height"] * 0.7
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        if how == "outside":
            page.get_by_role("heading", name="Add a node").click()
        else:
            page.get_by_test_id("search").focus()
            page.keyboard.press("Escape")
        chooser.wait_for(state="detached")
        assert page.locator(".react-flow__node").count() == 0
