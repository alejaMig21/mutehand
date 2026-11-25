"""The data system nodes inside a flow: they run on Data, need no desktop and no input lock, and hand their result on."""

import pytest

from workflow_factory import Flow, Node, run_flow, save_step

from fake_desktop import FakeDesktop, button, step


def desktop_with(*names, **kw):
    return FakeDesktop(controls=[button(n) for n in names], **kw)


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def teach(user_db):
    for name, control in (("a", "Alpha"), ("b", "Beta")):
        save_step(user_db, step(name, control, effect="no_change"))
    save_step(user_db, step("typer", "Notes", action="type_value"))


def fixed(value):
    return {"value": value}


def ref(node, field):
    return {"ref": {"node": node, "field": field}}


def data(node_id, op, **fields):
    return Node(node_id, kind="data", op=op, fields=fields)


def test_data_nodes_pass_their_results_on_through_references_without_any_listing_order(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Notes")
    flow = Flow(id="f", edges=[], nodes=[
        Node("e", kind="foreach", body="t", fields={"items": ref("s", "value")}),
        Node("t", "typer", fields={"text": ref("e", "item")}),
        data("s", "split", text=ref("d", "value"), separator=fixed(","), trim=fixed(True)),
        data("d", "fixed", value=fixed("a, b")),
    ])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert [text for _, text in desktop.typed] == ["a", "b"] and result.status == "finished"


def test_a_data_node_touches_no_control_and_needs_no_input_lock(tmp_path):
    desktop = desktop_with()
    flow = Flow(id="f", nodes=[data("m", "math", a=fixed(2), b=fixed(3), operation=fixed("add"))])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and result.outputs["m"] == {"value": 5} and desktop.calls == []


def test_a_bad_value_stops_the_node_with_a_message_that_never_holds_the_value(tmp_path):
    desktop = desktop_with()
    flow = Flow(id="f", nodes=[data("c", "convert", value=ref("run", "n"), to=fixed("number"))])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db", context={"n": "secret-9999"})

    assert result.status == "stopped" and result.blocked == {"c": "bad_data"}
    assert result.outputs["c"] == {"error": "the text is not a number"} and "secret-9999" not in str(result.outputs)


def test_a_data_node_whose_input_points_at_nothing_stops_instead_of_guessing(tmp_path):
    flow = Flow(id="f", nodes=[data("c", "convert", value=ref("run", "missing"), to=fixed("text"))])

    result = run_flow(flow, desktop=desktop_with(), user_db=tmp_path / "user.db")

    assert result.status == "stopped" and result.blocked == {"c": "missing_input"}


def branching_flow():
    return Flow(id="f", edges=[], nodes=[
        data("c", "compare", a=ref("run", "n"), b=fixed(5), operator=fixed("greater")),
        Node("i", kind="if", then="big", otherwise="small", fields={"condition": ref("c", "value")}),
        Node("big", "a"), Node("small", "b"),
    ])


@pytest.mark.parametrize("n, expected", [(9, ["Alpha"]), (1, ["Beta"])])
def test_an_if_can_route_on_a_true_or_false_from_another_node(tmp_path, n, expected):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")

    run_flow(branching_flow(), desktop=desktop, user_db=tmp_path / "user.db", context={"n": n})

    assert clicked(desktop) == expected


def test_an_if_whose_condition_is_not_true_or_false_stops_instead_of_choosing(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with("Alpha", "Beta")
    flow = Flow(id="f", edges=[], nodes=[
        Node("i", kind="if", then="big", otherwise="small", fields={"condition": ref("run", "n")}),
        Node("big", "a"), Node("small", "b"),
    ])

    result = run_flow(flow, desktop=desktop, user_db=tmp_path / "user.db", context={"n": 1})

    assert clicked(desktop) == [] and result.status == "stopped"


@pytest.mark.parametrize("kwargs, message", [
    (dict(op=None, fields={}), "operation"),
    (dict(op="sing", fields={}), "operation"),
    (dict(op="math", fields={"a": fixed(1)}), "needs"),
    (dict(op="not", fields={"a": fixed(True), "extra": fixed(1)}), "unknown field"),
])
def test_a_data_node_needs_a_known_operation_and_exactly_its_fields(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Node("d", kind="data", **kwargs)


def test_an_if_on_data_needs_a_then_but_no_effect_to_test():
    with pytest.raises(ValueError, match="then"):
        Node("i", kind="if", fields={"condition": fixed(True)})
    Node("i", kind="if", then="x", fields={"condition": fixed(True)})
