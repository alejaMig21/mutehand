"""The one command: `uv run mutehand [command]`. With no command it opens the editor."""

import sys
from collections.abc import Callable, Mapping, Sequence

Handler = Callable[[Sequence[str]], int | None]

DESCRIPTIONS = {
    "open": "open the flow editor in your browser (the default)",
    "run": "run a flow now, without the editor (--flow; see run --help)",
    "schedule": "run a flow every day with Windows Task Scheduler (create, list, delete)",
    "knowledge": "move steps and flows between machines (export, import, build-factory)",
    "mcp": "serve the tutor tools over MCP; an agent starts this, you normally never do",
}


def _commands() -> Mapping[str, Handler]:
    # imported here so that `--help` and a typo do not pay for the editor, the scheduler and the MCP libraries
    from workflow_factory import app, knowledge, mcp_server, schedule, workday

    return {"open": lambda argv: app.run(), "run": workday.main, "schedule": schedule.main,
            "knowledge": knowledge.main, "mcp": lambda argv: mcp_server.main()}


def _usage() -> str:
    width = max(map(len, DESCRIPTIONS))
    lines = [f"  {name:<{width}}  {text}" for name, text in DESCRIPTIONS.items()]
    return "usage: mutehand [command] [arguments]\n\ncommands:\n" + "\n".join(lines)


def main(argv: Sequence[str] | None = None, commands: Mapping[str, Handler] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help", "help"):
        print(_usage())
        return 0
    name, rest = (argv[0], argv[1:]) if argv else ("open", [])
    if name not in DESCRIPTIONS:
        print(f"unknown command {name!r}\n\n{_usage()}", file=sys.stderr)
        return 2
    handler = (commands or _commands())[name]
    return handler(rest) or 0
