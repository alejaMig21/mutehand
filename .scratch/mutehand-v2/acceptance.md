# Ticket 10: acceptance with non-technical personas on model v2

Run on 2026-11-27 against `mutehand-v2` after tickets 01 to 09 (tip `4dad0e6`), headless, screenshots only, no vocabulary given.
Harness: `tests/acceptance_server.py <first-day|everyday|many-apps> <short-empty-dir>`. Screenshots stay in the session scratchpad
(`mt3-casual`, `mt3-child`, `mt3-elephant`); they are not kept in the repo. Compared with the previous round in
`.scratch/editor-rethink/acceptance.md` (second round).

## Scores

| Persona | Dataset | Previous round | This round |
|---|---|---|---|
| casual | first-day | next 6/10, worked 4/10, 3 of 8 tries | next 7/10, worked 3/10, 2 of 10 tries (nothing to run) |
| casual | everyday | 8, 7, 8 of 8 | 8, 8, 10 of 10 |
| casual | many-apps | 6, 7, 5 of 8 | 6, 7, 8 of 10 |
| child | first-day | 5/10, 7 of 16 taps dead | 7/10, 7 of 33 taps dead |
| child | everyday | 7/10, 10 of 41 dead | 6/10, 21 of 93 dead (about 8 on a spot that had moved) |
| child | many-apps | 7/10, 5 of 21 dead | 7/10, 6 of 30 dead |
| elephant | first-day | 16 shocks, 15 clean, 0 data | about 25, 25 clean, 0 |
| elephant | everyday | 32, 29, 6 data | about 72, 72 clean, 0 lost or duplicated |
| elephant | many-apps | 28, 26, 1 data | about 75, 75 clean, 0 lost or duplicated |

Reading: everyday and many-apps improved for the casual person (10 of 10 tasks on everyday) and the elephant found no data problem
at all. The first day is still the weakest screen: all three personas stopped there because a flow cannot be made without the
assistant chat. That is a decision for the person, not a defect (see below).

## Defects fixed (tests in `tests/test_persona_v2_e2e.py`)

1. A step card named every program it was learned for (about 30) and the "Which program?" question ran off a phone screen: a card now names three and counts the rest, the question scrolls with Cancel in view and closes on Escape and outside clicks.
2. Only the latest deleted flow could be undone: every flow deleted in the last 10 minutes keeps its own Undo, also after a reload.
3. Rows jumped after saving a daily time or renaming: the confirmations no longer take room in the row.
4. Run now in an empty flow looked pressable and did nothing: it says "Nothing to run yet".
5. Escape did not leave the take-back question; a long pasted search ran off the screen.
6. Plain words: blocked (was rejected), need attention (was to fix), "Show me the message to copy", "Not ready yet", "Starting values", "paste it where you talk to your assistant".
7. The brand name at the top left now leads Home.

Checked and not a defect: the "older date after reload" was the harness's fixed fake clock (the real desktop records the real time); the harness now dates runs today. Two empty "New flow" rows do not appear from tapping New flow; an empty flow exists only when a node was added and then removed.

## Left on purpose (earlier decisions kept)

Close the program asks only when something would be lost; delete has Undo and no question; the phone layout of the empty canvas; clicks on a panel step add one node each; names are cut at 100 characters; the 320 px toolbar stacks.

## Decision for the person

- **First day:** with nothing learned there is no way to start a flow from the screen; all three personas stopped there. Options: keep the rule that lessons start only in the assistant chat (ADR 0006), or let a person create an empty flow by hand to see the editor.
