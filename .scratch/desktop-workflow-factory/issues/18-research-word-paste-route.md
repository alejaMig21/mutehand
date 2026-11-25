# 18: Research: moving text into Word

**Type:** research

**What to find out:** Whether setting a value through accessibility works in Word, or whether the clipboard route is needed, and what each costs in physical input.

**Blocked by:** 02

**Status:** resolved

- [x] Both routes tried on the real app, results recorded
- [x] Recommendation stated, including whether the node needs exclusive physical input

## Answer

See `docs/research/18-moving-text-into-word.md`. Accessibility `set-value` does not work in a Word page (document and Body refuse it) and `type` cannot target it. Two routes work with real input on the foreground window: `--headed press` per key (about 0.09 s per key, Word autocorrects) and `clipboard-set` + `ctrl+v` (instant, overwrites the clipboard, so back it up and restore it). Either way the node needs exclusive physical input, must refuse if the foreground window is not Word, and cannot read the page back by accessibility. Side effect: Word leaves undeletable empty recovery files in UnsavedFiles.
