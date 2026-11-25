---
status: accepted
---

# The apprentice never calls a language model at runtime

Runs are executed by a deterministic apprentice that replays lessons taught earlier by the tutor (Claude Code). The PC is often offline and workdays can last hours, so a model call per step would be slow, costly and unavailable. The price is that the apprentice cannot improvise: anything unexpected stops the flow and becomes a doubt for the tutor.

## Considered Options

- LLM agent in the loop on every step: rejected for cost, latency and offline use.
- Local offline model: deferred to a future version; the lesson store is the same either way.
