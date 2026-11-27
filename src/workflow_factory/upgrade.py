"""The start of a new data model: the old user database is kept as a dated copy and a new empty one begins.

A database made by a model that is gone has data and no schema version. The new one is stamped with `VERSION`
(SQLite's `user_version`), so the check holds for any database of an earlier model and never looks at what it holds.
Nothing is read from the old file. Raise `VERSION` when a later model needs the same clean start.
"""

import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

VERSION = 2
NOTICES = "CREATE TABLE IF NOT EXISTS notices (id TEXT PRIMARY KEY, copy TEXT NOT NULL)"
CLEAN_START = "clean-start"


def start_user_db(user_db: Path, today: date | None = None) -> None:
    """Run when the program starts. An old database is renamed next to itself with the date, a new one is created and
    holds the notice that tells the person where the copy is. A database already of this model is left alone."""
    user_db = Path(user_db)
    copy = None
    if user_db.exists():
        with closing(sqlite3.connect(user_db)) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            has_data = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' LIMIT 1").fetchone() is not None
        if version >= VERSION:
            return
        if has_data:
            copy = _free_name(user_db, today or date.today())
            user_db.rename(copy)
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(f"PRAGMA user_version = {VERSION}")
        db.execute(NOTICES)
        if copy:
            db.execute("INSERT INTO notices VALUES (?, ?)", (CLEAN_START, str(copy)))


def _free_name(user_db: Path, today: date) -> Path:
    stem, taken = f"{user_db.stem}-{today.isoformat()}", 1
    while (copy := user_db.with_name(f"{stem}{'' if taken == 1 else f'-{taken}'}{user_db.suffix}")).exists():
        taken += 1
    return copy


def list_notices(user_db: Path) -> list[dict]:
    """What the person is to be told once: an id and the place of the copy. A database with no notices lists none."""
    with closing(sqlite3.connect(user_db)) as db:
        try:
            return [{"id": id_, "copy": copy} for id_, copy in db.execute("SELECT id, copy FROM notices ORDER BY rowid")]
        except sqlite3.OperationalError:
            return []


def dismiss_notice(user_db: Path, notice_id: str) -> None:
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(NOTICES)
        db.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
