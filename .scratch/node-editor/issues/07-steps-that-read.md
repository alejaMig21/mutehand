# 07: Steps that read values out of an app

**What to build:** A basic operation that reads text or a value from a control and gives it out as Data, so a later node can use it. Private apps give only what the person allows.

**Blocked by:** 03

**Status:** resolved

- [x] Reading is free of the input lock and never prints values into reports unless enabled
- [x] The consent gate covers reading from a private app
- [x] A read step's output is checked by a test on a fake desktop

## Answer

New basic operation: the step action `read_value`. Its node gives out `{"value": <text of the control>}` (empty text when the control has none).
- `Desktop.read_text(control)`; the agent-desktop adapter uses `get --property value` (verified live on a throw-away probe window of ours:
  a value set in the box read back exactly). It acts on nothing, so `Step.uses_physical_input` is false for it: no input lock and no
  wait for the person.
- A password-type control is never read (`unreadable`, as before). In an app marked private (Telegram, browsers, or any the person marked)
  a read needs a consent record for the action `read_value`; without it the node stops with `no_consent` and nothing is read.
- Values live only in the run's Data (in memory and the local checkpoint); the report never holds them (tested with `--with-values`).
Tests: `tests/test_read_values.py` (10).
