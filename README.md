# Workflow factory

A deterministic apprentice for Windows desktop apps. A tutor (Claude Code, through MCP) teaches it **lessons**
once; afterwards it replays them without any language model, in **flows** you can edit, run, schedule and stop.
Terms are in `GLOSSARY.md`, decisions in `docs/adr/`, research notes in `docs/research/`.

## Open it

Double-click `Install.cmd` once. It puts a **Workflow Factory** shortcut on your Desktop and in the Start Menu
(it needs `uv sync` to have been run once). From then on, double-click the shortcut: the editor opens in your
browser with no console window, a second click opens the same one, and **Quit** in the top bar closes it.

## Status

All 16 build tickets and the research tickets are done and tested (`uv run pytest -q`, plus opt-in tests with
`-m live` and `-m web`). The product shell is in progress (`.scratch/usable-product/spec.md`): the launcher and
shortcut are done; teaching from the app, scheduling from the app and a first-run check are next. Until teaching
is in the app, the tutor still has to be connected by hand (see the table below). No lessons are taught yet; the
data folder starts empty. The example flow Vivaldi -> Word -> Telegram is not built (research in `docs/research/17`
to `19`); writing into a Word page needs the paste step of ticket 29.

## Setup

```text
uv sync
```

It needs the `agent-desktop` command line tool (the adapter looks for the real exe, not the npm `.cmd` shim).
Your data lives in `%LOCALAPPDATA%\workflow-factory` (`user.db`, `reports\`); set `WORKFLOW_FACTORY_USER_DB` or
`WORKFLOW_FACTORY_REPORT_DIR` to move it.

## Use it from a terminal (advanced)

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
