# Workflow factory

A mini n8n for Windows desktop apps whose building blocks are taught by an agent. A tutor (an agent in Claude Code,
through MCP) teaches a deterministic apprentice **lessons** about an app; each lesson becomes a **node** in the
editor; you wire nodes into **flows** that run, are scheduled and can be stopped, with no agent and no language
model involved. Terms are in `GLOSSARY.md`, decisions in `docs/adr/`, research notes in `docs/research/`.

## Open the editor

```text
uv sync                    # once
uv run workflow-factory    # opens the editor in your browser; Ctrl+C here or “Close the program” in the editor stops it
```

A second `uv run workflow-factory` while one is running opens the same editor. Nothing in the editor starts a
lesson; where teaching is needed, it shows the message to send in a chat.

## Teach it (an agent chat)

Open Claude Code in this folder (`claude`). The first time it asks you to approve the `workflow-factory` MCP
server that this folder's `.mcp.json` declares: say yes once. Then ask the agent to study an app. The tutor tools
are `observe_app`, `mark_app_private`, `set_study_order`, `study_status`, `list_open_doubts`, `answer_doubt`,
`record_consent`, `list_known_steps`, `create_flow`, `flow_status` and `teach_step` (`teach_lesson` still works as its old name). Each taught step appears in the editor as a node. The agent learns how to teach from `docs/agents/tutor.md`.
Recipes (one pattern taught once, reused on another app by teaching only the controls that differ) use `save_recipe`, `list_recipes`,
`apply_recipe` and `mark_step_known`.

## Other commands

| Command | What it does |
|---|---|
| `uv run workflow-factory run --flow <id> --app <process, e.g. mspaint.exe>` | run a flow now, without the editor (exit codes 0 to 5, a report in the data folder; `--help` lists the options) |
| `uv run workflow-factory schedule create ...` | run a flow every day with Windows Task Scheduler (`create`, `list`, `delete`) |
| `uv run workflow-factory knowledge export` | move lessons and flows between machines (`export`, `import`, `build-factory`) |

Your data lives in `%LOCALAPPDATA%\workflow-factory` (`user.db`, `reports\`); set `WORKFLOW_FACTORY_USER_DB` or
`WORKFLOW_FACTORY_REPORT_DIR` to move it. It needs the `agent-desktop` command line tool (the adapter looks for the
real exe, not the npm `.cmd` shim).

## Status

All 16 build tickets and the research tickets are done and tested (`uv run pytest -q`, plus opt-in tests with `-m
live` and `-m web`). The product shell is in progress (`.scratch/usable-product/spec.md`): the one command and the
zero-setup tutor connection are done; the editor was rebuilt around chores (Home, a top-to-bottom canvas, daily runs, an
Apps screen and a first-day guide: `.scratch/editor-rethink/spec.md`). No lessons are taught yet; the data folder starts empty. The example flow
Vivaldi -> Word -> Telegram is not built (research in `docs/research/17` to `19`); writing into a Word page needs the
paste step of ticket 29.

## Rules worth knowing

- Every acting step (click, drag, type) takes one machine-wide input lock and pauses while you use the computer.
- Secret fields are marked `secure`, never read back, and secrets are typed from the Windows Credential Manager.
- Lessons never store absolute screen coordinates (ADR 0004).
