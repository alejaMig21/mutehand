# 06: Error handling per node

**What to build:** Each node can stop (default, leaves a doubt), retry N times, or continue.

**Blocked by:** 03

**Status:** resolved

- [x] Stop leaves a doubt in the queue and the run state says which node
- [x] Retry waits and re-checks the precondition before each attempt
- [x] Continue passes an empty result and records that it did

## Answer

`Node.on_failure` is `stop` (default), `retry` or `continue`; `Node.retries` (1 to 10, default 3) applies to retry. The policy is saved with the flow.
- stop: one doubt in the queue and `RunResult.stopped` names the node (as before).
- retry: the node pauses 2 s, then 4 s, 8 s... (capped at 60 s) and runs again from its precondition check; the emergency stop is heard during the pause.
  After the last retry it stops with one doubt. On a for each the policy belongs to the for each: it retries the item it failed on and
  keeps the retries per item.
- continue: no doubt; the node gives out an empty result (`{}`), the run history shows it as `continued` with the reason, and
  `RunResult.continued` lists it. A later node that needs a field of that empty result stops with `missing_input` instead of guessing.
  On a for each, the failed item is given up and the next one goes on.
Tests: `tests/test_error_handling.py` (15).
