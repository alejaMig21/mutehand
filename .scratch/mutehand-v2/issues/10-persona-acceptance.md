# 10: Acceptance with non-technical personas

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** The casual, child and elephant personas use the finished model on first-day, everyday and many-apps data, seeing only pictures and given no vocabulary; what they cannot do is fixed and replayed. Scores are compared with the last round in `.scratch/editor-rethink/acceptance.md`.

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08, 09

**Status:** resolved

- [x] Each persona reports scores, tries finished and troubles with pictures on the three datasets
- [x] Every defect found is fixed with a test and rerun for the persona that found it
- [x] The report is written next to the spec and compares with the previous round

## Answer

Casual, child and elephant ran on first-day, everyday and many-apps; seven defects were fixed with tests and the rest were decisions kept. The report with scores and the comparison is `../acceptance.md`.
Commits: 844be6d (report), b4c6a24, f71c317, 3ff0b73, 5fd1c69, f50e427, 7e534e9 (fixes).
