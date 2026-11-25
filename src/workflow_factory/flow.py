"""Run a flow through the desktop port and store each node's measured effect."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from workflow_factory.desktop import Desktop

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


@dataclass(frozen=True)
class Locator:
    role: str
    name: str
    automation_id: str | None = None


@dataclass(frozen=True)
class Node:
    id: str
    locator: Locator


@dataclass(frozen=True)
class Flow:
    nodes: list[Node]


@dataclass(frozen=True)
class RunResult:
    effects: dict[str, Effect]


def run_flow(flow: Flow, desktop: Desktop, user_db: Path) -> RunResult:
    effects = {}
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        for node in flow.nodes:
            loc = node.locator
            control = desktop.find(loc.role, loc.name, loc.automation_id)
            if control is None:
                raise ControlNotFound(f"{loc.role} {loc.name!r}")
            before = set(desktop.snapshot())
            desktop.click(control)
            after = set(desktop.snapshot())
            if after - before:
                effect = Effect.REVEALED
            elif before - after:
                effect = Effect.CLOSED_DIALOG
            else:
                effect = Effect.NO_CHANGE
            effects[node.id] = effect
            db.execute(
                "INSERT INTO node_results VALUES (?, ?, ?)", (node.id, effect.value, desktop.now())
            )
    return RunResult(effects=effects)
