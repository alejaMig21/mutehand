"""Flows stored in SQLite: a user layer (editable) over a read-only factory layer (templates)."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from workflow_factory.flow import Flow, Node

SCHEMA = "CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, definition TEXT NOT NULL)"


def _dump(flow: Flow) -> str:
    return json.dumps({"nodes": [asdict(node) for node in flow.nodes], "edges": flow.edges})


def _load(flow_id: str, raw: str) -> Flow:
    data = json.loads(raw)
    nodes = [Node(**{**n, "inputs": tuple(tuple(pair) for pair in n["inputs"])}) for n in data["nodes"]]
    edges = None if data["edges"] is None else [tuple(edge) for edge in data["edges"]]
    return Flow(nodes=nodes, id=flow_id, edges=edges)


def save_flow(db_path: Path, flow: Flow) -> None:
    if not flow.id:
        raise ValueError("a flow needs an id to be saved")
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        db.execute("INSERT OR REPLACE INTO flows VALUES (?, ?)", (flow.id, _dump(flow)))


def _read(db: sqlite3.Connection, flow_id: str) -> Flow | None:
    row = db.execute("SELECT definition FROM flows WHERE id = ?", (flow_id,)).fetchone()
    return _load(flow_id, row[0]) if row else None


def load_flow(user_db: Path, factory_db: Path | None, flow_id: str) -> Flow | None:
    """The user's flow first, then the factory template (opened read-only)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        found = _read(db, flow_id)
    if found or factory_db is None or not factory_db.exists():
        return found
    with closing(sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)) as db:
        return _read(db, flow_id)
