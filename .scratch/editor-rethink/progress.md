# Editor rethink: build paused (2026-11-26)

Paused at the person's request (session usage running out). Resume: continue `/implement-spec` from this file.

## State

Integration branch `editor-rethink`, worktree `.claude/worktrees/editor-rethink`. The main checkout stays on
`effect-mismatch-stops-flow`. Nothing pushed.

| Ticket | State | Where |
|---|---|---|
| 01, 03, 07 | merged, resolved | on `editor-rethink` (tip before this note: 5205b31) |
| 02 Home | interrupted, near done | branch `ticket/02`, worktree `.claude/worktrees/agent-a0860db5365893272` |
| 08 strip | interrupted, early | branch `ticket/08`, worktree `.claude/worktrees/agent-a8c5331ab8e7d37d5` |
| 04, 05, 06, 09-14 | not started | |

- `ticket/02`: work up to 0b49293 committed and already merged with `editor-rethink` at 5205b31. On top, `80babe7 wip` (a canvas
  refit guard, its test, a rebuilt `web/dist`): unverified. It was checking that three tests which passed first time go red
  when what they protect is broken. Left: verify the wip, rebuild dist, all suites, screenshots, final report.
- `ticket/08`: `f7cf11e` (sentence per box) and `e1e6085` (success counts from the API), tree clean. Left: the strip itself,
  test warning, "Settings", removal of NodePanel and trust marks, screenshots, all suites.

Last green on `editor-rethink` content (ticket 07): pytest 705, browser 105, web unit 55, ruff clean.

## How to run it

- At most 2 subagents. Order: finish 02 and 08, then 04, 05, 06, 12, then 09, 10, 11, 13, 14, then `code-review` on the
  branch, one fix agent, tickets graph, journal, removal of the worktrees under `.claude/worktrees/`.
- Per agent: `git switch -c ticket/NN editor-rethink` in its own worktree (for 02 and 08, reuse the existing worktree);
  `UV_PROJECT_ENVIRONMENT=$TEMP/wfv-NN` (long paths break the 261-character scheduler limit); `uv sync --offline`;
  `npm ci --prefer-offline` in `web/`; pytest with `--basetemp=$TEMP/wft-NN` (parallel runs collide otherwise).
- Never `-m live`, never the real database, desktop, clipboard or scheduler. Conventional commits, no AI attribution.
- Merge: fast-forward when the ticket branch already holds the tip, a merger agent only on conflicts; then set the ticket
  `Status: resolved` with `## Answer`.
- Traps per ticket: `exploration.md` beside this file (written before 01, 03 and 07 landed).

## Decisions taken by implementers, to report to the person

- 03: the app field is now a list, so an app with no learned action cannot be typed. A product name equal to Windows' own
  counts as none; apps sharing a name show "Name (File)".
- 01: screen words stay "Flow"; same-title flows show "Name (identifier)".
- 07: a box added mid-chain is inserted between; the add panel is docked and Escape no longer closes it; positions saved by
  the old canvas live on unused in the old table.
