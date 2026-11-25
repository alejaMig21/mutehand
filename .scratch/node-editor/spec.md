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

## Interface design (chosen by the person, 2026-11-25)

Direction D: the structure of A ("Taller") with the colour scheme of B ("Plano"). The three reference images are
`mockups/node-editor/D1-taller-plano-canvas.png`, `D2-taller-plano-detail.png` and `D3-taller-plano-run.png`
(1440 x 900 CSS px); the other directions stay in `design/node-editor/` (not committed) for comparison.

- Structure: a top bar (flow name, saved state, safety summary, Test flow and Run flow, which becomes Stop while running);
  a full canvas with node cards joined by wires on a dotted grid; the node search panel as a floating card on the right
  over the canvas; the node detail as a window over the dimmed canvas with three panes (Data in, Settings, Data out); the
  run log as a sheet along the bottom.
- Colours: ground #0D1520, surface #142030, sunk #0A111A, ink #E4ECF6, muted #8EA2B7, line #26384C, accent #4CC9F0 with
  text #06202B on it, ok #5BE49B, warn #FFC857, bad #FF7A7A with text #2B0A0A on it, info #7DB8FF. Every text pair is at
  least 4.5:1 (lowest: muted on the surface, 6.3:1).
- Type: system sans (Segoe UI Variable) for the interface, Cascadia Mono for Data field names, values and the log.
- App icons are neutral letter chips, never a company's logo. Trust, consent, private app, adapted-from and doubts always
  show an icon and a word, never colour alone.
