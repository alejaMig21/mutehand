# 10: Flow engine

**What to build:** A flow is a graph of nodes stored in SQLite with free branching, IF nodes on measured effect, join nodes, and loops capped by iterations and time (up to 8 hours). Values travel in a typed run context; a node with a missing input does not start. Each loop iteration writes a checkpoint and re-verifies preconditions; N consecutive failures stop the loop and queue a doubt.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] Fan-out branches and a join node that waits for all its inputs
- [ ] An IF node routes on a measured effect
- [ ] A node with a missing typed input does not start
- [ ] A loop stops at its iteration cap or time cap
- [ ] Consecutive failures stop the loop and queue one doubt
- [ ] A consentless lesson blocks its node, not the whole flow
