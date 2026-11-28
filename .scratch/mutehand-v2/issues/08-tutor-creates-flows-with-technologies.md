# 08: The tutor creates flows with technologies

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** `create_flow` nodes carry the technology of each step node; the answer names the nodes that lack a locator for theirs, so the tutor teaches exactly that. `flow_status` reports the same. A described flow that mixes programs is saved even when lessons are missing. (Spec stories 36, 37.)

**Blocked by:** 03, 05

**Status:** resolved

- [x] A flow of two technologies is saved ready when both are learned, and not ready with the missing node named when one is not
- [x] After teaching the missing step on that technology, `flow_status` turns ready
- [x] A node naming a technology the step does not have is not an error: it is the missing lesson
- [x] Invalid node data is refused and nothing is saved
- [x] Behaviour is proven by MCP tests through the in-process client, red before green

## Answer

`create_flow` takes a technology on every step node and answers with `missing_lessons` (node, step, technology); `flow_status` reports the same and turns ready after the lesson.
Commits: df8f568.
