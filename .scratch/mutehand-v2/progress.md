# Mutehand model v2, phase 1: progress (paused 2026-11-27, battery)

Integration branch: `mutehand-v2` (local only, nothing pushed). Tip when paused: `11a0ae0`. Base: `step-model-v2` (ADR 0007, spec, tickets).
Remote: `https://github.com/alejaMig21/mutehand` (public). PR #1 (editor rethink + packaging + Mutehand rename) is merged; local `main` = remote `main`.

## Tickets

| # | Ticket | State |
|---|---|---|
| 01 | Words: Flow, Node, Step | merged (ticket/v2-01) |
| 02 | Clean start, dated copy | merged (ticket/v2-02) |
| 03 | Tutor teaches generic steps with tags | merged (ticket/v2-03) |
| 04 | List steps by technology, tag, text | merged (ticket/v2-04) |
| 05 | Node records technology | merged (ticket/v2-05) |
| 06 | Editor node technology | merged (ticket/v2-06) |
| 07 | One filter, panel grouped by node type | **in progress, agent stopped**: work is UNCOMMITTED in the worktree `.claude/worktrees/agent-a4d7bb100ce9bc628` on branch `ticket/v2-07` (modified: `web/src/SearchPanel.jsx`, `web/src/catalog.js`, `web/src/catalog.test.js`, `web/src/styles.css`, `tests/test_canvas_e2e.py`, `tests/test_daily_e2e.py`, `tests/test_editor_e2e.py`, and the built editor is half-rebuilt: delete and rebuild it). Not verified green. |
| 08 | Tutor creates flows with technologies | merged (ticket/v2-08) |
| 09 | Tutor guide, README, persona data | merged (ticket/v2-09) |
| 10 | Persona acceptance | not started (blocked by 07) |

Ticket files still say `Status: ready-for-agent`: set each to `resolved` with an `## Answer` (commits) when the spec is done.

## Last verified state

Tree at `ac82576` (tickets 01 to 05 merged): 843 pytest, 283 browser, 90 web unit, ruff clean. Tickets 06, 08, 09 each reported green on their own branches (06: 848/287+1 flaky/92; 08: 848/281+2 environmental; 09: 851/288). The final tip `11a0ae0` has NOT been run as a whole.

## How to resume

1. Run the suites on `mutehand-v2` first (short `UV_PROJECT_ENVIRONMENT` and short `--basetemp`; a long path breaks the scheduler tests by passing 261 characters).
2. Either resume ticket 07 (send the stopped agent `a4d7bb100ce9bc628` a message, or review the uncommitted diff and finish it in a new implementer) and merge it.
3. Ticket 10: persona round (casual, child, elephant) on the new model with `tests/acceptance_server.py`; compare with `.scratch/editor-rethink/acceptance.md`.
4. `code-review` on the integration branch (Standards and Spec reported apart), fix in one implementer, resolve the tickets, open the PR from `mutehand-v2` (push is authorized by the person for PRs; no other pushes), clean the implementer worktrees.

## Things to remember

- Known flaky browser test: `test_flow_titles_e2e.py::test_a_node_of_a_flow_never_saved_can_be_tested` (timeout under load; passes alone).
- Ticket 01's rename once damaged `box-sizing`, `box-shadow`, `border-box` in the CSS (fixed in 06): check the review for other renamed literals.
- The "Workflow factory - " Windows task prefix and the `workflow-factory` MCP key stay on purpose.
- Never `git add -A`: untracked `.atl/`, `.claude/`, `.scratch/excel-practice/`, `.scratch/tickets-graph.json` and the journal png stay out.
- Pending, parked by the person: PyPI publication (needs a LICENSE), the "Open program" node (phase 4), phases 2 to 4 of ADR 0007.
- The old implementer worktrees (`agent-*`) are still there; remove only the merged ones, never with `--force`.
