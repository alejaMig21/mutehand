# 14: Acceptance with non-technical personas

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** The casual user, child and elephant personas use the finished product seeing only pictures and given no vocabulary; what they cannot do is fixed.

**Blocked by:** 13

**Status:** resolved

- [x] Each persona reports scores, tries finished and troubles with pictures, on first day, everyday and many-apps data
- [x] Every defect found is fixed with a test and rerun for the persona that found it
- [ ] Findings that need the person's decision are listed with a recommendation

## Answer

Three personas (casual, child, elephant) ran on first-day, everyday and many-apps data through `tests/acceptance_server.py`, headless, with screenshots only. Scores, the 13 defects found (each fixed with a browser test and replayed for the persona that found it) and the decisions taken by the person are in `../acceptance.md`.
Commits: 80479bb, 3bafc6c, 345c2c8, e1b5d55, 97e0c81, 39dae82, f7334fa, ad47a43, plus the review fixes on `fix/review` (43cd360 to f65e0d3).
