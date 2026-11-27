"""Choosing a box explains it underneath (editor rethink, ticket 08). Opt-in: `pytest -m web`.

The built editor in a headless browser against the real API, with the stand-in desktop and Windows scheduler.
"""

import pytest
from test_canvas_e2e import choose, editor, node, open_flow, three_actions, three_in_a_row

from workflow_factory import Flow, Node, load_flow, save_flow, save_step

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


def strip(page):
    return page.get_by_role("region", name="About the chosen box")


def test_choosing_a_box_says_what_it_does_and_how_often_it_has_worked_and_shows_no_trust_label(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha", effect="revealed", factory_successes=2))
    save_step(db, step("save-file", "Beta", action="type_value"))
    save_flow(db, Flow(id="row", nodes=[Node("a", "open-menu"), Node("b", "save-file")], edges=[("a", "b")]))
    with editor(tmp_path) as page:
        open_flow(page, "row", "b")
        assert "Choose a box" in strip(page).inner_text()  # nothing chosen yet

        choose(page, "a")
        said = strip(page).inner_text()
        assert "Presses the Alpha button in Paint." in said and "It has worked 2 times." in said

        choose(page, "b")
        said = strip(page).inner_text()
        assert "Types text into the Beta button in Paint." in said and "worked" not in said  # no effect to compare with

        text = page.locator(".canvas").inner_text() + page.get_by_test_id("safety-summary").inner_text()
        assert not any(word in text for word in ("Trusted", "On trial", "Rejected", "Needs a re-check", "on trial"))


def test_a_system_box_is_explained_without_what_was_typed_into_it(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="s", nodes=[
        Node("w", kind="wait", fields={"seconds": {"value": 1}}), Node("a", "open-menu")], edges=[("w", "a")]))
    with editor(tmp_path) as page:
        open_flow(page, "s", "a")
        choose(page, "w")
        assert "Waits a while before the chore goes on." in strip(page).inner_text()


def test_settings_opens_the_detail_only_for_a_box_that_has_settings(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="j", nodes=[Node("a", "open-menu"), Node("j", kind="join")], edges=[("a", "j")]))
    with editor(tmp_path) as page:
        open_flow(page, "j", "j")
        choose(page, "j")
        assert page.get_by_test_id("open-detail").count() == 0  # a join has nothing to set

        choose(page, "a")
        page.get_by_test_id("open-detail").click()
        detail = page.get_by_test_id("detail")
        for pane in ("Data in", "Settings", "Data out"):
            assert detail.get_by_role("region", name=pane).count() == 1
        assert detail.get_by_test_id("test-node").count() == 0  # the test lives in the strip now
        assert detail.get_by_test_id("detail-delete").count() == 0  # so does removing


def test_test_this_box_warns_about_the_mouse_and_keyboard_before_it_does_anything(tmp_path):
    db = three_actions(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    save_flow(db, Flow(id="row", nodes=[Node("a", "open-menu"), Node("b", "save-file")], edges=[("a", "b")]))
    with editor(tmp_path, desktop) as page:
        open_flow(page, "row", "b")
        choose(page, "b")
        before = len(desktop.clicks)
        strip(page).get_by_test_id("test-node").click()

        warning = page.get_by_test_id("test-warning")
        assert "mouse and keyboard" in warning.inner_text()
        assert len(desktop.clicks) == before  # nothing happened yet
        warning.get_by_role("button", name="Cancel").click()
        assert page.get_by_test_id("test-warning").count() == 0 and len(desktop.clicks) == before

        strip(page).get_by_test_id("test-node").click()
        page.get_by_test_id("confirm-test").click()
        page.get_by_test_id("test-result").filter(has_text="Test finished").wait_for(timeout=10_000)
        assert len(desktop.clicks) == before + 1  # only that box ran


def test_remove_box_takes_the_chosen_box_and_its_lines_away(tmp_path):
    three_in_a_row(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "row", "c")
        choose(page, "b")
        strip(page).get_by_role("button", name="Remove box").click()

        assert node(page, "b").count() == 0 and page.locator(".react-flow__edge").count() == 0
        assert "Choose a box" in strip(page).inner_text()


def test_a_box_chosen_in_a_narrow_window_is_explained_inside_the_window_with_readable_buttons(tmp_path):
    three_in_a_row(tmp_path)
    with editor(tmp_path, size=(390, 740)) as page:
        open_flow(page, "row", "c")
        choose(page, "a")
        box = strip(page).bounding_box()

        assert box["x"] >= 0 and box["x"] + box["width"] <= 390
        assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
        for name in ("Test this box", "Remove box"):
            shown = strip(page).get_by_role("button", name=name).bounding_box()
            assert shown["height"] >= 40 and shown["x"] >= 0 and shown["x"] + shown["width"] <= 390


def test_the_strip_is_reached_and_used_by_keyboard_alone(tmp_path):
    three_in_a_row(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "row", "c")
        node(page, "a").press("Space")
        strip(page).get_by_test_id("test-node").press("Enter")
        page.get_by_test_id("confirm-test").press("Enter")
        page.get_by_test_id("test-result").filter(has_text="Test finished").wait_for(timeout=10_000)
        strip(page).get_by_test_id("delete-node").press("Enter")
        assert node(page, "a").count() == 0
        assert load_flow(tmp_path / "user.db", None, "row").nodes[0].id == "a"  # nothing was saved by pressing Remove
