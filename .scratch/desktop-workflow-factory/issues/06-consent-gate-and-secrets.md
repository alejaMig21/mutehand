# 06: Consent gate and secret references

**What to build:** Sensitive actions (password fields, system shortcuts, outward actions, veto text) run only when a consent record exists for that app, control and action. Anything the apprentice cannot read is blocked. Consents can be revoked. Secrets are stored in the Windows credential store and lessons hold only a reference; the value reaches the target through stdin.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] A sensitive lesson without consent is blocked and never reaches the desktop port
- [ ] A granted consent is stored with its scope and the lesson then runs freely
- [ ] Revoking a consent blocks the lesson again
- [ ] An unreadable control is blocked even with a broad consent
- [ ] Factory lessons in sensitive categories ship without active consent
- [ ] No recorded fake-desktop call contains a secret value
