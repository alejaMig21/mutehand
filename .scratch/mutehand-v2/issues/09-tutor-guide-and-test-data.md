# 09: Tutor guide, README and persona test data for the new model

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** `docs/agents/tutor.md` is rewritten for the new model and words: the naming rule, technologies and tags, adding a locator, listing before teaching, building a flow from a description, what a step takes in and gives out. The README and the persona harness datasets are updated so persons can try the new model. (Spec stories 38, 45.)

**Blocked by:** 03, 04, 08

**Status:** resolved

- [x] The playbook names every tool with its current arguments and the new words, and a test that checks the playbook against the tool names passes
- [x] The README describes the new model and words
- [x] The harness serves first-day, everyday and many-apps datasets built with generic steps, tags and nodes with technologies
- [x] No document or comment says chore, box or action
- [x] Existing suites and the linter pass

## Answer

`docs/agents/tutor.md` and the README describe the new model; a test checks every tool call in the playbook against the real tools; the persona harness datasets use generic steps, tags and nodes with technologies.
Commits: 11a0ae0.
