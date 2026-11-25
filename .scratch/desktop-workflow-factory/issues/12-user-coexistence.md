# 12: User coexistence

**What to build:** Before each physical-input action the apprentice compares the cursor position it left with the current one and checks the last-input time. If the user acted, it pauses, waits N seconds of idle, re-verifies preconditions, then resumes. Before sending keys it verifies the target window is foreground. A global emergency hotkey stops everything.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] A moved cursor or recent user input pauses the flow before the next physical action
- [ ] After idle time the flow re-verifies preconditions before resuming
- [ ] Keys are not sent when the target window is not foreground
- [ ] The emergency hotkey stops all running flows
- [ ] Mouse movement humanisation is reused from the predecessor code, parameters calibrated here
- [ ] All of it is tested through the fake input detector and clock
