# 02: Rename lesson to step in the code, with a migration

**What to build:** The code, storage, API and tutor tools use Step for what they call Lesson, and Lesson means the teaching session. Existing lessons migrate as one-step lessons and nothing is lost; the old tutor tool names keep working for one release.

**Blocked by:** none

**Status:** resolved

- [x] A migration test: a database written before the rename opens with every step intact
- [x] The glossary and the code use the same words
- [x] The tutor tools keep working with their old names

## Answer

Code, storage, API and web now say Step. `legacy.py` renames the old tables (`lessons`, `lesson_state`) and the `doubts.lesson` column in place on open, reads an old read-only factory file, upgrades old flow nodes and old export files, and the old API path `/api/lessons` and tool name `teach_lesson` still answer. Tests: `tests/test_rename_compat.py`. Lesson now means the teaching session, which has no code yet (recipes, ticket 08).
