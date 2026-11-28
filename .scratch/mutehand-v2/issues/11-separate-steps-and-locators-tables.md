# 11: Separate the step and its locators in storage

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`. **Later phase: not part of phase 1.**

**What to build:** Today a step is stored as one row per technology and name, and that row is the locator for that technology; the
pieces that belong to the step as a whole (its tags, and the rule that its action kind is the same everywhere) live in a side table and
in code. This ticket gives the model its physical shape: a table of steps (name, action kind, tags) and a table of locators (one per
technology, with everything learned and measured there: locator, precondition, effect, frame, mask, derived geometry, template, drag
destination, sensitivity, secret reference, version, counters, rejection state). The action kind then belongs to the step by
construction and the database refuses a locator whose action differs. Nothing a person or the tutor sees changes: the screens, the
tutor tools and the API answer as before. The new database starts empty as in ticket 02, so no data is migrated; the factory database
format gets the same shape.

Why it was left out of phase 1: the existing rows already are locators, so the phase-1 behaviour (generic names, tags, a technology per
node, one filter) works on them, and the action-per-step rule is enforced when teaching. The change has a large blast radius (every
reader of steps, consent, doubts, the run path and many tests) for no visible gain until a real need appears. Take it up if a
consistency fault shows up in use, or when components (phase 2) need steps queried by name across technologies in more places.

**Blocked by:** Phase 1 (tickets 01 to 10) merged. Best done with expand-contract: add the new tables beside the old one, move the
readers over in batches, then drop the old shape.

**Status:** open

- [ ] A step exists once by name, with one action kind and its tags; its locators are separate and one per technology
- [ ] Teaching a known name with a different action is refused by the database as well as by the tutor tool
- [ ] The factory database format has the same shape and the shipped knowledge is rebuilt from it
- [ ] The screens, the tutor tools and the HTTP API answer as before (no change in what a person or the tutor sees)
- [ ] Consent, privacy of private technologies, doubts and checkpoints behave as before, per step and technology
- [ ] The old per-technology step table and its readers are gone; no second model lives beside the new one
- [ ] Behaviour is proven by the existing browser, API and MCP tests plus database tests of the new constraints, red before green
