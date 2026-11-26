"""Windows Task Scheduler: create and delete the schedule that launches a workday.

Arguments are validated and passed to schtasks as a list (never through a shell), because a flow or
app name ends up inside the command line the scheduler will run later.
"""

import argparse
import csv
import io
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SAFE_NAME = re.compile(r"[\w.-]+")
SCHEDULE_PREFIX = "Workflow factory - "  # marks what this tool made, so it can list and remove only that
SCHEDULE_NAME = re.compile(r"[\w .-]{1,120}")  # the longest flow name plus " daily HHMM" fits
MAX_COMMAND_CHARS = 261  # the limit of schtasks /TR
CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _quote(argument: str) -> str:
    return f'"{argument}"' if " " in argument else argument


def workday_command(flow_id: str, app: str, extra: list[str] | None = None) -> str:
    """The command line the scheduler runs. pythonw (no console window) when it is there."""
    for label, value in (("flow", flow_id), ("app", app)):
        if not SAFE_NAME.fullmatch(value):
            raise ValueError(f"the {label} name may only use letters, digits, '_', '.' and '-': {value.removesuffix('.exe')!r}")
    if any('"' in part for part in (extra or [])):
        raise ValueError("extra arguments may not contain double quotes")
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    exe = windowless if windowless.exists() else python
    parts = ["-m", "workflow_factory.workday", "--flow", flow_id, "--app", app, "--fired", "daily", *(extra or [])]
    return f'"{exe}" ' + " ".join(_quote(part) for part in parts)


def full_name(name: str) -> str:
    """The name Windows sees: always carrying the prefix of this tool, never doubled."""
    bare = name.removeprefix(SCHEDULE_PREFIX)
    if not SCHEDULE_NAME.fullmatch(bare):
        raise ValueError(f"the schedule name may only use letters, digits, spaces, '_', '.' and '-': {name!r}")
    return SCHEDULE_PREFIX + bare


def create_schedule(name: str, flow_id: str, app: str, daily_at: str, extra: list[str] | None = None,
                runner=subprocess.run) -> None:
    """A task that runs the workday every day at HH:MM, in the logged-on user's session."""
    name = full_name(name)
    if not CLOCK.fullmatch(daily_at):
        raise ValueError(f"the time must look like HH:MM (24 hours), not {daily_at!r}")
    command = workday_command(flow_id, app, extra)
    if len(command) > MAX_COMMAND_CHARS:
        raise ValueError(f"the command is {len(command)} characters; Windows Task Scheduler accepts at most "
                         f"{MAX_COMMAND_CHARS} (use shorter paths or the default locations)")
    args = ["schtasks", "/Create", "/TN", name, "/TR", command, "/SC", "DAILY", "/ST", daily_at, "/F"]
    done = runner(args, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"schtasks could not create the task: {done.stderr.strip() or done.stdout.strip()}")


def delete_schedule(name: str, runner=subprocess.run) -> None:
    """Remove a schedule made by this tool (anything else is unreachable: names always get the prefix)."""
    name = full_name(name)
    runner(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True, timeout=60)


def list_schedules(runner=subprocess.run) -> list[str]:
    """The names of the schedules this tool created."""
    done = runner(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=60)
    names = [row[0].lstrip("\\") for row in csv.reader(io.StringIO(done.stdout)) if row]
    return [name for name in names if name.startswith(SCHEDULE_PREFIX)]


def _bare(name: str) -> str:
    return name.removeprefix(SCHEDULE_PREFIX)


def describe_schedules(runner=subprocess.run) -> list[dict]:
    """What the screen shows for each schedule this tool made: its name, the flow, the app and the daily time.

    The details come from the task's XML, which does not depend on the language of Windows. A task whose XML cannot be read is
    still listed by name."""
    result = []
    for name in list_schedules(runner=runner):
        info = {"name": _bare(name), "flow": None, "app": None, "at": None}
        done = runner(["schtasks", "/Query", "/TN", name, "/XML"], capture_output=True, text=True, timeout=60)
        if done.returncode == 0:
            info.update(_read_task_xml(done.stdout))
        result.append(info)
    return result


def _read_task_xml(xml: str) -> dict:
    try:
        root = ET.fromstring(re.sub(r"^<\?xml[^>]*\?>", "", xml.strip()))
    except ET.ParseError:
        return {}

    def text(tag: str) -> str:
        return next((e.text or "" for e in root.iter() if e.tag.endswith(tag)), "")

    arguments = text("Arguments")
    flow, app = re.search(r"--flow (\S+)", arguments), re.search(r"--app (\S+)", arguments)
    at = re.search(r"T(\d\d:\d\d)", text("StartBoundary"))
    return {"flow": flow and flow[1], "app": app and app[1], "at": at and at[1]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow_factory.schedule")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="run a flow every day at a time")
    create.add_argument("--name", required=True)
    create.add_argument("--flow", required=True)
    create.add_argument("--app", required=True)
    create.add_argument("--daily-at", required=True, metavar="HH:MM")
    commands.add_parser("list", help="the schedules this tool created")
    delete = commands.add_parser("delete", help="remove a schedule created by this tool")
    delete.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_schedule(args.name, args.flow, args.app, args.daily_at)
            print(f"task {args.name!r} will run flow {args.flow!r} every day at {args.daily_at}")
        elif args.command == "list":
            print("\n".join(list_schedules()) or "no schedules")
        else:
            delete_schedule(args.name)
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
