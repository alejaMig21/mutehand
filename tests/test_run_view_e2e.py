"""While a flow runs the nodes stay as big as before and each node shows its progress by a picture (defect 14b-A).
Opt-in: `pytest -m web`. The built editor in a headless browser against the real API, with the stand-in desktop."""

import pytest
from test_canvas_e2e import card, editor, node, open_flow, three_in_a_row

from fake_desktop import FakeDesktop, button

pytestmark = pytest.mark.web

SIZES = [(1280, 800), (683, 800)]


def node_size(page, node_id):
    rect = node(page, node_id).bounding_box()
    return rect["width"], rect["height"]


@pytest.mark.parametrize("size", SIZES, ids=["1280", "683"])
def test_a_run_does_not_shrink_the_nodes_and_the_log_stays_reachable(tmp_path, size):
    three_in_a_row(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    desktop.click_seconds = 1.0
    with editor(tmp_path, desktop, size=size) as page:
        open_flow(page, "row", "c")
        before = node_size(page, "b")
        canvas_before = page.locator(".stage .canvas").bounding_box()["height"]

        page.get_by_test_id("run").click()
        page.get_by_test_id("run-log").wait_for()
        page.wait_for_timeout(700)  # the canvas would have refitted by now
        during = node_size(page, "b")
        canvas_during = page.locator(".stage .canvas").bounding_box()["height"]
        print(f"{size}: node {before} -> {during}; canvas {canvas_before} -> {canvas_during}")
        assert during[1] >= before[1] * 0.95 and during[0] >= before[0] * 0.95  # nodes keep their size
        assert canvas_during >= canvas_before - 2

        assert "Running" in card(page, "a").inner_text()  # the running node is marked, in words and by picture
        assert node(page, "a").locator(".card-mark svg").count() == 1

        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for(timeout=10_000)
        after = node_size(page, "b")
        assert page.get_by_test_id("run-log").bounding_box()["height"] <= 70  # one line until asked for more
        assert after[1] >= before[1] * 0.95

        # per-node progress by pictures: one mark for each node, with its state
        marks = page.get_by_test_id("run-log").locator("[data-testid^=progress-]")
        assert [m.get_attribute("data-state") for m in marks.all()] == ["done", "done", "done"]
        assert marks.first.locator("svg").count() == 1

        page.get_by_role("button", name="Show details").click()
        assert "open-menu started" in page.get_by_test_id("run-log").inner_text()
        assert node_size(page, "b")[1] >= before[1] * 0.95  # reading the details leaves the nodes alone
        page.get_by_role("button", name="Hide details").click()
        assert "open-menu started" not in page.get_by_test_id("run-log").inner_text()
