# Node editor: a mini n8n whose steps are taught by an agent

Decisions come from the design grill of 2026-11-25 (answers recorded in engram `decision/editor-design`). Vocabulary is in
`GLOSSARY.md` (Step, Lesson, Recipe, Hole, Basic operation, System node, Trigger, Data) and the reasons in `docs/adr/0006`.

## Principles

- The editor never starts a lesson. It lists what was already taught and lets a person build, test, run and stop flows
  with no agent. Lessons start only through the tutor tools, in a chat with an agent.
- Steps are small and reusable. Recipes carry the pattern across apps; the agent teaches only the controls that differ.
- Every node speaks Data. Each field of a node is a fixed value or a reference to another node's output; expressions come
  later and the stored form already has room for them.
- Two audiences: engineers who program and people who do not. Simple by default, power opt-in, plain words.

## What the editor is

- An n8n-style free canvas: node cards joined by wires, a search panel on the right to add nodes, a detail view per node
  (inputs, settings, outputs), a run view with per-node status and a stop. There is no separate node-picker screen.
- The right panel groups: system nodes, apps (their steps, with the app icon, searchable) and recipes (dropping one expands
  it into connected nodes). A step adapted from another app carries a discreet "adapted from X" mark.
- Interface look: imitate n8n's structure with an own identity, chosen by the person among local design proposals.

## v1 system nodes

Triggers: manual, daily. Logic: if, compare, and, or, not. Flow: for each, join, wait, stop. Data: fixed value, convert
type, split/join/format text, regular expression, read/write an object field, math. Deferred: code node, web requests,
other triggers, sub-flows, flow versioning, the expression field.

## Behaviour that must hold

- Errors, per node: stop (default, leaves a doubt in the queue), retry N times, or continue. An error branch comes later.
- Safety is always visible: each step shows trusted, on trial or rejected; sensitive steps show a lock and their consent; a
  flow with a rejected step does not start and says which; private apps are distinguishable in the catalog.
- "Test this node" runs only that step against the real app and warns first that it will use the mouse and keyboard.
- The node detail shows the Data that entered and left in the last run. Values are hidden by default and shown on request;
  secrets are never shown.
- The editor shows the apprentice's open doubts as a count and marks the affected node, but cannot resolve them.

## Tickets

01 local design prototype; 02 rename lesson to step in the code; 03 Data and field bindings in the engine; 04 flow system
nodes; 05 data system nodes; 06 error handling per node; 07 steps that read values out of an app; 08 recipes in the tutor
tools; 09 new canvas shell with the right search panel; 10 node detail, test this node and Data panes; 11 run view,
safety marks and doubts count; 12 recipes in the editor.
