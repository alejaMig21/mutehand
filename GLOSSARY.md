# Desktop Workflow Factory

A system that automates repetitive work across Windows desktop apps. A deterministic apprentice replays what an AI tutor has taught it, and the user composes that knowledge into scheduled flows.

## Language

### Roles

**Apprentice**:
The deterministic process that replays lessons during a run. It never consults a language model and stops when anything is unexpected.
_Avoid_: Agent, bot, runner

**Tutor**:
Claude Code acting as teacher: it studies apps, teaches lessons, and answers doubts. It may be absent during a run.
_Avoid_: Teacher agent, supervisor

### Knowledge

**Lesson**:
One learned action with its precondition, the action itself, and the effect measured when it was taught.
_Avoid_: Skill, macro, recipe

**Precondition**:
What must be true on screen before a lesson may run.
_Avoid_: Guard, requirement

**Effect**:
The measured change a lesson causes, drawn from a closed vocabulary (closed dialog, revealed, value changed, no change, pixels changed).
_Avoid_: Result, outcome

**Frame**:
The exact conditions in which a lesson was measured: window state and size, resolution, scale, language, theme. The app and its version belong to the App key, not the frame. A lesson replays only inside its frame.
_Avoid_: Environment, context, setup

**Relevance mask**:
The subset of a frame's fields that actually matter for one lesson.
_Avoid_: Filter

**App key**:
An app's identity: process name plus executable version.
_Avoid_: App id

**To revalidate**:
The status of a lesson whose app changed version. The lesson is kept but not trusted until re-measured.
_Avoid_: Stale, expired

**Trusted / suspect / rejected**:
Confidence states of a lesson, derived from its success and failure counters. Rejected can only be restored by a human.
_Avoid_: Good, bad

**Factory knowledge**:
The read-only lessons and template flows shipped with each build.
_Avoid_: Default data, built-in

**User knowledge**:
The lessons, flows, consents, doubts and history that belong to one user and are never replaced by an update.
_Avoid_: Local data, custom data

**Origin**:
Whether a lesson came from factory knowledge or was taught locally.
_Avoid_: Source

**Study order**:
The sequence in which the tutor explores an app's controls to teach lessons systematically.
_Avoid_: Crawl plan

### Locating

**Locator ladder**:
The ordered ways to find an action's target: accessibility identity, then geometry derived from a re-located element, then bounded template search. Absolute screen coordinates are never a rung.
_Avoid_: Fallback chain, selector

**Template**:
A stored image fragment a lesson uses on the last rung of the locator ladder.
_Avoid_: Screenshot, sprite

### Flows

**Workday**:
One scheduled execution of a flow on the user's PC.
_Avoid_: Job, batch

**Flow**:
A graph of nodes, with branching, conditions, joins and capped loops, that describes a workday.
_Avoid_: Workflow, pipeline, script

**Node**:
One step of a flow: a lesson, or a group of lessons for one app, with typed inputs and outputs.
_Avoid_: Task, block, step

**Run context**:
The named, typed values that travel between nodes during one workday.
_Avoid_: Variables, state

**Checkpoint**:
A saved point in a running flow from which it can resume after a stop.
_Avoid_: Snapshot, save state

**Physical input**:
Real mouse, keyboard or focus use, as opposed to accessibility actions that need none. Nodes that need it cannot run at the same time as each other.
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
A pointer to a value kept in the Windows credential store. Lessons and the tutor only ever hold the reference.
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

### Coexistence

**User pause**:
The apprentice halting a flow because the user touched the mouse or keyboard, then waiting for idle and re-verifying preconditions before resuming.
_Avoid_: Interruption, yield

**Emergency stop**:
The global hotkey that halts all automation at once.
_Avoid_: Kill switch
