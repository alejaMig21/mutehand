# 21: Research: template search speed at 1920x1080

**Type:** research

**What to find out:** Time and accuracy of template search on a full-screen capture using only numeric arrays versus an image library, and which one to adopt.

**Blocked by:** 02

**Status:** resolved

- [x] Measured times for both approaches on 1920x1080 captures
- [x] Sensitivity to theme, scale and occlusion noted
- [x] Recommendation recorded for the bounded-region search in the locator ladder

## Answer

See `docs/research/21-template-search-speed.md`. Verdict: adopt numpy (shipped search, 0.13-0.18 s at 1920x1080 against 0.08-0.10 s for OpenCV); do not add OpenCV. The first row-scan implementation took 34 s and was replaced in this ticket. Sensitivity: noise is harmless; +30 brightness (0.89) and 37% occlusion (0.90) fall below the default min_score 0.95 and are rejected unless a lesson lowers it; an inverted theme or a 125% scale never match.
