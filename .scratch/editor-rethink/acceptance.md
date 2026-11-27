# Ticket 14: acceptance with non-technical personas

Run on 2026-11-27 against the finished build (tip 80479bb), headless, screenshots only, no vocabulary given.
Harness: `tests/acceptance_server.py <first-day|everyday|many-apps> <short-empty-dir>`.
Screenshots stay in the session scratchpad (`a14-casual`, `a14-child`, `a14-elephant`, replays in `replay14a`, `b14`); they are not kept in the repo.

## Scores (before the fixes)

| Persona | Dataset | Result |
|---|---|---|
| casual | first-day | knew what to do next 8/10, knew it worked 5/10, tries 2/3 |
| casual | everyday | 8/10, 6/10, tries 6/8 |
| casual | many-apps | 6/10, 6/10, tries 3/5 (could not find "Take back") |
| child | first-day | every tap visible 8/10, 4 of 20 taps without reaction, tries 6/8 |
| child | everyday | 7/10, about 8 of 55 taps without reaction, tries 8/11 |
| child | many-apps | 8/10, 4 of 17 taps without reaction, tries 6/9 |
| elephant | first-day | 12 shocks, 11 clean, 0 data problems |
| elephant | everyday | about 34 shocks, 32 clean, 2 data problems |
| elephant | many-apps | about 28 shocks, 25 clean, 0 data problems |

## Findings fixed (each with a browser test in `tests/test_acceptance_fixes_e2e.py` or `tests/test_run_view_e2e.py`)

1. Blocked chore said "restore it in Steps" (screen gone): now points to Allow again on Home and Apps.
2. Action chips on Apps looked like buttons and did nothing: plain labels now; "Cannot run yet" says why when pressed.
3. "Take back" never found: the harness had no consents; permissions section always shown with a plain empty state.
4. Banners said "boxes"; Run now banner named another chore: now steps and chore, naming the right one.
5. List jumped after Allow again and when a card opened: stable positions, confirmation where the person tapped.
6. Delete: Undo notice in place of the row, and it survives a reload (`deleted_at`, `GET /api/deleted`, 10 minutes).
7. 100 KB paste in Apps search gave "HTTP 414": input capped, no HTTP code is shown to a person.
8. Apps on the first day was a dead end: it shows the teach message with Copy.
9. Daily time typed in 12 h but shown in 24 h: shown as typed, with "Saved".
10. Ten identical "show me what to send" rows and jargon: one message per app, plain words.
11. Run now gave no reaction: "Running…" on the row at once.
12. A run shrank the canvas to half and made boxes tiny: the run log floats over a canvas corner with one picture per box.
13. 500 "internal error" after idle on harness servers: not reproduced in 35 minutes; the symptom is exactly reproduced by deleting the server's data folder, so the cause was a harness folder removed by a cleanup. The harness now stops with a clear message, and any 500 writes its traceback to the console.

## Decisions taken by the person (2026-11-27)

| Topic | Decision |
|---|---|
| "Close the program" quits at once when nothing is lost | Kept, but the button moved into a More menu at the end of the tabs, away from where a tap lands by accident (a tab can be closed by the browser, but the button also stops the local server). |
| Reject an action by hand | No button. Add one inside an open app on Apps only if a person asks. |
| Orphan daily run (task without chore) | No notice. Deleting a chore already removes its task. |
| Two pages renaming the same chore | Last write wins, no notice. |
| Ignored "changed elsewhere" banner then reload | Unsaved edits are dropped; the browser warns before leaving. No local draft. |
| Run data popup showing `{}` | Changed: a plain hint says `{}` means nothing. |
| Add panel below the fold at 390 px | Left as is. |
| Trash never purged | Left as is. |
| Same-title chores | Kept as "Name (identifier)". |
| App with no learned action cannot be typed | Kept: only apps with learned actions are offered. |
| Positions saved by the old canvas | Kept, unused. |
| Ticket 06: unfinished boxes held back, new chore created on its first box, templates never autosaved | Kept. |
| Ticket 02: browser tests marked `web` | Kept. |

Open for the next market test: each recommendation above is re-checked against what the personas say then.

## Fixed after the code review (same run)

- The daily box on the canvas and its Windows task now move together on every path (remove, add, re-time); an undo that cannot recreate the task drops the daily box and says so.
- A copy of a daily chore starts without a daily box.
- Private apps send opaque handles instead of action and control names; failed-check text is no longer sent.
- Stale prose, duplicated helpers and one relearn message were cleaned.
- Two flaky browser tests were fixed as test races (waiting for "Opening…" to end; a pause long enough to be seen under load).

## Second round (2026-11-27, after the fixes above; casual, child and elephant again, same datasets)

| Persona | Dataset | Before | After |
|---|---|---|---|
| casual | first-day | next 8/10, worked 5/10, tries 2/3 | next 6/10, worked 4/10, tries 3/8 (more tasks asked) |
| casual | everyday | 8, 6, 6/8 | 8, 7, 8/8 |
| casual | many-apps | 6, 6, 3/5 | 6, 7, 5/8 |
| child | first-day | 8/10, 4 of 20 taps dead | 5/10, 7 of 16 dead |
| child | everyday | 7/10, 8 of 55 dead | 7/10, 10 of 41 dead |
| child | many-apps | 8/10, 4 of 17 dead | 7/10, 5 of 21 dead |
| elephant | first-day | 12 shocks, 11 clean, 0 data | 16, 15, 0 |
| elephant | everyday | 34, 32, 2 data | 32, 29, 6 (1 reload during autosave, 5 from API-level double creates) |
| elephant | many-apps | 28, 25, 0 | 28, 26, 1 (a blank chore from random clicks) |

Honest reading: everyday and many-apps improved for the casual person; the first day is still the weakest screen (nothing to do without
the chat). The elephant held up on parallel runs, triple clicks, deletes and undo.

Fixed after this round (tests in `tests/test_market2_e2e.py`): More menu closes on outside click, Escape and tab choice; first-day stages are
plain, non-tappable words; Copy shows "Copied" at once and falls back to selecting the text; multi-word Apps search; one honest line after
Run now; Try again answers in place without the list jumping; Take back says it in plain words; Apps keeps its order; the flow screen says
"chore" instead of "flow"; Rename says "Renamed". The persona harness no longer stops itself on the first-day data.

Checked and left: the elephant's "reload loses the new chore" is a harness artefact (`page.reload()` skips the browser's leave warning; a real
reload shows it). Offline reload shows a blank page (the browser cannot load it). 100 KB names are cut to 100 characters. Six parallel API
creates of a copy make six copies (the screen disables its button while busy).

Decision to take in the morning: the app runs from the repository (`uv sync`, `uv run workflow-factory`); `DEFAULT_WEB_DIR` points at
`web/dist` inside the checkout, so an installed wheel would not find the editor. Ship as a repository, or package `web/dist` into the wheel.
