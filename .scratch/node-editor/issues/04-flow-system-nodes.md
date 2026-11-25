# 04: Flow system nodes: triggers, for each, wait, stop

**What to build:** Triggers (manual, daily) become nodes at the root of a flow; add for each (explicit iteration over a list in Data), wait and stop beside the existing if, join and loop.

**Blocked by:** 03

**Status:** resolved

- [x] A flow starts from a trigger node, by hand or on schedule
- [x] For each runs its body once per list item and stops cleanly when told
- [x] Wait and stop behave under the emergency stop and the user pause

## Answer

New node kinds in `flow.py`: `trigger` (fixed `mode` manual or daily, and a daily `at` as HH:MM), `foreach`, `wait`, `stop`.
- A run is started with `fired` (`run_flow(..., fired="manual")`, `workday --fired`, and the scheduled task passes `--fired daily`).
  Only the triggers of that mode fire; a manual run of a flow with no manual trigger fires them all, and a flow with no trigger
  runs as before. A trigger gives out the Data the workday started with.
- `foreach` repeats ONE body node (a step) once per item of its `items` list, giving `item`, `index` and `count` as Data; the body
  runs only inside it and cannot have edges of its own. It checkpoints per item, so a stop resumes at the item it was on.
  Not done: a body of several nodes (that comes with sub-flows).
- `wait` sleeps its `seconds` in one-second slices (the emergency stop is heard within a second) and a resume waits only the rest.
  A wait acts on nothing, so the person working does not pause it; the steps around it still do.
- `stop` ends the flow on purpose: nothing that has not run yet runs, the result is `finished` with `halted_by` set.
Tests: `tests/test_flow_nodes.py` (28), plus the workday and schedule tests.
