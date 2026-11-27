"""Flows stored in SQLite: a user layer (editable) over a read-only factory layer (templates)."""

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from contextlib import closing
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from workflow_factory.data import expressions
from workflow_factory.desktop import plain_app
from workflow_factory.flow import Flow, Node
from workflow_factory.legacy import add_text_column, upgrade_node
from workflow_factory.queue import last_runs, list_doubts
from workflow_factory.steps import Origin, Status, Step, list_steps, seen_versions, step_reports

SCHEMA = "CREATE TABLE IF NOT EXISTS flows (id TEXT PRIMARY KEY, definition TEXT NOT NULL)"
# where the editor drew each node: kept apart so moving a card never changes the definition a checkpoint belongs to.
LAYOUT_SCHEMA = "CREATE TABLE IF NOT EXISTS flow_positions (id TEXT PRIMARY KEY, positions TEXT NOT NULL)"
# what the person calls a flow: kept apart too, so a rename never drops a checkpoint. `app` is what a flow saved before nodes
# recorded their technology kept: it is only read, to give those nodes their technology, and cleared by the next save.
INFO_SCHEMA = "CREATE TABLE IF NOT EXISTS flow_info (id TEXT PRIMARY KEY, title TEXT, app TEXT)"
# a deleted flow waits here until it is undone: its words, places and daily runs, so that undo gives back all of them.
# ponytail: kept for good, and its identifier stays taken so a new flow never inherits the old history; purge by age if it grows.
TRASH_SCHEMA = ("CREATE TABLE IF NOT EXISTS flow_trash (id TEXT PRIMARY KEY, definition TEXT NOT NULL, positions TEXT, "
                "title TEXT, app TEXT, schedules TEXT NOT NULL, deleted_at TEXT)")
UNDO_WINDOW = timedelta(minutes=10)  # how long after a delete Home offers Undo again, e.g. after a reload
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


def save_flow(db_path: Path, flow: Flow, title: str | None = None) -> None:
    """Store a flow. A title left as None keeps the stored one."""
    if not flow.id:
        raise ValueError("a flow needs an id to be saved")
    title = None if title is None else check_title(title)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute(SCHEMA)
        db.execute(INFO_SCHEMA)
        db.execute("INSERT OR REPLACE INTO flows VALUES (?, ?)", (flow.id, _dump(flow)))
        db.execute("INSERT INTO flow_info (id, title) VALUES (?, ?) ON CONFLICT (id) DO UPDATE SET "
                   "title = COALESCE(excluded.title, title), app = NULL", (flow.id, title))


def set_title(user_db: Path, flow_id: str, title: str) -> None:
    """Rename: the title alone, so nothing a checkpoint or the history belongs to moves."""
    title = check_title(title)
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(INFO_SCHEMA)
        db.execute("INSERT INTO flow_info (id, title) VALUES (?, ?) ON CONFLICT (id) DO UPDATE SET title = excluded.title",
                   (flow_id, title))


def _trash_tables(db: sqlite3.Connection) -> None:
    for schema in (SCHEMA, LAYOUT_SCHEMA, INFO_SCHEMA, TRASH_SCHEMA):
        db.execute(schema)
    add_text_column(db, "flow_trash", "deleted_at")  # a trash made before deletions were dated


def trash_flow(user_db: Path, flow_id: str, schedules: list[dict]) -> bool:
    """Take the user's copy of a flow out of use, keeping all of it (and `schedules`, its daily runs) for `restore_flow`.
    False when the user has no such flow. A factory flow it shadowed shows again."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _trash_tables(db)
        row = db.execute("SELECT definition FROM flows WHERE id = ?", (flow_id,)).fetchone()
        if row is None:
            return False
        positions = db.execute("SELECT positions FROM flow_positions WHERE id = ?", (flow_id,)).fetchone()
        info = db.execute("SELECT title, app FROM flow_info WHERE id = ?", (flow_id,)).fetchone() or (None, None)
        db.execute("INSERT OR REPLACE INTO flow_trash VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (flow_id, row[0], positions and positions[0], *info, json.dumps(schedules), datetime.now(UTC).isoformat()))
        for table in ("flows", "flow_positions", "flow_info"):
            db.execute(f"DELETE FROM {table} WHERE id = ?", (flow_id,))
    return True


def restore_flow(user_db: Path, flow_id: str) -> list[dict] | None:
    """Undo `trash_flow`; the daily runs it kept, or None when nothing was deleted under that identifier."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _trash_tables(db)
        row = db.execute("SELECT definition, positions, title, app, schedules FROM flow_trash WHERE id = ?",
                         (flow_id,)).fetchone()
        if row is None:
            return None
        definition, positions, title, app, schedules = row
        db.execute("INSERT OR REPLACE INTO flows VALUES (?, ?)", (flow_id, definition))
        if positions is not None:
            db.execute("INSERT OR REPLACE INTO flow_positions VALUES (?, ?)", (flow_id, positions))
        db.execute("INSERT OR REPLACE INTO flow_info VALUES (?, ?, ?)", (flow_id, title, app))
        db.execute("DELETE FROM flow_trash WHERE id = ?", (flow_id,))
    return json.loads(schedules)


def trashed_ids(user_db: Path) -> list[str]:
    with closing(sqlite3.connect(user_db)) as db:
        return [row[0] for row in db.execute("SELECT id FROM flow_trash")] if _has_table(db, "flow_trash") else []


def recently_trashed(user_db: Path, now: datetime | None = None) -> list[dict]:
    """The flows deleted within the undo window, newest first: {id, title, daily_runs}. What was deleted earlier stays
    restorable but is no longer offered."""
    since = ((now or datetime.now(UTC)) - UNDO_WINDOW).isoformat()
    with closing(sqlite3.connect(user_db)) as db:
        if not _has_table(db, "flow_trash") or not any(c[1] == "deleted_at" for c in db.execute("PRAGMA table_info(flow_trash)")):
            return []
        rows = db.execute("SELECT id, title, schedules FROM flow_trash WHERE deleted_at >= ? ORDER BY deleted_at DESC", (since,))
        return [{"id": id_, "title": title or id_, "daily_runs": len(json.loads(tasks))} for id_, title, tasks in rows]


def _has_table(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _read(db: sqlite3.Connection, flow_id: str) -> tuple[Flow, str] | None:
    """(the flow, the app it was saved with before nodes recorded a technology: "" when none), or None."""
    if not _has_table(db, "flows"):  # e.g. a factory file that only ships steps
        return None
    row = db.execute("SELECT definition FROM flows WHERE id = ?", (flow_id,)).fetchone()
    if row is None:
        return None
    old = db.execute("SELECT app FROM flow_info WHERE id = ?", (flow_id,)).fetchone() if _has_table(db, "flow_info") else None
    return _load(flow_id, row[0]), (old and old[0]) or ""


def load_flow(user_db: Path, factory_db: Path | None, flow_id: str) -> Flow | None:
    """The user's flow first, then the factory template (opened read-only). A step node saved without a technology takes
    the app its flow was saved with, else the app that has the flow's steps: the next save keeps it on the node."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SCHEMA)
        found = _read(db, flow_id)
    if found is None and factory_db is not None and factory_db.exists():
        with closing(_read_only(factory_db)) as db:
            found = _read(db, flow_id)
    return found and _with_technologies(*found, user_db, factory_db)


def with_technology(flow: Flow, technology: str) -> Flow:
    """The flow with `technology` on every step node that names none."""
    return replace(flow, nodes=[replace(node, technology=technology) if node.kind in ("step", "loop") and not node.technology
                                else node for node in flow.nodes])


def _with_technologies(flow: Flow, old_app: str, user_db: Path, factory_db: Path | None) -> Flow:
    if all(node.technology for node in flow.nodes if node.kind in ("step", "loop")):
        return flow
    steps = list_steps(user_db, factory_db)
    return with_technology(flow, taught_app(old_app, steps) if old_app else guess_app(flow, steps))


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
    return {flow_id: {"title": title} if title else {} for flow_id, title in db.execute("SELECT id, title FROM flow_info")}


def stored_info(user_db: Path, factory_db: Path | None) -> dict[str, dict]:
    """{flow id: {"title"}}, holding only what was stored; the user's words over the factory's."""
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


def flow_summaries(user_db: Path, factory_db: Path | None) -> list[dict]:
    """`list_flows` with each flow's title: the person's words, else its identifier."""
    info = stored_info(user_db, factory_db)
    return [{**entry, "title": info.get(entry["id"], {}).get("title") or entry["id"]}
            for entry in list_flows(user_db, factory_db)]


def taught_app(app: str, steps: list[Step]) -> str:
    """The app as the taught steps spell it, so a run finds them: 'Paint' is paint.exe. Else as it was given."""
    known = sorted({step.app for step in steps})
    return app if app in known else next((name for name in known if plain_app(name) == plain_app(app)), app)


def _older(version: str, than: str) -> bool:
    return [int(n) for n in re.findall(r"\d+", version)] < [int(n) for n in re.findall(r"\d+", than)]


def _why_not(flow: Flow, learned: dict, seen: dict, waiting: bool) -> dict | None:
    """The first thing a run of `flow` would refuse or stop on, as {"why": code, "steps": [names], "by_technology":
    {technology: [names]}}, or None.

    `learned` is {(technology, step name): (step, state)}; `seen` the newest version of each app a run has met."""
    pairs = list(dict.fromkeys((node.technology, node.step) for node in flow.nodes if node.kind in ("step", "loop")))
    known = {pair: learned[pair] for pair in pairs if pair in learned}
    # A step taught again since the last run is newer than what was seen: only the mark a run left on it, or (for factory
    # knowledge, which holds no mark) an older version, means it has to be learned again.
    missing = [pair for pair in pairs if pair not in known]  # a step node with no technology is learned nowhere
    rejected = [pair for pair, (_, state) in known.items() if state == Status.REJECTED]
    stale = [pair for pair, (step, state) in known.items() if state == Status.TO_REVALIDATE and (
        step.status == Status.TO_REVALIDATE
        or (step.origin == Origin.FACTORY and pair[0] in seen and _older(step.version, seen[pair[0]])))]
    reasons = (  # (code, whether it holds, the (technology, step) pairs it is about)
        ("empty", not flow.nodes, []),
        ("expression", any(expressions(node.fields) for node in flow.nodes), []),
        ("not_learned", missing, missing),
        ("rejected", rejected, rejected),
        ("to_revalidate", stale, stale),
        ("question", waiting, []),
    )
    for why, holds, about in reasons:
        if holds:
            by_technology: dict[str, list[str]] = {}
            for tech, name in about:
                by_technology.setdefault(tech, []).append(name)
            return {"why": why, "steps": list(dict.fromkeys(name for _, name in about)), "by_technology": by_technology}
    return None


def flow_overview(user_db: Path, factory_db: Path | None) -> list[dict]:
    """What Home says about each flow: `flow_summaries` with the technologies its step nodes act on, how the last run
    went, and `blocked`: why it cannot run (see `_why_not`), or None. No desktop is asked and nothing seen on a screen is
    included."""
    steps = list_steps(user_db, factory_db)
    learned = {(step.app, step.name): (step, report["state"])
               for step, report in zip(steps, step_reports(user_db, steps), strict=True)}
    seen, runs = seen_versions(user_db), last_runs(user_db)
    waiting = {doubt.flow_id for doubt in list_doubts(user_db, "open")}
    overview = []
    for entry in flow_summaries(user_db, factory_db):
        try:
            flow = load_flow(user_db, factory_db, entry["id"])
            technologies = list(dict.fromkeys(node.technology for node in flow.nodes
                                              if node.kind in ("step", "loop") and node.technology))
            blocked = _why_not(flow, learned, seen, entry["id"] in waiting)
        except (ValueError, TypeError, KeyError):  # a definition that cannot be read must not hide the other flows
            technologies, blocked = [], {"why": "unreadable", "steps": [], "by_technology": {}}
        overview.append({**entry, "technologies": technologies, "last_run": runs.get(entry["id"]), "blocked": blocked})
    return overview


def create_flow(user_db: Path, title: str, app: str, nodes, edges, factory_db: Path | None = None) -> dict:
    """Save a new flow under an identifier made from its title, so it never replaces another, and say whether it can run.

    A step node that names no technology acts on `app`. A step the apprentice has not been taught is not an error: the flow
    is saved and `missing_steps` names the lessons still to teach. ValueError when the nodes are not a flow."""
    title, app = check_title(title), taught_app(check_app(app), list_steps(user_db, factory_db))
    taken = [*(entry["id"] for entry in list_flows(user_db, factory_db)), *trashed_ids(user_db)]
    flow_id = new_flow_id(title, taken)
    try:
        nodes = [{**node, "technology": node.get("technology") or app} if node.get("kind", "step") in ("step", "loop") else node
                 for node in nodes]
        flow = flow_from_dict(flow_id, {"nodes": nodes, "edges": edges})
    except (TypeError, KeyError, AttributeError):  # their words would show how the engine is built
        raise ValueError("that is not a valid flow") from None
    save_flow(user_db, flow, title)
    return flow_readiness(user_db, flow_id, factory_db)


def flow_readiness(user_db: Path, flow_id: str, factory_db: Path | None = None) -> dict:
    """{"flow_id", "ready", "why", "missing_steps"}: what stops a run of the flow, and the steps still to teach."""
    entry = next((e for e in flow_overview(user_db, factory_db) if e["id"] == flow_id), None)
    if entry is None:
        raise ValueError(f"no flow named {flow_id!r}")
    blocked = entry["blocked"]
    return {"flow_id": flow_id, "ready": blocked is None, "why": blocked and blocked["why"],
            "missing_steps": blocked["steps"] if blocked and blocked["why"] == "not_learned" else []}

