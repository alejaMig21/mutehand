# Usable product: a mini n8n whose nodes are taught by an agent

## Problem

Everything works but only from a terminal, one module at a time, and the editor is a thin canvas. The person wants
a product: one command to start it, an editor worth using, and teaching that happens in a chat with an agent.

## Decisions (the person's, 2026-11-25)

- **One command** run in the project folder starts everything: `uv run workflow-factory`. No `.cmd` launchers, no
  shortcuts, no installer, no sequence of terminal commands. The other tools are subcommands of the same command.
- **The editor never starts a lesson.** It only shows what has already been taught, as nodes, so a person builds
  custom flows with what they have and no agent. It is a serious product, a mini n8n whose components arrive through
  lessons; the first editor is considered poor and is redesigned, not patched.
- **Lessons start only through MCP in a chat with an agent.** The folder declares the tutor in `.mcp.json`, so
  opening Claude Code here needs one approval and no registration by hand. A tutor playbook tells the agent how to
  teach.
- The editor's look is prototyped locally first (the `local-design` skill), after the design questions are settled.
- No packaged `.exe`: a bundled Python is a large download on a slow metered connection.

## Done

25: the one command (`uv run workflow-factory`), the windowless-free launcher with reuse and a Quit button, and the
tutor connection through `.mcp.json` (verified with a real MCP handshake: eight tutor tools).

## Open work

26 tutor playbook and a documented teaching session (the agent side); 27 the editor as a node editor (design grill,
local prototype, then build); 28 schedule from the screen; 29 first-run check; 30 paste and key steps for apps that
refuse `set-value` (Word).

## Out of scope

A Teach button in the editor, shortcuts or launchers, a multi-user or remote mode, and any change to the safety
rules (ADR 0002).
