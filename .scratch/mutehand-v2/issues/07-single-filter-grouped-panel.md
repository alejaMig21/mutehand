# 07: One filter and a panel grouped by node type

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** The node panel has one search box that matches names and tags. Below it, collapsible sections by node type: Steps, Components (empty in this phase), Triggers, Order, Logic, Data. With the box empty only Steps and Components are open; while typing, every section with a match opens. A universal step shows only when its name or tags match. Escape clears the box. Adding a step node from a search takes the technology that was searched, or asks which one when the step has several. (Spec stories 1 to 9, 12, 13, 40 to 43.)

**Blocked by:** 04, 06

**Status:** ready-for-agent

- [ ] Typing "Excel" lists the steps learned for Excel; typing "Save" lists every Save whatever the technology; a universal step does not appear in either
- [ ] Sections collapse and expand, announce their name and state to a screen reader, and follow the rules for the empty and typing states
- [ ] The old program selector and the "decisions and repeats" section are gone; the system nodes appear under their own groups
- [ ] A message shows when nothing matches; the entry to teach stays
- [ ] It fits 683 px and 390 px, works from the keyboard alone, and keeps its contrast
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop, red before green
