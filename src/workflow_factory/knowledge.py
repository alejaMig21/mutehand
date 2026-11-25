"""Knowledge as files: export/import JSON for review and git, the factory build, template copies.

An export holds lessons and flows only. Consents are never exported and importing never grants one:
a consent is the person's own yes, given while teaching (ADR 0002). Secret values do not exist in
the database (lessons hold references into the Windows credential store), so none can leak here.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from workflow_factory.flows import SCHEMA as FLOW_SCHEMA
from workflow_factory.flows import flow_from_dict, flow_to_dict, list_flows, load_flow, save_flow
from workflow_factory.lessons import (
    SCHEMA as LESSON_SCHEMA,
)
from workflow_factory.lessons import (
    Origin,
    Status,
    find_lesson,
    forget_state,
    lesson_from_dict,
    lesson_report,
    lesson_to_dict,
    list_lessons,
    save_lesson,
)
from workflow_factory.paths import default_user_db

FORMAT_VERSION = 1
MAX_IMPORT_BYTES = 64 * 1024 * 1024
FLOW_ID = re.compile(r"[\w.-]+")


def export_knowledge(user_db: Path) -> dict:
    flows = [load_flow(user_db, None, entry["id"]) for entry in list_flows(user_db, None)]
    lessons = []
    for lesson in list_lessons(user_db, None):
        data = lesson_to_dict(lesson)
        if lesson_report(user_db, lesson)["state"] == "rejected":
            data["status"] = "rejected"  # a person's rejection travels with the lesson
        lessons.append(data)
    return {"version": FORMAT_VERSION, "lessons": lessons, "flows": [flow_to_dict(flow) for flow in flows]}


def _parse(data: dict, origin: Origin):
    """Everything is checked before anything is written, so a bad file changes nothing."""
    if not isinstance(data, dict):
        raise ValueError("the file must hold a JSON object")
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"unsupported knowledge format version {data.get('version')!r}")
    try:
        lessons = [lesson_from_dict(item) for item in data["lessons"]]
        flows = []
        for item in data["flows"]:
            if not FLOW_ID.fullmatch(str(item["id"])):
                raise ValueError(f"flow id {item['id']!r} may only use letters, digits, '_', '.' and '-'")
            flows.append(flow_from_dict(item["id"], item))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"the file is not valid knowledge: {error}") from None
    if origin == Origin.LOCAL:  # a file from elsewhere cannot vouch for itself
        keep = (Status.REJECTED, Status.TO_REVALIDATE)  # it may only make a lesson less trusted
        lessons = [replace(lesson, origin=origin, factory_successes=0, factory_failures=0,
                           status=lesson.status if lesson.status in keep else Status.SUSPECT)
                   for lesson in lessons]
    else:
        lessons = [replace(lesson, origin=origin) for lesson in lessons]
    return lessons, flows


def import_knowledge(user_db: Path, data: dict, overwrite: bool = False) -> None:
    """Add the lessons and flows to the user's knowledge.

    Nothing is trusted from the file: counters and a trusted status are reset, no consent is ever
    imported, and a lesson or flow the person already has is never replaced unless `overwrite`.
    """
    lessons, flows = _parse(data, Origin.LOCAL)
    clashes = [f"lesson {lesson.name!r}" for lesson in lessons if find_lesson(user_db, None, lesson.app, lesson.name)]
    clashes += [f"flow {flow.id!r}" for flow in flows if load_flow(user_db, None, flow.id)]
    if clashes and not overwrite:
        raise ValueError("already exists: " + ", ".join(clashes) + " (use overwrite to replace)")
    for lesson in lessons:
        forget_state(user_db, lesson.app, lesson.name)  # old counters mean nothing for new knowledge
        save_lesson(user_db, lesson)
    for flow in flows:
        save_flow(user_db, flow)


def build_factory(out_path: Path, data: dict) -> None:
    """Write the read-only factory file shipped with a build; a failed build never touches `out_path`."""
    lessons, flows = _parse(data, Origin.FACTORY)
    with tempfile.TemporaryDirectory(dir=out_path.parent, prefix=out_path.stem + "-") as folder:
        temporary = Path(folder) / out_path.name  # same volume as out_path, so the replace is atomic
        with closing(sqlite3.connect(temporary)) as db, db:  # an empty source still gives a valid file
            db.execute(LESSON_SCHEMA)
            db.execute(FLOW_SCHEMA)
        for lesson in lessons:
            save_lesson(temporary, lesson)
        for flow in flows:
            save_flow(temporary, flow)
        os.replace(temporary, out_path)


def duplicate_flow(user_db: Path, factory_db: Path | None, flow_id: str, new_id: str):
    """Copy a flow (typically a factory template) into the user layer, where it can be edited."""
    if not FLOW_ID.fullmatch(new_id):
        raise ValueError("a flow id may only use letters, digits, '_', '.' and '-'")
    original = load_flow(user_db, factory_db, flow_id)
    if original is None:
        raise ValueError(f"no flow named {flow_id!r}")
    if load_flow(user_db, None, new_id) is not None:
        raise ValueError(f"a flow named {new_id!r} already exists")
    copy = replace(original, id=new_id)
    save_flow(user_db, copy)
    return copy


def _read_json(path: Path):
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError(f"{path.name} is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="workflow_factory.knowledge")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write the user knowledge (lessons and flows) as JSON")
    export.add_argument("--user-db", type=Path, default=default_user_db())
    export.add_argument("--out", type=Path, help="file to write (default: standard output)")
    imp = commands.add_parser("import", help="add lessons and flows from a JSON file")
    imp.add_argument("--user-db", type=Path, default=default_user_db())
    imp.add_argument("file", type=Path)
    imp.add_argument("--overwrite", action="store_true", help="replace lessons and flows that already exist")
    build = commands.add_parser("build-factory", help="build the read-only factory file from a JSON file")
    build.add_argument("source", type=Path)
    build.add_argument("out", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "export":
            text = json.dumps(export_knowledge(args.user_db), indent=2, sort_keys=True)
            if args.out:
                args.out.write_text(text, encoding="utf-8")
            else:
                print(text)
        elif args.command == "import":
            import_knowledge(args.user_db, _read_json(args.file), overwrite=args.overwrite)
        else:
            build_factory(args.out, _read_json(args.source))
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
