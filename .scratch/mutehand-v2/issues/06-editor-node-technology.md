# 06: The editor shows and changes a node's technology

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** A step node shows the technology it acts on. It can be changed among the technologies its step has been learned for. The program selector disappears from the flow screen's header and panel: the node is the only place a technology is chosen. (Spec stories 10, 11, 20.)

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] A step node card and its detail show the technology with the program's name as the screens call it
- [ ] Changing the technology of a node offers only technologies the step is learned for and keeps it after a reload
- [ ] The flow screen has no program selector; saving, running and Undo still work
- [ ] It fits 683 px and 390 px wide windows, works from the keyboard and keeps its contrast
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop, red before green
