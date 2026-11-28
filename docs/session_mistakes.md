# Session mistakes and the changes proposed for them

Retro of the session of 2026-11-27 (Mutehand model v2 phase 1, `/implement-spec`). Nothing below is applied yet: the person chose to
come back to it later. Each item says what happened, the evidence, the kind of fix and where it would live. Severity order.

## 1. Plain background jobs never wake the agent

- **What happened:** suites were started as a `( ... ) &` subshell inside one command. That process sends no notification when it ends,
  so the agent wrote "when it finishes I will continue" and nothing could trigger it. The run ended at 22:51 and the person found out
  at 23:33. The person had already complained about silence earlier in the session ("hace horas que no me informas").
- **Kind:** automated check (mechanical).
- **Proposal:** a PreToolUse hook on Bash that rejects a command ending in `&` when `run_in_background` is not set, with the message
  "use run_in_background: it notifies when the job ends". Add one line to the global rules: a turn never ends promising to act when a
  job that does not notify finishes.

## 2. Long, repeated briefs for every implementer agent

- **What happened:** about 12 implementer agents, each briefed with roughly 700 words that copied the same standing rules (environment
  variables, `git add` rules, short temp paths, files not to touch). The log holds 95 "hand-back" reports; one agent re-sent the same
  final report four times while "waiting on background work". The `implement-spec` skill asks for context pointers, not copies.
- **Kind:** navigation.
- **Proposal:** one `docs/agents/implementer.md` with the standing rules, including "send the final report once and leave no wait
  timers". Each ticket brief becomes about five lines: the ticket path, the pointer to that file, the branch name.

## 3. Environment traps every agent hit again

- **What happened:** the Windows scheduler command limit (261 characters) broke tests whenever a temp path was long (167 mentions in the
  log); the pre-commit hook fails with "ruff is not installed" unless `UV_PROJECT_ENVIRONMENT` is set, so three agents created a `.venv`
  inside their worktree, which lengthens paths further; `git add -A` was blocked because it would have staged files that stay out on
  purpose (`.claude/`, `.atl/`, a screenshot with an account name).
- **Kind:** automated checks (mechanical).
- **Proposal:**
  - `tests/conftest.py` fails at the start with a clear message when the temp path is too long for the scheduler command.
  - `.githooks/pre-commit` finds ruff by itself instead of requiring the variable.
  - a commit hook (or a Bash hook) that refuses `git add -A` and `git add .` while those untracked files exist.

## 4. A wide rename broke CSS and nothing noticed

- **What happened:** ticket 01 turned `box-sizing`, `box-shadow` and `border-box` into `node-sizing`, `node-shadow` and `border-node`.
  Every test passed; another agent found it by chance while working on ticket 06.
- **Kind:** automated check.
- **Proposal:** a stylelint rule (`property-no-unknown`) in the web check, or a small test that reads `styles.css` and rejects
  properties that do not exist.

## 5. Tests written after the fix

- **What happened:** the agents of tickets 07 and 10 said they wrote some tests after the fix, so the red step was skipped. The `tdd`
  skill requires red first, but nothing checks it.
- **Kind:** review standard (judgement), with one mechanical aid.
- **Proposal:** give the review agent the rule "every `fix:` or `feat:` commit carries its test in the same commit", and add a
  commit-message hook that warns when such a commit changes nothing under `tests/`.

## 6. Project words used in chat without being explained

- **What happened:** "chore" and "box" were used in Spanish for hours without a definition. The glossary rule in the global instructions
  only covers questions and proposals, and it was followed halfway. The global `CLAUDE.md` has 258 lines with repeated rules (fix
  everything in the same turn, no "not checked" reports, verify before agreeing).
- **Kind:** global instructions.
- **Proposal:** widen the rule to "every term from `GLOSSARY.md` used in a reply is defined the first time or replaced by plain words",
  and prune the global file: move the memory and tooling protocols into a document it points to, keep only pointers and the rules that
  change behaviour.

## Seen and left alone

A command with quotes that failed once on Windows (the Edit and Write tools are the documented way); agent runs cut by network errors
(resumed by message and finished).

## Code review of this session (for the record)

Standards axis: no hard breaches in product code; judgement calls were a duplicated `.exe` stripping helper, a dead web helper
(`taughtApp`), two sentinels for "no technology" and a test that patches a private function. Spec axis: private technologies leaked a
locator's control name through `GET /api/steps`; the clean-start notice was shown until dismissed instead of once; the action kind was
not enforced as a property of the whole step; dead legacy readers of the old flow-level program remained. All were handed to one fix
implementer (branch `fix/v2-review`). Kept by design: the `steps` table still holds one row per technology and name (that row is the
locator), and the factory database keeps the same shape.
