# 02: Clean start with a dated copy of the old database

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** When this version starts and a user database from before exists, it is renamed to a copy that carries the date, a new empty database is created, and the person is told once, in plain words and on Home, where the copy is. Nothing is imported. A second start does not repeat any of it. (Spec stories 26, 27, 28.)

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] An existing database is kept under a dated name next to the original location and the new database is empty (no steps, no flows)
- [x] The notice appears once on Home, says where the copy is, and can be dismissed; after a reload or a second start it is not shown again
- [x] A first-ever start (no old database) shows no notice
- [x] Nothing in the old database is read into the new one; the factory knowledge is unaffected
- [x] Behaviour is proven by database tests and a browser test against the real API with the stand-in desktop and scheduler, red before green

## Answer

An old user database is kept as a dated copy next to the original, a new empty one is created and stamped with schema version 2, and Home tells the person once where the copy is. Later review fix: the notice is told once even if nobody presses "Got it".
Commits: 53ef3fa, 449cbba.
