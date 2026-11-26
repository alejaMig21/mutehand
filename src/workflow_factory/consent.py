"""Consent gate: a sensitive step runs only with a consent record for its app, control, action."""

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from workflow_factory.steps import Sensitivity, Step

# Safety net: a control named like an outward action needs consent even if nobody labelled the step.
OUTWARD_WORDS = ("send", "publish", "buy", "purchase", "pay", "post", "submit")

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


def effective_sensitivity(step: Step) -> Sensitivity | None:
    """The category that applies, whatever the step claims: labels come from teachers, files and factories."""
    if step.sensitive is not None:
        return step.sensitive
    if step.action == "type_secret":
        return Sensitivity.PASSWORD_FIELD
    if any(re.search(rf"\b{word}\b", step.locator.name.lower()) for word in OUTWARD_WORDS):
        return Sensitivity.OUTWARD_ACTION
    return None


def _reads_private_app(user_db: Path, step: Step) -> bool:
    """Reading what a private app shows needs consent like any sensitive action."""
    from workflow_factory.tutor import is_private  # tutor imports this module

    return step.action == "read_value" and is_private(user_db, step.app)


def scope_of(step: Step) -> Consent:
    locator = step.locator
    return Consent(step.app, locator.automation_id or locator.name, step.action)


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


def is_permitted(user_db: Path, step: Step) -> bool:
    """No consent record means blocked. Sensitivity is decided here, not trusted from the label."""
    if effective_sensitivity(step) is None and not _reads_private_app(user_db, step):
        return True
    scope = scope_of(step)
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        return db.execute(
            "SELECT 1 FROM consents WHERE app = ? AND control IN (?, '*') AND action = ?",
            (scope.app, scope.control, scope.action),
        ).fetchone() is not None
