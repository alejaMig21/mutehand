# 09: New canvas shell with the right search panel

**What to build:** Rebuild the editor shell in the chosen design: canvas, nodes added from the right search panel (system nodes and apps), wires, open and save. It lists only taught steps and never starts a lesson.

**Blocked by:** 01 03 04 05

**Status:** resolved

- [x] Add, connect, move and delete nodes; save and reopen a flow
- [x] The search panel finds system nodes and steps by name and by app
- [x] No control in the editor starts a lesson

## Answer

The editor screen is rebuilt in direction D (`web/src/styles.css` holds the tokens; checked against `mockups/node-editor/D1-taller-plano-canvas.png` in a headless screenshot).
- Top bar: flow name, state pill (draft, saved, running, finished...), Flows menu (new, open, duplicate a template), the app to run on,
  Run data (the values a run starts with), Save, Run flow.
- Canvas: custom node cards (system node icon or app letter chip, a "Needs consent" mark), wires, move, delete (button or Delete key).
  A node added while another is selected goes to its right and is wired after it; the view re-fits so nothing hides under the panel.
- Right search panel (`SearchPanel.jsx`, `catalog.js`): the system nodes (20) and the steps already taught, searched by name, hint, app
  or origin. It only adds what exists; the editor has no control that starts a lesson (browser test greps the whole screen).
- Wires that mean something: the first two wires out of an `if` are its then and otherwise; the first node a `for each` connects to is its
  body (stored as `body`, not as an edge). A flow stored with no edges is drawn one node after another. Stored flows are laid out in columns.
- Not here (later tickets): node detail window and Test this node (10), trust marks and doubts count (11), recipes (12).
Tests: `web/src/flowjson.test.js`, `web/src/catalog.test.js` (14) and `tests/test_editor_e2e.py` (12, headless).
