"""What the Apps screen says: one row per app, a search across all of them, and what one app holds (its actions, problems
first, and the permissions it was given with what would stop without each). Names, counts and codes only: no screen content,
and the actions of a private app are neither matched by a search nor offered as search results."""

import re
from dataclasses import asdict
from pathlib import Path

from workflow_factory.consent import Consent, consents, covers, needs_consent
from workflow_factory.desktop import plain_app
from workflow_factory.flows import flow_summaries, load_flow
from workflow_factory.steps import Status, app_names, list_steps, step_reports
from workflow_factory.tutor import is_private, private_apps

PROBLEMS = (str(Status.REJECTED), str(Status.TO_REVALIDATE))


def _label(app: str, names: dict[str, str]) -> str:
    """What the screen calls an app: the product name it declared, else its file name without the extension."""
    known = names.get(plain_app(app))
    base = re.sub(r"\.exe$", "", app, flags=re.IGNORECASE)
    return known or base[:1].upper() + base[1:]


def _words(text: str) -> list[str]:
    return re.sub(r"[-_]+", " ", text.lower()).split()


def _matches(words: list[str], *texts: str) -> bool:
    text = " ".join(_words(" ".join(texts)))
    return all(word in text for word in words)


def _known(user_db: Path, factory_db: Path | None) -> tuple[dict[str, str], list, list[dict]]:
    """The spelling of every app that has an action or a permission, the light steps and each step's report."""
    steps = list_steps(user_db, factory_db, light=True)
    spelling: dict[str, str] = {}
    for app in [*(step.app for step in steps), *(consent.app for consent in consents(user_db))]:
        spelling.setdefault(plain_app(app), app)
    return spelling, steps, step_reports(user_db, steps)


def app_rows(user_db: Path, factory_db: Path | None, query: str | None = None) -> list[dict]:
    """The apps, those with something for the person first, then by name. With a query, only the apps it matches: by their
    name, or by an action (`found` names them; never for a private app, whose action names stay out of every search)."""
    spelling, steps, reports = _known(user_db, factory_db)
    names, private, granted = app_names(user_db), private_apps(user_db), consents(user_db)
    rows = {key: {"app": app, "private": is_private(user_db, app, private), "actions": 0, "problems": 0, "found": [],
                  "permissions": sum(plain_app(c.app) == key for c in granted)} for key, app in spelling.items()}
    words = _words(query or "")
    for step, report in zip(steps, reports, strict=True):
        row = rows[plain_app(step.app)]
        row["actions"] += 1
        row["problems"] += report["state"] in PROBLEMS
        label = _label(step.app, names)
        # words that all name the app list the app itself, not each of its actions
        if words and not row["private"] and not _matches(words, step.app, label) and _matches(words, step.name, step.app, label):
            row["found"].append(step.name)
    shown = [row for row in rows.values() if not words or row["found"] or _matches(words, row["app"], _label(row["app"], names))]
    for row in shown:
        row["found"].sort()
        if not words:
            del row["found"]
    return sorted(shown, key=lambda row: (not row["problems"], _label(row["app"], names).casefold()))


def app_detail(user_db: Path, factory_db: Path | None, app: str) -> dict | None:
    """One app: its actions with the ones that have a problem first (and why a rejected one is), and each permission with the
    actions and chores that stop working if it is taken back. None when nothing is known under that name."""
    spelling, steps, reports = _known(user_db, factory_db)
    key = plain_app(app)
    if key not in spelling:
        return None
    mine = [(step, report) for step, report in zip(steps, reports, strict=True) if plain_app(step.app) == key]
    actions = [{"app": step.app, "name": step.name, "state": report["state"],
                "why": (report["why"] or {"kind": "person"}) if report["state"] == str(Status.REJECTED) else None}
               for step, report in mine]
    actions.sort(key=lambda action: (action["state"] not in PROBLEMS, action["name"]))
    by_name = {step.name: step for step, _ in mine}
    chores = [(entry, {node.step for node in load_flow(user_db, factory_db, entry["id"]).nodes if node.kind in ("step", "loop")})
              for entry in flow_summaries(user_db, factory_db) if plain_app(entry["app"] or "") == key]
    permissions = []
    for granted in consents(user_db):
        if plain_app(granted.app) != key:
            continue
        needing = {name: step for name, step in by_name.items() if needs_consent(user_db, step) and covers([_as(granted, step)], step)}
        permissions.append({**asdict(granted), "stops": {
            "actions": sorted(needing),
            "flows": sorted(({"id": entry["id"], "title": entry["title"]} for entry, used in chores if used & needing.keys()),
                            key=lambda flow: flow["id"])}})
    permissions.sort(key=lambda permission: (permission["control"], permission["action"]))
    return {"app": spelling[key], "private": is_private(user_db, app), "actions": actions, "permissions": permissions}


def _as(granted: Consent, step) -> Consent:
    """The consent as this step's app spells it: 'Mail' and 'mail.exe' are one app."""
    return Consent(step.app, granted.control, granted.action)
