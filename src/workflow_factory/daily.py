"""A flow's daily time. One fact held in two places that never disagree: a daily trigger node in the flow, and the
Windows task that runs it. This module changes the flow side and finds the task side; the API does both together."""

import os
from dataclasses import replace
from pathlib import Path

from workflow_factory import schedule
from workflow_factory.flow import Flow, Node
from workflow_factory.paths import default_user_db

ROW = 160  # the distance between two rows of the canvas, as in the editor


def _daily(node: Node) -> bool:
    return node.kind == "trigger" and node.fields["mode"]["value"] == "daily"


def trigger_time(flow: Flow) -> str | None:
    """The time written on the flow's first daily trigger node, if it has one."""
    return next((node.fields["at"]["value"] for node in flow.nodes if _daily(node)), None)


def _same_file(task_db: str | None, user_db: Path) -> bool:
    if task_db is None:  # a task made without --user-db opens the default data file
        return os.path.normcase(user_db) == os.path.normcase(default_user_db())
    return os.path.normcase(os.path.abspath(task_db)) == os.path.normcase(os.path.abspath(user_db))


def tasks_by_flow(user_db: Path, runner) -> dict[str, list[dict]]:
    """The Windows tasks that run flows from this data file, by flow and in name order (those of another data file are not
    ours, and are never listed or removed)."""
    found: dict[str, list[dict]] = {}
    for task in sorted(schedule.describe_schedules(runner=runner, with_db=True), key=lambda t: t["name"]):
        if task["flow"] and _same_file(task.get("db"), user_db):
            found.setdefault(task["flow"], []).append(task)
    return found


def with_daily(flow: Flow, at: str | None, positions: dict) -> tuple[Flow, dict]:
    """The flow with `at` as its daily time (None: without one) and the positions to store with it.

    A daily start node gets that time; else a manual one becomes daily; else a new one is put first, leading to the nodes
    nothing leads to. Removing a time removes every daily start node and its wires."""
    triggers = [node for node in flow.nodes if _daily(node)]
    if at is None:
        gone = {node.id for node in triggers}
        edges = None if flow.edges is None else [e for e in flow.edges if not gone & set(e)]
        kept = {id_: place for id_, place in positions.items() if id_ not in gone}
        return Flow(nodes=[n for n in flow.nodes if n.id not in gone], id=flow.id, edges=edges), kept
    fields = {"mode": {"value": "daily"}, "at": {"value": at}}
    if triggers or any(n.kind == "trigger" for n in flow.nodes):
        first_manual = next((n.id for n in flow.nodes if n.kind == "trigger" and not triggers), None)
        nodes = [replace(n, fields=fields) if _daily(n) or n.id == first_manual else n for n in flow.nodes]
        return Flow(nodes=nodes, id=flow.id, edges=flow.edges), positions
    ids = {n.id for n in flow.nodes}
    new = next(name for name in ("trigger", *(f"trigger{n}" for n in range(2, len(ids) + 3))) if name not in ids)
    start = Node(new, kind="trigger", fields=fields)
    first = [n.id for n in flow.nodes if n.id not in flow.owned and not any(t == n.id for _, t in flow.all_edges)]
    edges = None if flow.edges is None else [*flow.edges, *((new, root) for root in first)]
    placed = positions
    if first and first[0] in positions:
        above = positions[first[0]]
        placed = {**positions, new: {"x": above["x"], "y": above["y"] - ROW}}
    return Flow(nodes=[start, *flow.nodes], id=flow.id, edges=edges), placed
