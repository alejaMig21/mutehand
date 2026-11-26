# 06: Autosave and undo on the flow screen

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** Changes are kept as they are made, the screen says "Saved", and "Undo" takes back any change. The Save button goes. (Spec stories 26-28.)

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Every canvas or settings change is stored without a button; a reload shows it
- [ ] A change made elsewhere is shown and the person chooses; nothing is replaced silently
- [ ] A value a field cannot hold is not stored, the box says so and the state does not read "Saved"
- [ ] "Undo" restores the previous canvas, repeatedly; removing a box shows a notice with "Undo"
- [ ] Run and test use exactly what is on screen
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
