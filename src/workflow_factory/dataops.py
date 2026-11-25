"""The data system nodes as pure functions: named fields in, Data out.

A bad value raises DataError. Its message names the field or the problem and never the value, because a value may
come from a private app and the message can reach a report or the editor.
"""

import copy
import json
import math
import re

MAX_TEXT = 100_000  # characters a text operation will look at
MAX_PATTERN = 500
MAX_ITEMS = 100_000


class DataError(ValueError):
    """A value a data node cannot work with. The message never contains the value."""


def _kind(value) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "text", list: "list", dict: "object", type(None): "nothing"}.get(type(value), "other")


def _need(args: dict, name: str, *kinds: str):
    value = args[name]
    if _kind(value) not in kinds:
        raise DataError(f"{name} must be {' or '.join(kinds)}")
    return value


def _text(value, name="the value") -> str:
    """A simple value as text (what a person would read it as)."""
    kind = _kind(value)
    if kind == "text":
        return value
    if kind == "boolean":
        return "true" if value else "false"
    if kind == "number":
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
    if kind in ("list", "object"):
        return json.dumps(value)
    raise DataError(f"{name} has nothing to show as text")


def _number_from_text(text: str):
    text = text.strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    try:
        number = float(text)
    except ValueError:
        raise DataError("the text is not a number") from None
    if not math.isfinite(number) or not re.fullmatch(r"-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", text):
        raise DataError("the text is not a number")
    return number


# --- operations -------------------------------------------------------------------------------------------

def _fixed(a):
    return {"value": a["value"]}


def _convert(a):
    to, value = a["to"], a["value"]
    if to == "text":
        return {"value": _text(value)}
    kind = _kind(value)
    if to == "number":
        if kind == "number":
            return {"value": value}
        if kind == "text":
            return {"value": _number_from_text(value)}
        raise DataError("only a number or a text can become a number")
    if to == "integer":
        if kind == "number" and float(value).is_integer():
            return {"value": int(value)}
        if kind == "text" and re.fullmatch(r"\s*-?\d+\s*", value):
            return {"value": int(value)}
        raise DataError("the value is not a whole number")
    if to == "boolean":
        if kind == "boolean":
            return {"value": value}
        if kind == "number" and value in (0, 1):
            return {"value": bool(value)}
        if kind == "text" and value.strip().lower() in ("true", "false"):
            return {"value": value.strip().lower() == "true"}
        raise DataError("the value is not true or false")
    raise DataError("to must be text, number, integer or boolean")


def _split(a):
    text, separator = _need(a, "text", "text"), _need(a, "separator", "text")
    if not separator:
        raise DataError("separator must not be empty")
    if len(text) > MAX_TEXT:
        raise DataError("the text is too long")
    parts = text.split(separator)
    if a.get("trim") is True:
        parts = [part.strip() for part in parts]
    return {"value": parts}


def _join(a):
    items, separator = _need(a, "items", "list"), _need(a, "separator", "text")
    if len(items) > MAX_ITEMS:
        raise DataError("the list is too long")
    if any(_kind(item) not in ("text", "number", "boolean") for item in items):
        raise DataError("items must be a list of texts, numbers or booleans")
    return {"value": separator.join(_text(item) for item in items)}


def _format(a):
    template, values = _need(a, "template", "text"), _need(a, "values", "object")

    def fill(match):
        if match.group(0) in ("{{", "}}"):
            return match.group(0)[0]
        name = match.group(1)
        if name not in values:
            raise DataError(f"values has no field named {name}")
        return _text(values[name], name)

    return {"value": re.sub(r"\{\{|\}\}|\{([A-Za-z_]\w*)\}", fill, template)}


def _regex(a):
    text, pattern = _need(a, "text", "text"), _need(a, "pattern", "text")
    if not pattern or len(pattern) > MAX_PATTERN or len(text) > MAX_TEXT:
        raise DataError("the pattern or the text is empty or too long")
    try:
        found = re.search(pattern, text)
    except re.error:
        raise DataError("the pattern is not a valid regular expression") from None
    if not found:
        return {"match": False, "groups": [], "value": None}
    groups = ["" if g is None else g for g in found.groups()]
    return {"match": True, "groups": groups, "value": groups[0] if groups else found.group(0)}


def _path(a):
    path = _need(a, "path", "text")
    if not path:
        raise DataError("path must not be empty")
    return path.split(".")


def _get(a):
    current = _need(a, "object", "object", "list")
    for key in _path(a):
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            raise DataError("the path leads nowhere")
    return {"value": current}


def _set(a):
    result = copy.deepcopy(_need(a, "object", "object"))
    *parents, last = _path(a)
    current = result
    for key in parents:
        current = current.setdefault(key, {})
        if not isinstance(current, dict):
            raise DataError("the path goes through something that is not an object")
    current[last] = a["value"]
    return {"value": result}


def _number(a, name):
    value = a[name]
    if _kind(value) != "number":
        raise DataError(f"{name} must be a number")
    return value


def _math(a):
    x, y, operation = _number(a, "a"), _number(a, "b"), a["operation"]
    try:
        if operation == "add":
            result = x + y
        elif operation == "subtract":
            result = x - y
        elif operation == "multiply":
            result = x * y
        elif operation == "divide":
            result = x / y
        elif operation == "modulo":
            result = x % y
        elif operation == "power":
            if abs(y) > 1000:
                raise DataError("the exponent is too big")
            result = float(x) ** y
        else:
            raise DataError("operation must be add, subtract, multiply, divide, modulo or power")
    except ZeroDivisionError:
        raise DataError("division by zero") from None
    except OverflowError:
        raise DataError("the result is too big") from None
    if isinstance(result, complex) or not math.isfinite(result):
        raise DataError("the result is not a finite number")
    return {"value": int(result) if float(result).is_integer() and abs(result) < 2**53 else result}


def _compare(a):
    x, y, operator = a["a"], a["b"], a["operator"]
    kx, ky = _kind(x), _kind(y)
    if operator in ("equals", "not_equals"):
        same = kx == ky and x == y
        return {"value": same if operator == "equals" else not same}
    if operator in ("greater", "greater_or_equal", "less", "less_or_equal"):
        if kx != ky or kx not in ("number", "text"):
            raise DataError("only two numbers or two texts can be ordered")
        return {"value": {"greater": x > y, "greater_or_equal": x >= y, "less": x < y, "less_or_equal": x <= y}[operator]}
    if operator == "contains":
        if kx == "text" and ky == "text":
            return {"value": y in x}
        if kx == "list":
            return {"value": any(_kind(item) == ky and item == y for item in x)}
        raise DataError("contains needs a text and a text, or a list")
    if operator in ("starts_with", "ends_with"):
        if kx != "text" or ky != "text":
            raise DataError(f"{operator} needs two texts")
        return {"value": x.startswith(y) if operator == "starts_with" else x.endswith(y)}
    raise DataError("operator is not one of the known comparisons")


def _boolean(a, name):
    if not isinstance(a[name], bool):
        raise DataError(f"{name} must be true or false")
    return a[name]


def _and(a):
    return {"value": _boolean(a, "a") and _boolean(a, "b")}


def _or(a):
    return {"value": _boolean(a, "a") or _boolean(a, "b")}


def _not(a):
    return {"value": not _boolean(a, "a")}


# operation -> (required fields, optional fields, function)
OPS = {
    "fixed": (("value",), (), _fixed),
    "convert": (("value", "to"), (), _convert),
    "split": (("text", "separator"), ("trim",), _split),
    "join": (("items", "separator"), (), _join),
    "format": (("template", "values"), (), _format),
    "regex": (("text", "pattern"), (), _regex),
    "get": (("object", "path"), (), _get),
    "set": (("object", "path", "value"), (), _set),
    "math": (("a", "b", "operation"), (), _math),
    "compare": (("a", "b", "operator"), (), _compare),
    "and": (("a", "b"), (), _and),
    "or": (("a", "b"), (), _or),
    "not": (("a",), (), _not),
}


def check_op(op, fields: dict) -> None:
    """Raise ValueError unless `op` is a known operation and `fields` holds what it needs and nothing else."""
    if op not in OPS:
        raise ValueError(f"a data node needs an operation: one of {sorted(OPS)}")
    required, optional, _ = OPS[op]
    missing = [name for name in required if name not in fields]
    if missing:
        raise ValueError(f"the {op} operation needs the fields {missing}")
    unknown = [name for name in fields if name not in required + optional]
    if unknown:
        raise ValueError(f"the {op} operation has an unknown field {unknown[0]!r}")


def apply(op: str, args: dict) -> dict:
    """Run one operation on resolved field values and return its output Data."""
    required, optional, function = OPS[op]
    return function({**{name: None for name in optional}, **args})
