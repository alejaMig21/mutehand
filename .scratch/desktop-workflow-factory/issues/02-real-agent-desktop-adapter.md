# 02: Real agent-desktop adapter

**What to build:** The desktop port backed by the real agent-desktop CLI, proven by an opt-in live smoke test that opens Paint, finds a toolbar control by accessibility, and measures an effect.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Real adapter implements the same port as the fake
- [ ] Live test (marker `live`) drives Paint through the public entry point; it never runs by default
- [ ] Adapter never exposes force or trace screenshots
- [ ] Text for typing and secrets goes via stdin, never in process arguments
- [ ] Failures from the CLI surface as typed errors, not raw output
