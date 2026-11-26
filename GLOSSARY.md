# Desktop Workflow Factory

A mini n8n for Windows desktop apps whose building blocks are taught by an agent. A deterministic apprentice replays what an AI tutor has taught it, and the user wires that knowledge, with system nodes, into flows that run and are scheduled without any agent.

## Language

### Roles

**Apprentice**:
The deterministic process that replays steps during a run. It never consults a language model and stops when anything is unexpected.
_Avoid_: Agent, bot, runner

**Tutor**:
An agent in Claude Code acting as teacher: it studies apps, teaches steps and recipes in lessons, and answers doubts. It may be absent during a run.
_Avoid_: Teacher agent, supervisor

### Knowledge

**Lesson**:
A teaching session in which the tutor teaches the apprentice steps and recipes about one topic. It always goes through the tutor, never through the editor.
_Avoid_: Skill, macro

**Step**:
One learned action on one control of an app, with its precondition, the action itself and the effect measured when it was taught. A step that writes text or selects keeps no effect, so runs neither trust nor reject it. It is a node of a flow and is reusable.
_Avoid_: Action, task

**Basic operation**:
A generic kind of action the system provides (write text in a field, press a button, read text, wait for a control, paste). A step is a basic operation bound to one app's control.
_Avoid_: Command, primitive

**Recipe**:
An ordered pattern of steps with holes for each app's own controls, reusable across apps. Dropped into a flow it expands into connected nodes.
_Avoid_: Macro, template

**Hole**:
The place in a recipe that one app fills with its own control.
_Avoid_: Slot, parameter

**Precondition**:
What must be true on screen before a step may run.
_Avoid_: Guard, requirement

**Effect**:
The measured change a step causes, drawn from a closed vocabulary (closed dialog, revealed, value changed, no change, pixels changed).
_Avoid_: Result, outcome

**Frame**:
The exact conditions in which a step was measured: window state and size, resolution, scale, language, theme. The app and its version belong to the App key, not the frame. A step replays only inside its frame.
_Avoid_: Environment, context, setup

**Relevance mask**:
The subset of a frame's fields that actually matter for one step.
_Avoid_: Filter

**App key**:
An app's identity: process name plus executable version.
_Avoid_: App id

**To revalidate**:
The status of a step whose app changed version. The step is kept but not trusted until re-measured.
_Avoid_: Stale, expired

**Trusted / suspect / rejected**:
Confidence states of a step, derived from its success and failure counters. Rejected can only be restored by a human.
_Avoid_: Good, bad

**Factory knowledge**:
The read-only steps, recipes and template flows shipped with each build.
_Avoid_: Default data, built-in

**User knowledge**:
The steps, recipes, flows, consents, doubts and history that belong to one user and are never replaced by an update.
_Avoid_: Local data, custom data

**Origin**:
Whether a step came from factory knowledge or was taught locally.
_Avoid_: Source

**Study order**:
The sequence in which the tutor explores an app's controls to teach steps systematically.
_Avoid_: Crawl plan

### Locating

**Locator ladder**:
The ordered ways to find an action's target: accessibility identity, then geometry derived from a re-located element, then bounded template search. Absolute screen coordinates are never a rung.
_Avoid_: Fallback chain, selector

**Template**:
A stored image fragment a step uses on the last rung of the locator ladder.
_Avoid_: Screenshot, sprite

### Flows

**Workday**:
One scheduled execution of a flow on the user's PC.
_Avoid_: Job, batch

**Flow**:
A graph of nodes, with triggers, branching, conditions, joins and capped loops, that describes a workday.
_Avoid_: Workflow, pipeline, script

**Node**:
One piece of a flow: a step or a system node.
_Avoid_: Task, block

**System node**:
A node that comes with the app and needs no teaching: triggers, logic, loops, joins, waits and data handling.
_Avoid_: Built-in, utility node

**Trigger**:
A system node that starts a flow: by hand, or at a scheduled time.
_Avoid_: Event, starter

**Data**:
The one format in which every node takes in and gives out information: named fields, readable as text when a field needs text. Any node connects to any other because all of them speak it.
_Avoid_: Payload, item, message

**Run context**:
The Data a workday starts with.
_Avoid_: Variables, state

**Checkpoint**:
A saved point in a running flow from which it can resume after a stop.
_Avoid_: Snapshot, save state

**Physical input**:
Anything that acts on an app: mouse, keyboard, or an accessibility click or set-value, because all of them can take the foreground window (research 20). Every step needs it, so acting nodes never run at the same time as each other and pause while the person is active. Only reads (snapshot, find, get, capture) are free of it.
_Avoid_: Headed mode (a tool detail), UI input

### Safety

**Consent**:
The user's recorded yes to teaching the apprentice one sensitive action, scoped to an app, control and action.
_Avoid_: Permission, approval

**Consent gate**:
The rule that a sensitive action without a consent record is blocked, including anything the apprentice cannot read.
_Avoid_: Hard floor, blocklist

**Sensitive action**:
An action in a category that needs consent: password fields, system shortcuts, outward actions (send, publish, buy), and veto text.
_Avoid_: Dangerous action, risky action

**Secret reference**:
A pointer to a value kept in the Windows credential store. Steps and the tutor only ever hold the reference.
_Avoid_: Password field, stored credential

### Communication

**Tutor queue**:
The list of doubts the apprentice leaves for the tutor.
_Avoid_: Inbox, ticket list

**Doubt**:
One entry in the tutor queue: where the apprentice stopped, why, a structural capture, and its status (open, answered, dismissed).
_Avoid_: Issue, error, question

**Structural capture**:
A summary of the screen made of roles and counts only, with no text, so private content never leaves the machine.
_Avoid_: Screenshot, dump

**Private app**:
An app whose content must not reach the tutor (chats, browsers, anything the user marks). When the tutor observes one it receives a structural capture instead of control names.
_Avoid_: Sensitive app, protected app

### Coexistence

**User pause**:
The apprentice halting a flow because the user touched the mouse or keyboard, then waiting for idle and re-verifying preconditions before resuming.
_Avoid_: Interruption, yield

**Emergency stop**:
The global hotkey that halts all automation at once.
_Avoid_: Kill switch
