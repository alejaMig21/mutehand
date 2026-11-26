"""Flows stored in SQLite: a user layer (editable) over a read-only factory layer (templates)."""

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict
from functools import cache
from pathlib import Path

from workflow_factory.flow import Flow, Node
from workflow_factory.legacy import upgrade_node
from workflow_factory.steps import Step, list_steps

SCHEMA = "CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, definition TEXT NOT NULL)"
# where the editor drew each node: kept apart so moving a card never changes the definition a checkpoint belongs to.
# These are the places of the top-to-bottom canvas; the `flow_layout` table of the left-to-right one is no longer read.
LAYOUT_SCHEMA = "CREATE TABLE IF NOT EXISTS flow_positions (id TEXT PRIMARY KEY, positions TEXT NOT NULL)"
# what the person calls a flow and the app it runs on: kept apart too, so a rename never drops a checkpoint
INFO_SCHEMA = "CREATE TABLE IF NOT EXISTS flow_info (id TEXT PRIMARY KEY, title TEXT, app TEXT)"
MAX_TITLE_CHARS = 100
MAX_APP_CHARS = 100
MAX_NEW_ID_CHARS = 50  # an identifier goes into the command of a Windows task, which has little room


def flow_to_dict(flow: Flow) -> dict:
    return {"id": flow.id, "nodes": [asdict(node) for node in flow.nodes], "edges": flow.edges}


def flow_from_dict(flow_id: str, data: dict) -> Flow:
    """Build a flow from editor JSON; raises ValueError/TypeError/KeyError when it is not valid."""
    nodes = [Node(**{**upgrade_node(n), "inputs": tuple(tuple(pair) for pair in n.get("inputs", []))}) for n in data["nodes"]]
    edges = data.get("edges")
    return Flow(nodes=nodes, id=flow_id, edges=None if edges is None else [tuple(edge) for edge in edges])


def _dump(flow: Flow) -> str:
    return json.dumps(flow_to_dict(flow))


def _load(flow_id: str, raw: str) -> Flow:
    return flow_from_dict(flow_id, json.loads(raw))


def _unprintable(text: str) -> bool:
    return any(unicodedata.category(c) in ("Cc", "Cs") for c in text)  # control characters and lone surrogates


def check_title(title) -> str:
    """Any words the person likes, on one line; ValueError for anything that cannot be shown."""
    words = " ".join(title.split()) if isinstance(title, str) else ""
    if not words or len(words) > MAX_TITLE_CHARS or _unprintable(words):
        raise ValueError(f"A flow name needs 1 to {MAX_TITLE_CHARS} characters of text.")
    return words


def check_app(app) -> str:
    if not isinstance(app, str) or len(app) > MAX_APP_CHARS or _unprintable(app):
        raise ValueError(f"The app name must be text of at most {MAX_APP_CHARS} characters.")
    return app.strip()


def new_flow_id(title: str, taken: list[str]) -> str:
    """A short identifier made from the title, unlike every taken one even ignoring case (Windows task names do)."""
    words = "-".join(re.findall(r"\w+", unicodedata.normalize("NFC", title).lower()))
    base = words[:MAX_NEW_ID_CHARS - 5].strip("-") or "flow"
    used = {flow_id.casefold() for flow_id in taken}
    new, n = base, 2
    while new.casefold() in used:
        new, n = f"{base}-{n}", n + 1
    return new


def save_flow(db_path: Path, flow: Flow, title: str | None = None, app: str | None = None) -> None:
    """Store a flow. A title or app left as None keeps the stored one."""
    if not flow.id:
        raise ValueError("a flow needs an id to be saved")
    title = None if title is None else check_title(title)
    app = None if app is None else check_app(app)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        db.execute(INFO_SCHEMA)
        db.execute("INSERT OR REPLACE INTO flows VALUES (?, ?)", (flow.id, _dump(flow)))
        db.execute("INSERT INTO flow_info (id, title, app) VALUES (?, ?, ?) ON CONFLICT (id) DO UPDATE SET "
                   "title = COALESCE(excluded.title, title), app = COALESCE(excluded.app, app)", (flow.id, title, app))


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _read(db: sqlite3.Connection, flow_id: str) -> Flow | None:
    if not _has_table(db, "flows"):  # e.g. a factory file that only ships steps
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
    with closing(_read_only(factory_db)) as db:
        return _read(db, flow_id)


def _read_only(factory_db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)


def check_positions(positions) -> dict:
    """{node id: {"x": number, "y": number}}; ValueError for anything else."""
    if not isinstance(positions, dict) or not all(
            isinstance(p, dict) and set(p) == {"x", "y"} and all(type(v) in (int, float) for v in p.values())
            for p in positions.values()):
        raise ValueError("positions are {node id: {x, y}} with numbers")
    return positions


def save_layout(db_path: Path, flow_id: str, positions: dict) -> None:
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(LAYOUT_SCHEMA)
        db.execute("INSERT OR REPLACE INTO flow_positions VALUES (?, ?)", (flow_id, json.dumps(check_positions(positions))))


def load_layout(db_path: Path, flow_id: str) -> dict:
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(LAYOUT_SCHEMA)
        row = db.execute("SELECT positions FROM flow_positions WHERE id = ?", (flow_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def list_flows(user_db: Path, factory_db: Path | None) -> list[dict]:
    """Ids of the user's flows and of the factory templates they do not shadow."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        listing = {row[0]: "local" for row in db.execute("SELECT id FROM flows")}
    if factory_db is not None and factory_db.exists():
        with closing(_read_only(factory_db)) as db:
            if _has_table(db, "flows"):
                for (flow_id,) in db.execute("SELECT id FROM flows"):
                    listing.setdefault(flow_id, "factory")
    return [{"id": flow_id, "origin": origin} for flow_id, origin in sorted(listing.items())]


def _info_rows(db: sqlite3.Connection) -> dict:
    if not _has_table(db, "flow_info"):
        return {}
    return {flow_id: {key: value for key, value in (("title", title), ("app", app)) if value}
            for flow_id, title, app in db.execute("SELECT id, title, app FROM flow_info")}


def stored_info(user_db: Path, factory_db: Path | None) -> dict[str, dict]:
    """{flow id: {"title", "app"}}, holding only what was stored; the user's words over the factory's."""
    found = {}
    if factory_db is not None and factory_db.exists():
        with closing(_read_only(factory_db)) as db:
            found = _info_rows(db)
    with closing(sqlite3.connect(user_db)) as db:
        for flow_id, info in _info_rows(db).items():
            found[flow_id] = {**found.get(flow_id, {}), **info}
    return found


def guess_app(flow: Flow, steps: list[Step]) -> str:
    """The app that has the most of the flow's steps (the first met on a tie); '' when none is known."""
    apps = Counter(step.app for node in flow.nodes for step in steps if step.name == node.step)
    return apps.most_common(1)[0][0] if apps else ""


def describe_flow(flow_id: str, info: dict, flow: Callable[[], Flow], steps: Callable[[], list[Step]]) -> dict:
    """What the screen calls a flow. One stored before titles takes its identifier and the app of its steps."""
    app = info.get("app")
    if not app:
        try:
            app = guess_app(flow(), steps())
        except (ValueError, TypeError, KeyError):  # a definition that cannot be read must not hide the other flows
            app = ""
    return {"title": info.get("title") or flow_id, "app": app}


def flow_summaries(user_db: Path, factory_db: Path | None) -> list[dict]:
    """`list_flows` with each flow's title and app."""
    info = stored_info(user_db, factory_db)
    steps = cache(lambda: list_steps(user_db, factory_db))  # read once, and only for a flow with no app stored
    return [{**entry, **describe_flow(entry["id"], info.get(entry["id"], {}),
                                      lambda i=entry["id"]: load_flow(user_db, factory_db, i), steps)}
            for entry in list_flows(user_db, factory_db)]
