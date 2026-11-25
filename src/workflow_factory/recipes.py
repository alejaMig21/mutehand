"""Recipes: an ordered pattern of holes, taught on one app and applied to another by teaching only what differs.

A hole is one place in the pattern that each app fills with its own control. Applying a recipe to an app teaches one step
per hole (named `<recipe>-<hole>`), measuring each one. A hole that fails leaves a doubt that names the hole, and the
recipe stops there: later holes act on the app in order, so they never run past a failure.
"""

import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from workflow_factory.desktop import Desktop, DesktopError
from workflow_factory.queue import Reason, record_doubt
from workflow_factory.steps import ACTIONS, Locator, Sensitivity, find_step
from workflow_factory.tutor import teach_step

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (name TEXT PRIMARY KEY, holes TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recipe_bindings (  -- which step fills which hole, per app
    recipe TEXT NOT NULL, app TEXT NOT NULL, hole TEXT NOT NULL, step TEXT NOT NULL,
    PRIMARY KEY (recipe, app, hole)
);
"""

# what teach_step reports -> the fixed doubt vocabulary
_DOUBT_REASON = {"control_not_found": Reason.CONTROL_NOT_FOUND, "unreadable": Reason.CONTROL_NOT_FOUND}


def _connect(user_db: Path) -> sqlite3.Connection:
    db = sqlite3.connect(user_db)
    db.executescript(SCHEMA)
    return db


def _clean(hole: dict) -> dict:
    name = hole.get("hole")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("every hole needs a hole name")
    for key in ("role", "control_name"):
        if not isinstance(hole.get(key), str) or not hole[key]:
            raise ValueError(f"hole {name!r} needs a {key}")
    action = hole.get("action") or "click"
    if action not in ACTIONS:
        raise ValueError(f"hole {name!r} has an unknown action {action!r}")
    sensitive = hole.get("sensitive")
    if sensitive:
        Sensitivity(sensitive)
    return {"hole": name, "role": hole["role"], "control_name": hole["control_name"],
            "automation_id": hole.get("automation_id"), "action": action, "sensitive": sensitive or None}


def save_recipe(user_db: Path, name: str, holes: list[dict]) -> None:
    """Save (or replace) a recipe: the holes in order, each with the control it was first taught on."""
    cleaned = [_clean(hole) for hole in holes]
    if not cleaned:
        raise ValueError("a recipe needs at least one hole")
    names = [hole["hole"] for hole in cleaned]
    if len(set(names)) != len(names):
        raise ValueError("a hole name is used twice")
    with closing(_connect(user_db)) as db, db:
        db.execute("INSERT OR REPLACE INTO recipes VALUES (?, ?)", (name, json.dumps(cleaned)))


def list_recipes(user_db: Path) -> list[dict]:
    with closing(_connect(user_db)) as db:
        return [{"name": name, "holes": json.loads(holes)}
                for name, holes in db.execute("SELECT name, holes FROM recipes ORDER BY name")]


def _recipe(user_db: Path, name: str) -> dict:
    found = next((recipe for recipe in list_recipes(user_db) if recipe["name"] == name), None)
    if found is None:
        raise ValueError(f"no recipe named {name!r}")
    return found


def recipe_bindings(user_db: Path, recipe: str, app: str) -> dict[str, str]:
    """hole -> the step that fills it on this app."""
    with closing(_connect(user_db)) as db:
        return dict(db.execute("SELECT hole, step FROM recipe_bindings WHERE recipe = ? AND app = ?", (recipe, app)))


def _bind(user_db: Path, recipe: str, app: str, hole: str, step: str) -> None:
    with closing(_connect(user_db)) as db, db:
        db.execute("INSERT OR REPLACE INTO recipe_bindings VALUES (?, ?, ?, ?)", (recipe, app, hole, step))


def mark_step_known(user_db: Path, app: str, recipe: str, hole: str, step: str) -> None:
    """The app already has a step for this hole: bind it without acting on the app."""
    if hole not in {h["hole"] for h in _recipe(user_db, recipe)["holes"]}:
        raise ValueError(f"recipe {recipe!r} has no hole {hole!r}")
    if find_step(user_db, None, app, step) is None:
        raise ValueError(f"{app} has no step named {step!r}")
    _bind(user_db, recipe, app, hole, step)


def apply_recipe(user_db: Path, desktop: Desktop, recipe_name: str, fills: dict | None = None) -> dict:
    """Teach the recipe's steps on the app of `desktop`, one per hole in order.

    `fills` maps a hole to the control this app uses for it ({role, control_name, automation_id?}) or to a step the
    app already has ({known_step}); a hole with no fill is tried on the control the recipe was first taught on.
    """
    recipe, fills = _recipe(user_db, recipe_name), fills or {}
    unknown = set(fills) - {hole["hole"] for hole in recipe["holes"]}
    if unknown:
        raise ValueError(f"recipe {recipe_name!r} has no hole {sorted(unknown)[0]!r}")
    app = desktop.app_key().process
    bound = recipe_bindings(user_db, recipe_name, app)
    results: list[dict] = []
    for hole in recipe["holes"]:
        name, step_name = hole["hole"], f"{recipe_name}-{hole['hole']}"
        fill = fills.get(name)
        if fill and fill.get("known_step"):
            mark_step_known(user_db, app, recipe_name, name, fill["known_step"])
            results.append({"hole": name, "status": "already_known", "step": fill["known_step"]})
            continue
        locator = (Locator(fill["role"], fill["control_name"], fill.get("automation_id")) if fill
                   else Locator(hole["role"], hole["control_name"], hole["automation_id"]))
        existing = find_step(user_db, None, app, bound[name] if name in bound and not fill else step_name)
        if existing and (not fill or existing.locator == locator):
            _bind(user_db, recipe_name, app, name, existing.name)
            results.append({"hole": name, "status": "already_known", "step": existing.name})
            continue
        taught = teach_step(user_db, desktop, step_name, locator, hole["action"],
                            Sensitivity(hole["sensitive"]) if hole["sensitive"] else None)
        if taught["status"] == "consent_required":  # the tutor asks the person, records the consent and applies again
            return {"status": "consent_required", "hole": name, "category": taught["category"],
                    "scope": taught["scope"], "holes": results}
        _bind(user_db, recipe_name, app, name, step_name)
        results.append({"hole": name, "status": taught["status"], "step": step_name})
        if taught["status"] != "saved":
            _doubt(user_db, desktop, recipe_name, name, step_name, taught["status"])
            results += [{"hole": h["hole"], "status": "not_tried", "step": f"{recipe_name}-{h['hole']}"}
                        for h in recipe["holes"][len(results):]]
            return {"status": "stopped", "holes": results}
    return {"status": "applied", "holes": results}


def _doubt(user_db: Path, desktop: Desktop, recipe: str, hole: str, step: str, status: str) -> None:
    try:
        capture = dict(Counter(c.role for c in desktop.snapshot()))  # roles and counts only
    except DesktopError:
        capture = {}
    record_doubt(user_db, f"recipe:{recipe}", hole, step, _DOUBT_REASON.get(status, Reason.PRECONDITION_NOT_MET), capture)
