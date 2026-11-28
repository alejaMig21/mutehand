"""Step store: one table per SQLite file (user knowledge, factory knowledge)."""

import base64
import io
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from contextlib import closing
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np

from workflow_factory.desktop import FRAME_FIELDS, AppKey, Frame, plain_app
from workflow_factory.legacy import add_text_column, migrate_names, readable_table

SCHEMA = """
CREATE TABLE IF NOT EXISTS steps (
    app TEXT NOT NULL,
    version TEXT NOT NULL,
    name TEXT NOT NULL,
    precondition TEXT NOT NULL,
    action TEXT NOT NULL,
    role TEXT NOT NULL,
    control_name TEXT NOT NULL,
    automation_id TEXT,
    effect TEXT NOT NULL,
    origin TEXT NOT NULL,
    status TEXT NOT NULL,
    factory_successes INTEGER NOT NULL DEFAULT 0,
    factory_failures INTEGER NOT NULL DEFAULT 0,
    frame TEXT,    -- JSON of Frame, NULL = replay anywhere
    mask TEXT,     -- JSON list of the frame fields that matter
    capture BLOB,  -- canvas pixels, numpy .npy bytes
    sensitive TEXT,  -- Sensitivity category or NULL
    secret_ref TEXT, -- reference into the Windows credential store, never the value
    derived TEXT,    -- JSON of Derived (rung 2) or NULL
    template TEXT,   -- JSON of Template (rung 3; pixels as base64 .npy) or NULL
    drag_to TEXT,    -- JSON of the drag destination Endpoint or NULL
    PRIMARY KEY (app, name)
)
"""
# local counters live in the user database, even for factory steps (factory file is read-only)
STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS step_state (
    app TEXT NOT NULL,
    name TEXT NOT NULL,
    local_successes INTEGER NOT NULL DEFAULT 0,
    local_failures INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,  -- sticky: set at replay time, cleared only by restore_step
    restored INTEGER NOT NULL DEFAULT 0,  -- a human restored it: shipped counters no longer reject
    why TEXT,  -- JSON: what rejected it, so the person can decide; NULL = not rejected or not recorded
    PRIMARY KEY (app, name)
)
"""
# the newest version of each app a run has seen: lets the Apps screen show to_revalidate before any lookup
SEEN_SCHEMA = "CREATE TABLE IF NOT EXISTS app_seen (app TEXT PRIMARY KEY, version TEXT NOT NULL)"
# the product name each app's executable declared when it was last seen: what screens call it once it is closed
NAMES_SCHEMA = "CREATE TABLE IF NOT EXISTS app_names (app TEXT PRIMARY KEY, name TEXT NOT NULL)"
# pattern tags ("file", "mouse") belong to a step by name, whatever technologies it holds locators for; technology tags
# are not stored: they are the apps of the step's rows
TAGS_SCHEMA = "CREATE TABLE IF NOT EXISTS step_tags (name TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY (name, tag))"
COLUMNS = (
    "app, version, name, precondition, action, role, control_name, automation_id,"
    " effect, origin, status, factory_successes, factory_failures, frame, mask, capture, sensitive, secret_ref, derived, template, drag_to"
)
PLACEHOLDERS = ", ".join("?" * (COLUMNS.count(",") + 1))
# what a listing that only names and counts steps reads: everything but the pixels and the frame, which are the heavy part
LIGHT_COLUMNS = ", ".join("NULL" if column.strip() in ("frame", "mask", "capture", "derived", "template", "drag_to") else column.strip()
                          for column in COLUMNS.split(","))
# Below REJECTED_BELOW a step is rejected; everything else that is not trusted is suspect.
TRUSTED_AT, REJECTED_BELOW, OWN_SUCCESSES_TO_TRUST = 0.80, 0.30, 2


class Status(StrEnum):
    TRUSTED = "trusted"
    SUSPECT = "suspect"
    REJECTED = "rejected"
    TO_REVALIDATE = "to_revalidate"


class Sensitivity(StrEnum):
    """Categories of sensitive action that need a consent record."""

    PASSWORD_FIELD = "password_field"
    SYSTEM_SHORTCUT = "system_shortcut"
    OUTWARD_ACTION = "outward_action"
    VETO_TEXT = "veto_text"


class Origin(StrEnum):
    FACTORY = "factory"
    LOCAL = "local"


@dataclass(frozen=True)
class Locator:
    role: str
    name: str
    automation_id: str | None = None


@dataclass(frozen=True)
class Derived:
    """Rung 2: a point given as fractions of an anchor control that is re-located each time."""

    anchor: Locator
    fx: float
    fy: float


@dataclass(frozen=True)
class Template:
    """Rung 3: a stored image fragment searched for inside the anchor's region only."""

    anchor: Locator  # the search region is this control's area
    pixels: np.ndarray = field(compare=False)
    min_score: float = 0.95  # 1.0 is a pixel-exact match
    max_attempts: int = 3  # captures tried before giving up

    def __post_init__(self):
        if not 0 <= self.min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.pixels.ndim != 3 or self.pixels.size == 0:
            raise ValueError("template pixels must be a non-empty height x width x channels array")
        if self.pixels.std() < 2:  # a flat patch matches any area of similar colour
            raise ValueError("template is too flat to search for")


@dataclass(frozen=True)
class Endpoint:
    """Where an action lands, with the rungs the step defines."""

    locator: Locator
    derived: Derived | None = None
    template: Template | None = None


@dataclass(frozen=True)
class Step:
    app: str
    version: str
    name: str
    locator: Locator
    precondition: str = ""
    action: str = "click"
    effect: str = ""
    origin: Origin = Origin.LOCAL
    status: Status = Status.SUSPECT
    factory_successes: int = 0
    factory_failures: int = 0
    frame: Frame | None = None
    mask: tuple[str, ...] = FRAME_FIELDS
    capture: np.ndarray | None = field(default=None, compare=False)
    sensitive: Sensitivity | None = None
    secret_ref: str | None = None
    derived: Derived | None = None
    template: Template | None = None
    drag_to: Endpoint | None = None  # the destination of a drag, located with its own ladder

    @property
    def uses_physical_input(self) -> bool:
        """Every step action acts on the app. Research 20: even an accessibility click or set-value can take
        the foreground window, so only reading a value (a `get`, which acts on nothing) is free of the input lock."""
        return self.action != "read_value"

    @property
    def endpoint(self) -> Endpoint:
        return Endpoint(self.locator, self.derived, self.template)


def _load_derived(raw):
    if not raw:
        return None
    data = json.loads(raw)
    return Derived(anchor=Locator(**data["anchor"]), fx=data["fx"], fy=data["fy"])


def _dump_endpoint(endpoint):
    if endpoint is None:
        return None
    return json.dumps({
        "locator": asdict(endpoint.locator),
        "derived": json.loads(json.dumps(asdict(endpoint.derived))) if endpoint.derived else None,
        "template": json.loads(_dump_template(endpoint.template)) if endpoint.template else None,
    })


def _load_endpoint(raw):
    if not raw:
        return None
    data = json.loads(raw)
    return Endpoint(
        locator=Locator(**data["locator"]),
        derived=_load_derived(json.dumps(data["derived"])) if data["derived"] else None,
        template=_load_template(json.dumps(data["template"])) if data["template"] else None,
    )


def _dump_template(template):
    if template is None:
        return None
    return json.dumps({
        "anchor": asdict(template.anchor), "min_score": template.min_score,
        "max_attempts": template.max_attempts,
        "pixels": base64.b64encode(_pack(template.pixels)).decode(),
    })


def _load_template(raw):
    if not raw:
        return None
    data = json.loads(raw)
    return Template(anchor=Locator(**data["anchor"]), pixels=_unpack(base64.b64decode(data["pixels"])),
                    min_score=data["min_score"], max_attempts=data["max_attempts"])


def _pack(capture):
    if capture is None:
        return None
    buffer = io.BytesIO()
    np.save(buffer, capture, allow_pickle=False)
    return buffer.getvalue()


MAX_PIXEL_BYTES = 64 * 1024 * 1024  # a stored capture or template this big is refused, not allocated


def _unpack(blob):
    if blob is None:
        return None
    buffer = io.BytesIO(blob)
    try:  # read the declared shape first: a tiny header can claim terabytes
        version = np.lib.format.read_magic(buffer)
        reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
        shape, _, dtype = reader(buffer)
    except Exception as error:  # noqa: BLE001 - any malformed header is just "bad pixel data"
        raise ValueError(f"unreadable pixel data: {error}") from None
    if math.prod(shape) * dtype.itemsize > MAX_PIXEL_BYTES:
        raise ValueError("pixel data is too large")
    buffer.seek(0)
    return np.load(buffer, allow_pickle=False)


def _row_to_step(row) -> Step:
    (app, version, name, precondition, action, role, control, automation_id, effect, origin,
     status, factory_successes, factory_failures, frame, mask, capture, sensitive, secret_ref, derived, template, drag_to) = row
    return Step(
        app=app, version=version, name=name, precondition=precondition, action=action,
        locator=Locator(role, control, automation_id), effect=effect,
        origin=Origin(origin), status=Status(status),
        factory_successes=factory_successes, factory_failures=factory_failures,
        frame=Frame(**json.loads(frame)) if frame else None,
        mask=tuple(json.loads(mask)) if mask else FRAME_FIELDS,
        capture=_unpack(capture),
        sensitive=Sensitivity(sensitive) if sensitive else None, secret_ref=secret_ref,
        derived=_load_derived(derived), template=_load_template(template),
        drag_to=_load_endpoint(drag_to),
    )


ACTIONS = ("click", "select", "drag", "type_secret", "type_value", "read_value", "paste_text", "press_keys")


def refused_write(action: str, role: str) -> bool:
    """A grid cell can accept a value write and report it back while the grid stays empty: a run would "finish" blank."""
    return action == "type_value" and role == "cell"


def validate_step(step: Step) -> None:
    """Everything that would make save_step refuse, so callers can check before acting."""
    if step.action not in ACTIONS:
        raise ValueError(f"unknown action {step.action!r}; use one of {', '.join(ACTIONS)}")
    if (step.action == "type_secret") != bool(step.secret_ref):
        raise ValueError("a secret reference goes with the type_secret action, and only with it")
    if step.secret_ref and step.sensitive != Sensitivity.PASSWORD_FIELD:
        raise ValueError("a step that types a secret must be marked as a password_field")
    unknown = [name for name in step.mask if name not in FRAME_FIELDS]
    if unknown:
        raise ValueError(f"mask names unknown frame fields: {', '.join(unknown)}")
    for endpoint in (step.endpoint, step.drag_to):
        derived = endpoint.derived if endpoint else None
        if derived and not (0 <= derived.fx <= 1 and 0 <= derived.fy <= 1):
            raise ValueError("a derived point is a fraction of its anchor (0..1), never a screen coordinate")
    if step.action == "drag" and step.drag_to is None:
        raise ValueError("a drag step needs a destination (drag_to)")


def _prepare(db: sqlite3.Connection, *schemas: str) -> None:
    """Bring a database written by an earlier version up to date, then make sure the tables exist."""
    migrate_names(db)
    for schema in schemas:
        db.execute(schema)
    if STATE_SCHEMA in schemas:
        add_text_column(db, "step_state", "why")


def save_step(db_path: Path, step: Step) -> None:
    validate_step(step)
    with closing(sqlite3.connect(db_path)) as db, db:
        _prepare(db, SCHEMA)
        loc = step.locator
        db.execute(
            f"INSERT OR REPLACE INTO steps ({COLUMNS}) VALUES ({PLACEHOLDERS})",
            (step.app, step.version, step.name, step.precondition, step.action,
             loc.role, loc.name, loc.automation_id, step.effect, str(step.origin),
             str(step.status), step.factory_successes, step.factory_failures,
             json.dumps(asdict(step.frame)) if step.frame else None,
             json.dumps(list(step.mask)), _pack(step.capture),
             str(step.sensitive) if step.sensitive else None, step.secret_ref,
             json.dumps(asdict(step.derived)) if step.derived else None,
             _dump_template(step.template), _dump_endpoint(step.drag_to)),
        )


def _find_in(db: sqlite3.Connection, app: str, name: str, table: str = "steps") -> Step | None:
    row = db.execute(
        f"SELECT {COLUMNS} FROM {table} WHERE app = ? AND name = ?", (app, name)
    ).fetchone()
    return _row_to_step(row) if row else None


def find_step(user_db: Path, factory_db: Path | None, app: str, name: str) -> Step | None:
    """User knowledge first, then factory knowledge (opened read-only)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, SCHEMA)
        found = _find_in(db, app, name)
    if found or factory_db is None or not factory_db.exists():
        return found
    with closing(sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)) as db:
        table = readable_table(db, "steps")
        return _find_in(db, app, name, table) if table else None


def revalidate_changed_versions(user_db: Path, app: str, current_version: str) -> None:
    """A version change keeps every step of the app but stops trusting it.

    Rejected steps stay rejected: only a human restores those."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, SCHEMA, SEEN_SCHEMA)
        db.execute("INSERT OR REPLACE INTO app_seen VALUES (?, ?)", (app, current_version))
        db.execute(
            "UPDATE steps SET status = ? WHERE app = ? AND version != ? AND status != ?",
            (str(Status.TO_REVALIDATE), app, current_version, str(Status.REJECTED)),
        )


def seen_versions(user_db: Path) -> dict[str, str]:
    """The newest version of each app that a run has met."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(SEEN_SCHEMA)
        return dict(db.execute("SELECT app, version FROM app_seen"))


def record_app_name(user_db: Path, key: AppKey) -> None:
    """Call whenever an app is seen: keeps the name it declares, under the plain name of the app."""
    name = key.name.strip()
    if name.lower().endswith(".exe"):  # no screen shows an extension, whoever wrote it
        name = name[:-4]
    if name:
        with closing(sqlite3.connect(user_db)) as db, db:
            db.execute(NAMES_SCHEMA)
            db.execute("INSERT OR REPLACE INTO app_names (app, name) VALUES (?, ?)", (plain_app(key.process), name))


def app_names(user_db: Path) -> dict[str, str]:
    """Plain app name -> what to call it, for every app seen that declares a product name. Apps that declare the same
    one (parts of one suite) carry their file name too, so the person can tell them apart."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(NAMES_SCHEMA)
        names = dict(db.execute("SELECT app, name FROM app_names"))
    shared = Counter(name.casefold() for name in names.values())
    return {app: f"{name} ({app.capitalize()})" if shared[name.casefold()] > 1 else name for app, name in names.items()}


def add_tags(user_db: Path, name: str, tags: list[str]) -> list[str]:
    """Merge pattern tags into a step's (by name, never lost) and return them all. Tags are lower case and trimmed."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(TAGS_SCHEMA)
        db.executemany("INSERT OR IGNORE INTO step_tags VALUES (?, ?)",
                       [(name, tag) for tag in {t.strip().casefold() for t in tags} - {""}])
        return sorted(tag for (tag,) in db.execute("SELECT tag FROM step_tags WHERE name = ?", (name,)))


def step_tags(user_db: Path, name: str) -> list[str]:
    return add_tags(user_db, name, [])


def all_tags(user_db: Path) -> dict[str, list[str]]:
    """Step name -> its pattern tags, for every name that has any. One read."""
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute(TAGS_SCHEMA)
        found: dict[str, list[str]] = {}
        for name, tag in db.execute("SELECT name, tag FROM step_tags ORDER BY tag"):
            found.setdefault(name, []).append(tag)
        return found


def words(text: str) -> list[str]:
    """Lower case, accents removed, split on anything that is not a letter or digit."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", plain)


def search_matches(query: str, name: str, tags: list[str]) -> bool:
    """The one search rule: every word of the query starts a word of the step's name or of one of its tags (pattern tags
    and technology names alike). Capitals and accents do not matter. An empty query matches everything."""
    present = [word for text in (name, *tags) for word in words(text)]
    return all(any(word.startswith(part) for word in present) for part in words(query))


def confidence(successes: int, failures: int) -> float:
    """Failures weigh three times a success; the +1/+2 keeps untested steps at 0.5."""
    return (successes + 1) / (successes + 3 * failures + 2)


def _state(db: sqlite3.Connection, step: Step) -> tuple[int, int, bool, bool]:
    row = db.execute(
        "SELECT local_successes, local_failures, rejected, restored FROM step_state"
        " WHERE app = ? AND name = ?",
        (step.app, step.name),
    ).fetchone()
    return row or (0, 0, False, False)


def _derive_status(step: Step, local_successes: int, local_failures: int) -> Status:
    successes = step.factory_successes + local_successes
    failures = step.factory_failures + local_failures
    score = confidence(successes, failures)
    if score < REJECTED_BELOW:
        return Status.REJECTED
    if score >= TRUSTED_AT and local_successes >= OWN_SUCCESSES_TO_TRUST and failures == 0:
        return Status.TRUSTED
    return Status.SUSPECT


def record_outcome(user_db: Path, step: Step, success: bool, got: str = "", at: str = "") -> Status:
    """Count one replay result and return the step's status afterwards. `got` is the effect that was measured."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, STATE_SCHEMA)
        db.execute("INSERT OR IGNORE INTO step_state (app, name) VALUES (?, ?)",
                   (step.app, step.name))
        column = "local_successes" if success else "local_failures"
        db.execute(f"UPDATE step_state SET {column} = {column} + 1 WHERE app = ? AND name = ?",
                   (step.app, step.name))
        successes, failures, _, _ = _state(db, step)
        derived = _derive_status(step, successes, failures)
        if derived == Status.REJECTED:
            why = {"kind": "different_effect", "expected": step.effect, "got": got, "at": at}
            db.execute("UPDATE step_state SET rejected = 1, why = ? WHERE app = ? AND name = ?",
                       (None if success else json.dumps(why), step.app, step.name))
        return derived


def _status_of(step: Step, state: tuple, app_version: str) -> Status:
    successes, failures, rejected, restored = state
    derived = _derive_status(step, successes, failures)
    if rejected or (not restored and Status.REJECTED in (step.status, derived)):
        return Status.REJECTED
    if step.status == Status.TO_REVALIDATE or step.version != app_version:
        return Status.TO_REVALIDATE
    return Status.SUSPECT if derived == Status.REJECTED else derived  # restored by a human


def current_status(user_db: Path, step: Step, app_version: str) -> Status:
    """What the apprentice may do with this step right now (rejection outranks revalidation)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, STATE_SCHEMA)
        state = _state(db, step)
    return _status_of(step, state, app_version)


def restore_step(user_db: Path, app: str, name: str) -> None:
    """Human action: forget local failures and lift a rejection. Nothing else restores a rejected step."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, SCHEMA, STATE_SCHEMA)
        db.execute("INSERT OR IGNORE INTO step_state (app, name) VALUES (?, ?)", (app, name))
        db.execute(
            "UPDATE step_state SET local_successes = 0, local_failures = 0, rejected = 0,"
            " restored = 1, why = NULL WHERE app = ? AND name = ?",
            (app, name),
        )
        db.execute(
            "UPDATE steps SET status = ? WHERE app = ? AND name = ? AND status = ?",
            (str(Status.SUSPECT), app, name, str(Status.REJECTED)),
        )


def list_steps(user_db: Path, factory_db: Path | None, light: bool = False) -> list[Step]:
    """Every step the apprentice could use: the user's, plus factory ones they do not shadow. `light` leaves out the pixels
    and the frame (the steps are for naming and counting, not for replaying), which keeps a long list quick."""
    columns = LIGHT_COLUMNS if light else COLUMNS
    found: dict[tuple[str, str], Step] = {}
    if factory_db is not None and factory_db.exists():
        with closing(sqlite3.connect(f"{factory_db.resolve().as_uri()}?mode=ro", uri=True)) as db:
            table = readable_table(db, "steps")
            for row in db.execute(f"SELECT {columns} FROM {table}") if table else []:
                step = _row_to_step(row)
                found[(step.app, step.name)] = step
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, SCHEMA)
        for row in db.execute(f"SELECT {columns} FROM steps"):
            step = _row_to_step(row)
            found[(step.app, step.name)] = step  # the user's step shadows the factory's
    return sorted(found.values(), key=lambda step: (step.app, step.name))


def step_reports(user_db: Path, steps: list[Step]) -> list[dict]:
    """The numbers behind each step's state, for an app's steps. One read, however many steps."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, STATE_SCHEMA)
        db.execute(SEEN_SCHEMA)
        states = {(app, name): rest for app, name, *rest in db.execute(
            "SELECT app, name, local_successes, local_failures, rejected, restored, why FROM step_state")}
        seen = dict(db.execute("SELECT app, version FROM app_seen"))
    reports = []
    for step in steps:
        *state, why = states.get((step.app, step.name), (0, 0, False, False, None))
        successes = step.factory_successes + state[0]
        failures = step.factory_failures + state[1]
        status = _status_of(step, tuple(state), seen.get(step.app, step.version))
        reports.append({
            "state": str(status),
            "successes": successes, "failures": failures,
            "confidence": round(confidence(successes, failures), 2),
            "why": json.loads(why) if status == Status.REJECTED and why else None,
        })
    return reports


def step_report(user_db: Path, step: Step) -> dict:
    return step_reports(user_db, [step])[0]


def reject_step(user_db: Path, app: str, name: str) -> None:
    """Human action: stop trusting this step. Works for factory steps too (the mark lives in the user file)."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, STATE_SCHEMA)
        db.execute("INSERT OR IGNORE INTO step_state (app, name) VALUES (?, ?)", (app, name))
        db.execute("UPDATE step_state SET rejected = 1, restored = 0, why = ? WHERE app = ? AND name = ?",
                   (json.dumps({"kind": "person"}), app, name))


def step_to_dict(step: Step) -> dict:
    """A step as plain JSON-able data (pixels as base64 .npy). Holds a secret reference, never a value."""
    return {
        "app": step.app, "version": step.version, "name": step.name,
        "precondition": step.precondition, "action": step.action, "effect": step.effect,
        "origin": str(step.origin), "status": str(step.status),
        "factory_successes": step.factory_successes, "factory_failures": step.factory_failures,
        "locator": asdict(step.locator),
        "frame": asdict(step.frame) if step.frame else None, "mask": list(step.mask),
        "capture": base64.b64encode(_pack(step.capture)).decode() if step.capture is not None else None,
        "sensitive": str(step.sensitive) if step.sensitive else None,
        "secret_ref": step.secret_ref,
        "derived": asdict(step.derived) if step.derived else None,
        "template": json.loads(_dump_template(step.template)) if step.template else None,
        "drag_to": json.loads(_dump_endpoint(step.drag_to)) if step.drag_to else None,
    }


def step_from_dict(data: dict) -> Step:
    """Inverse of step_to_dict; raises ValueError when the data is not a valid step."""
    try:
        step = Step(
            app=data["app"], version=data["version"], name=data["name"], locator=Locator(**data["locator"]),
            precondition=data.get("precondition", ""), action=data.get("action", "click"),
            effect=data.get("effect", ""), origin=Origin(data.get("origin", "local")),
            status=Status(data.get("status", "suspect")),
            factory_successes=data.get("factory_successes", 0), factory_failures=data.get("factory_failures", 0),
            frame=Frame(**data["frame"]) if data.get("frame") else None,
            mask=FRAME_FIELDS if data.get("mask") is None else tuple(data["mask"]),  # () is a real mask
            capture=_unpack(base64.b64decode(data["capture"])) if data.get("capture") else None,
            sensitive=Sensitivity(data["sensitive"]) if data.get("sensitive") else None,
            secret_ref=data.get("secret_ref"),
            derived=_load_derived(json.dumps(data["derived"])) if data.get("derived") else None,
            template=_load_template(json.dumps(data["template"])) if data.get("template") else None,
            drag_to=_load_endpoint(json.dumps(data["drag_to"])) if data.get("drag_to") else None,
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"not a valid step: {error}") from None
    validate_step(step)
    return step


def forget_state(user_db: Path, app: str, name: str) -> None:
    """Drop the local counters and flags of a step that is being replaced by new knowledge."""
    with closing(sqlite3.connect(user_db)) as db, db:
        _prepare(db, STATE_SCHEMA)
        db.execute("DELETE FROM step_state WHERE app = ? AND name = ?", (app, name))
