# 11: Run view, safety marks and doubts count

**What to build:** Run a whole flow with live status per node and a stop that works at once; each step shows trusted, on trial or rejected, sensitive steps show a lock and consent, a flow with a rejected step does not start, and a counter marks open doubts on the affected nodes.

**Blocked by:** 09

**Status:** resolved

- [x] Live per-node status and a stop that ends the run
- [x] A flow with a rejected step refuses to start and names the step
- [x] Doubts show as a count on the node and cannot be resolved from the editor

## Answer

Run view in direction D (checked against `mockups/node-editor/D3-taller-plano-run.png` in a headless screenshot).
- Live status on each card (running, done, stopped, skipped, carried on, paused for you) as an icon and a word; the run log sits below the canvas
  (`GET /api/runs/<id>` now carries `log`). **Stop** replaces Run flow while a run goes: `POST /api/runs/<id>/stop` sets the emergency stop, the run ends
  as `emergency` at the next node or wait, and the flag is cleared once no run is left so the next one can start. While the person uses the PC the node
  reports `paused` and the editor says "Paused: you moved the mouse. It resumes when you stop using the PC."
- Safety marks on every step card, always icon plus word: Trusted / On trial / Rejected / Needs a re-check, a lock with Consent given or Needs
  consent, Private app. `/api/steps` carries `state`, `private` and `consent`. The top bar sums them up (steps on trial, rejected, consents missing, doubts).
- A flow with a rejected step does not start from the editor: Run flow is off and says which step ('save-file' is rejected), and the API refuses
  with the same words. A scheduled run is different on purpose: it starts and stops at that node leaving a doubt, so the tutor hears about it.
- Doubts show as "N doubts" on the node and in the top bar (`/api/doubts?status=open` filtered by flow). The editor has no control to answer or
  dismiss one: that stays in the Tutor queue screen and the tutor tools (browser test checks the buttons).
Tests: `tests/test_run_safety.py`, `tests/test_api_runview.py`, `web/src/safety.test.js` and 3 more browser tests.
