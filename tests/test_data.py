"""Data: every node takes in and gives out named fields, and a node's field is bound to a fixed value, to another
node's output, or to an expression that is stored but not run yet."""

import pytest

from workflow_factory import Flow, Node, answer_doubt, load_flow, run_flow, save_flow, save_step

from fake_desktop import FakeDesktop, button, step


def desktop_with(*names, **kw):
    return FakeDesktop(controls=[button(n) for n in names], **kw)


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def teach(user_db):
    save_step(user_db, step("scroll", "Down", effect="no_change"))
    save_step(user_db, step("typer", "Notes", action="type_value"))


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


def test_a_field_with_a_fixed_value_is_typed_without_any_run_data(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    run_flow(Flow(id="f", nodes=[Node("t", "typer", fields={"text": fixed("hello")})]), desktop=desktop,
             user_db=tmp_path / "user.db")

    assert [text for _, text in desktop.typed] == ["hello"]


def test_a_field_can_point_at_the_data_a_workday_starts_with(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    run_flow(Flow(id="f", nodes=[Node("t", "typer", fields={"text": ref("run", "name")})]), desktop=desktop,
             user_db=tmp_path / "user.db", context={"name": "Ada"})

    assert [text for _, text in desktop.typed] == ["Ada"]


def flow_that_passes_data():
    return Flow(id="f", nodes=[Node("scroll", "scroll"), Node("t", "typer", fields={"text": ref("scroll", "effect")})])


def test_a_field_can_point_at_the_output_of_an_earlier_node(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Down", "Notes")

    run_flow(flow_that_passes_data(), desktop=desktop, user_db=tmp_path / "user.db")

    assert [text for _, text in desktop.typed] == ["no_change"]  # the effect the first node measured


def test_the_data_of_finished_nodes_survives_a_stop_in_the_checkpoint(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db)
    first = desktop_with("Down")  # the typing control is missing: the second node stops with a doubt

    run_flow(flow_that_passes_data(), desktop=first, user_db=user_db)
    answer_doubt(user_db, 1)
    second = desktop_with("Down", "Notes")
    run_flow(flow_that_passes_data(), desktop=second, user_db=user_db)

    assert clicked(first) == ["Down"] and clicked(second) == []  # the first node did not run again
    assert [text for _, text in second.typed] == ["no_change"]  # but its output was still there


def test_a_field_that_points_at_nothing_stops_the_node_instead_of_typing_something_else(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")

    run_flow(Flow(id="f", nodes=[Node("t", "typer", fields={"text": ref("run", "missing")})]), desktop=desktop,
             user_db=tmp_path / "user.db", context={"name": "Ada"})

    assert desktop.typed == []


def test_fields_round_trip_through_saving_and_loading_a_flow(tmp_path):
    user_db = tmp_path / "user.db"
    flow = Flow(id="f", nodes=[Node("a", "scroll"),
                               Node("t", "typer", fields={"text": ref("a", "effect"), "label": fixed("x"),
                                                          "later": {"expression": "upper(a.effect)"}})])

    save_flow(user_db, flow)

    assert load_flow(user_db, None, "f").nodes == flow.nodes


@pytest.mark.parametrize("binding, message", [
    ({}, "exactly one"), ({"value": 1, "ref": {"node": "a", "field": "x"}}, "exactly one"),
    ({"nope": 1}, "unknown"), ({"ref": {"node": "a"}}, "field"), ({"ref": "a.x"}, "ref"),
    ({"expression": 3}, "expression"), ("text", "exactly one"),
], ids=["empty", "two kinds", "unknown kind", "ref without field", "ref not an object", "expression not text", "not an object"])
def test_a_malformed_binding_is_refused_when_the_node_is_made(binding, message):
    with pytest.raises(ValueError, match=message):
        Node("t", "typer", fields={"text": binding})


def test_a_reference_to_a_node_that_does_not_exist_is_refused_with_the_flow():
    with pytest.raises(ValueError, match="unknown node"):
        Flow(id="f", nodes=[Node("t", "typer", fields={"text": ref("ghost", "x")})])


def test_a_node_cannot_reference_its_own_output():
    with pytest.raises(ValueError, match="itself"):
        Flow(id="f", nodes=[Node("t", "typer", fields={"text": ref("t", "effect")})])


def test_an_expression_is_stored_but_a_run_refuses_to_start_with_one(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")
    flow = Flow(id="f", nodes=[Node("t", "typer", fields={"text": {"expression": "upper(name)"}})])

    with pytest.raises(ValueError, match="expression"):
        run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db", context={"name": "Ada"})

    assert desktop.typed == [] and desktop.calls == []  # nothing was touched
