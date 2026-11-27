"""What the node detail shows: the Data that entered and left each node, hidden by default, and testing one node alone.

Values stay in memory (the API keeps the last ones per flow). By default only their shape leaves the server; the values
come out only when the person asks to see them. A secret never reaches this module: the core never holds one.
"""

from workflow_factory.data import RUN, MissingData, references, resolve
from workflow_factory.flow import Flow, Node

TESTABLE_KINDS = ("step", "data")


def snapshot(flow: Flow, outputs: dict, context: dict) -> dict:
    """node id -> {"in": the fields that entered it, "out": what it gave out}. A field pointing at nothing is left out."""
    result = {}
    for node in flow.nodes:
        entered = {}
        for name, binding in node.fields.items():
            try:
                entered[name] = resolve(binding, outputs, context)
            except (MissingData, ValueError):
                pass  # not there yet, or an expression that is not run yet
        for name, _ in node.inputs:
            if name in context:
                entered[name] = context[name]
        result[node.id] = {"in": entered, "out": dict(outputs.get(node.id, {}))}
    return result


def shape(value) -> dict:
    """What a value is, without showing it."""
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "text", "size": len(value)}
    if isinstance(value, list):
        return {"type": "list", "size": len(value)}
    if isinstance(value, dict):
        return {"type": "object", "size": len(value)}
    return {"type": "nothing"}


def present(snap: dict, values: bool) -> dict:
    """The snapshot as the editor may show it: shapes unless the person asked for the values."""
    show = (lambda value: value) if values else shape
    return {node_id: {side: {name: show(value) for name, value in fields.items()} for side, fields in sides.items()}
            for node_id, sides in snap.items()}


def single_node_flow(flow: Flow, node_id: str, outputs: dict) -> Flow:
    """A flow of that one node, for "Test this node": what it took from other nodes is the Data they gave in the last run."""
    node = next((n for n in flow.nodes if n.id == node_id), None)
    if node is None:
        raise ValueError(f"no node {node_id!r} in this flow")
    if node.kind not in TESTABLE_KINDS:
        raise ValueError(f"a {node.kind} node cannot be tested alone")
    fields = dict(node.fields)
    for name, target in references(node.fields):
        if target == RUN:
            continue  # the Data given for the test itself
        try:
            fields[name] = {"value": resolve(node.fields[name], outputs, {})}
        except MissingData:
            raise ValueError(f"node {target!r} has no data yet: run the flow first so this node has something to work on") from None
    return Flow(trial=f"{flow.id}#test:{node_id}", nodes=[Node(**{**node.__dict__, "fields": fields})], edges=[])
