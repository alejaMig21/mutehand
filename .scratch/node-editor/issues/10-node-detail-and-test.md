# 10: Node detail, Test this node and Data panes

**What to build:** Open a node to see its inputs, settings and outputs; Test this node runs just that step after warning about mouse and keyboard; panes show the Data in and out of the last run, hidden by default and shown on request, secrets never.

**Blocked by:** 09 06

**Status:** resolved

- [x] Test this node runs one step against the real app and shows its result
- [x] Values stay hidden until asked and secrets never appear
- [x] Settings edit a field as a fixed value or a reference picked from a list

## Answer

Double click a node (or Open details) to get the detail window over the dimmed canvas: Data in, Settings, Data out
(`web/src/NodeDetail.jsx`, checked against `mockups/node-editor/D2-taller-plano-detail.png` in a headless screenshot).
- Settings: every field of a system node is edited as a fixed value (text, number, true or false, list or object; never guessed) or as a
  reference picked from a list of what the run data and the other nodes give out (`bindings.js`, `FieldEditor.jsx`). A step that types takes a
  `text` field. Each node also takes its failure policy (stop, retry N, carry on) and a step its typed inputs and "needs the mouse or keyboard".
- Data panes: `GET /api/flows/<id>/data` gives the Data that entered and left each node in the last run or test, as shapes ("text, 24
  characters") unless `?values=1`; the Show values switch (off by default) asks for the values. No secret is ever there: the core never holds one.
- Test this node: `POST /api/flows/<id>/nodes/<node>/test` runs that one node alone (steps and data nodes only), with the Data the last run gave
  its inputs (a reference to another node becomes the value it had; none yet means "run the flow first"). A step that acts on the app asks first:
  "This will use your mouse and keyboard". The tested flow is saved first. A failing test leaves a doubt like any run.
Tests: `tests/test_nodedata.py` (22), `tests/test_api_nodedata.py` (8), `web/src/bindings.test.js`, and 4 more browser tests.
