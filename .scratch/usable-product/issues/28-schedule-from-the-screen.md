# 28: Schedule a flow from the editor

**What to build:** The editor lists the schedules this product created and lets the person add a daily time or remove one, through the Windows Task Scheduler wrapper that already exists.

**Blocked by:** 27

**Status:** resolved

- [x] List, create and delete a schedule from the screen
- [x] Only schedules created by this tool are shown or removable
- [x] A created schedule appears in Windows Task Scheduler and runs the flow headlessly

## Answer

A Schedules tab (`web/src/Schedules.jsx`) over `GET/POST/DELETE /api/schedules`, through the existing Task Scheduler wrapper.
- List: only tasks whose name carries this tool's prefix; each shows its flow, app and daily time, read from the task XML (the same on any Windows
  language). A task of the person's own is never listed, and asking to remove one is "no such schedule" (names get the prefix or are refused).
- Create: flow, app and a time; names are checked before anything reaches `schtasks` (no shell); the task is named `<flow> daily HHMM` (a colon is not
  allowed in a task name). The task starts the flow's daily triggers (`--fired daily`) and carries `--user-db` when the editor uses another data folder.
- Verified for real: `pytest -m live -k scheduler` creates a task, Windows runs it with no window and the workday's own exit code comes back, and a
  second test reads flow, app and time back from the real scheduler and deletes it. `schedule list` now exists on the command line too.
Tests: `tests/test_api_schedules.py` (9), `tests/test_schedule.py` (+3, one live), one browser test.
