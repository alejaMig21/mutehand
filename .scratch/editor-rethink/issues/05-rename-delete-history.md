# 05: Rename, delete with undo, history per flow

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** From a flow's "More" the person renames it, deletes it with an undo notice, and reads what happened in past runs. (Spec stories 22-24.)

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Renaming changes the title only; history, schedule and checkpoint stay with the flow
- [ ] Deleting removes the flow and its daily run at once; "Undo" on the notice restores both
- [ ] A running flow cannot be deleted without being told to stop first
- [ ] The history of one flow reads in plain words, newest first, with box names even after the flow changed
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
