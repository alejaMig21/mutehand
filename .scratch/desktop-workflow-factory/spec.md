# Spec: desktop-workflow-factory v1

Status: ready-for-agent (local copy; move to the issue tracker once `/setup-matt-pocock-skills` has run).
Source: design interview 2026-11-13, Q1-Q20 (engram project `desktop-workflow-factory`, topics under `architecture/*`).

## Problem Statement

A person wants their Windows PC to carry out repetitive "workday" tasks across many desktop apps (Paint, Word, Telegram, a browser, File Explorer) without a language model running at execution time. Today's predecessor (hubstaff-automation) only drives mouse and keyboard from pixels and breaks when anything moves. Generic agent runtimes need an LLM on every step, which is costly, slow, and unavailable when the PC is offline. The user also needs control over what automation may do (passwords, sending messages, buying) and must be able to keep using the PC while flows run.

## Solution

Two roles on top of the agent-desktop CLI (accessibility-tree perception and actions):

- **Apprentice**: a deterministic Python process that replays learned **lessons** inside the exact **frame** (app + version, window state, resolution, scale, language, theme) in which they were measured. It never calls an LLM. When anything is unexpected it stops that flow and leaves a doubt in the **tutor queue**.
- **Tutor**: Claude Code. It studies apps, teaches lessons, answers queue doubts, and fixes bad lessons, using the project's own MCP tools. It is often absent (the PC is frequently offline); the apprentice must work without it.

Users compose lessons into **flows** (graphs with branching, IF, joins, capped loops, typed data) in a local web editor, and schedule them with Windows Task Scheduler. The product ships with a read-only **factory** knowledge base (pre-taught lessons and template flows) so end users do not need to teach anything for common apps.

## User Stories

1. As an end user, I want to open a local web app and see my flows, so that I can manage my automations without the command line.
2. As an end user, I want to build a flow by dragging lesson nodes from a palette and connecting them, so that I can describe a workday visually.
3. As an end user, I want to configure typed inputs on a node, so that data from one app (e.g. text from a browser) reaches another (e.g. a document).
4. As an end user, I want a node not to start when one of its required inputs is missing, so that a flow never acts on bad data.
5. As an end user, I want to branch a flow into parallel paths and rejoin them with a join node, so that independent work does not wait in line.
6. As an end user, I want an IF node that branches on a measured effect, so that a flow can react to what really happened on screen.
7. As an end user, I want loops capped by both iteration count and elapsed time (up to 8 hours), so that a runaway loop cannot go on forever.
8. As an end user, I want each loop iteration to write a checkpoint, so that a stopped flow resumes from the last good point.
9. As an end user, I want a loop to stop after N consecutive failures and queue a doubt, so that a broken step does not repeat endlessly.
10. As an end user, I want to run a flow manually and see live per-node status, so that I can watch progress and failures.
11. As an end user, I want a run history showing what each workday did and what stopped and why (no data values by default), so that I can audit runs without exposing private content.
12. As an end user, I want to duplicate a factory template flow into my own layer, so that I can customize it without altering shipped content.
13. As an end user, I want to export and import flows as JSON, so that I can review them or keep them in git.
14. As an end user, I want a lesson library per app that shows factory vs local origin and confidence state, so that I know which actions I can trust.
15. As an end user, I want to manually mark or reject a lesson, so that I can remove an action I do not trust.
16. As an end user, I want a consents screen listing every granted consent with its scope (app, control, action), so that I can see what the apprentice is allowed to do.
17. As an end user, I want to revoke a consent from the UI, so that I can withdraw permission instantly.
18. As an end user, I want factory lessons in sensitive categories to ship without active consent, so that nothing sensitive runs until I grant it at first use.
19. As an end user, I want the apprentice to pause when I touch the mouse or keyboard, so that automation never fights me for the PC.
20. As an end user, I want the apprentice to wait for N seconds of idle and re-verify preconditions before resuming, so that a pause never resumes into a changed screen.
21. As an end user, I want the apprentice to verify the target window is in the foreground before pressing keys, so that text never lands in the wrong app (for example Telegram).
22. As an end user, I want a global emergency hotkey that stops everything at once, so that I can halt automation immediately.
23. As an end user, I want the editor served only on `127.0.0.1` behind a token, so that nothing else on my network can control my PC.
24. As an end user, I want my local knowledge database never overwritten by a product update, so that updating the product does not erase what I taught.
25. As an end user, I want lessons marked "to revalidate" (not deleted) when an app's version changes, so that I keep my work but do not trust it blindly.
26. As an end user, I want secrets stored in the Windows Credential Manager and referenced by lessons, so that no password sits in my database.
27. As an end user, I want flows launched by Windows Task Scheduler, so that workdays start without me opening anything.
28. As the tutor, I want an MCP tool to observe an app (a summarized snapshot), so that I can study it without seeing private content.
29. As the tutor, I want an MCP tool to set the study order for an app, so that I explore it systematically.
30. As the tutor, I want an MCP tool to name and store a lesson with precondition, action and measured effect, so that knowledge persists for the apprentice.
31. As the tutor, I want lessons autosaved as soon as an effect is measured, so that an interrupted session loses nothing and can resume.
32. As the tutor, I want an MCP tool to list open doubts, so that I can see what the apprentice could not do.
33. As the tutor, I want to answer a doubt by teaching a new lesson or fixing an old one and mark it answered, so that the stopped flow can resume.
34. As the tutor, I want to stop and ask the user for consent when I meet a password field, system shortcut, outward action or veto text, so that sensitive abilities are only taught with permission.
35. As the tutor, I want observations of apps marked private (Telegram, browsers) to be summarized to roles and counts, so that private text never reaches me.
36. As the tutor, I want no MCP tool that exposes `--force` or trace screenshots, so that I cannot bypass agent-desktop's protections.
37. As the tutor, I want to pass secrets only by reference, so that I never see their values.
38. As the apprentice, I want to locate controls by accessibility (role + name + automation id) first, so that actions survive layout changes.
39. As the apprentice, I want a second rung of derived geometry (offset or fraction relative to a re-located element or window), so that moving targets like desktop icons still work.
40. As the apprentice, I want a third rung of bounded template search inside a region using a stored template, so that canvas-like content without accessibility can be handled.
41. As the apprentice, I want to never use absolute screen coordinates, so that actions do not depend on a fixed layout.
42. As the apprentice, I want to go to the tutor queue instead of silently falling through to the next rung when one fails, so that unexpected states are reviewed.
43. As the apprentice, I want to verify each lesson's precondition and measure its effect against a closed vocabulary (closed_dialog, revealed, value_changed, no_change, pixels_changed), so that success is objective.
44. As the apprentice, I want to look up lessons in the user database first and then the factory database, so that local corrections override shipped knowledge.
45. As the apprentice, I want to block any action lacking a consent record, so that unconsented sensitive actions never run.
46. As the apprentice, I want to treat "unreadable" as "blocked", so that I never act on something I cannot perceive.
47. As the apprentice, I want to serialize nodes that need exclusive physical input and run others in parallel, so that throughput is high without input collisions.
48. As the apprentice, I want to write a queue row when I stop (node, lesson, reason, structural capture, status open), so that the tutor knows exactly what to fix.
49. As the apprentice, I want the stop reasons limited to precondition not met, control not found, no consent and template no match, so that doubts are triaged consistently.
50. As a maintainer, I want lessons to track local success/failure counters separately from shipped factory counters, so that a lesson is never "trusted locally" without two own successes.
51. As a maintainer, I want confidence computed as (successes + 1) / (successes + 3 * failures + 2) with trusted >= 0.80 (>= 2 own successes, 0 failures), suspect < 0.50, rejected < 0.30 restorable only by a human, so that trust is explainable.
52. As a maintainer, I want a command that exports the user database to JSON, so that knowledge can be reviewed and versioned.
53. As a maintainer, I want to run the whole system's tests against a fake desktop with no real screen access, so that tests are fast, safe and deterministic.
54. As a maintainer, I want opt-in live smoke tests, so that real agent-desktop behavior is checked without running on every commit.
55. As a maintainer, I want unverified assumptions listed as explicit risks, so that surprises are found early.

## Implementation Decisions

**Architecture and roles**
- Apprentice is a deterministic process with no LLM at runtime. The tutor is Claude Code and is optional at runtime.
- agent-desktop (Rust CLI) provides perception and accessibility actions. Physical mouse reuses a curated slice of the predecessor project (confidence, concepts, frontier, delta classification, app map, hard-floor orchestration, Bezier mouse movement, wander, SendInput). The predecessor's vision adapters are dropped.
- Python project (uv) with stdlib `sqlite3`. A TypeScript/React Flow frontend lives beside it; its bundle is prebuilt so users need no Node.
- First study target is Windows Paint, in full (toolbars are accessible; the canvas has no interactive element, so it uses the geometry and template rungs).

**Single test seam: the desktop port**
- One interface isolates everything that touches the machine: the agent-desktop adapter, the user-input/idle detector (cursor position and last-input time), and the clock. Production wires agent-desktop; tests wire fakes.
- The core exposes public entry points: run a flow, study an app, MCP tools, answer queue doubts, consent grant/revoke. All other modules (lessons, frames, flows, queue, consent gate, coexistence) are exercised through those with real SQLite on a temp file.

**Storage**
- Two SQLite files: a read-only FACTORY database shipped with each build (default lessons and template flows) and a USER database (local lessons, flows, consents, queue, run history). Product updates replace only the factory file. Each lesson records provenance (`factory` or `local`). Lookup order: user first, then factory.
- JSON is only for export/import/review/git; no YAML.

**App identity and frame**
- App key = process name + executable version. On version change the app's lessons become `to_revalidate`, never deleted.
- A frame is a record with named fields (app + version, window state/size, resolution, scale, language, theme), per-field tolerance, and a per-lesson relevance mask. A numpy vector view computes distance; canvas captures are real pixel tensors. Replay is allowed only inside the frame where the lesson was measured.

**Lesson**
- Fields: precondition, action, measured effect, success/fail counters (factory and local kept separate), status (`trusted | suspect | rejected | to_revalidate`), frame + relevance mask, origin (`factory | local`).
- Actions: click, drag (origin and destination, both located by the ladder), scroll/zoom (region), bounded search_pattern.
- Locator ladder per action endpoint: (1) accessibility role + name + automation id; (2) derived geometry relative to a re-located element or window; (3) bounded template search in a region with a template stored in the lesson. Absolute screen coordinates are never used. A failed rung goes to the tutor queue; it does not silently fall through.
- Pixel comparison is the apprentice's own code on a PNG from the full-screen screenshot command; agent-desktop does not match appearance. Matching is deterministic but sensitive to theme, scale and occlusion.
- No GOAP planner in v1: lessons are stored with preconditions and effects and used as-is.

**Consent gate (hard floor)**
- Sensitive categories: password fields, system shortcuts, outward actions (send, publish, buy), veto text. When the tutor meets one it stops and asks the user. A yes is stored in the lesson with scope (app, control, action). No consent record means blocked. "Unreadable" means blocked.
- No per-task permission and no quota unless the user writes one. Factory lessons in sensitive categories ship without active consent; the user grants it at first use.
- Secrets are references to the Windows Credential Manager; values pass to agent-desktop via stdin only, never in batch JSON or process arguments. Project MCP tools never expose force or trace screenshots. Observations of apps marked private are summarized to roles and counts.
- Consents screen can only revoke; granting happens at teaching time.

**Flows**
- Flow = graph stored in SQLite (factory template layer, read-only; user layer, editable; users duplicate templates). Nodes are a lesson or group of lessons of one app, with precondition, expected effect and typed inputs/outputs. Free branching, IF nodes on measured effect, join nodes, loops capped by iterations AND time (8 h allowed).
- Data travels in a typed run context of named values; a node does not start with a missing input.
- Each node declares whether it needs exclusive physical input (mouse/keyboard/focus, headed mode, canvas, drags). Those serialize; others may run in parallel.
- Each loop iteration writes a checkpoint to disk and re-verifies preconditions; N consecutive failures stop the loop and queue a doubt.
- Windows Task Scheduler launches runs. Run reports contain no values unless the user asks.

**Tutor and MCP tools**
- Project-owned MCP tools wrap agent-desktop: observe, set study order, name/save lesson, list and answer queue doubts. Lessons autosave when measured; interrupted sessions resume.
- Tutor queue = table in the user database. Row: node, lesson, reason (precondition not met, control not found, no consent, template no match), structural capture (roles and counts only), status (`open | answered | dismissed`). The tutor answers by teaching or fixing a lesson; a human may also record an answer in the UI. Answering makes the stopped flow resumable from its last checkpoint. Offline tutor: the stopped flow waits, independent flows continue.

**User coexistence**
- Before each physical-input action: compare the cursor position left by the apprentice with the current one and check last-input time. If the user acted, pause, wait N seconds of idle, re-verify preconditions, then resume.
- Before sending keys, verify the target window is foreground; otherwise do not press.
- A global emergency hotkey stops everything. A dedicated machine is recommended for long physical-input flows, not required.

**Local web app**
- Served by the Python app on `127.0.0.1` with a token. Five screens: flow editor (palette from lessons, connect, configure, run, live status), lesson library, tutor queue view, run history, consents (revoke only). Teaching from the UI and a first-run wizard are out of v1.
- Own editor on React Flow (MIT); n8n is excluded because its license forbids commercial redistribution.

## Testing Decisions

- A good test drives external behavior through a public entry point (run a flow, call an MCP tool, answer a doubt, revoke a consent) and asserts observable outcomes (database rows, queue entries, which actions the fake desktop received, flow status). It does not assert internal calls or private structure.
- Strict TDD: test red before code green, one behavior at a time.
- Default tests use the fake desktop port and a real SQLite temp file. No mocks of internal modules.
- Behaviors to cover through the seam: lookup order (user then factory), version change to `to_revalidate`, confidence thresholds and local-vs-factory counters, locator ladder and queue-on-failure, consent block and revoke, unreadable = blocked, secrets never in recorded fake-desktop arguments, flow branching/IF/join/loops/caps/checkpoint resume, exclusive-input serialization, user-input pause/idle/re-verify/foreground check/emergency stop, queue lifecycle, private-app summarization.
- Frontend: tested separately against the local HTTP API.
- Live smoke tests behind an opt-in marker cross the same port with real agent-desktop (Paint first). They never run by default.
- Prior art: the predecessor project's tests for confidence, delta classification and hard floor; port them with the code.

## Out of Scope

- Teaching from the web UI and a first-run wizard.
- A GOAP/planner; any LLM or local model at runtime (a local offline agent is a future direction).
- Quotas (only if a user writes one), per-task permission prompts.
- YAML flow format; using n8n.
- Enforcing a dedicated machine or session.
- Cross-platform support beyond Windows.
- Moving the spec into an issue tracker (waits for tracker setup).

## Further Notes

**Unverified risks to resolve early** (agent-desktop facts come from bundled docs, not live tests except where noted):
- `launch --cdp` for Vivaldi page text.
- Word paste route: `set-value` vs clipboard.
- Telegram launch (no window found by absolute path).
- Parallel accessibility actions on different windows.
- numpy vs opencv speed for template search at 1920x1080 (not measured).
- Recycle Bin and desktop icons reachable by accessibility (explorer shell window was hidden).
- Real secure-field redaction.
- Apps with inaccessible windows reject semantic commands but accept screenshots and coordinate input.

**agent-desktop protection limits** (docs): screenshots and non-secure app text are unredacted; notifications are verbatim; trace screenshots store unredacted PNGs; batch JSON text lands in process args; there is no Windows permission dialog; it has no notion of veto text, outward actions or consent. The consent gate and secret handling above exist because of these gaps.

**Project hygiene**: uv + pytest, `web/` frontend with its own package manifest, new git repo on `main`, one branch per ticket, conventional commits without attribution, no push until requested.

**Suggested next steps**: `/setup-matt-pocock-skills` (tracker), `domain-modeling` for `GLOSSARY.md` and ADRs (frame, lesson, flow, node, apprentice, tutor, study order, consent gate), then `/to-tickets`.
