# 13: Remove the old screens

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** Navigation becomes Home, Apps and "Close the program". The Steps, Tutor queue, Run history, Schedules, Consents and Setup check screens go. The glossary records the on-screen words and ADR 0006 notes that the editor may show a chat message. (Spec stories 51, 61-63, 65.)

**Blocked by:** 04, 05, 09, 10, 11, 12

**Status:** resolved

- [ ] Only Home, Apps and the flow screen remain; no ability listed in the spec is lost
- [ ] Tests of removed screens are rewritten to the new places and keep what they protected
- [ ] A paused run says why wherever it is shown
- [ ] "Close the program" asks when something would be lost and says how to open it again
- [ ] The glossary maps chore, box and action to Flow, Node and Step
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message

## Answer

Navigation is Home, Apps and "Close the program"; the six old screens and their dead endpoints are gone, each ability proven on its new place. Not placed: a person rejecting an action, and removing a daily run whose chore no longer exists.
Commits: 44c2c33, 4db0181.
