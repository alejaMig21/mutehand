# 20: Research: parallel accessibility actions on different windows

**Type:** research

**What to find out:** Whether accessibility actions on two windows at the same time interfere with each other or with the user's focus.

**Blocked by:** 02

**Status:** resolved

- [x] Experiment with two apps in parallel, results recorded
- [x] Verdict on whether nodes without physical input can safely overlap

## Answer

See `docs/research/20-parallel-accessibility-actions.md`. Two windows can be read and written at the same time with no crossed values or errors (30/30 rounds). Reads never touch the foreground; `click` and `set-value` can take it even in headless mode, so accessibility writes are not "no physical input". Decision moved to ticket 24.
