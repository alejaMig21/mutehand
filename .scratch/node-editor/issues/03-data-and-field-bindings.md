# 03: Data and field bindings in the engine

**What to build:** Every node takes in and gives out Data (named fields); a node's field is stored as a fixed value, a reference to another node's output, or an expression kept for later. The run context becomes the Data a workday starts with; typed inputs give way to Data.

**Blocked by:** 02

**Status:** resolved

- [x] Data flows from one node to the next in a run and is checkpointed
- [x] A saved flow with fixed and referenced fields loads, runs and round-trips
- [x] The stored field form has room for expressions without a migration

## Answer

`src/workflow_factory/data.py` defines the binding forms: a node's `fields` map a name to exactly one of `{"value": ...}`,
`{"ref": {"node": id, "field": name}}` (node `run` is the Data a workday starts with) or `{"expression": "..."}`.
Each finished step records `{"effect": ...}` as its output Data, saved in the checkpoint (`outputs`), and a type_value node
takes its text from a `text` field (the older typed `inputs` still work). Expressions are stored and round-trip, but
`run_flow` refuses to start with one. Tests: `tests/test_data.py`. Not done here, by design: the Data of steps that read
values out of an app (ticket 07) and the system nodes (tickets 04, 05).
