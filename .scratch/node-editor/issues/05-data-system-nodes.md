# 05: Data system nodes

**What to build:** Fixed value, convert type, split/join/format text, regular expression, read and write an object field, math, and the boolean nodes compare, and, or, not.

**Blocked by:** 03

**Status:** resolved

- [x] Each node is a pure function of its Data with tests for normal and bad input
- [x] A bad value fails the node with a clear message, never silently
- [x] None of them needs the desktop or the input lock

## Answer

`src/workflow_factory/dataops.py` holds the pure functions; a flow node is `Node(id, kind="data", op=..., fields={...})` and every
operation gives out `{"value": ...}` (regex also `match` and `groups`). Operations: fixed, convert (text, number, integer, boolean),
split (optional trim), join, format (named places only, doubled braces), regex (pattern and text length capped), get and set (dotted
path), math (add, subtract, multiply, divide, modulo, power), compare (equals, not_equals, greater, greater_or_equal, less,
less_or_equal, contains, starts_with, ends_with), and, or, not. Booleans are never confused with numbers and a truth is never guessed.
- A bad value fails the node with the doubt reason `bad_data` and the message `{"error": ...}` in its output Data; the message
  names the problem, never the value (`result.outputs` is in memory only; the report never holds it, tested).
- Data nodes touch no control and take no input lock.
- `if` can now route on a true or false (`fields["condition"]`) as well as on a measured effect.
- A reference between nodes now also orders them (the node waits for the one it points at), and a `foreach` body waits as its foreach.
Tests: `tests/test_dataops.py` (111), `tests/test_data_nodes.py` (12).
