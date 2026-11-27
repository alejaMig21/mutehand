"""What needs the person: one list that Home and the flow screen both read, so they never disagree.

A stopped flow is the first kind. Each item holds only roles, names the person gave and codes: no screen content, and no
name of a box in a private app."""

from pathlib import Path

from workflow_factory.flows import flow_summaries, load_flow, taught_app
from workflow_factory.queue import last_runs, list_doubts
from workflow_factory.steps import Status, list_steps, step_reports
from workflow_factory.tutor import is_private, private_apps


def rejected_by_person(report: dict) -> bool:
    """Is this step rejected, and not by a failed check? A rejection nobody recorded counts as the person's."""
    why = report["why"]
    return report["state"] == str(Status.REJECTED) and (why or {}).get("kind") != "different_effect"


def attention_items(user_db: Path, factory_db: Path | None) -> list[dict]:
    """A flow stopped with an open doubt, one item per flow, oldest first. `detail` of the doubt is the reason; the words
    for it belong to the screen. `rejected_by_person` lists the steps of the flow the person rejected: trying again does
    not lift those."""
    by_flow: dict[str, list] = {}
    for doubt in list_doubts(user_db, "open"):
        by_flow.setdefault(doubt.flow_id, []).append(doubt)  # a test of one box is kept under "<flow>#test:<box>": no match
    flows = {entry["id"]: entry for entry in flow_summaries(user_db, factory_db)}  # a deleted flow is not here
    waiting = [flow_id for flow_id in by_flow if flow_id in flows]
    if not waiting:
        return []
    steps = list_steps(user_db, factory_db)
    reports = {(step.app, step.name): report for step, report in zip(steps, step_reports(user_db, steps), strict=True)}
    private, runs, items = private_apps(user_db), last_runs(user_db), []
    for flow_id in waiting:
        flow, entry = load_flow(user_db, factory_db, flow_id), flows[flow_id]
        app = taught_app(entry["app"], steps)
        order = {node.id: n for n, node in enumerate(flow.nodes)}
        doubt = min(by_flow[flow_id], key=lambda d: (order.get(d.node_id, len(order)), d.id))  # the first box in flow order
        hidden = is_private(user_db, app, private) if app else False
        used = dict.fromkeys(node.step for node in flow.nodes if node.kind in ("step", "loop"))
        person = [{"app": app, "step": name} for name in used if (report := reports.get((app, name))) and rejected_by_person(report)]
        last = runs.get(flow_id)
        items.append({
            "kind": "stopped", "flow": flow_id, "title": entry["title"], "app": app, "private": hidden,
            "node": doubt.node_id, "box": None if hidden else (doubt.step or None), "reason": doubt.detail or str(doubt.reason),
            "doubt": doubt.id, "note": doubt.note, "at": last["at"] if last else None,
            "rejected_by_person": person,  # to call "Allow again" with: never printed for a private app
        })
    return sorted(items, key=lambda item: item["doubt"])
