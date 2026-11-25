# Research 23: secure-field redaction in practice

Date: 2026-11-25. Question: does agent-desktop really redact password fields in a live test, how does a
secret typed through stdin behave, and does the write result say it was not verified?

## Method

A throw-away WinForms window of my own (one plain text box, one with `UseSystemPasswordChar`) on the
secondary monitor, launched without activation and closed afterwards. Only a made-up dummy value was
used (`dummy-secret-23`). After each write, the real content of each box was read back through Win32
`WM_GETTEXT` from the same machine (outside agent-desktop) to see what actually arrived.

## Results

| Probe | Plain field | Password field |
|---|---|---|
| `snapshot` entry | `name` "Plain field", states `[]` | **`states: ["secure"]`, no `name` at all** (the accessible name was withheld) |
| `get <ref> --property value` | the value | **`null`** |
| `set-value <ref> VALUE` | `delivered_verified`, `verification_scope: element_value`, `post_state.value` echoes the value | **`delivered_unverified`**, `verification_reason: secure_field`, `verification_scope: unavailable`, **no value in `post_state`** |
| `set-value <ref> --stdin` | same as above | same as above, and the dummy value appears **nowhere** in the reply |
| value really arrived (Win32 read-back) | yes | **yes** (the write works, it is only unverifiable) |
| `type <ref> --stdin` (default headless mode) | `POLICY_DENIED`: "Target is not actionable: supported_action (semantic action is unavailable and focus fallback is denied)" | same |

## Findings that changed the code

1. **Redaction is real and the write result says so.** A secure field reports `delivered_unverified`
   with `verification_reason: secure_field`; the value is never echoed in a reply or readable with `get`.
2. **`snapshot()` never marked secure fields** (the adapter only read the flag in `find`). A lesson that
   found the field by role and position would not have been treated as secret. Fixed: `_walk` now sets
   `secure` from `states`.
3. **`type` is refused without focus on a field that offers only `SetValue`** (this WinForms edit is one;
   Paint-style canvases and many custom controls are others). The adapter's `type_text` / `type_secret`
   would have failed there. Fixed: on `POLICY_DENIED` they fall back to `set-value --stdin`, which takes
   no focus and replaces the field content. Other error codes are not retried. A failed secret write
   still withholds the CLI message.
4. A secure control has no name, so a lesson cannot find it by name: it must use role, automation id or
   position from the anchor. (The consent scope for a secret is already the control, not its label.)

## Not covered

Other toolkits (browser password inputs, WPF `PasswordBox`, UWP) were not run; the `secure` state and the
`secure_field` reason are what the CLI documents for them and what it did for this one.

## Impact

`src/workflow_factory/agent_desktop.py`: `_walk` marks secure controls; `_enter` implements the
`set-value` fallback. Tests: `tests/test_agent_desktop_adapter.py` (five new tests).
