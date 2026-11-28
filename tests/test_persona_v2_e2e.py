"""What the non-technical personas could not do on the finished model v2 (mutehand-v2 ticket 10), each fixed once and kept fixed.
Driven in the built editor. Opt-in: `pytest -m web`."""

import pytest
from test_canvas_e2e import editor
from test_flow_more_e2e import more, served
from test_home_e2e import put_flow, put_flows, says

from workflow_factory import save_step

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
