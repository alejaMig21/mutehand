# 23: Research: secure-field redaction in practice

**Type:** research

**What to find out:** Whether password fields are really redacted by agent-desktop in a live test (so far taken from its docs only), and how typing a secret through stdin behaves.

**Blocked by:** 02

**Status:** resolved

- [x] Live test on a harmless password field, results recorded without exposing values
- [x] Confirm the write result reports it was not verified for secure fields

## Answer

See `docs/research/23-secure-field-redaction.md`. Redaction is real: a password field is listed with states ["secure"] and no name, `get value` returns null, and a write reports `delivered_unverified` with `verification_reason: secure_field` and no value. The write does arrive (read back by Win32). Two adapter defects found and fixed: snapshot() did not mark secure controls; `type` is refused (POLICY_DENIED) on SetValue-only fields, so type_text/type_secret now fall back to set-value --stdin.
