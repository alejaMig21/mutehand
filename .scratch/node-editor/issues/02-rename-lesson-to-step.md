# 02: Rename lesson to step in the code, with a migration

**What to build:** The code, storage, API and tutor tools use Step for what they call Lesson, and Lesson means the teaching session. Existing lessons migrate as one-step lessons and nothing is lost; the old tutor tool names keep working for one release.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] A migration test: a database written before the rename opens with every step intact
- [ ] The glossary and the code use the same words
- [ ] The tutor tools keep working with their old names
