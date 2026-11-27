"""Triggers, for each, wait and stop: the system nodes that control how a flow runs."""

import pytest

from workflow_factory import Flow, Node, answer_doubt, clear_emergency_stop, emergency_stop, run_flow, save_step

from fake_desktop import FakeDesktop, button, step


def desktop_with(*names, **kw):
    return FakeDesktop(controls=[button(n) for n in names], **kw)


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def teach(user_db):
    for name, control in (("a", "Alpha"), ("b", "Beta"), ("scroll", "Down")):
        save_step(user_db, step(name, control))  # no taught effect: nothing to differ from
    save_step(user_db, step("typer", "Notes", action="type_value"))


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


def trigger(node_id, mode, at=None):
    fields = {"mode": fixed(mode)}
    if at:
        fields["at"] = fixed(at)
    return Node(node_id, kind="trigger", fields=fields)


# --- triggers ---------------------------------------------------------------------------------------------

def two_trigger_flow():
    return Flow(id="f", nodes=[trigger("m", "manual"), trigger("d", "daily", "09:00"), Node("a", "a"), Node("b", "b")],
                edges=[("m", "a"), ("d", "b")])


def test_a_manual_run_fires_the_manual_trigger_and_skips_what_hangs_from_the_daily_one(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")

    run_flow(two_trigger_flow(), desktop=desktop, user_db=tmp_path / "user.db")

    assert clicked(desktop) == ["Alpha"]


def test_a_scheduled_run_fires_the_daily_trigger(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")

    run_flow(two_trigger_flow(), desktop=desktop, user_db=tmp_path / "user.db", fired="daily")

    assert clicked(desktop) == ["Beta"]


def test_pressing_run_on_a_flow_that_only_has_a_daily_trigger_still_runs_it(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha")
    flow = Flow(id="f", nodes=[trigger("d", "daily", "09:00"), Node("a", "a")], edges=[("d", "a")])

    run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert clicked(desktop) == ["Alpha"]  # the person asked for it by hand


def test_a_trigger_gives_out_the_data_the_workday_started_with(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")
    flow = Flow(id="f", nodes=[trigger("m", "manual"), Node("t", "typer", fields={"text": ref("m", "name")})],
                edges=[("m", "t")])

    run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db", context={"name": "Ada"})

    assert [text for _, text in desktop.typed] == ["Ada"]


@pytest.mark.parametrize("fields, message", [
    ({}, "mode"), ({"mode": fixed("hourly")}, "mode"), ({"mode": fixed("daily")}, "HH:MM"),
    ({"mode": fixed("daily"), "at": fixed("25:00")}, "HH:MM"), ({"mode": ref("run", "m")}, "mode"),
], ids=["no mode", "unknown mode", "daily without time", "impossible time", "mode from data"])
def test_a_trigger_must_say_how_it_starts(fields, message):
    with pytest.raises(ValueError, match=message):
        Node("t", kind="trigger", fields=fields)


# --- for each ---------------------------------------------------------------------------------------------

def each_flow(items, body=None, **kw):
    body = body or Node("t", "typer", fields={"text": ref("e", "item")})
    return Flow(id="f", nodes=[Node("e", kind="foreach", body="t", fields={"items": items}), body], **kw)


def test_for_each_runs_its_body_once_per_item_with_the_item_as_data(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    result = run_flow(each_flow(fixed(["a", "b", "c"])), desktop=desktop, user_db=tmp_path / "user.db")

    assert [text for _, text in desktop.typed] == ["a", "b", "c"]
    assert result.status == "finished"


def test_for_each_can_take_its_list_from_the_data_a_workday_starts_with(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    run_flow(each_flow(ref("run", "names")), desktop=desktop, user_db=tmp_path / "user.db",
             context={"names": ["Ada", "Grace"]})

    assert [text for _, text in desktop.typed] == ["Ada", "Grace"]


def test_for_each_with_an_empty_list_finishes_without_running_its_body(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    result = run_flow(each_flow(fixed([])), desktop=desktop, user_db=tmp_path / "user.db")

    assert desktop.typed == [] and result.status == "finished"


def test_for_each_over_something_that_is_not_a_list_stops_with_a_doubt(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    result = run_flow(each_flow(fixed("abc")), desktop=desktop, user_db=tmp_path / "user.db")

    assert desktop.typed == [] and result.status == "stopped"


def test_the_body_of_for_each_never_runs_on_its_own(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Down")
    flow = Flow(id="f", nodes=[Node("e", kind="foreach", body="b", fields={"items": fixed([1, 2])}), Node("b", "scroll")])

    run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert clicked(desktop) == ["Down", "Down"]  # twice for two items, not three times


def test_a_stopped_for_each_resumes_at_the_item_it_stopped_on(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db)
    flow = Flow(id="f", nodes=[Node("e", kind="foreach", body="b", fields={"items": fixed([1, 2, 3, 4, 5])}),
                               Node("b", "scroll")])
    first = desktop_with("Down", vanish_after=2)  # two items work, then the control is gone

    run_flow(flow, desktop=first, user_db=user_db)
    answer_doubt(user_db, 1)
    second = desktop_with("Down")
    result = run_flow(flow, desktop=second, user_db=user_db)

    assert clicked(first) == ["Down"] * 2 and clicked(second) == ["Down"] * 3  # it did not start over
    assert result.status == "finished"


def test_for_each_needs_a_body_that_is_a_step_with_no_edges_of_its_own():
    with pytest.raises(ValueError, match="body"):
        Node("e", kind="foreach", fields={"items": fixed([1])})
    with pytest.raises(ValueError, match="items"):
        Node("e", kind="foreach", body="t")
    with pytest.raises(ValueError, match="unknown node"):
        Flow(id="f", nodes=[Node("e", kind="foreach", body="ghost", fields={"items": fixed([1])})])
    nodes = [Node("e", kind="foreach", body="t", fields={"items": fixed([1])}), Node("t", "typer"), Node("x", "a")]
    with pytest.raises(ValueError, match="own"):
        Flow(id="f", nodes=nodes, edges=[("x", "t")])
    with pytest.raises(ValueError, match="step"):
        Flow(id="f", nodes=[Node("e", kind="foreach", body="j", fields={"items": fixed([1])}), Node("j", kind="join")])


# --- wait -------------------------------------------------------------------------------------------------

def wait_flow(seconds):
    return Flow(id="f", nodes=[Node("w", kind="wait", fields={"seconds": seconds}), Node("a", "a")])


def test_wait_sleeps_the_requested_seconds_and_then_the_next_node_runs(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha")

    run_flow(wait_flow(fixed(5)), desktop=desktop, user_db=tmp_path / "user.db")

    assert desktop.slept_total == pytest.approx(5) and clicked(desktop) == ["Alpha"]


def test_wait_can_take_its_seconds_from_data(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha")

    run_flow(wait_flow(ref("run", "pause")), desktop=desktop, user_db=tmp_path / "user.db", context={"pause": 3})

    assert desktop.slept_total == pytest.approx(3)


def test_the_emergency_stop_ends_a_wait_within_a_second_and_a_resume_waits_only_the_rest(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db)
    first = desktop_with("Alpha")
    first.on_sleep.append(lambda: emergency_stop() if first.slept_total >= 2 else None)

    result = run_flow(wait_flow(fixed(100)), desktop=first, user_db=user_db)

    assert result.status == "emergency" and first.slept_total == pytest.approx(2)
    clear_emergency_stop()
    second = desktop_with("Alpha")
    second.on_sleep.append(lambda: emergency_stop() if second.slept_total >= 1 else None)
    run_flow(wait_flow(fixed(100)), desktop=second, user_db=user_db)
    clear_emergency_stop()
    third = desktop_with("Alpha")
    run_flow(wait_flow(fixed(100)), desktop=third, user_db=user_db)
    assert first.slept_total + second.slept_total + third.slept_total == pytest.approx(100)  # no second spent twice


def test_a_wait_does_not_pause_for_the_person_because_it_acts_on_nothing(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha")
    desktop.on_sleep.append(desktop.user_acts)  # the person keeps working while the flow waits

    only_a_wait = Flow(id="f", nodes=[Node("w", kind="wait", fields={"seconds": fixed(3)})])  # a later step would pause

    result = run_flow(only_a_wait, desktop=desktop, user_db=tmp_path / "user.db")

    assert desktop.slept_total == pytest.approx(3) and result.status == "finished"


@pytest.mark.parametrize("seconds", [0, -1, 100000, "5", True], ids=["zero", "negative", "over eight hours", "text", "bool"])
def test_a_wait_with_an_impossible_fixed_time_is_refused_when_the_node_is_made(seconds):
    with pytest.raises(ValueError, match="seconds"):
        Node("w", kind="wait", fields={"seconds": fixed(seconds)})


def test_a_wait_whose_data_is_not_a_good_number_stops_with_a_doubt_instead_of_waiting(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha")

    result = run_flow(wait_flow(ref("run", "pause")), desktop=desktop, user_db=tmp_path / "user.db",
                      context={"pause": "soon"})

    assert desktop.slept_total == 0 and result.status == "stopped"


# --- stop -------------------------------------------------------------------------------------------------

def test_stop_ends_the_flow_cleanly_and_nothing_after_it_runs(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    flow = Flow(id="f", nodes=[Node("a", "a"), Node("s", kind="stop"), Node("b", "b")])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert clicked(desktop) == ["Alpha"] and result.status == "finished" and result.halted_by == "s"


def test_a_stop_that_hangs_from_a_trigger_that_did_not_fire_halts_nothing(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    flow = Flow(id="f", nodes=[trigger("m", "manual"), trigger("d", "daily", "09:00"), Node("s", kind="stop"),
                               Node("a", "a"), Node("b", "b")],
                edges=[("m", "a"), ("a", "b"), ("d", "s")])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert clicked(desktop) == ["Alpha", "Beta"] and result.halted_by is None
