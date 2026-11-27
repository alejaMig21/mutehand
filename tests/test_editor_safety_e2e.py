"""The editor never destroys work, never loses a run and never hides what a button does. Opt-in: `pytest -m web`.

Each test is a defect that simulated users found in the built editor.
"""

import re

import pytest
from test_editor_e2e import open_page, serve

from workflow_factory import (
    Flow,
    Node,
    Sensitivity,
    grant_consent,
    load_flow,
    reject_step,
    run_flow,
    save_flow,
    save_step,
)

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web

@pytest.fixture
def app(tmp_path):
    """A seeded editor and a headless page on it: (page, folder, desktop)."""
    from playwright.sync_api import sync_playwright

    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_step(db, step("save-file", "Beta"))
    save_step(db, step("Close dialog", "Missing"))
    save_flow(db, Flow(id="morning", nodes=[Node("n1", "open-menu"), Node("n2", "save-file")]))
    save_flow(db, Flow(id="weekly", nodes=[Node("n1", "open-menu"), Node("n2", "Close dialog")]))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = serve(tmp_path, desktop)
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.set_viewport_size({"width": 1366, "height": 768})
            page.set_default_timeout(8_000)
            page.get_by_test_id("palette-open-menu").wait_for()
            yield page, tmp_path, desktop
            browser.close()
    finally:
        server.stop()


def open_flow(page, name):
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id(f"flow-{name}").click()
    page.locator('.react-flow__node[data-id="n2"]').wait_for()
    page.get_by_test_id("app-name").select_option("paint.exe")


def wait_status(page, words):
    page.get_by_test_id("run-status").filter(has_text=re.compile(f"^{words}$", re.IGNORECASE)).wait_for(timeout=10_000)


def stored(folder, name):
    return [n.step or n.kind for n in load_flow(folder / "user.db", None, name).nodes]


def add_wait(page):
    search = page.get_by_test_id("search")
    search.fill("wait")
    page.get_by_test_id("system-wait").click()
    search.fill("")


def answer_dialogs(page, accept):
    asked = []
    page.on("dialog", lambda d: (asked.append(d.message), d.accept() if accept["now"] else d.dismiss()))
    return asked


# WCAG contrast of every visible button against what is painted behind it
CONTRAST = """() => {
  const rgb = (c) => c.match(/[\\d.]+/g).map(Number)
  const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
    .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
  const behind = (el) => { for (; el; el = el.parentElement) { const c = rgb(getComputedStyle(el).backgroundColor)
    if (c.length < 4 || c[3] > 0.5) return c } return [255, 255, 255] }
  return [...document.querySelectorAll('button')].filter((b) => b.offsetParent && !b.disabled && b.innerText.trim()).map((b) => {
    const [a, z] = [lum(rgb(getComputedStyle(b).color)), lum(behind(b))].sort((x, y) => y - x)
    return [b.innerText.trim(), (a + 0.05) / (z + 0.05)]
  }).filter(([, ratio]) => ratio < 4.5)
}"""


def test_every_button_on_every_screen_can_be_read(app):
    page, folder, _ = app
    reject_step(folder / "user.db", "paint.exe", "save-file")
    grant_consent(folder / "user.db", "paint.exe", "Send", "click")
    run_flow(load_flow(folder / "user.db", None, "weekly"), desktop=FakeDesktop(controls=[button("Alpha")]),
             user_db=folder / "user.db")
    unreadable = {}

    def look(screen):
        page.wait_for_timeout(500)
        if found := page.evaluate(CONTRAST):
            unreadable[screen] = found

    look("flow screen")
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("attention").wait_for()
    look("home")
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-paint.exe").click()
    page.get_by_test_id("app-card-paint.exe").get_by_test_id("app-permission-Send-click").wait_for()
    look("apps")

    assert unreadable == {}


def test_a_new_flow_gets_its_own_name(app):
    page, _, _ = app
    open_flow(page, "morning")
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("new-flow").click()
    assert page.get_by_test_id("flow-title").input_value() not in ("morning", "weekly")


def test_a_new_flow_named_like_another_destroys_nothing(app):
    page, folder, _ = app
    page.get_by_test_id("flow-title").fill("morning")
    add_wait(page)
    wait_status(page, "saved")

    assert stored(folder, "morning") == ["open-menu", "save-file"] and stored(folder, "morning-2") == ["wait"]


def test_a_change_that_cannot_be_kept_is_shown_and_never_dropped_without_asking(app):
    page, folder, _ = app
    accept = {"now": False}
    asked = answer_dialogs(page, accept)
    open_flow(page, "morning")
    wait_status(page, "saved")
    assert page.evaluate("() => window.dispatchEvent(new Event('beforeunload', {cancelable: true}))")  # nothing to lose
    page.get_by_test_id("search").fill("two paths")
    page.get_by_test_id("system-if").click()  # a choice with no yes path cannot be stored yet
    wait_status(page, "not saved")
    assert page.evaluate("() => !window.dispatchEvent(new Event('beforeunload', {cancelable: true}))")

    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-weekly").click()
    page.wait_for_timeout(500)
    assert asked and page.get_by_test_id("flow-title").input_value() == "morning"
    assert page.locator(".react-flow__node").count() == 3
    assert stored(folder, "morning") == ["open-menu", "save-file"]


def test_run_runs_what_is_on_the_screen(app):
    page, folder, desktop = app
    open_flow(page, "morning")
    page.locator('.react-flow__node[data-id="n2"]').click()
    page.get_by_test_id("delete-node").click()
    page.get_by_test_id("run").click()
    wait_status(page, "finished")

    assert [c.name for c in desktop.clicks] == ["Alpha"] and stored(folder, "morning") == ["open-menu"]


def test_a_run_stays_with_its_flow_and_survives_a_reload_and_a_lost_request(app):
    page, _, desktop = app
    desktop.click_seconds = 2.5
    open_flow(page, "morning")
    page.get_by_test_id("run").dblclick()  # a double click starts it; it must not also stop it
    page.get_by_test_id("stop").wait_for()
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-weekly").click()
    page.get_by_test_id("running-elsewhere").filter(has_text="morning").wait_for()
    assert page.locator(".react-flow__node.status-done, .react-flow__node.status-running").count() == 0

    page.reload()
    page.get_by_test_id("running-elsewhere").filter(has_text="morning").wait_for()
    failed = []
    page.route(re.compile(r"/api/runs/\w+$"), lambda route: (failed.append(1), route.abort()) if not failed else route.continue_())
    open_flow(page, "morning")
    page.get_by_test_id("stop").wait_for()
    wait_status(page, "finished")
    assert failed and [c.name for c in desktop.clicks] == ["Alpha", "Beta"]
    assert page.get_by_test_id("error").count() == 0


def test_a_run_that_cannot_start_says_why_and_where_to_go(app):
    page, folder, _ = app
    run_flow(load_flow(folder / "user.db", None, "weekly"), desktop=FakeDesktop(controls=[button("Alpha")]),
             user_db=folder / "user.db")  # leaves an open doubt
    open_flow(page, "weekly")
    page.get_by_test_id("run").click()
    outcome = page.get_by_test_id("run-outcome")
    outcome.filter(has_text="stopped earlier").wait_for()
    assert "Starting" not in page.get_by_test_id("run-log").inner_text()

    outcome.get_by_role("button", name="Show the stopped node").click()  # the strip says why, and offers Try again
    reason = page.get_by_test_id("strip-reason")
    reason.wait_for()
    assert "not on the screen" in reason.inner_text() and "control_not_found" not in reason.inner_text()


def test_the_flow_screen_notices_what_was_changed_in_apps(app):
    page, folder, _ = app
    reject_step(folder / "user.db", "paint.exe", "save-file")  # another window, or the tutor, did it
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("open-flow-morning").click()
    page.get_by_test_id("node-n2").filter(has_text="Rejected").wait_for()
    assert page.get_by_test_id("run").is_disabled()

    page.get_by_role("button", name="Open Apps").click()  # the notice says where to go
    page.get_by_test_id("app-row-paint.exe").click()
    page.get_by_test_id("app-allow-again-save-file").click()
    page.get_by_test_id("app-problem-save-file").wait_for(state="detached")
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("open-flow-morning").click()

    page.get_by_test_id("node-n2").wait_for()
    page.get_by_test_id("node-n2").filter(has_not_text="Rejected").wait_for()  # read again as the screen comes back
    assert page.get_by_test_id("run").is_enabled()


def test_allowing_an_action_far_down_an_app_keeps_the_place_and_says_so_in_view(app):
    page, folder, _ = app
    for number in range(30):
        save_step(folder / "user.db", step(f"step-{number:02}", "Alpha"))
    reject_step(folder / "user.db", "paint.exe", "step-29")
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-paint.exe").click()
    allow = page.get_by_test_id("app-allow-again-step-29")
    allow.scroll_into_view_if_needed()

    allow.click()
    page.get_by_test_id("app-problem-step-29").wait_for(state="detached")
    said = page.get_by_test_id("announce")
    said.filter(has_text="is allowed again").wait_for()
    page.wait_for_timeout(300)

    rect = said.bounding_box()
    assert 0 <= rect["y"] and rect["y"] + rect["height"] <= 768  # said where the person looks, wherever the page is scrolled


def test_a_screen_that_could_not_load_never_claims_there_is_nothing(app):
    page, _, _ = app
    page.route(re.compile(r"/api/apps"), lambda route: route.abort())
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("load-error").wait_for()
    assert page.get_by_test_id("apps-empty").count() == 0

    page.unroute(re.compile(r"/api/apps"))
    page.get_by_test_id("retry").click()
    page.get_by_test_id("app-row-paint.exe").wait_for()


def test_a_flow_is_built_and_its_node_opened_with_the_keyboard_alone(app):
    page, folder, _ = app
    page.get_by_test_id("flow-title").fill("by-keys")
    for entry in ("palette-open-menu", "palette-save-file"):
        page.get_by_test_id(entry).press("Enter")
    page.locator('.react-flow__node[data-id="n1"]').press("Space")  # select it
    page.get_by_role("button", name=re.compile("Remove the wire to save-file")).press("Enter")
    page.locator(".react-flow__edge").wait_for(state="detached")
    page.get_by_test_id("connect-to").select_option("n2")
    page.locator(".react-flow__edge").wait_for(state="attached")

    page.locator('.react-flow__node[data-id="n2"]').press("Enter")
    detail = page.get_by_test_id("detail")
    detail.wait_for()
    for _ in range(25):
        page.keyboard.press("Tab")
        assert page.evaluate("() => Boolean(document.activeElement.closest('[data-testid=detail]'))")
    page.keyboard.press("Escape")
    page.wait_for_function("() => document.activeElement.dataset.id === 'n2'")  # the focus returns to the node
    assert detail.count() == 0
    assert page.locator('.react-flow__node[data-id="n2"]').evaluate(
        "n => getComputedStyle(n.querySelector('.card')).outlineStyle") == "solid"

    page.get_by_test_id("open-flows").press("Enter")
    page.keyboard.press("Escape")
    assert page.get_by_test_id("new-flow").count() == 0
    wait_status(page, "saved")
    assert load_flow(folder / "user.db", None, "by-keys").edges == [("n1", "n2")]


def test_at_double_zoom_the_main_actions_stay_on_screen_and_the_canvas_is_not_covered(app):
    page, _, _ = app
    page.set_viewport_size({"width": 683, "height": 384})
    page.reload()
    page.get_by_test_id("search").wait_for()
    assert page.locator(".canvas").bounding_box()["height"] >= 220  # the nodes to add go under it, not over it
    page.get_by_test_id("app-more-toggle").click()
    for test_id in ("undo", "run", "tab-apps", "quit"):
        rect = page.get_by_test_id(test_id).bounding_box()
        assert rect["x"] >= 0 and rect["x"] + rect["width"] <= 683, test_id
    assert page.evaluate("() => document.querySelector('main').scrollWidth <= 683")


@pytest.mark.parametrize("width", [683, 390])
def test_in_a_narrow_window_no_notice_covers_the_panel_of_nodes(app, width):
    page, folder, _ = app
    reject_step(folder / "user.db", "paint.exe", "save-file")
    page.set_viewport_size({"width": width, "height": 800})
    page.reload()
    open_flow(page, "morning")
    page.get_by_test_id("cannot-start").wait_for()
    page.get_by_test_id("search").click(timeout=2_000)  # nothing lies over it
    page.get_by_test_id("palette-open-menu").click(timeout=2_000)

    page.locator('.react-flow__node[data-id="n3"]').wait_for()


def test_history_and_apps_speak_plain_words(app):
    page, folder, _ = app
    run_flow(load_flow(folder / "user.db", None, "weekly"), desktop=FakeDesktop(controls=[button("Alpha")]),
             user_db=folder / "user.db")
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("more-weekly").click()
    page.get_by_test_id("more-history-weekly").click()
    run = page.locator('[data-testid^="history-run-"]').first
    run.filter(has_text="Close dialog").wait_for()
    text = run.inner_text()
    assert "Close dialog" in text and "not on the screen" in text
    assert not re.search(r"control_not_found|no_change|\bn[12]\b|T\d\d:", text)

    page.get_by_test_id("tab-apps").click()
    page.wait_for_function("() => document.title.startsWith('Apps')")
    page.get_by_test_id("app-row-paint.exe").click()
    words = page.get_by_test_id("app-card-paint.exe").inner_text()
    assert "Trusted" not in words and "On trial" not in words  # how far an action is trusted is never a label


def test_a_wrong_link_says_so_instead_of_showing_an_empty_editor(tmp_path):
    from playwright.sync_api import sync_playwright

    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))  # something is learned: Home offers a new flow
    server = serve(tmp_path, FakeDesktop(controls=[]))
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.goto("about:blank")
            page.goto(server.url + "/#token=wrong")
            page.get_by_test_id("locked").wait_for()
            assert page.get_by_test_id("search-panel").count() == 0
            page.goto(server.url + "/#token=e2e-token")  # the right link, pasted in the same tab
            page.get_by_test_id("search-panel").wait_for()  # the same tab still remembers it was on the flow screen
            browser.close()
    finally:
        server.stop()


def remove_the_wires_of(page, node_id):
    page.wait_for_timeout(400)  # the canvas re-fits after a node is added
    page.locator(f'.react-flow__node[data-id="{node_id}"]').click()
    wires = page.get_by_role("button", name=re.compile("^Remove the wire to"))
    while wires.count():
        wires.first.click()


def test_nodes_nobody_wired_are_pointed_out_and_can_be_chained_in_one_press(app):
    page, folder, _ = app
    page.get_by_test_id("flow-title").fill("chained")
    for entry in ("palette-open-menu", "palette-save-file", "palette-Close dialog"):
        page.get_by_test_id(entry).click()
    assert page.get_by_test_id("unwired").count() == 0  # new nodes join by themselves
    remove_the_wires_of(page, "n1")
    remove_the_wires_of(page, "n2")
    notice = page.get_by_test_id("unwired")
    notice.filter(has_text="at the same time").wait_for()
    notice.get_by_role("button", name="Connect them in order").click()
    assert page.get_by_test_id("unwired").count() == 0
    wait_status(page, "saved")

    assert load_flow(folder / "user.db", None, "chained").edges == [("n1", "n2"), ("n2", "n3")]


def test_the_list_of_steps_says_what_is_rejected_or_already_allowed(app):
    page, folder, _ = app
    save_step(folder / "user.db", step("send-it", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(folder / "user.db", "paint.exe", "Send", "click")
    reject_step(folder / "user.db", "paint.exe", "save-file")
    page.reload()

    assert "Rejected" in page.get_by_test_id("palette-save-file").inner_text()
    assert "Consent given" in page.get_by_test_id("palette-send-it").inner_text()


def test_a_step_can_be_dragged_from_the_list_to_the_canvas(app):
    page, _, _ = app
    page.get_by_test_id("palette-open-menu").drag_to(page.locator(".react-flow__pane"), target_position={"x": 200, "y": 150})
    page.locator('.react-flow__node[data-id="n1"]').wait_for()

    assert page.locator(".react-flow__node").count() == 1


def test_the_keyboard_focus_is_never_dropped_and_changes_are_announced(app):
    page, _, _ = app
    on_page = "() => document.activeElement !== document.body"
    open_flow(page, "morning")
    page.wait_for_function(on_page)
    page.locator('.react-flow__node[data-id="n2"]').press("Space")
    page.get_by_test_id("delete-node").press("Enter")
    page.wait_for_function("() => document.activeElement.dataset.testid === 'search'")
    assert "Deleted save-file" in page.get_by_test_id("editor-announce").inner_text()
    page.get_by_test_id("palette-open-menu").press("Enter")
    assert "Added open-menu" in page.get_by_test_id("editor-announce").inner_text()


def test_the_run_data_of_one_flow_does_not_follow_to_another(app):
    page, _, _ = app
    open_flow(page, "morning")
    page.get_by_test_id("run-data").click()
    page.get_by_test_id("context").fill('{"only": "for morning"}')
    open_flow(page, "weekly")
    page.get_by_test_id("run-data").click()

    assert page.get_by_test_id("context").input_value() == "{}"


def test_at_double_zoom_the_node_window_stacks_without_covering_its_own_controls(app):
    page, _, _ = app
    page.set_viewport_size({"width": 683, "height": 384})
    open_flow(page, "morning")
    page.locator('.react-flow__node[data-id="n1"]').press("Enter")
    settings = page.get_by_test_id("on-failure").bounding_box()
    footer = page.locator(".detail-foot").bounding_box()
    out = page.get_by_role("region", name="Data out").bounding_box()

    assert settings["y"] + settings["height"] <= out["y"] <= out["y"] + out["height"] <= footer["y"]


def test_an_app_says_why_an_action_is_blocked_and_what_allowing_it_again_does(app):
    page, folder, _ = app
    teach = Flow(id="teach", nodes=[Node("n1", "Menu opens")])
    save_flow(folder / "user.db", teach)
    run_flow(teach, desktop=FakeDesktop(controls=[button("Alpha")]), user_db=_taught(folder, "Menu opens"))
    reject_step(folder / "user.db", "paint.exe", "save-file")
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-paint.exe").click()

    failed = page.get_by_test_id("app-problem-Menu opens").inner_text()
    assert "is rejected" in failed and "something new appeared" in failed and "nothing changed on screen" in failed
    assert "You rejected it" in page.get_by_test_id("app-problem-save-file").inner_text()
    assert page.get_by_test_id("app-problem-open-menu").count() == 0  # only a blocked action needs a reason

    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("more-teach").click()
    page.get_by_test_id("more-history-teach").click()
    page.locator('[data-testid^="history-run-"]').first.filter(has_text="did not change the way it did").wait_for()


def _taught(folder, name):
    save_step(folder / "user.db", step(name, "Alpha", effect="revealed"))
    return folder / "user.db"


def test_a_node_dropped_on_an_empty_canvas_stays_where_it_was_dropped(app):
    page, _, _ = app
    pane = page.locator(".react-flow__pane")
    page.get_by_test_id("palette-open-menu").drag_to(pane, target_position={"x": 150, "y": 380})
    node = page.locator('.react-flow__node[data-id="n1"]')
    node.wait_for()
    page.wait_for_timeout(600)

    rect, canvas = node.bounding_box(), pane.bounding_box()
    assert abs(rect["x"] - canvas["x"] - 150) < 30 and abs(rect["y"] - canvas["y"] - 380) < 30


def test_a_notice_appearing_does_not_move_what_is_under_the_pointer(app):
    page, _, _ = app
    entry = page.get_by_test_id("palette-save-file")
    before = entry.bounding_box()
    page.get_by_test_id("palette-open-menu").click()
    page.get_by_test_id("palette-save-file").click()
    remove_the_wires_of(page, "n1")
    page.get_by_test_id("unwired").wait_for()

    assert entry.bounding_box() == before


def test_where_the_person_was_survives_a_reload(app):
    page, folder, _ = app
    open_flow(page, "morning")
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("tab-home").click()

    page.get_by_test_id("open-flow-morning").click()
    page.reload()

    page.locator('.react-flow__node[data-id="n2"]').wait_for()
    assert page.get_by_test_id("flow-title").input_value() == "morning"


def test_a_double_click_on_the_empty_canvas_moves_nothing(app):
    page, _, _ = app
    open_flow(page, "morning")
    page.wait_for_timeout(600)
    view = "() => document.querySelector('.react-flow__viewport').style.transform"
    before = page.evaluate(view)
    page.locator(".react-flow__pane").dblclick(position={"x": 40, "y": 40})
    page.wait_for_timeout(600)

    assert page.evaluate(view) == before


def test_the_closed_page_says_how_to_open_it_again(app):
    page, _, _ = app
    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_test_id("app-more-toggle").click()
    page.get_by_test_id("quit").click()

    assert "uv run mutehand" in page.get_by_test_id("closed").inner_text()


def test_a_test_of_one_node_shows_the_servers_words_untouched_and_says_when_it_cannot_reach_it(app):
    page, _, _ = app
    open_flow(page, "morning")
    page.locator('.react-flow__node[data-id="n1"]').click()
    page.route("**/nodes/n1/test", lambda route: route.fulfill(
        status=400, content_type="application/json", body='{"error": "no step named open_menu"}'))
    page.get_by_test_id("test-node").click()
    page.get_by_test_id("confirm-test").click()
    page.get_by_test_id("test-result").filter(has_text="no step named open_menu").wait_for()

    page.unroute("**/nodes/n1/test")
    page.route(re.compile(r".*/api/runs/\w+$"), lambda route: route.abort())
    page.get_by_test_id("test-node").click()
    page.get_by_test_id("confirm-test").click()
    page.get_by_test_id("test-result").filter(has_text="still trying").wait_for()


def test_the_run_data_node_says_in_plain_words_that_empty_braces_mean_no_values(app):
    page, _, _ = app
    open_flow(page, "morning")
    page.get_by_test_id("run-data").click()

    hint = page.get_by_test_id("context-hint").inner_text()
    assert "nothing" in hint and "{}" in hint and "JSON" not in hint
