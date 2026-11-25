"""Run a flow through the desktop port and store each node's measured effect."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from workflow_factory.consent import is_permitted
from workflow_factory.desktop import Desktop
from workflow_factory.lessons import (
    Status,
    current_status,
    find_lesson,
    record_outcome,
    revalidate_changed_versions,
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


class ControlNotFound(Exception):
    """The locator matched nothing; the flow stops (tutor queue arrives in a later ticket)."""


class LessonNotFound(Exception):
    """No lesson with that name for this app in user or factory knowledge."""


@dataclass(frozen=True)
class Node:
    id: str
    lesson: str


@dataclass(frozen=True)
class Flow:
    nodes: list[Node]


@dataclass(frozen=True)
class RunResult:
    effects: dict[str, Effect]
    blocked: dict[str, str]  # node id -> why it did not run
    statuses: dict[str, Status]  # node id -> lesson status after the run


def run_flow(
    flow: Flow, desktop: Desktop, user_db: Path, factory_db: Path | None = None
) -> RunResult:
    effects, blocked, statuses = {}, {}, {}
    key = desktop.app_key()
    revalidate_changed_versions(user_db, key.process, key.version)
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        for node in flow.nodes:
            lesson = find_lesson(user_db, factory_db, key.process, node.lesson)
            if lesson is None:
                raise LessonNotFound(node.lesson)
            status = current_status(user_db, lesson, key.version)
            if status in (Status.REJECTED, Status.TO_REVALIDATE):
                blocked[node.id] = str(status)
                continue
            if not is_permitted(user_db, lesson):  # before any desktop call
                blocked[node.id] = "no_consent"
                continue
            if lesson.frame and not lesson.frame.matches(desktop.frame(), lesson.mask):
                blocked[node.id] = "out_of_frame"
                continue
            loc = lesson.locator
            control = desktop.find(loc.role, loc.name, loc.automation_id)
            if control is None:
                raise ControlNotFound(f"{loc.role} {loc.name!r}")
            if not control.readable:  # unreadable means blocked, whatever the consent
                blocked[node.id] = "unreadable"
                continue
            before = set(desktop.snapshot())
            if lesson.action == "type_secret":
                desktop.type_secret(control, lesson.secret_ref)  # the value never enters the core
            else:
                desktop.click(control)
            after = set(desktop.snapshot())
            if after - before:
                effect = Effect.REVEALED
            elif before - after:
                effect = Effect.CLOSED_DIALOG
            else:
                effect = Effect.NO_CHANGE
            effects[node.id] = effect
            if lesson.effect:  # nothing taught to compare against means nothing to count
                statuses[node.id] = record_outcome(user_db, lesson, effect == lesson.effect)
            db.execute(
                "INSERT INTO node_results VALUES (?, ?, ?)", (node.id, effect.value, desktop.now())
            )
    return RunResult(effects=effects, blocked=blocked, statuses=statuses)
