# 18: Research: moving text into Word

**Type:** research

**What to find out:** Whether setting a value through accessibility works in Word, or whether the clipboard route is needed, and what each costs in physical input.

**Blocked by:** 02

**Status:** in progress (waiting for the person's permission for real typing and the clipboard)

- [ ] Both routes tried on the real app, results recorded
- [ ] Recommendation stated, including whether the node needs exclusive physical input

## Answer

Partial, see `docs/research/18-moving-text-into-word.md`. Word is enabled again. Accessibility `set-value` does not work in the page (`ACTION_NOT_SUPPORTED` on the document and its Body) and a headless `type` is denied; so the node needs exclusive physical input. Real typing and the clipboard route were not run: the first was blocked by the permission system, the second needs the person's clipboard. Waiting for the person's decision.
