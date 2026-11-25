"""Flows stored in SQLite: a user layer (editable) over a read-only factory layer (templates)."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from workflow_factory.flow import Flow, Node

SCHEMA = "CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, definition TEXT NOT NULL)"


def flow_to_dict(flow: Flow) -> dict:
    return {"id": flow.id, "nodes": [asdict(node) for node in flow.nodes], "edges": flow.edges}


def flow_from_dict(flow_id: str, data: dict) -> Flow:
    """Build a flow from editor JSON; raises ValueError/TypeError/KeyError when it is not valid."""
    nodes = [Node(**{**n, "inputs": tuple(tuple(pair) for pair in n.get("inputs", []))}) for n in data["nodes"]]
    edges = data.get("edges")
    return Flow(nodes=nodes, id=flow_id, edges=None if edges is None else [tuple(edge) for edge in edges])


def _dump(flow: Flow) -> str:
    return json.dumps(flow_to_dict(flow))


def _load(flow_id: str, raw: str) -> Flow:
    return flow_from_dict(flow_id, json.loads(raw))


def save_flow(db_path: Path, flow: Flow) -> None:
    if not flow.id:
        raise ValueError("a flow needs an id to be saved")
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        db.execute("INSERT OR REPLACE INTO flows VALUES (?, ?)", (flow.id, _dump(flow)))


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _read(db: sqlite3.Connection, flow_id: str) -> Flow | None:
    if not _has_table(db, "flows"):  # e.g. a factory file that only ships lessons
        return None
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


def list_flows(user_db: Path, factory_db: Path | None) -> list[dict]:
    """Ids of the user's flows and of the factory templates they do not shadow."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        listing = {row[0]: "local" for row in db.execute("SELECT id FROM flows")}
    if factory_db is not None and factory_db.exists():
        with closing(sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)) as db:
            if _has_table(db, "flows"):
                for (flow_id,) in db.execute("SELECT id FROM flows"):
                    listing.setdefault(flow_id, "factory")
    return [{"id": flow_id, "origin": origin} for flow_id, origin in sorted(listing.items())]
