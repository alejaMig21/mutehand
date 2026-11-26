# 07: Top-to-bottom canvas and add panel

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** The canvas reads top to bottom, new boxes join by themselves, and the add panel offers the flow's app actions plus decisions, repeats and waits in plain words, with the other system nodes and recipes under their own heading. Mockups E and F, canvas and panel. (Spec stories 29-37, 40, 47-48.)

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Boxes lay out top to bottom with connection points above and below; positions the person sets are kept
- [ ] Positions stored by the left-to-right canvas are ignored once; no flow loses nodes or wires
- [ ] A new box joins after the chosen box, or after the last one; paths out of a decision are labelled
- [ ] The panel lists only the chosen app's actions, searchable, and every system node and recipe stays available
- [ ] Boxes show done, stopped, running and not reached with a mark and a word
- [ ] A missing action offers the message to send in a chat; nothing starts a lesson
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
