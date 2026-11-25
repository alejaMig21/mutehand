"""Data: what every node takes in and gives out (a JSON object of named fields) and how a node's field is bound to it.

A field of a node is stored as exactly one of three forms, so a saved flow never needs a migration to grow:
  {"value": <JSON>}                          a fixed value;
  {"ref": {"node": id, "field": name}}       a field of another node's output (node "run" is the Data a workday starts with);
  {"expression": "<text>"}                   kept for later: it is stored and round-trips, but no run starts with one yet.
"""

import json
from collections.abc import Iterator

RUN = "run"  # the node id that names the Data a workday starts with
KINDS = ("value", "ref", "expression")


class MissingData(LookupError):
    """A field points at a node or a field that holds nothing (yet)."""


def check_binding(name: str, binding) -> None:
    """Raise ValueError unless `binding` is exactly one well-formed form."""
    if not isinstance(binding, dict) or len(binding) != 1:
        raise ValueError(f"field {name!r} must hold exactly one of value, ref or expression")
    ((kind, body),) = binding.items()
    if kind not in KINDS:
        raise ValueError(f"field {name!r} has an unknown binding kind {kind!r}; use one of {list(KINDS)}")
    if kind == "value":
        try:
            json.dumps(body)
        except (TypeError, ValueError) as error:
            raise ValueError(f"field {name!r}: the value must be JSON data") from error
    elif kind == "ref":
        if not isinstance(body, dict) or set(body) != {"node", "field"}:
            raise ValueError(f"field {name!r}: a ref must be an object with a node and a field")
        if not all(isinstance(body[part], str) and body[part] for part in ("node", "field")):
            raise ValueError(f"field {name!r}: the node and the field of a ref must be non-empty text")
    elif not isinstance(body, str):
        raise ValueError(f"field {name!r}: an expression must be text")


def references(fields: dict) -> Iterator[tuple[str, str]]:
    """(field name, node id) of every reference in a node's fields."""
    for name, binding in fields.items():
        if "ref" in binding:
            yield name, binding["ref"]["node"]


def expressions(fields: dict) -> list[str]:
    """The names of the fields that hold an expression."""
    return [name for name, binding in fields.items() if "expression" in binding]


def resolve(binding: dict, outputs: dict, context: dict):
    """The value of a field now. Raises MissingData when it points at something that is not there."""
    if "value" in binding:
        return binding["value"]
    if "ref" in binding:
        node, name = binding["ref"]["node"], binding["ref"]["field"]
        source = context if node == RUN else outputs.get(node)
        if source is None or name not in source:
            raise MissingData(f"{node}.{name} holds nothing")
        return source[name]
    raise ValueError("expressions are not supported yet")
