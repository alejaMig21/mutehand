# 04: Daily time per flow

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** A person sets, changes and stops a flow's daily time from its Home row and from the first box of the canvas. Both read one fact: a daily trigger node and its Windows task exist together or not at all. (Spec stories 19, 20, 38, 39.)

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Setting a time on Home creates the Windows task and shows it on the first box, and the other way round
- [ ] Changing the time leaves exactly one task; stopping removes it and the trigger
- [ ] A task the scheduler refuses leaves nothing half done and says why in plain words
- [ ] "Run now" starts a flow whether or not it has a daily time
- [ ] Schedules made before this ticket show on their flows
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
