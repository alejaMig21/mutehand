"""Run a flow through the desktop port and store each node's measured effect."""

import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from workflow_factory.consent import is_permitted
from workflow_factory.desktop import Desktop
from workflow_factory.ladder import locate
from workflow_factory.lessons import (
    Status,
    current_status,
    find_lesson,
    record_outcome,
    revalidate_changed_versions,
)
from workflow_factory.queue import (
    Reason,
    clear_checkpoint,
    has_open_doubt,
    load_checkpoint,
    record_doubt,
    save_checkpoint,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS node_results (
    node_id TEXT NOT NULL,
    effect TEXT NOT NULL,
    finished_at TEXT NOT NULL
)
"""


class Effect(StrEnum):
    """Closed vocabulary of measured effects (see GLOSSARY.md)."""

    CLOSED_DIALOG = "closed_dialog"
    REVEALED = "revealed"
    VALUE_CHANGED = "value_changed"
    NO_CHANGE = "no_change"
    PIXELS_CHANGED = "pixels_changed"


class LessonNotFound(Exception):
    """No lesson with that name for this app in user or factory knowledge."""


@dataclass(frozen=True)
class Node:
    id: str
    lesson: str


@dataclass(frozen=True)
class Flow:
    nodes: list[Node]
    id: str | None = None  # None: derived from the nodes, so unrelated flows never share state

    @property
    def definition(self) -> str:
        return ";".join(f"{node.id}={node.lesson}" for node in self.nodes)

    @property
    def key(self) -> str:
        return self.id or self.definition


@dataclass(frozen=True)
class RunResult:
    effects: dict[str, Effect]
    blocked: dict[str, str]  # node id -> why it did not run (detailed reason)
    statuses: dict[str, Status]  # node id -> lesson status after the run
    stopped: str | None = None  # node id where the flow stopped and left a doubt
    waiting: bool = False  # the flow has an open doubt, so it did not run


# Detailed block reason -> the fixed doubt vocabulary
DOUBT_REASON = {
    "no_consent": Reason.NO_CONSENT,
    "control_not_found": Reason.CONTROL_NOT_FOUND,
    "unreadable": Reason.CONTROL_NOT_FOUND,
    "out_of_frame": Reason.PRECONDITION_NOT_MET,
    "rejected": Reason.PRECONDITION_NOT_MET,
    "to_revalidate": Reason.PRECONDITION_NOT_MET,
    "template_no_match": Reason.TEMPLATE_NO_MATCH,
}


def _gate(lesson, user_db, key, desktop):
    """Why this node may not run, or the control to act on when it may."""
    status = current_status(user_db, lesson, key.version)
    if status in (Status.REJECTED, Status.TO_REVALIDATE):
        return str(status), None
    if not is_permitted(user_db, lesson):  # before any desktop call
        return "no_consent", None
    if lesson.frame and not lesson.frame.matches(desktop.frame(), lesson.mask):
        return "out_of_frame", None
    endpoints = [lesson.endpoint] + ([lesson.drag_to] if lesson.action == "drag" else [])
    targets = []
    for endpoint in endpoints:  # a drag needs both ends
        target, reason = locate(endpoint, desktop)
        if reason:
            return reason, None
        if not target.control.readable:  # unreadable means blocked, whatever the consent
            return "unreadable", None
        if target.control.secure and lesson.action != "type_secret":  # password fields take secrets only
            return "unreadable", None
        targets.append(target)
    return None, targets


def effect_of(before, after) -> Effect:
    if after - before:
        return Effect.REVEALED
    if before - after:
        return Effect.CLOSED_DIALOG
    return Effect.NO_CHANGE


def _store_effect(user_db: Path, node_id: str, effect: Effect, finished_at: str) -> None:
    with closing(sqlite3.connect(user_db)) as db, db:  # short-lived: other writers share this file
        db.execute(SCHEMA)
        db.execute("INSERT INTO node_results VALUES (?, ?, ?)", (node_id, effect.value, finished_at))


def run_flow(
    flow: Flow, desktop: Desktop, user_db: Path, factory_db: Path | None = None
) -> RunResult:
    effects, blocked, statuses = {}, {}, {}
    if has_open_doubt(user_db, flow.key):  # a stopped flow waits for the tutor
        return RunResult(effects, blocked, statuses, waiting=True)
    key = desktop.app_key()
    revalidate_changed_versions(user_db, key.process, key.version)
    ids = [node.id for node in flow.nodes]
    resume_from = load_checkpoint(user_db, flow.key, flow.definition)
    pending = flow.nodes[ids.index(resume_from) + 1 :] if resume_from in ids else flow.nodes
    for node in pending:
        lesson = find_lesson(user_db, factory_db, key.process, node.lesson)
        if lesson is None:
            raise LessonNotFound(node.lesson)
        reason, targets = _gate(lesson, user_db, key, desktop)
        target = targets[0] if targets else None
        if reason:
            blocked[node.id] = reason
            capture = dict(Counter(c.role for c in desktop.snapshot()))  # roles and counts only
            record_doubt(user_db, flow.key, node.id, node.lesson, DOUBT_REASON[reason], capture)
            return RunResult(effects, blocked, statuses, stopped=node.id)
        before = set(desktop.snapshot())
        if lesson.action == "type_secret":
            desktop.type_secret(target.control, lesson.secret_ref)  # the value never enters the core
        elif lesson.action == "drag":
            source, destination = targets
            desktop.drag(source.control, source.point, destination.control, destination.point)
        elif target.point:
            desktop.click_at(target.control, *target.point)
        else:
            desktop.click(target.control)
        effect = effect_of(before, set(desktop.snapshot()))
        effects[node.id] = effect
        if lesson.effect:  # nothing taught to compare against means nothing to count
            statuses[node.id] = record_outcome(user_db, lesson, effect == lesson.effect)
        _store_effect(user_db, node.id, effect, desktop.now())
        save_checkpoint(user_db, flow.key, node.id, flow.definition)
    clear_checkpoint(user_db, flow.key)
    return RunResult(effects, blocked, statuses)
