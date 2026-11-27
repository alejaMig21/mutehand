"""What needs the person: one list that Home and the flow screen both read, so they never disagree.

Kinds: a stopped flow, steps to learn again after an app update, a rejected step a flow needs, and a required setup
piece that is missing. Each item holds only roles, names the person gave and codes: no screen content, and no name of a
step in a private app: where a button needs one to send back, it gets a handle (see `tutor.handle`)."""

from pathlib import Path

from workflow_factory.checks import run_checks
from workflow_factory.flows import flow_overview, flow_summaries, load_flow, taught_app
from workflow_factory.queue import last_runs, list_doubts
from workflow_factory.steps import Status, list_steps, step_reports
from workflow_factory.tutor import handle, is_private, private_apps


def rejected_by_person(report: dict) -> bool:
    """Is this step rejected, and not by a failed check? A rejection nobody recorded counts as the person's."""
    why = report["why"]
    return report["state"] == str(Status.REJECTED) and (why or {}).get("kind") != "different_effect"


def attention_items(user_db: Path, factory_db: Path | None, data_dir: Path | None = None) -> list[dict]:
    """Everything that needs the person: stopped flows (oldest first), then steps to learn again, rejected steps and
    missing setup. `data_dir` is where the setup check looks; without it no setup item is listed."""
    steps = list_steps(user_db, factory_db)
    stopped = _stopped(user_db, factory_db, steps)
    return [*stopped, *_blocking(user_db, factory_db, steps, {item["flow"] for item in stopped}), *_setup(data_dir)]


def _stopped(user_db: Path, factory_db: Path | None, steps: list) -> list[dict]:
    """A flow stopped with an open doubt, one item per flow, oldest first. `detail` of the doubt is the reason; the words
    for it belong to the screen. `rejected_by_person` lists the steps of the flow the person rejected: trying again does
    not lift those."""
    by_flow: dict[str, list] = {}
    for doubt in list_doubts(user_db, "open"):
        by_flow.setdefault(doubt.flow_id, []).append(doubt)  # a test of one node is kept under "<flow>#test:<node>": no match
    flows = {entry["id"]: entry for entry in flow_summaries(user_db, factory_db)}  # a deleted flow is not here
    waiting = [flow_id for flow_id in by_flow if flow_id in flows]
    if not waiting:
        return []
    reports = {(step.app, step.name): report for step, report in zip(steps, step_reports(user_db, steps), strict=True)}
    private, runs, items = private_apps(user_db), last_runs(user_db), []
    for flow_id in waiting:
        flow, entry = load_flow(user_db, factory_db, flow_id), flows[flow_id]
        app = taught_app(entry["app"], steps)
        order = {node.id: n for n, node in enumerate(flow.nodes)}
        doubt = min(by_flow[flow_id], key=lambda d: (order.get(d.node_id, len(order)), d.id))  # the first node in flow order
        hidden = is_private(user_db, app, private) if app else False
        used = dict.fromkeys(node.step for node in flow.nodes if node.kind in ("step", "loop"))
        person = [{"app": app, "step": handle(app, name) if hidden else name} for name in used
                  if (report := reports.get((app, name))) and rejected_by_person(report)]
        last = runs.get(flow_id)
        items.append({
            "kind": "stopped", "flow": flow_id, "title": entry["title"], "app": app, "private": hidden,
            "node": doubt.node_id, "step": None if hidden else (doubt.step or None), "reason": doubt.detail or str(doubt.reason),
            "doubt": doubt.id, "note": doubt.note, "at": last["at"] if last else None,
            "rejected_by_person": person,  # to call "Allow again" with: a handle, not the name, for a private app
        })
    return sorted(items, key=lambda item: item["doubt"])


def _setup(data_dir: Path | None) -> list[dict]:
    """A required setup piece that is missing, with what it is for and how to fix it. A working setup lists nothing."""
    checks = run_checks(data_dir) if data_dir else []
    return [{"kind": "setup", **{key: check[key] for key in ("id", "title", "why", "fix")}}
            for check in checks if not check["ok"] and not check["optional"]]


def _blocking(user_db: Path, factory_db: Path | None, steps: list, stopped: set[str]) -> list[dict]:
    """What keeps a flow from running and only the person can change: by app, the steps to learn again with the flows
    they block, and each rejected step with why and the flows it blocks. A step no flow needs raises nothing. A
    stopped flow has its own card, which already offers what a rejection needs."""
    private = private_apps(user_db)
    reports = {(step.app, step.name): r for step, r in zip(steps, step_reports(user_db, steps), strict=True)}
    relearn: dict[str, dict] = {}
    rejected: dict[tuple[str, str], dict] = {}
    for flow in flow_overview(user_db, factory_db):
        blocked = flow["blocked"]
        if not blocked or blocked["why"] not in ("to_revalidate", "rejected"):
            continue
        app, mine = flow["app"], {"id": flow["id"], "title": flow["title"]}
        hidden = is_private(user_db, app, private)
        if blocked["why"] == "to_revalidate":
            item = relearn.setdefault(app, {"kind": "relearn", "app": app, "private": hidden, "steps": [], "flows": []})
            item["steps"] += [name for name in blocked["steps"] if not hidden and name not in item["steps"]]
            item["flows"].append(mine)
        elif flow["id"] not in stopped:
            for name in blocked["steps"]:
                why = (reports.get((app, name)) or {}).get("why") or {"kind": "person"}  # nobody recorded it: the person's
                item = rejected.setdefault((app, name), {
                    "kind": "rejected", "app": app, "private": hidden, "step": handle(app, name) if hidden else name,
                    "why": {"kind": why.get("kind")} if hidden else why, "flows": []})
                item["flows"].append(mine)
    for item in relearn.values():
        item["steps"].sort()
    return [*sorted(relearn.values(), key=lambda i: i["app"]), *(rejected[key] for key in sorted(rejected))]
