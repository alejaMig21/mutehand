import pytest

from workflow_factory import (
    Flow,
    Node,
    Sensitivity,
    answer_doubt,
    list_doubts,
    run_flow,
    save_step,
)

from fake_desktop import FakeDesktop, button, step


def teach(user_db, **controls):
    """teach(db, a="Alpha") saves step 'a' that clicks the control named Alpha."""
    for name, control in controls.items():
        save_step(user_db, step(name, control, effect="revealed"))


def desktop_with(*names, **kw):
    return FakeDesktop(controls=[button(n) for n in names], **kw)


def clicked(desktop):
    return [c.name for c in desktop.clicks]


# --- branching, join, IF -----------------------------------------------------------------------

def test_fan_out_branches_all_run_and_a_join_waits_for_all_of_them(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta", c="Gamma", d="Delta")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("b", "b"), Node("c", "c"), Node("j", kind="join"),
                               Node("d", "d")],
                edges=[("a", "b"), ("a", "c"), ("b", "j"), ("c", "j"), ("j", "d")])
    desktop = desktop_with("Alpha", "Beta", "Gamma", "Delta")

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None
    names = clicked(desktop)
    assert names[0] == "Alpha" and names[-1] == "Delta"  # the join's successor comes last
    assert sorted(names[1:3]) == ["Beta", "Gamma"]


def test_an_if_node_routes_on_a_measured_effect_and_skips_the_other_branch(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta", c="Gamma")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("choose", kind="if", on="a", equals="revealed",
                                                    then="b", otherwise="c"),
                               Node("b", "b"), Node("c", "c")],
                edges=[("a", "choose")])
    revealing = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")],
                            reveals={("button", "Alpha"): [button("New")]})
    quiet = desktop_with("Alpha", "Beta", "Gamma")

    run_flow(flow, desktop=revealing, user_db=user_db)
    other = run_flow(Flow(id="g", nodes=flow.nodes, edges=flow.edges), desktop=quiet, user_db=user_db)

    assert clicked(revealing) == ["Alpha", "Beta"]  # effect revealed -> then
    assert clicked(quiet) == ["Alpha", "Gamma"]  # no change -> otherwise
    assert other.stopped is None


# --- typed run context ---------------------------------------------------------------------------

def typing_flow():
    return Flow(id="f", nodes=[Node("t", "typer", inputs=(("text", "str"),))])


def teach_typer(user_db):
    save_step(user_db, step("typer", "Notes", action="type_value"))


def test_a_node_types_a_value_from_the_typed_run_context(tmp_path):
    user_db = tmp_path / "user.db"
    teach_typer(user_db)
    desktop = desktop_with("Notes")

    run_flow(typing_flow(), desktop=desktop, user_db=user_db, context={"text": "hello"})

    assert [text for _, text in desktop.typed] == ["hello"]


@pytest.mark.parametrize("context", [{}, {"text": 42}], ids=["missing input", "wrong type"])
def test_a_node_with_a_missing_or_mistyped_input_does_not_start(tmp_path, context):
    user_db = tmp_path / "user.db"
    teach_typer(user_db)
    desktop = desktop_with("Notes")

    result = run_flow(typing_flow(), desktop=desktop, user_db=user_db, context=context)

    assert result.stopped == "t" and result.blocked == {"t": "missing_input"}
    assert desktop.calls == [] and [d.reason for d in list_doubts(user_db)] == ["precondition_not_met"]


def test_a_consentless_step_blocks_its_node_while_the_other_branch_still_runs(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, ok="Alpha")
    save_step(user_db, step("risky", "Send", sensitive=Sensitivity.OUTWARD_ACTION))
    flow = Flow(id="f", nodes=[Node("r", "risky"), Node("o", "ok")], edges=[])  # independent branches
    desktop = desktop_with("Send", "Alpha")

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped == "r" and result.blocked == {"r": "no_consent"}
    assert clicked(desktop) == ["Alpha"]  # the independent branch finished
    assert [d.node_id for d in list_doubts(user_db)] == ["r"]


# --- loops -----------------------------------------------------------------------------------------

def loop_flow(**kw):
    return Flow(id="loop", nodes=[Node("l", "scroll", kind="loop", **kw)], edges=[])


def teach_scroll(user_db):
    save_step(user_db, step("scroll", "Down", effect="no_change"))


def test_a_loop_stops_at_its_iteration_cap(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    desktop = desktop_with("Down")

    result = run_flow(loop_flow(max_iterations=3, max_seconds=60), desktop=desktop, user_db=user_db)

    assert result.stopped is None and clicked(desktop) == ["Down"] * 3


def test_a_loop_stops_at_its_time_cap(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    desktop = desktop_with("Down", seconds_per_action=40)

    run_flow(loop_flow(max_iterations=50, max_seconds=100), desktop=desktop, user_db=user_db)

    assert clicked(desktop) == ["Down"] * 3  # 0 s, 40 s, 80 s run; at 120 s the cap stops it


def test_a_loop_may_not_exceed_eight_hours_and_needs_both_caps():
    with pytest.raises(ValueError, match="8 hours"):
        Node("l", "scroll", kind="loop", max_iterations=5, max_seconds=8 * 3600 + 1)
    with pytest.raises(ValueError, match="both"):
        Node("l", "scroll", kind="loop", max_iterations=5)


def test_a_loop_ends_early_on_the_effect_it_waits_for(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    desktop = desktop_with("Down")  # every click measures no_change

    run_flow(loop_flow(max_iterations=10, max_seconds=60, stop_when_effect="no_change"),
             desktop=desktop, user_db=user_db)

    assert clicked(desktop) == ["Down"]


def test_consecutive_failures_stop_the_loop_and_queue_exactly_one_doubt(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    desktop = desktop_with()  # the control is never there

    result = run_flow(loop_flow(max_iterations=10, max_seconds=60, stop_after_failures=3),
                      desktop=desktop, user_db=user_db)

    finds = [call for call in desktop.calls if call[0] == "find"]
    assert result.stopped == "l" and len(finds) == 3  # preconditions re-verified on every iteration
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]


def test_every_iteration_writes_a_checkpoint_so_a_stopped_loop_resumes_where_it_was(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    flow = loop_flow(max_iterations=5, max_seconds=60, stop_after_failures=1)
    first = desktop_with("Down", vanish_after=2)  # two iterations work, then the control is gone

    run_flow(flow, desktop=first, user_db=user_db)
    answer_doubt(user_db, 1)
    second = desktop_with("Down")
    result = run_flow(flow, desktop=second, user_db=user_db)

    assert clicked(first) == ["Down"] * 2
    assert clicked(second) == ["Down"] * 3  # iterations 3, 4 and 5: it did not start over
    assert result.stopped is None


def test_a_flow_with_a_cycle_or_an_unknown_edge_is_rejected():
    nodes = [Node("a", "x"), Node("b", "y")]
    with pytest.raises(ValueError, match="cycle"):
        Flow(nodes=nodes, edges=[("a", "b"), ("b", "a")])
    with pytest.raises(ValueError, match="unknown"):
        Flow(nodes=nodes, edges=[("a", "zzz")])


def test_a_loop_iteration_whose_effect_differs_from_the_taught_one_counts_as_a_failure(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("scroll", "Down", effect="revealed", factory_successes=50))  # taught: reveals
    desktop = desktop_with("Down")  # but clicking changes nothing

    result = run_flow(loop_flow(max_iterations=10, max_seconds=60, stop_after_failures=3),
                      desktop=desktop, user_db=user_db)

    assert result.stopped == "l" and clicked(desktop) == ["Down"] * 3
    assert [d.reason for d in list_doubts(user_db)] == ["precondition_not_met"]


@pytest.mark.parametrize("type_name, value, accepted", [
    ("int", True, False), ("int", 3, True), ("float", 3, True), ("float", True, False),
    ("bool", 1, False), ("bool", False, True), ("str", "x", True),
])
def test_typed_inputs_accept_only_values_of_their_declared_type(tmp_path, type_name, value, accepted):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("typer", "Notes", action="type_value"))
    flow = Flow(id="f", nodes=[Node("t", "typer", inputs=(("v", type_name),))])
    desktop = desktop_with("Notes")

    result = run_flow(flow, desktop=desktop, user_db=user_db, context={"v": value})

    assert (result.stopped is None) is accepted


def test_a_join_after_an_if_still_runs_when_one_branch_was_skipped(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta", c="Gamma", d="Delta")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("choose", kind="if", on="a", equals="revealed",
                                                    then="b", otherwise="c"),
                               Node("b", "b"), Node("c", "c"), Node("j", kind="join"), Node("d", "d")],
                edges=[("a", "choose"), ("b", "j"), ("c", "j"), ("j", "d")])
    desktop = FakeDesktop(controls=[button(n) for n in ("Alpha", "Beta", "Gamma", "Delta")],
                          reveals={("button", "Alpha"): [button("New")]})

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None and clicked(desktop) == ["Alpha", "Beta", "Delta"]


def test_nodes_behind_a_blocked_node_wait_and_run_after_the_doubt_is_answered(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("b", "b")])
    first = desktop_with("Beta")  # Alpha is missing: a is blocked, b must not run

    run_flow(flow, desktop=first, user_db=user_db)
    answer_doubt(user_db, 1)
    second = desktop_with("Alpha", "Beta")
    result = run_flow(flow, desktop=second, user_db=user_db)

    assert clicked(first) == [] and clicked(second) == ["Alpha", "Beta"]
    assert result.stopped is None


def test_the_loop_time_cap_counts_time_already_spent_before_a_stop(tmp_path):
    user_db = tmp_path / "user.db"
    teach_scroll(user_db)
    flow = loop_flow(max_iterations=50, max_seconds=100, stop_after_failures=1)
    first = desktop_with("Down", seconds_per_action=40, vanish_after=2)  # 80 s spent, then it breaks

    run_flow(flow, desktop=first, user_db=user_db)
    answer_doubt(user_db, 1)
    second = desktop_with("Down", seconds_per_action=40)
    run_flow(flow, desktop=second, user_db=user_db)

    assert clicked(second) == ["Down"]  # 80 s + 40 s passes the 100 s cap: one more iteration only


def test_the_effect_a_loop_waits_for_ends_it_even_if_it_differs_from_the_taught_effect(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("scroll", "Down", effect="revealed", factory_successes=50))
    desktop = desktop_with("Down")  # measures no_change, which is what the loop waits for

    result = run_flow(loop_flow(max_iterations=10, max_seconds=60, stop_when_effect="no_change"),
                      desktop=desktop, user_db=user_db)

    assert result.stopped is None and clicked(desktop) == ["Down"]


def test_an_if_node_waits_for_the_node_it_tests_even_when_listed_before_it(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta", c="Gamma")
    flow = Flow(id="f", nodes=[Node("choose", kind="if", on="a", equals="revealed", then="b", otherwise="c"),
                               Node("a", "a"), Node("b", "b"), Node("c", "c")], edges=[])
    desktop = FakeDesktop(controls=[button(n) for n in ("Alpha", "Beta", "Gamma")],
                          reveals={("button", "Alpha"): [button("New")]})

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.stopped is None and clicked(desktop) == ["Alpha", "Beta"]


def test_a_node_naming_a_step_that_does_not_exist_leaves_a_doubt_instead_of_crashing(tmp_path):
    user_db = tmp_path / "user.db"

    result = run_flow(Flow(id="f", nodes=[Node("n", "never-taught")]), desktop=desktop_with("X"),
                      user_db=user_db)

    assert result.stopped == "n" and [d.reason for d in list_doubts(user_db)] == ["precondition_not_met"]


def test_effect_names_in_a_flow_must_be_part_of_the_closed_vocabulary():
    with pytest.raises(ValueError, match="revealled"):
        Node("c", kind="if", on="a", equals="revealled", then="b")
    with pytest.raises(ValueError, match="nothing"):
        Node("l", "x", kind="loop", max_iterations=2, max_seconds=5, stop_when_effect="nothing")


def test_progress_reports_every_node_as_running_then_done_blocked_or_skipped(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, a="Alpha", b="Beta", c="Gamma", z="Missing")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("choose", kind="if", on="a", equals="revealed",
                                                    then="b", otherwise="c"),
                               Node("b", "b"), Node("c", "c"), Node("z", "z")],
                edges=[("a", "choose")])
    desktop = FakeDesktop(controls=[button(n) for n in ("Alpha", "Beta", "Gamma")],
                          reveals={("button", "Alpha"): [button("New")]})
    events = []

    run_flow(flow, desktop=desktop, user_db=user_db, progress=lambda node, status: events.append((node, status)))

    final = {}
    for node, status in events:
        final[node] = status
    assert final == {"a": "done", "choose": "done", "b": "done", "c": "skipped", "z": "blocked"}
    assert events.index(("a", "running")) < events.index(("a", "done"))


def test_a_second_run_of_the_same_flow_is_refused_while_the_first_is_alive_but_a_dead_ones_lock_is_ignored(tmp_path):
    from workflow_factory.queue import acquire_run_lock, release_run_lock

    user_db = tmp_path / "user.db"
    save_step(user_db, step("a", "Alpha"))  # no taught effect: nothing to count against it
    flow = Flow(id="f", nodes=[Node("a", "a")])

    assert acquire_run_lock(user_db, "f")  # a live run (this very process)
    busy = run_flow(flow, desktop=desktop_with("Alpha"), user_db=user_db)
    release_run_lock(user_db, "f")
    assert acquire_run_lock(user_db, "f", pid=4_000_001)  # a run whose process died without cleaning up
    stale = desktop_with("Alpha")
    ran = run_flow(flow, desktop=stale, user_db=user_db)
    again = run_flow(flow, desktop=desktop_with("Alpha"), user_db=user_db)  # the lock was released after the run

    assert busy.busy is True and busy.status == "busy"
    assert ran.status == "finished" and clicked(stale) == ["Alpha"] and again.status == "finished"
