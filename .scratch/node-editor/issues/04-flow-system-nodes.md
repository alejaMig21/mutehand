# 04: Flow system nodes: triggers, for each, wait, stop

**What to build:** Triggers (manual, daily) become nodes at the root of a flow; add for each (explicit iteration over a list in Data), wait and stop beside the existing if, join and loop.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] A flow starts from a trigger node, by hand or on schedule
- [ ] For each runs its body once per list item and stops cleanly when told
- [ ] Wait and stop behave under the emergency stop and the user pause
