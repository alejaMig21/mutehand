# 17: Research: reading Vivaldi page text via CDP launch

**Type:** research

**What to find out:** Whether launching Vivaldi with the CDP option gives reliable page text where the accessibility snapshot times out. Record the result and the exact commands in a research note.

**Blocked by:** 02

**Status:** resolved

- [x] Verdict recorded with evidence (what worked, what timed out)
- [x] Impact on the "Vivaldi to Word to Telegram" example flow stated

## Answer

See `docs/research/17-vivaldi-page-text.md`. CDP (own Vivaldi instance, separate profile, loopback port) reads the full page in 0.2-0.6 s. The accessibility snapshot did not time out: its default (interactive only, depth 10) simply does not contain the page, and with all elements and depth 30 a 5000-paragraph page is silently cut while `complete: true`. Attaching to the person's own running Vivaldi was not tested on purpose.
