# 09: A stopped flow: try again and ask for help

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** A flow that stopped appears first on Home and, on its canvas, as the chosen red box explained in the strip. "Try again" runs it from where it stopped and says whether it worked; "Ask for help" shows the message to send, with an optional note. Mockups B (attention) and E. (Spec stories 6-10, 14, 44, 64.)

**Blocked by:** 02, 08

**Status:** ready-for-agent

- [ ] One server list of attention items feeds Home and the flow screen
- [ ] Home lists stopped flows first with a count, flow, box and plain reason; the section is absent when empty
- [ ] "Try again" closes the open doubt as tried again, lifts a check-made rejection the run needs, and resumes
- [ ] The result reads as fixed, or as the same or a new problem
- [ ] A step the person rejected is never lifted by "Try again"
- [ ] "Ask for help" copies a message naming flow, box and reason, keeps the note on the doubt, and leaves it open
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
