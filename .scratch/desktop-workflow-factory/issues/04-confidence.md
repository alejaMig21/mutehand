# 04: Confidence and counters

**What to build:** Each lesson tracks success and failure counters, with factory counters and local counters kept separate. Confidence is (successes + 1) / (successes + 3 x failures + 2). A lesson is trusted at 0.80 or more with at least two own successes and no failures; suspect below 0.50; rejected below 0.30, restorable only by a human.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] A shipped factory lesson with high counters is not "trusted locally" until it has two own successes
- [ ] Failures lower confidence and move the state to suspect then rejected at the thresholds
- [ ] A rejected lesson is never replayed and only a human action restores it
- [ ] Behaviour checked through run outcomes, not by reading internal counters directly
