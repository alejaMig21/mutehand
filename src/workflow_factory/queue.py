"""Tutor queue (doubts the apprentice leaves) and flow checkpoints, in the user database."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Reason(StrEnum):
    """Why the apprentice stopped: a closed list so doubts are triaged consistently."""

    PRECONDITION_NOT_MET = "precondition_not_met"
    CONTROL_NOT_FOUND = "control_not_found"
    NO_CONSENT = "no_consent"
    TEMPLATE_NO_MATCH = "template_no_match"


_REASONS = ", ".join(f"'{reason.value}'" for reason in Reason)
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS doubts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    lesson TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ({_REASONS})),
    capture TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'answered', 'dismissed'))
);
CREATE TABLE IF NOT EXISTS checkpoints (
    flow_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,  -- JSON: done nodes, effects, loop progress, run context
    definition TEXT NOT NULL  -- the flow when saved: an edited flow is not resumed
);
"""


@dataclass(frozen=True)
class Doubt:
    id: int
    flow_id: str
    node_id: str
    lesson: str
    reason: Reason
    capture: dict[str, int]  # roles and counts only, never text
    status: str


def _connect(user_db: Path) -> sqlite3.Connection:
    db = sqlite3.connect(user_db)
    db.executescript(SCHEMA)
    return db


def record_doubt(user_db: Path, flow_id: str, node_id: str, lesson: str,
                 reason: Reason, capture: dict[str, int]) -> int:
    with closing(_connect(user_db)) as db, db:
        cursor = db.execute(
            "INSERT INTO doubts (flow_id, node_id, lesson, reason, capture) VALUES (?, ?, ?, ?, ?)",
            (flow_id, node_id, lesson, str(reason), json.dumps(capture)),
        )
        return cursor.lastrowid


def list_doubts(user_db: Path, status: str | None = None) -> list[Doubt]:
    query = "SELECT id, flow_id, node_id, lesson, reason, capture, status FROM doubts"
    args = ()
    if status:
        query, args = query + " WHERE status = ?", (status,)
    with closing(_connect(user_db)) as db:
        return [Doubt(i, f, n, lesson, Reason(r), json.loads(c), s)
                for i, f, n, lesson, r, c, s in db.execute(query + " ORDER BY id", args)]


def _close_doubt(user_db: Path, doubt_id: int, new_status: str) -> None:
    with closing(_connect(user_db)) as db, db:
        changed = db.execute("UPDATE doubts SET status = ? WHERE id = ? AND status = 'open'",
                             (new_status, doubt_id)).rowcount
    if not changed:
        raise ValueError(f"doubt {doubt_id} is not open")


def answer_doubt(user_db: Path, doubt_id: int) -> None:
    _close_doubt(user_db, doubt_id, "answered")


def dismiss_doubt(user_db: Path, doubt_id: int) -> None:
    """Abandon the stopped run: its checkpoint goes, so the flow starts over next time."""
    _close_doubt(user_db, doubt_id, "dismissed")
    with closing(_connect(user_db)) as db, db:
        db.execute("DELETE FROM checkpoints WHERE flow_id = (SELECT flow_id FROM doubts WHERE id = ?)",
                   (doubt_id,))


def has_open_doubt(user_db: Path, flow_id: str) -> bool:
    with closing(_connect(user_db)) as db:
        return db.execute("SELECT 1 FROM doubts WHERE flow_id = ? AND status = 'open'",
                          (flow_id,)).fetchone() is not None


def save_checkpoint(user_db: Path, flow_id: str, state: dict, definition: str) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?)",
                   (flow_id, json.dumps(state), definition))


def load_checkpoint(user_db: Path, flow_id: str, definition: str) -> dict | None:
    """Saved state, only when the flow still has the definition it was saved with."""
    with closing(_connect(user_db)) as db:
        row = db.execute("SELECT state, definition FROM checkpoints WHERE flow_id = ?",
                         (flow_id,)).fetchone()
    return json.loads(row[0]) if row and row[1] == definition else None


def clear_checkpoint(user_db: Path, flow_id: str) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("DELETE FROM checkpoints WHERE flow_id = ?", (flow_id,))
