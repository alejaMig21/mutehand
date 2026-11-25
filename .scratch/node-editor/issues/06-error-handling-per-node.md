# 06: Error handling per node

**What to build:** Each node can stop (default, leaves a doubt), retry N times, or continue.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Stop leaves a doubt in the queue and the run state says which node
- [ ] Retry waits and re-checks the precondition before each attempt
- [ ] Continue passes an empty result and records that it did
