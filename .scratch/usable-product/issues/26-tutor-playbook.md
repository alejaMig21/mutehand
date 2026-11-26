# 26: Tutor playbook: teaching from an agent chat with zero setup

**What to build:** An agent opened in this folder knows how to teach: a playbook (docs/agents/tutor.md, pointed to from CLAUDE.md) says how to study an app, when to ask the person, how consent and private apps work, how a lesson becomes a node (name, inputs, outputs) and what to check before saving it. A documented teaching session on a simple app proves it end to end.

**Blocked by:** 25

**Status:** resolved

- [x] Opening Claude Code here and approving the project server is all the setup
- [x] The playbook is the only place that says how to teach; CLAUDE.md only points to it
- [x] A lesson taught in a real agent chat appears in the editor as a node

## Answer

`docs/agents/tutor.md` is the playbook: setup (none), a lesson in order (ask, warn, observe, plan, teach one step at a time, check, close), names,
inputs and outputs, what to check before saving, recipes, doubts, what not to do. `CLAUDE.md` only points to it (a test checks that it names no tool).
- Verified: the real stdio handshake with the server exactly as `.mcp.json` declares it lists 13 tools; a scripted session that follows the playbook
  through the MCP protocol on a simple app (observe, plan, teach, read step, consent asked and recorded, resume) leaves steps that `/api/steps` lists
  (what the editor shows as nodes) and a flow built from them runs and reads the value (`tests/test_tutor_session.py`); a test keeps the playbook naming
  every tool the server has.
- Needs the person: the same lesson in a real Claude Code chat. Open `claude` in this folder, approve the `workflow-factory` server once, and say
  "teach yourself this app: <name>". The tools and the playbook are what that chat will use.
