# 12: The first day

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** With nothing to show, Home says what the product is for, gives the message to teach it something with a copy button, and shows the three stages; with actions learned but no flow it offers "New chore". Mockup A without its example. (Spec stories 1-4.)

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The empty Home shows the sentence, the message with "Copy this message" and the three stages
- [ ] With actions and no flows, "New chore" is the main button
- [ ] The rule that the editor shows no lesson wording is replaced by: nothing in the editor starts a lesson
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
