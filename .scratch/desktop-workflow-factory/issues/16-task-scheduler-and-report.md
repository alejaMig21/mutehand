# 16: Task Scheduler launch and run report

**What to build:** A workday can be launched by Windows Task Scheduler without the UI open, and each run produces a local report of what ran, what stopped and why, with no data values unless the user asks.

**Blocked by:** 10

**Status:** ready-for-agent

- [ ] A command-line entry runs a named flow headlessly and exits with a status
- [ ] The report lists nodes, outcomes and stop reasons only
- [ ] A value appears in the report only when the user enables it
