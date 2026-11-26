"""What the node detail shows: the Data that entered and left each node. Values are hidden by default (only their shape
shows) and a node can be tested on its own from the Data the last run gave its inputs."""

import pytest

from workflow_factory import Flow, Node
from workflow_factory.nodedata import present, shape, single_node_flow, snapshot


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


def flow():
    return Flow(id="f", nodes=[
        Node("d", kind="data", op="fixed", fields={"value": fixed("hello")}),
        Node("c", kind="data", op="convert", fields={"value": ref("d", "value"), "to": fixed("text")}),
        Node("s", "typer", fields={"text": ref("run", "name")}),
    ])


OUTPUTS = {"d": {"value": "hello"}, "c": {"value": "hello"}}


def test_a_snapshot_holds_what_entered_and_left_each_node():
    snap = snapshot(flow(), OUTPUTS, {"name": "Ada"})

    assert snap["c"] == {"in": {"value": "hello", "to": "text"}, "out": {"value": "hello"}}
    assert snap["s"] == {"in": {"text": "Ada"}, "out": {}}  # it did not run yet: nothing left it


def test_a_field_that_points_at_nothing_is_left_out_instead_of_guessed():
    snap = snapshot(flow(), {}, {})

    assert snap["c"]["in"] == {"to": "text"} and snap["s"]["in"] == {}


def test_typed_inputs_taken_from_the_run_data_are_part_of_what_entered():
    node = Node("t", "typer", inputs=(("name", "str"),))

    assert snapshot(Flow(id="f", nodes=[node]), {}, {"name": "Ada", "other": 1})["t"]["in"] == {"name": "Ada"}


@pytest.mark.parametrize("value, expected", [
    ("héllo", {"type": "text", "size": 5}), (3, {"type": "number"}), (2.5, {"type": "number"}), (True, {"type": "boolean"}),
    ([1, 2], {"type": "list", "size": 2}), ({"a": 1}, {"type": "object", "size": 1}), (None, {"type": "nothing"}),
])
def test_a_shape_says_what_a_value_is_without_showing_it(value, expected):
    assert shape(value) == expected


def test_hidden_by_default_the_values_never_appear_in_what_is_presented():
    shown = present(snapshot(flow(), OUTPUTS, {"name": "Ada"}), values=False)

    assert shown["s"]["in"] == {"text": {"type": "text", "size": 3}}
    assert "hello" not in str(shown) and "Ada" not in str(shown)


def test_on_request_the_values_are_presented_as_they_are():
    shown = present(snapshot(flow(), OUTPUTS, {"name": "Ada"}), values=True)

    assert shown["s"]["in"] == {"text": "Ada"} and shown["c"]["out"] == {"value": "hello"}


def test_a_node_is_tested_alone_with_the_data_the_last_run_gave_it():
    alone = single_node_flow(flow(), "c", OUTPUTS)

    assert [n.id for n in alone.nodes] == ["c"] and alone.edges == []
    assert alone.nodes[0].fields["value"] == fixed("hello")  # the reference became the value it had
    assert alone.nodes[0].fields["to"] == fixed("text")


def test_a_reference_to_the_run_data_stays_a_reference_so_the_test_uses_the_data_given_now():
    alone = single_node_flow(flow(), "s", OUTPUTS)

    assert alone.nodes[0].fields["text"] == ref("run", "name")


def test_a_node_whose_input_has_no_data_yet_cannot_be_tested_and_says_what_to_do():
    with pytest.raises(ValueError, match="run the flow"):
        single_node_flow(flow(), "c", {})


@pytest.mark.parametrize("kind", ["trigger", "wait", "stop", "join", "if", "foreach"])
def test_only_steps_and_data_nodes_are_tested_alone(kind):
    fields = {"items": fixed([])} if kind == "foreach" else {"seconds": fixed(1)} if kind == "wait" else \
        {"mode": fixed("manual")} if kind == "trigger" else {"condition": fixed(True)} if kind == "if" else {}
    nodes = [Node("x", kind=kind, fields=fields, then="y" if kind == "if" else None, body="y" if kind == "foreach" else None),
             Node("y", "typer")]
    with pytest.raises(ValueError, match="cannot be tested alone"):
        single_node_flow(Flow(id="f", nodes=nodes), "x", {})


def test_an_unknown_node_is_refused():
    with pytest.raises(ValueError, match="no node"):
        single_node_flow(flow(), "ghost", {})
