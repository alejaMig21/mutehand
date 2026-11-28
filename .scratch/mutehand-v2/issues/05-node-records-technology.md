# 05: A node records the technology it acts on

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** A step node stores the step name and the technology it acts on. Running a flow resolves each step node by name and its technology. A node whose step has no locator for its technology is refused before anything is touched, with a doubt that names the node, the step and the technology. The program stops being a property of the flow in the stored data, the API and Home. A flow with nodes of several technologies runs them one after another, each on its own technology; the engine still drives one program at a time. (Spec stories 14 to 17, 20.)

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] A flow with an Excel node and a Paint node runs each on its own technology through the stand-in desktop, in order
- [x] A node whose step is not learned on its technology is refused before any action and leaves a doubt naming node, step and technology
- [x] Home and the run endpoints no longer ask for or return a flow-level program; flows saved without one still open
- [x] Consent is checked per step and technology; a private technology keeps its rules
- [x] Behaviour is proven by engine and API tests and a browser test of Home, red before green

## Answer

A step node records the technology it acts on; a run resolves each step node by name and technology, refuses a node without a locator before touching anything and leaves a doubt naming node, step and technology; the flow-level program left the data, the API and Home. Later review fix: the readers of flows saved before this were removed.
Commits: merge ac82576 (ticket/v2-05), 7ebc7d1.
