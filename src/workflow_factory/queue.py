"""Tutor queue (doubts the apprentice leaves) and flow checkpoints, in the user database."""

import ctypes
import json
import os
import sqlite3
from contextlib import closing
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from workflow_factory.legacy import add_text_column, migrate_names


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
    step TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ({_REASONS})),
    capture TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'answered', 'dismissed')),
    note TEXT,  -- what the person wrote when answering, if anything
    detail TEXT,  -- the exact cause behind the triage reason, as the run history names it
    technology TEXT  -- the program the node acts on (a step node), as its steps are stored
);
CREATE TABLE IF NOT EXISTS run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    stopped_node TEXT
);
CREATE TABLE IF NOT EXISTS run_nodes (  -- what each node did: never any data value
    run_id INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- done | blocked | skipped
    reason TEXT,
    effect TEXT,
    step TEXT,  -- the step it ran, so the history still reads after the flow changes
    kind TEXT,  -- what kind of box it was (and, for a data box, its op): node ids are reused when a flow is rebuilt
    op TEXT
);
CREATE INDEX IF NOT EXISTS run_nodes_by_run ON run_nodes (run_id);
CREATE TABLE IF NOT EXISTS run_locks (  -- which process is running a flow right now
    flow_id TEXT PRIMARY KEY,
    pid INTEGER NOT NULL
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
    step: str
    reason: Reason
    capture: dict[str, int]  # roles and counts only, never text
    status: str
    note: str | None = None
    detail: str | None = None
    closed_as: str | None = None  # "tried_again" when the person closed it by trying again; None for the tutor's answer
    technology: str | None = None  # the program the node of a step acts on; None for any other node


def _connect(user_db: Path) -> sqlite3.Connection:
    db = sqlite3.connect(user_db)
    migrate_names(db)
    db.executescript(SCHEMA)
    for column in ("step", "kind", "op"):
        add_text_column(db, "run_nodes", column)
    add_text_column(db, "doubts", "detail")
    add_text_column(db, "doubts", "closed_as")
    add_text_column(db, "doubts", "technology")
    return db


def record_doubt(user_db: Path, flow_id: str, node_id: str, step: str,
                 reason: Reason, capture: dict[str, int], detail: str | None = None,
                 technology: str | None = None) -> int:
    with closing(_connect(user_db)) as db, db:
        cursor = db.execute(
            "INSERT INTO doubts (flow_id, node_id, step, reason, capture, detail, technology) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (flow_id, node_id, step, str(reason), json.dumps(capture), detail, technology),
        )
        return cursor.lastrowid


def list_doubts(user_db: Path, status: str | None = None) -> list[Doubt]:
    query = "SELECT id, flow_id, node_id, step, reason, capture, status, note, detail, closed_as, technology FROM doubts"
    args = ()
    if status:
        query, args = query + " WHERE status = ?", (status,)
    with closing(_connect(user_db)) as db:
        return [Doubt(i, f, n, step, Reason(r), json.loads(c), s, note, detail, closed_as, technology)
                for i, f, n, step, r, c, s, note, detail, closed_as, technology in db.execute(query + " ORDER BY id", args)]


def _close_doubt(user_db: Path, doubt_id: int, new_status: str, note: str | None = None) -> None:
    with closing(_connect(user_db)) as db, db:
        # a note the person left earlier stays unless this closing brings another
        changed = db.execute("UPDATE doubts SET status = ?, note = COALESCE(?, note) WHERE id = ? AND status = 'open'",
                             (new_status, note, doubt_id)).rowcount
    if not changed:
        raise ValueError(f"doubt {doubt_id} is not open")


def answer_doubt(user_db: Path, doubt_id: int, note: str | None = None) -> None:
    _close_doubt(user_db, doubt_id, "answered", note)


def dismiss_doubt(user_db: Path, doubt_id: int) -> None:
    """Abandon the stopped run: its checkpoint goes, so the flow starts over next time."""
    _close_doubt(user_db, doubt_id, "dismissed")
    with closing(_connect(user_db)) as db, db:
        db.execute("DELETE FROM checkpoints WHERE flow_id = (SELECT flow_id FROM doubts WHERE id = ?)",
                   (doubt_id,))


def leave_note(user_db: Path, doubt_id: int, note: str) -> None:
    """The person's own words on an open doubt, for whoever answers it. The doubt stays open."""
    with closing(_connect(user_db)) as db, db:
        changed = db.execute("UPDATE doubts SET note = ? WHERE id = ? AND status = 'open'", (note or None, doubt_id)).rowcount
    if not changed:
        raise ValueError(f"doubt {doubt_id} is not open")


def close_as_tried_again(user_db: Path, flow_id: str) -> int:
    """The person tried the flow again: every open doubt of it closes (parallel branches may have left several) and the
    checkpoint stays, so the run goes on from where it stopped. How many were closed."""
    with closing(_connect(user_db)) as db, db:
        return db.execute("UPDATE doubts SET status = 'answered', closed_as = 'tried_again' WHERE flow_id = ? AND status = 'open'",
                          (flow_id,)).rowcount


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


def record_run(user_db: Path, flow_id: str, started_at: str, finished_at: str, status: str,
               stopped_node: str | None, nodes: list[dict], keep: int = 500) -> int:
    with closing(_connect(user_db)) as db, db:
        run_id = db.execute(
            "INSERT INTO run_history (flow_id, started_at, finished_at, status, stopped_node)"
            " VALUES (?, ?, ?, ?, ?)", (flow_id, started_at, finished_at, status, stopped_node)).lastrowid
        db.executemany(
            "INSERT INTO run_nodes (run_id, node_id, status, reason, effect, step, kind, op) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(run_id, n["node_id"], n["status"], n.get("reason"), n.get("effect"), n.get("step"), n.get("kind"), n.get("op"))
             for n in nodes])
        old = "SELECT id FROM run_history ORDER BY id DESC LIMIT -1 OFFSET ?"  # everything after the newest `keep`
        db.execute(f"DELETE FROM run_nodes WHERE run_id IN ({old})", (keep,))
        db.execute(f"DELETE FROM run_history WHERE id IN ({old})", (keep,))
        return run_id


def list_runs(user_db: Path, flow_id: str | None = None, limit: int = 50) -> list[dict]:
    """Recent runs, newest first, with what each node did and why it stopped."""
    query = "SELECT id, flow_id, started_at, finished_at, status, stopped_node FROM run_history"
    args: tuple = ()
    if flow_id:
        query, args = query + " WHERE flow_id = ?", (flow_id,)
    with closing(_connect(user_db)) as db:
        runs = [dict(zip(("id", "flow_id", "started_at", "finished_at", "status", "stopped_node"), row, strict=True))
                for row in db.execute(query + " ORDER BY id DESC LIMIT ?", (*args, limit))]
        for run in runs:
            run["nodes"] = [
                {"node_id": n, "status": o, "reason": r, "effect": e, "step": s, "kind": k, "op": p}
                for n, o, r, e, s, k, p in db.execute(
                    "SELECT node_id, status, reason, effect, step, kind, op FROM run_nodes WHERE run_id = ? ORDER BY rowid",
                    (run["id"],))]
    return runs


def last_runs(user_db: Path) -> dict[str, dict]:
    """{flow id: {"status", "at"}} of the newest recorded run of each flow."""
    with closing(_connect(user_db)) as db:
        # ponytail: only the runs `record_run` keeps (the newest 500): a flow idle for longer reads as never run
        return {flow_id: {"status": status, "at": at} for flow_id, status, at in db.execute(
            "SELECT flow_id, status, finished_at FROM run_history WHERE id IN (SELECT MAX(id) FROM run_history GROUP BY flow_id)")}


def _pid_alive(pid: int) -> bool:
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


def acquire_run_lock(user_db: Path, flow_id: str, pid: int | None = None) -> bool:
    """Claim the right to run a flow. False while another live run holds it; a dead process's claim is ignored."""
    pid = pid or os.getpid()
    with closing(_connect(user_db)) as db:
        db.isolation_level = None  # manual transaction: check and claim must be one step
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute("SELECT pid FROM run_locks WHERE flow_id = ?", (flow_id,)).fetchone()
            if row and _pid_alive(row[0]):
                db.execute("ROLLBACK")
                return False
            db.execute("INSERT OR REPLACE INTO run_locks VALUES (?, ?)", (flow_id, pid))
            db.execute("COMMIT")
            return True
        except Exception:
            db.execute("ROLLBACK")
            raise


def locked_flows(user_db: Path) -> list[str]:
    """The flows a live process is running right now: this editor's runs and a scheduled one's alike."""
    with closing(_connect(user_db)) as db:
        return [flow_id for flow_id, pid in db.execute("SELECT flow_id, pid FROM run_locks") if _pid_alive(pid)]


def release_run_lock(user_db: Path, flow_id: str, pid: int | None = None) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("DELETE FROM run_locks WHERE flow_id = ? AND pid = ?", (flow_id, pid or os.getpid()))
