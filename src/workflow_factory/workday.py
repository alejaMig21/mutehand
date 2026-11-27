"""`python -m workflow_factory.workday --flow ID`: run one workday headlessly and exit.

This is what Windows Task Scheduler launches; no UI has to be open. It prints one line
(`status=... report=...`), writes a report of what ran, what stopped and why, and exits with a
status the scheduler can show: 0 finished, 1 stopped (a doubt was left), 2 waiting for the tutor,
3 emergency stop, 4 error. The report holds no data values unless `--with-values` is given.
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from workflow_factory.agent_desktop import AgentDesktop
from workflow_factory.desktop import DesktopError
from workflow_factory.flow import clear_emergency_stop, emergency_stop, run_flow
from workflow_factory.flows import load_flow
from workflow_factory.hotkey import EmergencyHotkey
from workflow_factory.paths import default_report_dir, default_user_db
from workflow_factory.queue import list_doubts, list_runs

EXIT_FINISHED, EXIT_STOPPED, EXIT_WAITING, EXIT_EMERGENCY, EXIT_ERROR, EXIT_BUSY = 0, 1, 2, 3, 4, 5
EXIT_BY_STATUS = {"finished": EXIT_FINISHED, "stopped": EXIT_STOPPED, "waiting": EXIT_WAITING,
                  "emergency": EXIT_EMERGENCY, "busy": EXIT_BUSY}
KEEP_REPORTS = 200


def build_report(user_db: Path, flow_id: str, result, context: dict, with_values: bool) -> dict:
    """Nodes, outcomes and stop reasons only. Values appear only when the person asked for them."""
    run = next((r for r in list_runs(user_db, flow_id) if r["id"] == result.run_id), None)
    report = {
        "flow": flow_id, "status": result.status,
        "started_at": run["started_at"] if run else None, "finished_at": run["finished_at"] if run else None,
        "stopped_node": result.stopped,
        "nodes": run["nodes"] if run else [],
        # every open doubt of this flow, including ones from earlier runs
        "open_doubts": [{"id": d.id, "node_id": d.node_id, "step": d.step, "reason": str(d.reason),
                         "detail": d.detail}
                        for d in list_doubts(user_db, "open") if d.flow_id == flow_id],
    }
    if with_values:
        report["context"] = context
    return report


def write_report(folder: Path, report: dict, run_id: int | None, keep: int = KEEP_REPORTS) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    flow = re.sub(r"[^\w.-]", "_", str(report["flow"]))  # a flow name never becomes a path
    path = folder / f"{flow}-{stamp}-{run_id or 0}.json"
    attempt = 1
    while path.exists():  # two reports in one second must not overwrite each other
        attempt += 1
        path = folder / f"{flow}-{stamp}-{run_id or 0}-{attempt}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    reports = sorted(folder.glob("*.json"), key=lambda p: (p.stat().st_mtime_ns, p.name))
    for old in reports[: max(0, len(reports) - keep)]:  # only the newest reports are kept
        old.unlink(missing_ok=True)
    return path


def _fail(args, flow_id: str, code: str, message: str | None = None) -> int:
    """Exit 4 and, because pythonw has no stderr, leave a report that says why (the code only)."""
    if message:
        print(f"error: {message}", file=sys.stderr)
    report = {"flow": flow_id, "status": "error", "error": code, "nodes": [], "open_doubts": []}
    try:
        print(f"status=error report={write_report(args.report_dir, report, None)}")
    except OSError:
        print(f"status=error error={code}")
    return EXIT_ERROR


def main(argv: list[str] | None = None, desktop_for=AgentDesktop) -> int:
    parser = argparse.ArgumentParser(prog="workflow_factory.workday")
    parser.add_argument("--flow", required=True)
    parser.add_argument("--app", help="ignored: a task made before nodes recorded their technology still passes it")
    parser.add_argument("--context", default="{}", help="JSON object with the run's typed values")
    parser.add_argument("--context-file", type=Path, help="a JSON file with the typed values (no quoting needed)")
    parser.add_argument("--with-values", action="store_true", help="also write the context values to the report")
    parser.add_argument("--data-dir", type=Path,
                        help="one folder for user.db and reports/ (keeps a scheduled command short)")
    parser.add_argument("--user-db", type=Path)
    parser.add_argument("--factory-db", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--fired", choices=["manual", "daily"], default="manual",
                        help="which triggers start the flow: the scheduled task passes daily")
    parser.add_argument("--no-hotkey", action="store_true")
    args = parser.parse_args(argv)
    if args.data_dir:
        args.user_db = args.user_db or args.data_dir / "user.db"
        args.report_dir = args.report_dir or args.data_dir / "reports"
    args.user_db = args.user_db or default_user_db()
    args.report_dir = args.report_dir or default_report_dir()
    try:
        return _run(args, desktop_for)
    except Exception as error:  # noqa: BLE001 - a crash must never look like "stopped" (1): exit 4, class name only
        return _fail(args, args.flow, type(error).__name__)


def _run(args, desktop_for) -> int:
    try:
        text = args.context_file.read_text(encoding="utf-8") if args.context_file else args.context
        context = json.loads(text)
        if not isinstance(context, dict):
            raise ValueError
    except (ValueError, OSError):
        return _fail(args, args.flow, "BAD_CONTEXT", "the context must be a JSON object")
    flow = load_flow(args.user_db, args.factory_db, args.flow)
    if flow is None:
        return _fail(args, args.flow, "NO_SUCH_FLOW", f"no flow named {args.flow!r}")

    clear_emergency_stop()  # a stop pressed earlier in this process must not block today's workday
    hotkey = None
    if not args.no_hotkey:
        hotkey = EmergencyHotkey(emergency_stop)
        try:
            hotkey.start()
        except RuntimeError as error:
            print(f"warning: {error}", file=sys.stderr)
            hotkey = None
    try:
        result = run_flow(flow, desktop_for, args.user_db, args.factory_db, context=context,
                         fired=args.fired)
    except DesktopError as error:  # e.g. the app is not running: the code only, never screen text
        return _fail(args, flow.key, getattr(error, "code", "DESKTOP_ERROR"))
    finally:
        if hotkey:
            hotkey.stop()

    report = build_report(args.user_db, flow.key, result, context, args.with_values)
    print(f"status={result.status} report={write_report(args.report_dir, report, result.run_id)}")
    return EXIT_BY_STATUS[result.status]


if __name__ == "__main__":
    raise SystemExit(main())
