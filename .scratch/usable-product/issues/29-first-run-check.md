# 29: First-run check

**What to build:** A screen that says in plain words whether what the product needs is present (agent-desktop, Claude Code for teaching, the data folder, a second monitor if wanted) and how to fix each missing piece.

**Blocked by:** 27

**Status:** resolved

- [x] Each requirement shows as ok or missing with one plain fix
- [x] The check reads and installs nothing
- [x] It shows on the first run and can be reopened

## Answer

`src/workflow_factory/checks.py` + `GET /api/checks` + a Setup check tab (`web/src/Checks.jsx`).
- Five items, each with its title, why it matters and, when missing, one plain fix: agent-desktop (`npm install -g agent-desktop`), Claude Code
  (needed to teach, not to run flows), the data folder (`uv run workflow-factory` creates it), the teaching connection (`.mcp.json` next to where you
  start Claude Code), and a second monitor (optional, for tests of the product itself). The screen says Ready, Optional or Missing in words with an icon.
- It reads only: a test makes `subprocess.run` and `Popen` fail, and checks that not even the missing data folder gets created.
- First run: the app opens on this screen once (`checked.json` in the data folder is written by the screen after it was shown, never by the check);
  after that the editor opens, and the tab brings it back.
Tests: `tests/test_checks.py` (8) and one browser test; every other browser test starts as a later run.
