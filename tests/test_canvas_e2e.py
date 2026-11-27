"""The canvas reads top to bottom and its boxes join by themselves (editor rethink, ticket 07). Opt-in: `pytest -m web`.

The built editor in a headless browser against the real API, with the stand-in desktop and Windows scheduler.
"""

import json
import re
import sqlite3
from contextlib import closing, contextmanager
from itertools import pairwise

import pytest
from fake_scheduler import FakeScheduler
from test_editor_e2e import DIST, open_page

from workflow_factory import Flow, Node, load_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.flows import flow_summaries

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


@contextmanager
def editor(tmp_path, desktop=None, size=(1280, 860), screen="editor"):
    """A headless page on the built editor over this test's database."""
    from playwright.sync_api import sync_playwright

    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: desktop,
                       token="e2e-token", web_dir=DIST, schedule_runner=FakeScheduler())
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server, screen)
            page.set_viewport_size({"width": size[0], "height": size[1]})
            page.set_default_timeout(8_000)
            yield page
            browser.close()
    finally:
        server.stop()


def three_actions(tmp_path):
    for name, control in (("open-menu", "Alpha"), ("save-file", "Beta"), ("close-box", "Gamma")):
        save_step(tmp_path / "user.db", step(name, control))
    return tmp_path / "user.db"


def node(page, node_id):
    return page.locator(f'.react-flow__node[data-id="{node_id}"]')


def open_flow(page, flow_id, last):
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id(f"flow-{flow_id}").click()
    node(page, last).wait_for()
    page.wait_for_timeout(500)  # the canvas has fitted it into the window


def save(page):
    page.get_by_test_id("run-status").filter(has_text=re.compile("^Saved$")).wait_for()


def middle(page, node_id):
    box = node(page, node_id).bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def lines(flow):
    return sorted(tuple(edge) for edge in flow.all_edges)


BRANCHED = [
    Node("a", "open-menu"),
    Node("d", kind="if", fields={"condition": {"value": True}}, then="b", otherwise="c"),
    Node("b", "save-file"), Node("c", "close-box"),
    Node("r", kind="foreach", fields={"items": {"value": [1]}}, body="x"), Node("x", "open-menu"),
]
WIRES = [("a", "d"), ("d", "b"), ("d", "c"), ("b", "r")]


def drawn_left_to_right(tmp_path):
    """A flow stored with the positions the earlier canvas gave it: one column per distance from the start."""
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="old", nodes=BRANCHED, edges=WIRES))
    across = {n: {"x": 60 + column * 250, "y": 60 + row * 140} for n, column, row in (
        ("a", 0, 0), ("d", 1, 0), ("b", 2, 0), ("c", 2, 1), ("r", 3, 0), ("x", 4, 0))}
    with closing(sqlite3.connect(db)) as opened, opened:
        opened.execute("CREATE TABLE flow_layout (id TEXT PRIMARY KEY, positions TEXT NOT NULL)")
        opened.execute("INSERT INTO flow_layout VALUES ('old', ?)", (json.dumps(across),))
    return db


def test_a_flow_drawn_left_to_right_opens_top_to_bottom_and_keeps_every_box_and_line(tmp_path):
    db = drawn_left_to_right(tmp_path)
    before = load_flow(db, None, "old")
    with editor(tmp_path) as page:
        open_flow(page, "old", "x")

        assert page.locator(".react-flow__node").count() == 6 and page.locator(".react-flow__edge").count() == 5
        for source, target in [*WIRES, ("r", "x")]:
            above, below = node(page, source).bounding_box(), node(page, target).bounding_box()
            assert above["y"] + above["height"] < below["y"], (source, target)
        assert middle(page, "b")[0] < middle(page, "d")[0] < middle(page, "c")[0]  # yes on the left, no on the right
        labels = page.locator(".react-flow__edge-text").all_text_contents()
        assert sorted(labels) == ["each item", "no", "yes"]
        box = node(page, "a").bounding_box()
        for kind, edge_y in (("target", box["y"]), ("source", box["y"] + box["height"])):
            handle = node(page, "a").locator(f".react-flow__handle.{kind}").bounding_box()
            assert abs(handle["y"] + handle["height"] / 2 - edge_y) < 4, kind
            assert abs(handle["x"] + handle["width"] / 2 - middle(page, "a")[0]) < 4, kind

        save(page)
    after = load_flow(db, None, "old")
    assert after.nodes == before.nodes and lines(after) == lines(before)


def add(page, *entries):
    for entry in entries:
        page.get_by_test_id(entry).click()
        page.wait_for_timeout(300)  # the canvas re-fits


def choose(page, node_id):
    node(page, node_id).click()


def only(db):
    """The one chore a test built: it is kept under the name it had when its first box was added."""
    return next(f["id"] for f in flow_summaries(db, None))


def stored_wires(db, name=None):
    return lines(load_flow(db, None, name or only(db)))


def save_as(page, title="made"):
    page.get_by_test_id("flow-title").fill(title)
    save(page)


def test_boxes_join_by_themselves_after_the_chosen_box_or_the_last_one(tmp_path):
    db = three_actions(tmp_path)
    with editor(tmp_path) as page:
        add(page, "palette-open-menu", "palette-save-file")  # n1, n2: after the last one
        assert page.get_by_test_id("unwired").count() == 0
        assert node(page, "n1").bounding_box()["y"] < node(page, "n2").bounding_box()["y"]

        choose(page, "n1")
        add(page, "palette-close-box", "palette-open-menu")  # n3 goes between n1 and n2, then n4 after n3
        tops = [node(page, n).bounding_box()["y"] for n in ("n1", "n3", "n4", "n2")]
        assert tops == sorted(tops) and len(set(tops)) == 4
        save_as(page)

        assert stored_wires(db) == [("n1", "n3"), ("n3", "n4"), ("n4", "n2")]


def test_the_two_paths_of_a_decision_are_labelled_and_filled_by_adding_boxes(tmp_path):
    db = three_actions(tmp_path)
    with editor(tmp_path) as page:
        add(page, "palette-open-menu", "system-if", "palette-save-file")  # n3 takes the yes path
        choose(page, "n2")
        add(page, "palette-close-box")  # n4 the no path

        assert sorted(page.locator(".react-flow__edge-text").all_text_contents()) == ["no", "yes"]
        assert middle(page, "n3")[0] < middle(page, "n2")[0] < middle(page, "n4")[0]
        save_as(page)

        decision = load_flow(db, None, only(db)).nodes[1]
        assert (decision.then, decision.otherwise) == ("n3", "n4")


def test_a_third_line_out_of_a_decision_is_refused_in_words(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="forked", edges=[("d", "b"), ("d", "c")], nodes=[
        Node("d", kind="if", fields={"condition": {"value": True}}, then="b", otherwise="c"),
        Node("b", "save-file"), Node("c", "close-box"), Node("e", "open-menu")]))
    with editor(tmp_path) as page:
        open_flow(page, "forked", "e")
        node(page, "d").press("Space")
        page.get_by_test_id("connect-to").select_option("e")

        assert "two paths" in page.get_by_test_id("error").inner_text()
        assert page.locator(".react-flow__edge").count() == 2


def test_a_repeat_takes_the_next_action_and_a_start_box_leads_to_the_first_one(tmp_path):
    db = three_actions(tmp_path)
    with editor(tmp_path) as page:
        add(page, "system-foreach", "palette-open-menu", "palette-save-file")  # n2 is repeated, n3 follows
        page.get_by_text("Other boxes").click()
        add(page, "system-manual-trigger")  # n4 goes above the first box
        assert page.get_by_test_id("unwired").count() == 0
        assert node(page, "n4").bounding_box()["y"] < node(page, "n1").bounding_box()["y"]
        save_as(page)

        flow = load_flow(db, None, only(db))
        assert flow.nodes[0].body == "n2" and sorted(flow.edges) == [("n1", "n3"), ("n4", "n1")]


def test_a_recipe_joins_after_the_last_box_as_a_chain(tmp_path):
    from workflow_factory.recipes import apply_recipe, save_recipe

    db = three_actions(tmp_path)
    save_recipe(db, "two-presses", [{"hole": name, "role": "button", "control_name": name} for name in ("Alpha", "Beta")])
    apply_recipe(db, FakeDesktop(controls=[button("Alpha"), button("Beta")]), "two-presses")
    with editor(tmp_path) as page:
        add(page, "palette-close-box", "recipe-two-presses")
        node(page, "n3").wait_for()
        assert page.get_by_test_id("unwired").count() == 0
        save_as(page)

        assert stored_wires(db) == [("n1", "n2"), ("n2", "n3")]


def panel(page):
    return page.get_by_role("complementary", name="Add a box")


def offered(page):
    return panel(page).get_by_role("list", name="Actions").get_by_role("button").all_inner_texts()


def test_the_panel_offers_only_the_chosen_apps_actions_and_finds_them_by_plain_words(tmp_path):
    db = three_actions(tmp_path)
    save_step(db, step("write-text", "Alpha", app="word.exe"))
    with editor(tmp_path) as page:
        page.get_by_test_id("palette-open-menu").wait_for()
        assert panel(page).get_by_role("heading", name="Add a box").is_visible()
        assert offered(page) == ["close-box", "open-menu", "save-file"]

        page.get_by_test_id("app-name").select_option("word.exe")
        page.get_by_test_id("palette-write-text").wait_for()
        assert offered(page) == ["write-text"]

        page.get_by_test_id("app-name").select_option("paint.exe")
        find = page.get_by_role("searchbox", name="Find an action")
        find.fill("file save")  # plain words, in any order
        page.get_by_test_id("palette-open-menu").wait_for(state="detached")
        assert offered(page) == ["save-file"]
        find.fill("write text")  # another app's action is not offered
        panel(page).get_by_text("Nothing matches").wait_for()


def test_decisions_repeats_and_waits_are_in_plain_words_and_every_other_box_and_recipe_is_still_there(tmp_path):
    from workflow_factory.recipes import save_recipe

    db = three_actions(tmp_path)
    save_recipe(db, "two-presses", [{"hole": name, "role": "button", "control_name": name} for name in ("Alpha", "Beta")])
    with editor(tmp_path) as page:
        page.get_by_test_id("recipe-two-presses").wait_for()
        decisions = panel(page).get_by_role("region", name="Decisions and repeats")
        assert decisions.get_by_role("button").all_inner_texts() == ["Two paths: yes or no", "Repeat for each", "Wait a while"]
        assert panel(page).get_by_role("heading", name="Recipes").is_visible()
        assert page.get_by_test_id("recipe-two-presses").is_visible()
        assert not page.get_by_test_id("system-compare").is_visible()  # kept under its own heading, closed at first

        page.get_by_text("Other boxes").click()
        for key in ("manual-trigger", "daily-trigger", "join", "stop", "compare", "and", "or", "not", "fixed", "convert",
                    "split", "join-text", "format", "regex", "get", "set", "math"):
            assert page.get_by_test_id(f"system-{key}").is_visible(), key

        add(page, "system-if")
        assert "Two paths: yes or no" in page.get_by_test_id("node-n1").inner_text()


def test_a_search_opens_the_other_boxes_that_match(tmp_path):
    three_actions(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("search").fill("compare")
        page.get_by_test_id("system-compare").wait_for()
        page.get_by_test_id("system-compare").click()
        node(page, "n1").wait_for()


def card(page, node_id):
    return page.get_by_test_id(f"node-{node_id}")


def says(page, node_id, words):
    card(page, node_id).filter(has_text=words).wait_for()
    mark = card(page, node_id).locator(".card-mark").filter(has_text=words)
    assert mark.locator("svg").count() == 1, "a mark and a word, never colour alone"


def three_in_a_row(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="row", nodes=[Node("a", "open-menu"), Node("b", "save-file"), Node("c", "close-box")],
                       edges=[("a", "b"), ("b", "c")]))
    return db


def test_the_boxes_of_a_stopped_run_say_done_stopped_here_and_not_reached(tmp_path):
    three_in_a_row(tmp_path)
    with editor(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Gamma")])) as page:  # Beta is not on screen
        open_flow(page, "row", "c")
        for node_id, title in (("a", "1. open-menu"), ("b", "2. save-file"), ("c", "3. close-box")):
            assert title in card(page, node_id).inner_text()
        assert "Not reached" not in card(page, "c").inner_text()  # nothing ran yet

        page.get_by_test_id("run").click()

        says(page, "a", "Done")
        says(page, "b", "Stopped here")
        says(page, "c", "Not reached")
        green = page.locator(".react-flow__edge.on")
        assert [e.get_attribute("data-id") for e in green.all()] == ["a-b"]  # the line it went down


def test_the_running_box_says_so_and_after_stop_nothing_is_left_running(tmp_path):
    three_in_a_row(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    desktop.click_seconds = 1.5
    with editor(tmp_path, desktop) as page:
        open_flow(page, "row", "c")
        page.get_by_test_id("run").click()
        says(page, "a", "Running")
        says(page, "c", "Not reached")

        page.get_by_test_id("stop").click()
        page.get_by_test_id("run-status").filter(has_text="Stopped by you").wait_for()

        assert page.locator(".react-flow__node").filter(has_text="Running").count() == 0
        says(page, "c", "Not reached")


def test_the_path_not_taken_is_not_reached(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="forked", edges=[("d", "b"), ("d", "c")], nodes=[
        Node("d", kind="if", fields={"condition": {"value": True}}, then="b", otherwise="c"),
        Node("b", "save-file"), Node("c", "close-box")]))
    with editor(tmp_path) as page:
        open_flow(page, "forked", "c")
        page.get_by_test_id("run").click()

        says(page, "b", "Done")
        says(page, "c", "Not reached")


# the person's clipboard is never touched: the page gets a stand-in
CLIPBOARD = """Object.defineProperty(navigator, 'clipboard', { value: { writeText: (text) => window.refuseCopy
  ? Promise.reject(new Error('refused')) : (window.copied = text, Promise.resolve()) } })"""


def stub_clipboard(page):
    page.add_init_script(CLIPBOARD)
    page.reload()


def test_a_missing_action_offers_the_message_to_send_in_a_chat_and_nothing_is_started(tmp_path):
    from workflow_factory.tutor import mark_private

    save_step(tmp_path / "user.db", step("open-chat", "Alice from accounts", app="zzqx.exe"))
    mark_private(tmp_path / "user.db", "zzqx.exe")
    desktop = FakeDesktop(controls=[button("Alice from accounts")], app="zzqx.exe")
    with editor(tmp_path, desktop) as page:
        sent = []
        stub_clipboard(page)
        page.on("request", lambda request: sent.append((request.method, request.url)))
        page.get_by_test_id("palette-open-chat").wait_for()
        teach = page.get_by_role("button", name="It is not here: teach it")
        assert page.get_by_test_id("chat-text").count() == 0

        page.get_by_test_id("search").fill("archive a chat")
        teach.press("Enter")
        message = "I want to teach you a new action in Zzqx: archive a chat"
        assert page.get_by_test_id("chat-text").inner_text() == message
        assert "chat" in page.get_by_test_id("chat-message").inner_text().lower() and teach.get_attribute("aria-expanded") == "true"

        page.keyboard.press("Tab")
        assert page.evaluate("() => document.activeElement.innerText").strip() == "Copy this message"
        page.keyboard.press("Enter")
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        assert page.evaluate("() => window.copied") == message
        assert "Alice" not in page.get_by_test_id("chat-message").inner_text()

        page.get_by_test_id("search").fill("")
        assert page.get_by_test_id("chat-text").inner_text() == "I want to teach you a new action in Zzqx: [what you want done]"
        assert page.get_by_text("Copied. Paste it in the chat.").count() == 0  # that was another message

        page.evaluate("() => { window.refuseCopy = true }")
        page.get_by_role("button", name="Copy this message").click()
        page.get_by_text("Could not copy by itself. The message is selected: press Ctrl+C, then paste it in the chat.").wait_for()

        assert {method for method, _ in sent} <= {"GET"} and desktop.calls == []  # it only shows words
        teach.click()
        assert page.get_by_test_id("chat-text").count() == 0


def test_with_nothing_learned_the_panel_still_says_how_to_teach(tmp_path):
    save_flow(tmp_path / "user.db", Flow(id="old", nodes=[Node("a", "open-menu")]))  # a chore whose action is not known here
    with editor(tmp_path, screen=None) as page:
        page.get_by_test_id("open-chore-old").click()
        panel(page).get_by_text("Nothing learned yet.").wait_for()
        page.get_by_role("button", name="It is not here: teach it").click()

        words = page.get_by_test_id("chat-text").inner_text()
        assert words == "I want to teach you a chore: [what you want done, and in which program]"


VIEW = "() => document.querySelector('.react-flow__viewport').style.transform"


def test_the_zoom_buttons_work_from_the_keyboard_and_show_everything_again(tmp_path):
    drawn_left_to_right(tmp_path)
    with editor(tmp_path) as page:
        open_flow(page, "old", "x")
        fitted = page.evaluate(VIEW)
        for name in ("Zoom in", "Zoom out"):
            before = page.evaluate(VIEW)
            page.get_by_role("button", name=name).press("Enter")
            page.wait_for_function(f"(was) => ({VIEW})() !== was", arg=before)
        page.get_by_role("button", name="Zoom in").press("Enter")
        page.get_by_role("button", name="Zoom in").press("Enter")
        page.get_by_role("button", name="Show everything").press("Enter")
        page.wait_for_timeout(500)

        assert page.evaluate(VIEW) == fitted
        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()
        for box in (n.bounding_box() for n in page.locator(".react-flow__node").all()):
            assert canvas["y"] <= box["y"] and box["y"] + box["height"] <= canvas["y"] + canvas["height"]


LONG = "Quill Ledger Professional Accounting Workbench for Teams and Families"
SMALL = """() => [...document.querySelectorAll('.search-panel button, .search-panel select, .search-panel input, '
    + '.search-panel summary, .zoom button')].filter((e) => e.offsetParent && e.getBoundingClientRect().height < 43.5)
    .map((e) => e.outerHTML.slice(0, 80))"""


@pytest.mark.parametrize("width,height", [(683, 384), (390, 740)])
def test_in_a_narrow_window_everything_added_fits_is_readable_and_works_from_the_keyboard(tmp_path, width, height):
    from test_editor_safety_e2e import CONTRAST

    from workflow_factory.tutor import observe

    long_step = "open-the-" + "very-" * 12 + "long-menu"
    save_step(tmp_path / "user.db", step(long_step, "Alpha", app="zzqx.exe"))
    observe(tmp_path / "user.db", FakeDesktop(controls=[], app="zzqx.exe", product_name=LONG))
    with editor(tmp_path, size=(width, height)) as page:
        stub_clipboard(page)
        entry = page.get_by_test_id(f"palette-{long_step}")
        entry.press("Enter")
        node(page, "n1").wait_for()
        page.get_by_text("Other boxes").press("Enter")
        page.get_by_test_id("system-join").press("Enter")
        node(page, "n2").wait_for()
        page.get_by_role("button", name="It is not here: teach it").press("Enter")
        page.get_by_role("button", name="Copy this message").press("Enter")
        page.get_by_text("Copied. Paste it in the chat.").wait_for()
        for name in ("Zoom in", "Zoom out", "Show everything"):
            page.get_by_role("button", name=name).press("Enter")

        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()
        column = panel(page).bounding_box()
        assert column["y"] >= canvas["y"] + canvas["height"] - 1, "the panel goes under the canvas"
        assert canvas["height"] >= 220 and canvas["width"] >= width - 20
        for part in panel(page).locator("button, select, input, summary, [data-testid=chat-text]").all():
            if part.is_visible():
                box = part.bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= width, part
        assert page.evaluate("() => [document.documentElement, document.querySelector('main'), "
                             "document.querySelector('.search-panel')].every((e) => e.scrollWidth <= e.clientWidth)")
        assert page.evaluate(CONTRAST) == [] and page.evaluate(SMALL) == []


def test_the_panel_and_zoom_buttons_are_large_enough_and_readable_in_a_wide_window(tmp_path):
    from test_editor_safety_e2e import CONTRAST

    three_actions(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("palette-open-menu").wait_for()
        page.get_by_text("Other boxes").click()
        page.get_by_role("button", name="It is not here: teach it").click()

        assert page.evaluate(CONTRAST) == [] and page.evaluate(SMALL) == []
        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()
        assert panel(page).bounding_box()["x"] >= canvas["x"] + canvas["width"] - 1  # beside the canvas, over none of it


def test_every_box_stays_in_sight_while_the_flow_runs_and_where_it_stopped(tmp_path):
    db = three_actions(tmp_path)
    boxes = [Node(f"b{i}", "open-menu") for i in range(4)] + [Node("last", "save-file")]
    save_flow(db, Flow(id="tall", nodes=boxes, edges=[(a.id, b.id) for a, b in pairwise(boxes)]))
    with editor(tmp_path, FakeDesktop(controls=[button("Alpha")]), size=(1280, 800)) as page:
        open_flow(page, "tall", "last")
        page.get_by_test_id("run").click()
        page.get_by_test_id("run-outcome").wait_for()
        page.wait_for_timeout(800)  # the canvas has made room for what the run shows

        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()
        notices = page.locator(".notices").bounding_box()
        for box in (n.bounding_box() for n in page.locator(".react-flow__node").all()):
            assert notices["y"] + notices["height"] <= box["y"], "no notice lies over a box"
            assert box["y"] + box["height"] <= canvas["y"] + canvas["height"], "no box is under the run log"


def test_a_run_that_ends_while_another_screen_is_open_leaves_every_box_in_sight(tmp_path):
    three_in_a_row(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    desktop.click_seconds = 0.5
    with editor(tmp_path, desktop) as page:
        open_flow(page, "row", "c")
        page.get_by_test_id("run").click()
        page.get_by_test_id("tab-apps").click()
        page.wait_for_timeout(2_500)  # the run ends while the canvas is not on screen
        page.get_by_test_id("tab-home").click()
        page.get_by_test_id("open-chore-row").click()
        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for()
        page.wait_for_timeout(800)

        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()
        for box in (n.bounding_box() for n in page.locator(".react-flow__node").all()):
            assert box["width"] > 150 and canvas["x"] <= box["x"] and box["x"] + box["width"] <= canvas["x"] + canvas["width"]
            assert canvas["y"] <= box["y"] and box["y"] + box["height"] <= canvas["y"] + canvas["height"]


def test_in_a_narrow_window_what_can_be_done_with_the_chosen_box_covers_no_box(tmp_path):
    three_in_a_row(tmp_path)
    with editor(tmp_path, size=(390, 740)) as page:
        open_flow(page, "row", "c")
        choose(page, "a")
        chosen = page.get_by_role("region", name="About the chosen box").bounding_box()
        canvas = page.get_by_role("region", name="Boxes of this chore").bounding_box()

        assert chosen["y"] >= canvas["y"] + canvas["height"] - 1
        assert chosen["y"] + chosen["height"] <= panel(page).bounding_box()["y"] + 1
        assert chosen["x"] >= 0 and chosen["x"] + chosen["width"] <= 390


def test_where_the_person_puts_a_box_is_kept_after_a_reload(tmp_path):
    db = three_actions(tmp_path)
    save_flow(db, Flow(id="two", nodes=[Node("a", "open-menu"), Node("b", "save-file")]))
    with editor(tmp_path) as page:
        open_flow(page, "two", "b")
        x, y = middle(page, "b")
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 260, y + 40, steps=10)
        page.mouse.up()
        save(page)

        page.reload()
        node(page, "b").wait_for()
        page.wait_for_timeout(500)
        assert middle(page, "b")[0] - middle(page, "a")[0] > 150  # not lined up under the first one again
