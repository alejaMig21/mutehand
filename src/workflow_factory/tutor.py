"""What the tutor (Claude Code) can do through the project's own tools.

Deliberately small: observe (summarised), study order, teach/fix a step, list and answer
doubts. There is no force option and no screenshot tracing here, and secrets only ever appear
as references.
"""

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path

from workflow_factory.consent import Consent, effective_sensitivity, grant_consent, is_permitted, scope_of
from workflow_factory.desktop import Desktop, plain_app
from workflow_factory.flow import TEXT_ACTIONS, effect_of, select
from workflow_factory.queue import answer_doubt, list_doubts
from workflow_factory.steps import (
    Locator,
    Sensitivity,
    Status,
    Step,
    add_tags,
    all_tags,
    app_names,
    find_step,
    list_steps,
    record_app_name,
    refused_write,
    save_step,
    search_matches,
    step_reports,
    validate_step,
    words,
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


def mark_private(user_db: Path, app: str) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("INSERT OR IGNORE INTO private_apps VALUES (?)", (plain_app(app),))


def private_apps(user_db: Path) -> frozenset[str]:
    """The names (no .exe, lower case) of every private app: the defaults and the ones the person marked."""
    with closing(_connect(user_db)) as db:
        return DEFAULT_PRIVATE_APPS | {row[0] for row in db.execute("SELECT app FROM private_apps")}


_HANDLE_KEY = secrets.token_bytes(16)  # lives as long as the process: a handle is only good for the page that asked for it


def handle(*names: str) -> str:
    """An opaque stand-in for names the browser must not see (a step or control of a private app). The same names give the
    same handle in this process, so a button can send it back; nothing about the names can be read from it."""
    return "h" + hmac.new(_HANDLE_KEY, json.dumps(names).encode(), hashlib.sha256).hexdigest()[:16]


def is_private(user_db: Path, app: str, known: frozenset[str] | None = None) -> bool:
    return plain_app(app) in (known if known is not None else private_apps(user_db))


def step_context(user_db: Path, steps: list[Step], private: frozenset[str] | None = None) -> dict[str, dict]:
    """Per step name: its pattern tags and the technologies (as the screens name them) it has a locator for. A private
    technology is left out, and a name known only there has no entry, so nothing about it can be found or shown."""
    private = private_apps(user_db) if private is None else private
    shown, tags, context = app_names(user_db), all_tags(user_db), {}
    for step in steps:
        if plain_app(step.app) not in private:
            entry = context.setdefault(step.name, {"tags": tags.get(step.name, []), "technologies": set()})
            entry["technologies"].add(shown.get(plain_app(step.app), step.app))
    return {name: {**entry, "technologies": sorted(entry["technologies"])} for name, entry in context.items()}


def known_steps(user_db: Path, factory_db: Path | None, technology: str | None = None, tag: str | None = None,
                query: str | None = None) -> list[dict]:
    """What the apprentice knows, one entry per step name: name, action, pattern tags, technologies and state (trusted
    if any technology's step is). The filters combine: a technology it has a locator for, a pattern or technology tag,
    and the search rule on name and tags. A private technology's steps are only counted, in a last {"private", "count"}
    entry, and only when no tag or text is asked for (they have none to match)."""
    steps = list_steps(user_db, factory_db, light=True)
    private = private_apps(user_db)
    context, reports = step_context(user_db, steps, private), step_reports(user_db, steps)
    wanted = plain_app(technology) if technology else None
    grouped: dict[str, list[tuple[Step, str]]] = {}
    hidden: set[str] = set()
    for step, report in zip(steps, reports, strict=True):
        if wanted and plain_app(step.app) != wanted:
            continue
        if plain_app(step.app) in private:
            hidden.add(step.name)
        else:
            grouped.setdefault(step.name, []).append((step, report["state"]))
    entries = []
    for name, rows in grouped.items():
        tags, technologies = context[name]["tags"], context[name]["technologies"]
        if (tag is None or words(tag) in [words(t) for t in [*tags, *technologies]]) \
                and (not query or search_matches(query, name, [*tags, *technologies])):
            states = [state for _, state in rows]
            entries.append({"name": name, "action": rows[0][0].action, "tags": tags, "technologies": technologies,
                            "state": str(Status.TRUSTED) if Status.TRUSTED in states else states[0]})
    # names known only on private technologies; with a technology asked for, that technology's own steps
    count = len(hidden if wanted else hidden - context.keys())
    if count and tag is None and not query:
        entries.append({"private": True, "count": count})
    return sorted(entries, key=lambda entry: entry.get("name", "￿"))


def observe(user_db: Path, desktop: Desktop) -> dict:
    """A summarised snapshot. Private apps are reduced to roles and counts: no names at all."""
    key = desktop.app_key()
    record_app_name(user_db, key)
    app = key.process
    controls = desktop.snapshot()
    summary = {
        "app": app,
        "private": is_private(user_db, app),
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


def technology_in(user_db: Path, name: str, taught_on: str, product: str = "") -> str | None:
    """The technology a step name gives away, as written in the name, or None. Technologies are the apps of every step
    known, the one being taught and the product names seen; a word counts whole, with or without `.exe`."""
    known = {plain_app(step.app) for step in list_steps(user_db, None, light=True)} | {plain_app(taught_on)}
    terms = known | {n.casefold() for n in app_names(user_db).values()} | ({product.casefold()} if product else set())
    for term in sorted(terms - {""}, key=len, reverse=True):
        if found := re.search(rf"(?<![^\W_]){re.escape(term)}(?:\.exe)?(?![^\W_])", name, re.IGNORECASE):
            return found.group()
    return None


def teach_step(
    user_db: Path, desktop: Desktop, name: str, locator: Locator, action: str = "click",
    sensitive: Sensitivity | None = None, secret_ref: str | None = None, tags: list[str] | None = None,
) -> dict:
    """Perform the action once, measure its effect and save the step at once (autosave). A step is named by what it
    does: its name is refused if it carries a technology. `tags` are pattern tags, merged into the step's by name."""
    key = desktop.app_key()
    if given := technology_in(user_db, name, key.process, key.name.strip().removesuffix(".exe")):
        return {"status": "name_has_technology", "message": (
            f"A step name must say what it does and must not contain a technology name or a program's process name "
            f"({given!r} is one). Name the step by its action, for example 'Save', and teach it again.")}
    record_app_name(user_db, key)
    candidate = Step(app=key.process, version=key.version, name=name, locator=locator,
                       action=action, sensitive=sensitive, secret_ref=secret_ref)
    category = effective_sensitivity(candidate)  # declared, or implied by the action or the control name
    candidate = replace(candidate, sensitive=category)
    validate_step(candidate)  # refuse before touching the app: a step that cannot be saved never runs
    if refused_write(action, locator.role):
        return {"status": "cell_requires_paste_text"}
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
    elif action == "read_value":
        desktop.read_text(control)  # a read acts on nothing: the step is taught by proving the control answers
    elif action == "select":
        refused = select(desktop, key.process, control)
        if refused:
            return {"status": refused}
    elif action not in TEXT_ACTIONS:  # no text to write yet: finding the control is the whole proof
        desktop.click(control)
    effect = effect_of(before, set(desktop.snapshot()))
    # no effect a run could contradict: nothing was done, or what a selection changes depends on what is selected
    taught = "" if action in TEXT_ACTIONS or action == "select" else str(effect)
    save_step(user_db, replace(candidate, sensitive=category, effect=taught, frame=desktop.frame()))
    return {"status": "saved", "step": name, "effect": str(effect), "tags": add_tags(user_db, name, tags or [])}


def list_open_doubts(user_db: Path) -> list[dict]:
    return [
        {"id": d.id, "flow_id": d.flow_id, "node_id": d.node_id, "step": d.step,
         "reason": str(d.reason), "detail": d.detail, "capture": d.capture, "status": d.status,
         "note": d.note}  # what the person wrote when asking for help
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
