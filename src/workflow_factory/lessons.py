"""Lesson store: one table per SQLite file (user knowledge, factory knowledge)."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
    app TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    precondition TEXT NOT NULL,
    action TEXT NOT NULL,
    role TEXT NOT NULL,
    control_name TEXT NOT NULL,
    automation_id TEXT,
    effect TEXT NOT NULL,
    origin TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (app, name)
)
"""
COLUMNS = (
    "app, version, name, precondition, action, role, control_name, automation_id,"
    " effect, origin, status"
)


class Status(StrEnum):
    TRUSTED = "trusted"
    SUSPECT = "suspect"
    REJECTED = "rejected"
    TO_REVALIDATE = "to_revalidate"


class Origin(StrEnum):
    FACTORY = "factory"
    LOCAL = "local"


@dataclass(frozen=True)
class Locator:
    role: str
    name: str
    automation_id: str | None = None


@dataclass(frozen=True)
class Lesson:
    app: str
    version: str
    name: str
    locator: Locator
    precondition: str = ""
    action: str = "click"
    effect: str = ""
    origin: Origin = Origin.LOCAL
    status: Status = Status.SUSPECT


def _row_to_lesson(row) -> Lesson:
    app, version, name, precondition, action, role, control, automation_id, effect, origin, status = row
    return Lesson(
        app=app, version=version, name=name, precondition=precondition, action=action,
        locator=Locator(role, control, automation_id), effect=effect,
        origin=Origin(origin), status=Status(status),
    )


def save_lesson(db_path: Path, lesson: Lesson) -> None:
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        loc = lesson.locator
        db.execute(
            f"INSERT OR REPLACE INTO lessons ({COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (lesson.app, lesson.version, lesson.name, lesson.precondition, lesson.action,
             loc.role, loc.name, loc.automation_id, lesson.effect, str(lesson.origin),
             str(lesson.status)),
        )


def _find_in(db: sqlite3.Connection, app: str, name: str) -> Lesson | None:
    row = db.execute(
        f"SELECT {COLUMNS} FROM lessons WHERE app = ? AND name = ?", (app, name)
    ).fetchone()
    return _row_to_lesson(row) if row else None


def find_lesson(user_db: Path, factory_db: Path | None, app: str, name: str) -> Lesson | None:
    """User knowledge first, then factory knowledge (opened read-only)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        found = _find_in(db, app, name)
    if found or factory_db is None or not factory_db.exists():
        return found
    with closing(sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)) as db:
        return _find_in(db, app, name)


def revalidate_changed_versions(user_db: Path, app: str, current_version: str) -> None:
    """A version change keeps every lesson of the app but stops trusting it.

    Rejected lessons stay rejected: only a human restores those."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        db.execute(
            "UPDATE lessons SET status = ? WHERE app = ? AND version != ? AND status != ?",
            (str(Status.TO_REVALIDATE), app, current_version, str(Status.REJECTED)),
        )
