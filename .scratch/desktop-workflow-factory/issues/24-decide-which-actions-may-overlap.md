# 24: Decide which lesson actions may run in parallel

**Type:** decision (needs the person)

**Why:** Research 20 (`docs/research/20-parallel-accessibility-actions.md`) measured that an accessibility
`click` or `set-value` can take the foreground window. `Lesson.uses_physical_input` only counts drag,
typing and coordinate rungs, so an accessibility click overlaps other nodes and ignores the
user-coexistence pause, yet it can steal the person's focus.

**Options:**
1. Treat every acting node (click, drag, type) as physical input: one at a time under the machine-wide
   lock, always paused while the person is active. Safe; parallel waves then overlap only reads, waits and
   control nodes.
2. Keep overlapping accessibility clicks, but pause them while the person is active and save/restore the
   foreground window around each action (restoring needs an OS call that is itself focus-changing).
3. Keep today's behaviour and document the risk.

**Blocked by:** 20

**Status:** resolved

## Answer

Option 1 chosen by the person on 2026-11-25: every lesson action takes the machine-wide input lock and pauses while the person is active (`Lesson.uses_physical_input` is always true). Parallel waves now overlap only non-acting work.
