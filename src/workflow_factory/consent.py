"""Consent gate: a sensitive lesson runs only with a consent record for its app, control, action."""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from workflow_factory.lessons import Lesson

SCHEMA = """
CREATE TABLE IF NOT EXISTS consents (
    app TEXT NOT NULL,
    control TEXT NOT NULL,
    action TEXT NOT NULL,
    PRIMARY KEY (app, control, action)
)
"""


@dataclass(frozen=True)
class Consent:
    app: str
    control: str  # a control id/name, or "*" for any control of the app
    action: str


def scope_of(lesson: Lesson) -> Consent:
    locator = lesson.locator
    return Consent(lesson.app, locator.automation_id or locator.name, lesson.action)


def grant_consent(user_db: Path, app: str, control: str, action: str) -> None:
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        db.execute("INSERT OR IGNORE INTO consents VALUES (?, ?, ?)", (app, control, action))


def revoke_consent(user_db: Path, app: str, control: str, action: str) -> bool:
    """True if a consent was revoked, False if there was none to revoke."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        return db.execute(
            "DELETE FROM consents WHERE app = ? AND control = ? AND action = ?",
            (app, control, action),
        ).rowcount > 0


def consents(user_db: Path) -> list[Consent]:
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        return [Consent(*row) for row in db.execute("SELECT app, control, action FROM consents")]


def is_permitted(user_db: Path, lesson: Lesson) -> bool:
    """No consent record means blocked. Typing a secret is always sensitive, label or not."""
    if lesson.sensitive is None and lesson.action != "type_secret":
        return True
    scope = scope_of(lesson)
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        return db.execute(
            "SELECT 1 FROM consents WHERE app = ? AND control IN (?, '*') AND action = ?",
            (scope.app, scope.control, scope.action),
        ).fetchone() is not None
