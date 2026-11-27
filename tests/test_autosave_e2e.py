"""Changes are kept as they are made and "Undo" takes them back (editor rethink, ticket 06). Opt-in: `pytest -m web`.

The built editor in a headless browser against the real API, with the stand-in desktop and Windows scheduler.
"""

import re

import pytest
from test_canvas_e2e import editor, node, open_flow, three_actions

from workflow_factory import Flow, Node, load_flow, save_flow

pytestmark = pytest.mark.web

SAVED = re.compile("^Saved$")


def seed(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="morning", nodes=[Node("n1", "open-menu"), Node("n2", "save-file")]))
    return db


def stored(db, name="morning"):
    return [n.step or n.kind for n in load_flow(db, None, name).nodes]


def status(page, words):
    try:
        page.get_by_test_id("run-status").filter(has_text=re.compile(f"^{words}$")).wait_for(timeout=10_000)
    except Exception as e:
        raise AssertionError(f"{words!r} expected, the screen said {page.get_by_test_id('run-status').inner_text()!r}: "
                             f"{page.locator('.notices').inner_text()!r}") from e


def add(page, query, test_id):
    page.get_by_test_id("search").fill(query)
    page.get_by_test_id(test_id).click()
    page.get_by_test_id("search").fill("")


def count(page):
    return page.locator(".react-flow__node").count()


def test_a_change_is_stored_without_a_button_and_a_reload_shows_it(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        assert page.get_by_test_id("save").count() == 0
        add(page, "wait", "system-wait")
        status(page, "Saved")
        assert stored(db) == ["open-menu", "save-file", "wait"]

        page.reload()  # the flow screen comes back with the flow
        node(page, "n1").wait_for()
        assert count(page) == 3


def test_moving_a_node_and_naming_the_flow_are_kept_too(tmp_path):
    seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        page.get_by_test_id("flow-title").fill("Early start")
        status(page, "Saved")
        a = node(page, "n2").bounding_box()
        page.mouse.move(a["x"] + 20, a["y"] + 20)
        page.mouse.down()
        page.mouse.move(a["x"] + 160, a["y"] + 60, steps=8)
        page.mouse.up()
        page.wait_for_timeout(1200)
        status(page, "Saved")
        page.reload()  # the flow screen comes back with the flow
        node(page, "n2").wait_for()
        assert page.get_by_test_id("flow-title").input_value() == "Early start"
        after = node(page, "n2").bounding_box()
        assert abs(after["x"] - a["x"]) > 20 or abs(after["y"] - a["y"]) > 20


def test_a_new_flow_is_stored_when_it_has_a_node_and_not_before(tmp_path):
    db = three_actions(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("tab-home").click()
        page.get_by_test_id("new-flow").click()
        page.get_by_test_id("flow-title").fill("Fresh one")
        page.wait_for_timeout(1000)
        assert not db.exists() or load_flow(db, None, "fresh-one") is None
        add(page, "wait", "system-wait")
        status(page, "Saved")
        assert stored(db, "fresh-one") == ["wait"]


def test_a_change_made_elsewhere_is_shown_and_the_person_chooses(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        save_flow(db, Flow(id="morning", nodes=[Node("n1", "close-node")]))  # another window
        add(page, "wait", "system-wait")
        notice = page.get_by_test_id("changed-elsewhere")
        notice.wait_for()
        page.wait_for_timeout(800)
        assert stored(db) == ["close-node"]  # nothing was replaced
        assert page.get_by_test_id("run-status").inner_text() != "Saved"

        notice.get_by_role("button", name="Keep what I see").click()
        status(page, "Saved")
        assert stored(db) == ["open-menu", "save-file", "wait"]
        assert notice.count() == 0


def test_the_person_can_take_the_other_version_instead(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        save_flow(db, Flow(id="morning", nodes=[Node("n1", "close-node")]))
        add(page, "wait", "system-wait")
        page.get_by_test_id("changed-elsewhere").get_by_role("button", name="Show the other version").click()
        page.wait_for_function("document.querySelectorAll('.react-flow__node').length === 1")
        status(page, "Saved")
        assert stored(db) == ["close-node"]
        page.wait_for_timeout(800)
        assert stored(db) == ["close-node"]


def test_a_value_a_field_cannot_hold_is_not_stored_and_the_node_says_so(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        add(page, "wait", "system-wait")
        status(page, "Saved")
        page.locator('.react-flow__node[data-id="n3"]').dblclick()
        page.get_by_test_id("value-seconds").fill("2,5")
        page.get_by_test_id("close-detail").click()
        status(page, "Not saved")
        assert "Seconds to wait" in page.get_by_test_id("not-saved").inner_text()
        assert "Not saved" in page.get_by_test_id("node-n3").inner_text()
        page.wait_for_timeout(800)
        wait = [n for n in load_flow(db, None, "morning").nodes if n.kind == "wait"][0]
        assert wait.fields["seconds"]["value"] == 5  # what was stored before is untouched

        page.locator('.react-flow__node[data-id="n3"]').dblclick()
        assert page.get_by_test_id("value-seconds").input_value() == "2,5"  # still there to fix
        page.get_by_test_id("value-seconds").fill("7")
        page.get_by_test_id("close-detail").click()
        status(page, "Saved")
        wait = [n for n in load_flow(db, None, "morning").nodes if n.kind == "wait"][0]
        assert wait.fields["seconds"]["value"] == 7


def test_a_node_that_is_not_finished_is_held_back_and_says_what_it_needs(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        add(page, "two paths", "system-if")
        status(page, "Not saved")
        assert "yes" in page.get_by_test_id("not-saved").inner_text().lower()
        assert stored(db) == ["open-menu", "save-file"]
        add(page, "wait", "system-wait")  # the new node joins after the last one: the yes path
        status(page, "Saved")
        assert "if" in stored(db)


def test_undo_takes_back_changes_one_after_another(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        undo = page.get_by_test_id("undo")
        assert undo.is_disabled()
        add(page, "wait", "system-wait")
        page.wait_for_timeout(700)
        add(page, "wait", "system-wait")
        assert count(page) == 4
        undo.click()
        assert count(page) == 3
        undo.click()
        assert count(page) == 2 and undo.is_disabled()
        status(page, "Saved")
        assert stored(db) == ["open-menu", "save-file"]  # the undone state is kept too


def test_undo_from_the_keyboard_and_a_settings_change_is_one_step(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        add(page, "wait", "system-wait")
        page.wait_for_timeout(700)
        page.locator('.react-flow__node[data-id="n3"]').dblclick()
        page.get_by_test_id("value-seconds").fill("9")
        page.get_by_test_id("close-detail").click()
        status(page, "Saved")
        page.get_by_test_id("undo").focus()
        page.keyboard.press("Enter")
        status(page, "Saved")
        wait = [n for n in load_flow(db, None, "morning").nodes if n.kind == "wait"][0]
        assert wait.fields["seconds"]["value"] == 5
        page.locator(".canvas").click(position={"x": 5, "y": 5})  # away from any field: the shortcut takes the node back
        page.keyboard.press("Control+z")
        page.wait_for_function("document.querySelectorAll('.react-flow__node').length === 2")


def test_removing_a_node_offers_undo_and_undo_brings_it_back(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        node(page, "n2").click()
        page.get_by_test_id("delete-node").click()
        notice = page.get_by_test_id("removed-notice")
        notice.wait_for()
        status(page, "Saved")
        assert stored(db) == ["open-menu"]
        notice.get_by_role("button", name="Undo").click()
        node(page, "n2").wait_for()
        status(page, "Saved")
        assert stored(db) == ["open-menu", "save-file"] and notice.count() == 0


def test_a_node_removed_with_the_key_offers_undo_too(tmp_path):
    seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        node(page, "n2").click()
        page.keyboard.press("Delete")
        page.get_by_test_id("removed-notice").get_by_role("button", name="Undo").click()
        node(page, "n2").wait_for()


def test_run_uses_exactly_what_is_on_screen(tmp_path):
    db = seed(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "morning", "n2")
        node(page, "n2").click()
        page.get_by_test_id("delete-node").click()
        page.get_by_test_id("run").click()  # at once, before the change has had time to be stored by itself
        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for(timeout=10_000)
        assert stored(db) == ["open-menu"]


@pytest.mark.parametrize("width,height", [(683, 384), (390, 740)])
def test_the_new_controls_fit_and_work_from_the_keyboard(tmp_path, width, height):
    seed(tmp_path)
    with editor(tmp_path, size=(width, height)) as page:
        open_flow(page, "morning", "n2")
        add(page, "wait", "system-wait")
        for test_id in ("undo", "run-status"):
            rect = page.get_by_test_id(test_id).bounding_box()
            assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width, test_id
        assert page.evaluate(f"() => document.documentElement.scrollWidth <= {width}")
        shown = page.get_by_test_id("undo").bounding_box()
        assert shown["height"] >= 40
        page.get_by_test_id("undo").focus()
        page.keyboard.press("Space")
        page.wait_for_function("document.querySelectorAll('.react-flow__node').length === 2")
        node(page, "n2").click()
        page.get_by_test_id("delete-node").click()
        notice = page.get_by_test_id("removed-notice").get_by_role("button", name="Undo")
        rect = notice.bounding_box()
        assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width and rect["height"] >= 40
        assert notice.inner_text().strip() == "Undo"
