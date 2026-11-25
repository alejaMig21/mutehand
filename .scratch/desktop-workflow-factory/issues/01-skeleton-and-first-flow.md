# 01: Skeleton and first end-to-end flow

**What to build:** A new git repo on `main` with a Python (uv) project, pytest, and the user database. A one-node flow ("click a control located by accessibility") runs against a fake desktop port and records the measured effect. This establishes the single test seam: everything touching the machine (agent-desktop, user-input detector, clock) sits behind the desktop port, and tests use real SQLite on a temp file.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] Repo initialised on `main`, conventional commits, no attribution
- [x] pytest runs with no live marker by default; `live` marker registered and opt-in
- [x] Desktop port interface plus fake implementation exist
- [x] Running a one-node flow through the public entry point clicks the fake control and stores its effect in the user database
- [x] Test written first (red) and covers the behaviour through the entry point only
