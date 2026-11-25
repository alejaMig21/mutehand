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
    factory_successes INTEGER NOT NULL DEFAULT 0,
    factory_failures INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (app, name)
)
"""
# local counters live in the user database, even for factory lessons (factory file is read-only)
STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS lesson_state (
    app TEXT NOT NULL,
    name TEXT NOT NULL,
    local_successes INTEGER NOT NULL DEFAULT 0,
    local_failures INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,  -- sticky: set at replay time, cleared only by restore_lesson
    restored INTEGER NOT NULL DEFAULT 0,  -- a human restored it: shipped counters no longer reject
    PRIMARY KEY (app, name)
)
"""
COLUMNS = (
    "app, version, name, precondition, action, role, control_name, automation_id,"
    " effect, origin, status, factory_successes, factory_failures"
)
PLACEHOLDERS = ", ".join("?" * (COLUMNS.count(",") + 1))
# Below REJECTED_BELOW a lesson is rejected; everything else that is not trusted is suspect.
TRUSTED_AT, REJECTED_BELOW, OWN_SUCCESSES_TO_TRUST = 0.80, 0.30, 2


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
    factory_successes: int = 0
    factory_failures: int = 0


def _row_to_lesson(row) -> Lesson:
    (app, version, name, precondition, action, role, control, automation_id, effect, origin,
     status, factory_successes, factory_failures) = row
    return Lesson(
        app=app, version=version, name=name, precondition=precondition, action=action,
        locator=Locator(role, control, automation_id), effect=effect,
        origin=Origin(origin), status=Status(status),
        factory_successes=factory_successes, factory_failures=factory_failures,
    )


def save_lesson(db_path: Path, lesson: Lesson) -> None:
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        loc = lesson.locator
        db.execute(
            f"INSERT OR REPLACE INTO lessons ({COLUMNS}) VALUES ({PLACEHOLDERS})",
            (lesson.app, lesson.version, lesson.name, lesson.precondition, lesson.action,
             loc.role, loc.name, loc.automation_id, lesson.effect, str(lesson.origin),
             str(lesson.status), lesson.factory_successes, lesson.factory_failures),
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


def confidence(successes: int, failures: int) -> float:
    """Failures weigh three times a success; the +1/+2 keeps untested lessons at 0.5."""
    return (successes + 1) / (successes + 3 * failures + 2)


def _state(db: sqlite3.Connection, lesson: Lesson) -> tuple[int, int, bool, bool]:
    row = db.execute(
        "SELECT local_successes, local_failures, rejected, restored FROM lesson_state"
        " WHERE app = ? AND name = ?",
        (lesson.app, lesson.name),
    ).fetchone()
    return row or (0, 0, False, False)


def _derive_status(lesson: Lesson, local_successes: int, local_failures: int) -> Status:
    successes = lesson.factory_successes + local_successes
    failures = lesson.factory_failures + local_failures
    score = confidence(successes, failures)
    if score < REJECTED_BELOW:
        return Status.REJECTED
    if score >= TRUSTED_AT and local_successes >= OWN_SUCCESSES_TO_TRUST and failures == 0:
        return Status.TRUSTED
    return Status.SUSPECT


def record_outcome(user_db: Path, lesson: Lesson, success: bool) -> Status:
    """Count one replay result and return the lesson's status afterwards."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(STATE_SCHEMA)
        db.execute("INSERT OR IGNORE INTO lesson_state (app, name) VALUES (?, ?)",
                   (lesson.app, lesson.name))
        column = "local_successes" if success else "local_failures"
        db.execute(f"UPDATE lesson_state SET {column} = {column} + 1 WHERE app = ? AND name = ?",
                   (lesson.app, lesson.name))
        successes, failures, _, _ = _state(db, lesson)
        derived = _derive_status(lesson, successes, failures)
        if derived == Status.REJECTED:
            db.execute("UPDATE lesson_state SET rejected = 1 WHERE app = ? AND name = ?",
                       (lesson.app, lesson.name))
        return derived


def current_status(user_db: Path, lesson: Lesson, app_version: str) -> Status:
    """What the apprentice may do with this lesson right now (rejection outranks revalidation)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(STATE_SCHEMA)
        successes, failures, rejected, restored = _state(db, lesson)
        derived = _derive_status(lesson, successes, failures)
    if rejected or (not restored and Status.REJECTED in (lesson.status, derived)):
        return Status.REJECTED
    if lesson.status == Status.TO_REVALIDATE or lesson.version != app_version:
        return Status.TO_REVALIDATE
    return Status.SUSPECT if derived == Status.REJECTED else derived  # restored by a human


def restore_lesson(user_db: Path, app: str, name: str) -> None:
    """Human action: forget local failures and lift a rejection. Nothing else restores a rejected lesson."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        db.execute(STATE_SCHEMA)
        db.execute("INSERT OR IGNORE INTO lesson_state (app, name) VALUES (?, ?)", (app, name))
        db.execute(
            "UPDATE lesson_state SET local_successes = 0, local_failures = 0, rejected = 0,"
            " restored = 1 WHERE app = ? AND name = ?",
            (app, name),
        )
        db.execute(
            "UPDATE lessons SET status = ? WHERE app = ? AND name = ? AND status = ?",
            (str(Status.SUSPECT), app, name, str(Status.REJECTED)),
        )
