# 01: Words: Flow, Node, Step

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** Every screen, user-facing API message and tutor message says Flow, Node and Step. "Chore", "box" and "action" are gone. Test ids and code names that already say flow, node or step stay; ones that say chore, box or action are renamed with the words. The Apps screen already lists programs with their actions, so its words change here too and nothing else about it. (Spec stories 18, 19, 21, 22, 25, 45.)

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] No screen (Home, the flow screen, Apps, first day, the closed page, notices, errors) shows "chore", "box" or "action" in any viewport
- [x] The API's user-facing messages and the tutor tools' messages use the same words
- [x] Home lists flows by title exactly as before; "New chore" is now "New flow" and nothing else on Home changes
- [x] Browser tests assert the new words; the old ones are not kept next to them
- [x] Existing suites, web unit tests and the linter pass; `GLOSSARY.md` and ADR 0007 already carry the vocabulary

## Answer

The screens, the API's user messages and the tutor tools say Flow, Node and Step; "chore", "box" and "action" are gone, and a test guards the screens against them.
Commits: 51ac13b.
