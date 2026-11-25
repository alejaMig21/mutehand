# 08: Locator ladder

**What to build:** Every action endpoint is found by the ladder: accessibility identity first, then geometry derived from a re-located element or window, then a bounded template search with a stored template. Absolute screen coordinates are never used. When a rung fails the apprentice stops and queues a doubt instead of falling through silently. Drag actions locate both ends this way.

**Blocked by:** 05, 07

**Status:** resolved

- [x] A control found by accessibility is used without touching later rungs
- [x] When accessibility fails, derived geometry is used only if the lesson defines it
- [x] Template search is bounded in region and attempts, and a miss queues a "template no match" doubt
- [x] No action ever receives an absolute screen coordinate
- [x] A moved window or icon still resolves through derived geometry in a fake-desktop scenario
