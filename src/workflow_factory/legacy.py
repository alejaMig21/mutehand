"""What an earlier version wrote, so a database or a file made before the rename of lesson to step still opens.

Nothing here deletes data: tables and columns are renamed in place and old keys are read as the new ones.
"""

import sqlite3

TABLES = {"lessons": "steps", "lesson_state": "step_state"}


def migrate_names(db: sqlite3.Connection) -> None:
    """Rename the old tables and the old doubts column in place. Safe to run on every open."""
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for old, new in TABLES.items():
        if old in existing and new not in existing:
            db.execute(f"ALTER TABLE {old} RENAME TO {new}")
    if "doubts" in existing:
        columns = {row[1] for row in db.execute("PRAGMA table_info(doubts)")}
        if "lesson" in columns and "step" not in columns:
            db.execute("ALTER TABLE doubts RENAME COLUMN lesson TO step")


def readable_table(db: sqlite3.Connection, new: str) -> str | None:
    """The table to read in a database we cannot change (the read-only factory file): the new name, else the old."""
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if new in existing:
        return new
    old = next((o for o, n in TABLES.items() if n == new and o in existing), None)
    return old


def upgrade_node(node: dict) -> dict:
    """A flow node written before the rename: its lesson key and kind are the step's."""
    node = dict(node)
    if "lesson" in node and "step" not in node:
        node["step"] = node.pop("lesson")
    if node.get("kind") == "lesson":
        node["kind"] = "step"
    return node


def upgrade_knowledge(data: dict) -> dict:
    """An export written before the rename kept its steps under the key lessons."""
    data = dict(data)
    if "steps" not in data and "lessons" in data:
        data["steps"] = data.pop("lessons")
    return data
