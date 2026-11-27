---
status: accepted
---

# Generic steps with tags, a technology per node, and sub-flows as components

Excel was only the guinea pig of the first lessons, and it shaped the model badly: steps are stored and listed per app, so "Save workbook" (Excel) and "Save" (Paint) are unrelated, the editor filters nodes by program, and a node such as Save exposes no folder or file name. We decided to start the knowledge model again, with no migration, and to supersede the part of ADR 0006 that makes a step belong to one app. The rest of ADR 0006 holds: steps stay small and indivisible, there are no big composite lesson nodes, and Data stays the one format between nodes.

- **A step is generic.** It is named by what it does ("Save"), never by a program, and holds one **locator** per **technology** it has been learned for (Excel, Word, Paint). Its **technology tags** come from where it was learned; the tutor may add free **pattern tags** ("file", "mouse"). A **universal step** has no technology.
- **A node records its technology.** A step node says which technology it acts on, so one flow can use several programs. The engine still runs one program per run until phase 4.
- **A component is a flow used as a node.** It declares its own inputs and outputs, as many of each as it needs, as an explicit list of name and type. Inputs are the run data the sub-flow starts with. Its technology tags are computed from the steps inside it. A multi-step action such as Save (click Save, write the name, choose the folder, confirm) is built once as a component of small steps, so a failure still names the inner step.
- **One filter, grouped by node type.** The node panel has a single search box that matches a step or component name and its tags. Below it, collapsible sections by node type: Steps, Components, Triggers, Order, Logic, Data. With the filter empty only Steps and Components are open. A universal step shows only when its name or tags match what is typed.
- **The screens use the domain words:** Flow, Node, Step. "Chore", "box" and "action" are retired.
- **Icons:** a program shows its own icon, read from its executable on the person's PC; each node type has one icon.

## Considered options

- **Keep the per-app storage and show a grouped view.** Rejected: the person does not want to keep what the first lessons taught, and a view over a flawed model hides the flaw.
- **Composite nodes that run several steps inside one node.** Rejected for the reasons of ADR 0006. Components give the same result with the inner steps visible.
- **The program as a property of the whole flow.** Rejected: it forbids a flow that goes from a browser to Word to a chat.

## Consequences

- The user database starts empty. The old one is kept as a dated copy (`user.db`, renamed) and nothing is imported.
- The tutor tools (`teach_step`, `list_known_steps`, `create_flow`, `flow_status`), `docs/agents/tutor.md`, the API, the editor panel, the Apps screen and the tests change with the model. The tutor must now think about what each step takes in and gives out, and publish multi-step actions as components.
- Recipes (one pattern, one hole per app) overlap with generic steps that hold several locators. Whether recipes stay is decided in phase 2.
- Built in phases, each with its own PR: (1) the model, tags, one filter, grouped panel, names, tutor tools; (2) components with inputs and outputs; (3) icons; (4) the engine for several programs per run, an "open program" node, and universal steps such as a mouse move with natural noise.
