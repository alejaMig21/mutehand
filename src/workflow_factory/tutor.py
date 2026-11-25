"""What the tutor (Claude Code) can do through the project's own tools.

Deliberately small: observe (summarised), study order, teach/fix a step, list and answer
doubts. There is no force option and no screenshot tracing here, and secrets only ever appear
as references.
"""

import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path

from workflow_factory.consent import Consent, effective_sensitivity, grant_consent, is_permitted, scope_of
from workflow_factory.desktop import Desktop
from workflow_factory.flow import effect_of
from workflow_factory.queue import answer_doubt, list_doubts
from workflow_factory.steps import (
    Locator,
    Sensitivity,
    Status,
    Step,
    find_step,
    save_step,
    validate_step,
)

# Apps whose content is private by default; the user can mark more.
DEFAULT_PRIVATE_APPS = frozenset({"telegram", "vivaldi", "chrome", "msedge", "firefox", "brave"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS private_apps (app TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS study_order (
    app TEXT NOT NULL,
    position INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    control_name TEXT NOT NULL,
    automation_id TEXT,
    PRIMARY KEY (app, position)
);
"""


@dataclass(frozen=True)
class StudyStep:
    """One step to teach, in the order the tutor chose to explore the app."""

    name: str
    locator: Locator


def _connect(user_db: Path) -> sqlite3.Connection:
    db = sqlite3.connect(user_db)
    db.executescript(SCHEMA)
    return db


def _app_name(app: str) -> str:
    """'Telegram', 'TELEGRAM.EXE' and 'telegram.exe' are one app."""
    return app.lower().removesuffix(".exe")


def mark_private(user_db: Path, app: str) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("INSERT OR IGNORE INTO private_apps VALUES (?)", (_app_name(app),))


def _is_private(user_db: Path, app: str) -> bool:
    if _app_name(app) in DEFAULT_PRIVATE_APPS:
        return True
    with closing(_connect(user_db)) as db:
        row = db.execute("SELECT 1 FROM private_apps WHERE app = ?", (_app_name(app),)).fetchone()
    return row is not None


def observe(user_db: Path, desktop: Desktop) -> dict:
    """A summarised snapshot. Private apps are reduced to roles and counts: no names at all."""
    app = desktop.app_key().process
    controls = desktop.snapshot()
    summary = {
        "app": app,
        "private": _is_private(user_db, app),
        "roles": dict(Counter(control.role for control in controls)),
    }
    if not summary["private"]:
        summary["controls"] = [
            {"role": c.role, "name": c.name, "automation_id": c.automation_id} for c in controls
        ]
    return summary


def set_study_order(user_db: Path, app: str, steps: list[StudyStep]) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("DELETE FROM study_order WHERE app = ?", (app,))
        db.executemany(
            "INSERT INTO study_order VALUES (?, ?, ?, ?, ?, ?)",
            [(app, i, s.name, s.locator.role, s.locator.name, s.locator.automation_id)
             for i, s in enumerate(steps)],
        )


def study_status(user_db: Path, app: str) -> dict:
    """Where the study stands: a step is done once its step exists (autosaved when measured)."""
    with closing(_connect(user_db)) as db:
        rows = db.execute(
            "SELECT name, role, control_name, automation_id FROM study_order WHERE app = ?"
            " ORDER BY position", (app,)).fetchall()
    def done(row) -> bool:  # a step on the same control that is still trusted for this app version
        step = find_step(user_db, None, app, row[0])
        return (
            step is not None
            and step.status != Status.TO_REVALIDATE
            and step.locator == Locator(row[1], row[2], row[3])
        )

    pending = [row for row in rows if not done(row)]
    nxt = None
    if pending:
        name, role, control_name, automation_id = pending[0]
        nxt = {"name": name, "role": role, "control_name": control_name, "automation_id": automation_id}
    return {"done": len(rows) - len(pending), "total": len(rows), "next": nxt}


def record_consent(user_db: Path, app: str, control: str, action: str) -> None:
    """Call only after the user said yes to this sensitive action (ADR 0002)."""
    grant_consent(user_db, app, control, action)


def _consent_required(category: Sensitivity, scope: Consent) -> dict:
    return {
        "status": "consent_required", "category": str(category),
        "scope": {"app": scope.app, "control": scope.control, "action": scope.action},
    }


def teach_step(
    user_db: Path, desktop: Desktop, name: str, locator: Locator, action: str = "click",
    sensitive: Sensitivity | None = None, secret_ref: str | None = None,
) -> dict:
    """Perform the action once, measure its effect and save the step at once (autosave)."""
    key = desktop.app_key()
    candidate = Step(app=key.process, version=key.version, name=name, locator=locator,
                       action=action, sensitive=sensitive, secret_ref=secret_ref)
    category = effective_sensitivity(candidate)  # declared, or implied by the action or the control name
    candidate = replace(candidate, sensitive=category)
    validate_step(candidate)  # refuse before touching the app: a step that cannot be saved never runs
    if category and not is_permitted(user_db, candidate):  # ask before touching anything
        return _consent_required(category, scope_of(candidate))
    control = desktop.find(locator.role, locator.name, locator.automation_id)
    if control is None:
        return {"status": "control_not_found"}
    if not control.readable:  # cannot be perceived: never taught, and no consent can change that
        return {"status": "unreadable"}
    if control.secure:  # a password field is a sensitive category and only takes secrets
        category = Sensitivity.PASSWORD_FIELD
        if not is_permitted(user_db, replace(candidate, sensitive=category)):
            return _consent_required(category, scope_of(candidate))
        if action != "type_secret":
            return {"status": "secure_field_requires_type_secret"}
    before = set(desktop.snapshot())
    if action == "type_secret":
        desktop.type_secret(control, secret_ref)
    else:
        desktop.click(control)
    effect = effect_of(before, set(desktop.snapshot()))
    save_step(user_db, replace(candidate, sensitive=category, effect=str(effect), frame=desktop.frame()))
    return {"status": "saved", "step": name, "effect": str(effect)}


def list_open_doubts(user_db: Path) -> list[dict]:
    return [
        {"id": d.id, "flow_id": d.flow_id, "node_id": d.node_id, "step": d.step,
         "reason": str(d.reason), "capture": d.capture, "status": d.status}
        for d in list_doubts(user_db, status="open")
    ]


def answer_doubt_by_teaching(
    user_db: Path, desktop: Desktop, doubt_id: int, name: str, locator: Locator, **teach_kw
) -> dict:
    """Answer a doubt by (re)teaching its step; the doubt closes only if the step was saved."""
    doubt = next((d for d in list_doubts(user_db) if d.id == doubt_id), None)
    if doubt is None or doubt.status != "open":
        raise ValueError(f"doubt {doubt_id} is not open")
    if doubt.step != name:
        raise ValueError(f"doubt {doubt_id} is about step {doubt.step!r}, not {name!r}")
    result = teach_step(user_db, desktop, name, locator, **teach_kw)
    if result["status"] != "saved":
        return result
    answer_doubt(user_db, doubt_id)
    return {**result, "status": "answered", "doubt": doubt_id}
