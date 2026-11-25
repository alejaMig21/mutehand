
import numpy as np
import pytest

from workflow_factory import (
    Derived,
    Endpoint,
    Flow,
    Locator,
    Node,
    Template,
    list_doubts,
    load_flow,
    run_flow,
    save_flow,
    save_step,
)

from fake_desktop import FakeDesktop, button, icon, step

TWO_PARALLEL_BRANCHES = dict(id="f", edges=[])  # no edge between the nodes: they may run together


def desktop_for_parallel(**kw):
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")], **kw)
    desktop.click_seconds = 0.15  # long enough that two unserialised actions would overlap
    return desktop


def test_two_physical_input_nodes_in_parallel_branches_never_overlap_in_time(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("a", "Alpha"))
    save_step(user_db, step("b", "Beta"))
    flow = Flow(nodes=[Node("a", "a", exclusive_input=True), Node("b", "b", exclusive_input=True)],
                **TWO_PARALLEL_BRANCHES)
    desktop = desktop_for_parallel()

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None and len(desktop.clicks) == 2
    assert desktop.max_active == 1


def test_an_accessibility_click_still_takes_the_machine_so_two_of_them_never_overlap(tmp_path):
    # research 20: a click or set-value through accessibility can take the foreground window, so it is
    # not free of physical input even when the step uses no coordinates
    user_db = tmp_path / "user.db"
    save_step(user_db, step("a", "Alpha"))
    save_step(user_db, step("b", "Beta"))
    flow = Flow(nodes=[Node("a", "a"), Node("b", "b")], **TWO_PARALLEL_BRANCHES)
    desktop = desktop_for_parallel()

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None and len(desktop.clicks) == 2
    assert desktop.max_active == 1


ANCHOR = Locator(role="icon", name="Recycle Bin")
TEMPLATE = Template(anchor=ANCHOR, pixels=np.random.default_rng(1).integers(0, 255, (6, 6, 3), dtype=np.uint8))
PHYSICAL_STEPS = {
    "derived geometry": dict(derived=Derived(anchor=ANCHOR, fx=0.5, fy=0.5)),
    "drag": dict(action="drag", drag_to=Endpoint(locator=ANCHOR)),
    "template search": dict(template=TEMPLATE),
}


@pytest.mark.parametrize("step_kw", PHYSICAL_STEPS.values(), ids=PHYSICAL_STEPS.keys())
def test_a_step_that_may_use_the_mouse_is_serialised_even_if_its_node_forgot_to_say_so(tmp_path, step_kw):
    user_db = tmp_path / "user.db"
    for name in ("a", "b"):
        save_step(user_db, step(name, "Alpha", **step_kw))
    flow = Flow(nodes=[Node("a", "a"), Node("b", "b")], **TWO_PARALLEL_BRANCHES)
    desktop = FakeDesktop(controls=[button("Alpha"), icon("Recycle Bin", 0, 0, 40, 40)])
    desktop.click_seconds = 0.15

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None and desktop.max_active == 1


def test_the_exclusive_input_flag_survives_saving_and_loading_the_flow(tmp_path):
    user_db = tmp_path / "user.db"
    flow = Flow(id="f", nodes=[Node("a", "a", exclusive_input=True), Node("b", "b")])

    save_flow(user_db, flow)
    loaded = load_flow(user_db, None, "f")

    assert [node.exclusive_input for node in loaded.nodes] == [True, False]


def test_typing_takes_the_keyboard_so_two_typing_nodes_never_overlap(tmp_path):
    user_db = tmp_path / "user.db"
    for name in ("a", "b"):
        save_step(user_db, step(name, "Alpha", action="type_value"))
    flow = Flow(nodes=[Node("a", "a", inputs=(("t", "str"),)), Node("b", "b", inputs=(("t", "str"),))],
                **TWO_PARALLEL_BRANCHES)
    desktop = FakeDesktop(controls=[button("Alpha")])
    desktop.click_seconds = 0.15

    result = run_flow(flow, desktop=desktop, user_db=user_db, context={"t": "x"})

    assert result.stopped is None and len(desktop.typed) == 2 and desktop.max_active == 1


def test_a_desktop_failure_in_one_branch_leaves_a_doubt_and_the_other_branch_still_finishes(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("a", "Alpha"))
    save_step(user_db, step("b", "Beta"))
    flow = Flow(nodes=[Node("a", "a"), Node("b", "b")], **TWO_PARALLEL_BRANCHES)
    desktop = desktop_for_parallel()
    desktop.fail_on = {"Alpha"}

    result = run_flow(flow, desktop=desktop, user_db=user_db)  # must not raise

    assert result.stopped == "a" and result.blocked == {"a": "action_failed"}
    assert [c.name for c in desktop.clicks if c.name == "Beta"] == ["Beta"]
    assert [d.reason for d in list_doubts(user_db)] == ["precondition_not_met"]


def test_the_stopped_node_is_the_first_blocked_one_in_flow_order_not_the_first_to_fail(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("a", "Missing A"))
    save_step(user_db, step("b", "Missing B"))
    flow = Flow(nodes=[Node("a", "a"), Node("b", "b")], **TWO_PARALLEL_BRANCHES)

    for _ in range(5):
        fresh = tmp_path / f"{_}.db"
        save_step(fresh, step("a", "Missing A"))
        save_step(fresh, step("b", "Missing B"))
        assert run_flow(flow, desktop=FakeDesktop(controls=[]), user_db=fresh).stopped == "a"
