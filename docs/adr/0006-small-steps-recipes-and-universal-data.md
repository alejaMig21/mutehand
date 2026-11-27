---
status: accepted
---

# Small reusable steps, recipes across apps, and one Data format between nodes

The product is a mini n8n whose building blocks are taught by an agent. We decided that a **step** (one action on one
control of an app) is the node, kept small so steps can be reused; that a **lesson** is the teaching session that leaves
steps and **recipes** (ordered patterns of steps with holes for each app's controls); and that every node takes in and
gives out one format, **Data**. Nothing in the editor starts a lesson: it may show words for the person to send in a chat (and a button that copies
them), but teaching happens only through the tutor tools, in that chat. The person's own example: once the apprentice knows how
to send a message in Telegram, a recipe lets the agent teach only the controls that differ for WhatsApp.

## Considered options

- **Big composite lesson nodes** ("save file as", with parameters, built by the agent). Rejected: they cannot be reused
  across apps, and one failing detail hides inside a big node.
- **Typed ports per node with strict types.** Rejected for one universal Data envelope: any node connects to any other,
  conversions are explicit nodes, and a text field accepts any result that can be shown as text.
- **A Teach button in the editor.** Rejected: the editor must work without an agent for people who only build flows.

## Consequences

- `GLOSSARY.md` now says Step, Lesson, Recipe, Hole, Basic operation, System node, Trigger and Data. The code still says
  `Lesson` for what the glossary calls a step (table, API, the `teach_lesson` tool) until the rename ticket runs; existing
  lessons migrate as one-step lessons and nothing is lost.
- A node's `inputs` of `(name, type)` and the typed run context give way to Data. Each field is stored as a fixed value, a
  reference to another node's output, or (later) an expression, so adding expressions will not break saved flows.
- Triggers, loops and joins are system nodes; v1 has manual and daily triggers and the model leaves room for more.
- Showing Data of a run keeps the existing privacy rules: values hidden by default and shown on request, secrets never.
