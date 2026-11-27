# Mutehand

A mini n8n for Windows desktop apps whose building blocks are taught by an agent. A tutor (an agent in Claude Code,
through MCP) teaches a deterministic apprentice **lessons** about an app; each lesson becomes a **node** in the
editor; you wire nodes into **flows** that run, are scheduled and can be stopped, with no agent and no language
model involved. Terms are in `GLOSSARY.md`, decisions in `docs/adr/`, research notes in `docs/research/`.

## Open the editor

```text
uv sync                    # once
uv run mutehand    # opens the editor in your browser; Ctrl+C here or “Close the program” in the editor stops it
```

A second `uv run mutehand` while one is running opens the same editor. Nothing in the editor starts a
lesson; where teaching is needed, it shows the message to send in a chat.

## Package it

```text
cd web && npm ci && npm run build   # the editor is built into src/workflow_factory/web (tracked, so a plain checkout runs)
uv build                            # dist/mutehand-<version>-py3-none-any.whl, editor included
```

The wheel needs Python 3.14 and Windows (the desktop adapter and `pywin32`); it installs the `mutehand` command.

## Teach it (an agent chat)

Open Claude Code in this folder (`claude`). The first time it asks you to approve the `workflow-factory` MCP
server that this folder's `.mcp.json` declares: say yes once. Then ask the agent to study an app. The tutor tools
are `observe_app`, `mark_app_private`, `set_study_order`, `study_status`, `list_open_doubts`, `answer_doubt`,
`record_consent`, `list_known_steps`, `list_node_kinds`, `create_flow`, `flow_status` and `teach_step` (`teach_lesson` still works as its old name). Each taught step appears in the editor as a node. The agent learns how to teach from `docs/agents/tutor.md`.
Recipes (one pattern taught once, reused on another app by teaching only the controls that differ) use `save_recipe`, `list_recipes`,
`apply_recipe` and `mark_step_known`.

## Other commands

| Command | What it does |
|---|---|
| `uv run mutehand run --flow <id>` | run a flow now, without the editor (exit codes 0 to 5, a report in the data folder; `--help` lists the options) |
| `uv run mutehand schedule create ...` | run a flow every day with Windows Task Scheduler (`create`, `list`, `delete`) |
| `uv run mutehand knowledge export` | move lessons and flows between machines (`export`, `import`, `build-factory`) |

Your data lives in `%LOCALAPPDATA%\workflow-factory` (`user.db`, `reports\`); set `WORKFLOW_FACTORY_USER_DB` or
`WORKFLOW_FACTORY_REPORT_DIR` to move it. It needs the `agent-desktop` command line tool (the adapter looks for the
real exe, not the npm `.cmd` shim).

## Status

The editor is rebuilt around flows (14 tickets, `.scratch/editor-rethink/`): Home lists the flows with a daily time and what needs
attention, Apps lists the programs it knows, a flow screen draws a flow top to bottom and saves itself, a deleted flow can be undone,
and a first-day guide shows what to do with nothing taught. The tutor can also build a flow from a description
(`list_known_steps`, `list_node_kinds`, `create_flow`, `flow_status`). Tests: `uv run pytest -q`, plus opt-in `-m web` (headless browser)
and `-m live` (real apps; `tests/test_live_excel.py` and `test_live_word.py` need `WF_LIVE_EXCEL=1` / `WF_LIVE_WORD=1`). No lessons are
taught yet; the data folder starts empty. The example flow Vivaldi -> Word -> Telegram is not built (research in `docs/research/17` to `19`).

## Rules worth knowing

- Every acting step (click, drag, type) takes one machine-wide input lock and pauses while you use the computer.
- Secret fields are marked `secure`, never read back, and secrets are typed from the Windows Credential Manager.
- Lessons never store absolute screen coordinates (ADR 0004).
