# 02: Real agent-desktop adapter

**What to build:** The desktop port backed by the real agent-desktop CLI, proven by an opt-in live smoke test that opens Paint, finds a toolbar control by accessibility, and measures an effect.

**Blocked by:** 01

**Status:** resolved

- [x] Real adapter implements the same port as the fake
- [x] Live test (marker `live`) drives Paint through the public entry point; it never runs by default
- [x] Adapter never exposes force or trace screenshots
- [x] Text for typing and secrets goes via stdin, never in process arguments
- [x] Failures from the CLI surface as typed errors, not raw output
