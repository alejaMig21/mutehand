"""What a node does when it fails: stop (the default, leaves a doubt), retry N times, or continue."""

import pytest

from workflow_factory import Flow, Node, emergency_stop, list_doubts, run_flow, save_step

from fake_desktop import FakeDesktop, button, step


def desktop_with(*names, **kw):
    return FakeDesktop(controls=[button(n) for n in names], **kw)


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def teach(user_db):
    for name, control in (("a", "Alpha"), ("b", "Beta"), ("scroll", "Down")):
        save_step(user_db, step(name, control, effect="no_change"))


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


def two_nodes(**kw):
    return Flow(id="f", nodes=[Node("a", "a", **kw), Node("b", "b")])


def test_stop_is_the_default_it_leaves_one_doubt_and_the_run_names_the_node(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}

    result = run_flow(two_nodes(), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "stopped" and result.stopped == "a" and result.blocked == {"a": "action_failed"}
    assert [(d.node_id, d.step) for d in list_doubts(tmp_path / "user.db")] == [("a", "a")] and clicked(desktop) == []


def test_retry_tries_again_after_a_pause_and_succeeds_without_leaving_a_doubt(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}
    desktop.on_sleep.append(desktop.fail_on.clear)  # the problem goes away while the flow waits

    result = run_flow(two_nodes(on_failure="retry", retries=2), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and clicked(desktop) == ["Alpha", "Beta"]
    assert desktop.slept_total > 0 and list_doubts(tmp_path / "user.db") == []


def test_retry_checks_the_precondition_again_before_each_attempt(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Beta")  # Alpha is not on screen yet
    desktop.on_sleep.append(lambda: desktop._controls.append(button("Alpha")) if len(desktop._controls) == 1 else None)

    result = run_flow(two_nodes(on_failure="retry", retries=2), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and clicked(desktop) == ["Alpha", "Beta"]


def test_a_retry_that_never_works_gives_up_after_its_attempts_with_one_doubt(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}

    result = run_flow(two_nodes(on_failure="retry", retries=2), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "stopped" and result.stopped == "a" and len(list_doubts(tmp_path / "user.db")) == 1
    assert desktop.slept_total == pytest.approx(2.0 + 4.0)  # two pauses, a little longer each time


def test_the_emergency_stop_interrupts_the_pause_between_retries(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}
    desktop.on_sleep.append(emergency_stop)

    result = run_flow(two_nodes(on_failure="retry", retries=5), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "emergency" and desktop.slept_total == pytest.approx(2.0)


def test_continue_passes_an_empty_result_on_records_that_it_did_and_leaves_no_doubt(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}

    result = run_flow(two_nodes(on_failure="continue"), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and clicked(desktop) == ["Beta"]  # the flow went on
    assert result.continued == {"a": "action_failed"} and result.outputs["a"] == {}
    assert list_doubts(tmp_path / "user.db") == []


def test_what_continued_after_a_failure_shows_up_in_the_run_history(tmp_path):
    from workflow_factory.queue import list_runs

    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    desktop.fail_on = {"Alpha"}

    run_flow(two_nodes(on_failure="continue"), desktop=desktop, user_db=tmp_path / "user.db")

    (run,) = list_runs(tmp_path / "user.db")
    assert {(n["node_id"], n["status"], n["reason"]) for n in run["nodes"]} == {("a", "continued", "action_failed"), ("b", "done", None)}


def test_a_node_that_needs_the_empty_result_of_a_continued_one_stops_instead_of_guessing(tmp_path):
    flow = Flow(id="f", nodes=[
        Node("c", kind="data", op="convert", on_failure="continue", fields={"value": ref("run", "n"), "to": fixed("number")}),
        Node("m", kind="data", op="math", fields={"a": ref("c", "value"), "b": fixed(1), "operation": fixed("add")}),
    ])

    result = run_flow(flow, desktop=desktop_with(), user_db=tmp_path / "user.db", context={"n": "abc"})

    assert result.continued == {"c": "bad_data"} and result.blocked == {"m": "missing_input"} and result.status == "stopped"


def test_a_for_each_retries_the_item_it_failed_on_without_starting_over(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Down")
    desktop.fail_on = {"Down"}
    desktop.on_sleep.append(desktop.fail_on.clear)
    flow = Flow(id="f", nodes=[Node("e", kind="foreach", body="s", on_failure="retry", fields={"items": fixed([1, 2])}),
                               Node("s", "scroll")])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and clicked(desktop) == ["Down", "Down"]


@pytest.mark.parametrize("kwargs", [dict(on_failure="explode"), dict(on_failure="retry", retries=0),
                                    dict(on_failure="retry", retries=11), dict(on_failure="retry", retries=1.5),
                                    dict(on_failure="retry", retries=True)])
def test_a_failure_policy_must_be_one_of_the_three_with_a_sensible_retry_count(kwargs):
    with pytest.raises(ValueError, match="on_failure|retries"):
        Node("a", "a", **kwargs)


def test_the_policy_is_saved_with_the_flow(tmp_path):
    from workflow_factory import load_flow, save_flow

    flow = two_nodes(on_failure="retry", retries=3)
    save_flow(tmp_path / "user.db", flow)

    assert load_flow(tmp_path / "user.db", None, "f").nodes == flow.nodes
