# Workflow factory

A deterministic apprentice for Windows desktop apps. A tutor (Claude Code, through MCP) teaches it **lessons**
once; afterwards it replays them without any language model, in **flows** you can edit, run, schedule and stop.
Terms are in `GLOSSARY.md`, decisions in `docs/adr/`, research notes in `docs/research/`.

## Status

All 16 build tickets and the research tickets are done and tested (`uv run pytest -q`, plus opt-in live tests
with `-m live`). It is not packaged: there are no installed commands, everything runs as
`uv run python -m workflow_factory.<module>`. No lessons are taught yet; the data folder starts empty.
The example flow Vivaldi -> Word -> Telegram is not built: its research is in `docs/research/17` to `19`.
Writing into a Word page needs real input (paste or keys), which the adapter does not do yet (`docs/research/18`).

## Setup

```text
uv sync
```

It needs the `agent-desktop` command line tool (the adapter looks for the real exe, not the npm `.cmd` shim).
Your data lives in `%LOCALAPPDATA%\workflow-factory` (`user.db`, `reports\`); set `WORKFLOW_FACTORY_USER_DB` or
`WORKFLOW_FACTORY_REPORT_DIR` to move it.

## Use it

| What | Command |
|---|---|
| Teach (tutor tools for Claude Code) | `uv run python -m workflow_factory.mcp_server` as an MCP server over stdio. Register it in Claude Code with your own MCP settings, pointing at this folder. Tools: `observe_app`, `mark_app_private`, `set_study_order`, `study_status`, `list_open_doubts`, `record_consent`. |
| See and edit flows, lessons, consents, the doubts queue and run history | `uv run python -m workflow_factory.editor` (loopback only, token protected; it prints the address; `--no-hotkey` skips the emergency hotkey) |
| Run a flow | `uv run python -m workflow_factory.workday --flow <flow id> --app <process, e.g. mspaint.exe> --data-dir <folder>` (exit codes 0 to 5, report in the data folder; `--context-file` gives the typed values) |
| Run a flow every day (Windows Task Scheduler) | `uv run python -m workflow_factory.schedule create ...` and `... delete`; see `--help` |
| Move knowledge between machines | `uv run python -m workflow_factory.knowledge export`, `import`, `build-factory` |

## Rules worth knowing

- Every acting step (click, drag, type) takes one machine-wide input lock and pauses while you use the computer.
- Secret fields are marked `secure`, never read back, and secrets are typed from the Windows Credential Manager.
- Lessons never store absolute screen coordinates (ADR 0004).
