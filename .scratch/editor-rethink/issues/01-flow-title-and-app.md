# 01: Flow title and remembered app

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** A person names a flow with any words, spaces included, and the flow remembers the app it runs on. The title is what every screen shows; the identifier keeps addresses, checkpoints, history and Windows tasks safe. (Spec stories 21, 25.)

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The flow name field accepts free text; the flows menu, run history and schedules show the title
- [ ] A flow keeps its app after reload, and Run uses it
- [ ] Flows saved before this ticket take their identifier as title and the app most of their steps belong to
- [ ] Two flows with the same title stay two flows and neither is overwritten without asking
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
