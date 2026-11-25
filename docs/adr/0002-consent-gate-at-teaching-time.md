---
status: accepted
---

# Safety is a consent gate at teaching time, not a fixed forbidden list

Sensitive actions (password fields, system shortcuts, outward actions, veto text) are blocked unless a consent record exists, granted by the user while the tutor teaches the lesson. A fixed never-touch list was rejected because the user, not the tool, decides what their own PC may do; per-run permission prompts and quotas were rejected because workdays run unattended for hours. Factory lessons in sensitive categories ship without active consent, and anything the apprentice cannot read is blocked.

## Consequences

agent-desktop has no concept of consent, veto text or outward actions, so this gate is entirely ours. Secrets are stored only as references to the Windows credential store and piped to the tool by stdin; neither lessons nor the tutor ever hold the value.
