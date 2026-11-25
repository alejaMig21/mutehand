# 11: Exclusive physical input

**What to build:** Each node declares whether it needs exclusive physical input (mouse, keyboard, focus). Those nodes are serialized; nodes without that need may run in parallel.

**Blocked by:** 10

**Status:** resolved

- [x] Two physical-input nodes in parallel branches never overlap in time
- [x] Accessibility-only nodes in parallel branches may overlap
- [x] The flag is stored per node and visible to the editor
- [x] Parallel accessibility actions on different windows are marked as an unverified risk (see research tickets)
