"""What an earlier version wrote (it called a step a lesson) must still open after the rename. Nothing is lost."""

import asyncio
import json
import sqlite3
import urllib.request
from contextlib import closing

from mcp.client import Client

from workflow_factory import (
    Flow,
    Node,
    export_knowledge,
    find_step,
    import_knowledge,
    list_doubts,
    list_steps,
    load_flow,
    save_flow,
    save_step,
)
from workflow_factory.api import ApiServer
from workflow_factory.mcp_server import build_server

from fake_desktop import FakeDesktop, button, step

LEGACY_LESSONS = """
CREATE TABLE lessons (
    app TEXT NOT NULL, version TEXT NOT NULL, name TEXT NOT NULL, precondition TEXT NOT NULL, action TEXT NOT NULL,
    role TEXT NOT NULL, control_name TEXT NOT NULL, automation_id TEXT, effect TEXT NOT NULL, origin TEXT NOT NULL,
    status TEXT NOT NULL, factory_successes INTEGER NOT NULL DEFAULT 0, factory_failures INTEGER NOT NULL DEFAULT 0,
    frame TEXT, mask TEXT, capture BLOB, sensitive TEXT, secret_ref TEXT, derived TEXT, template TEXT, drag_to TEXT,
    PRIMARY KEY (app, name)
)
"""
LEGACY_STATE = """
CREATE TABLE lesson_state (
    app TEXT NOT NULL, name TEXT NOT NULL, local_successes INTEGER NOT NULL DEFAULT 0,
    local_failures INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0, restored INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (app, name)
)
"""
LEGACY_DOUBTS = """
CREATE TABLE doubts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, flow_id TEXT NOT NULL, node_id TEXT NOT NULL, lesson TEXT NOT NULL,
    reason TEXT NOT NULL, capture TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', note TEXT
)
"""
OLD_ROW = ("paint.exe", "1.0", "pencil", "", "click", "button", "Pencil", None, "no_change", "local", "trusted", 0, 0,
           None, None, None, None, None, None, None, None)


def legacy_database(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(LEGACY_LESSONS)
        db.execute(LEGACY_STATE)
        db.execute(LEGACY_DOUBTS)
        db.execute("INSERT INTO lessons VALUES (" + ",".join("?" * 21) + ")", OLD_ROW)
        db.execute("INSERT INTO lesson_state VALUES ('paint.exe', 'pencil', 5, 1, 0, 0)")
        db.execute("INSERT INTO doubts (flow_id, node_id, lesson, reason, capture) VALUES ('f', 'n', 'pencil', 'control_not_found', '{}')")


def tables(path):
    with closing(sqlite3.connect(path)) as db:
        return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_a_database_written_before_the_rename_opens_with_every_step_intact(tmp_path):
    user_db = tmp_path / "user.db"
    legacy_database(user_db)

    steps = list_steps(user_db, None)

    assert [(s.app, s.name, s.locator.name) for s in steps] == [("paint.exe", "pencil", "Pencil")]
    assert find_step(user_db, None, "paint.exe", "pencil") is not None
    with closing(sqlite3.connect(user_db)) as db:
        assert db.execute("SELECT local_successes, local_failures FROM step_state").fetchall() == [(5, 1)]  # counters kept
    assert {"steps", "step_state"} <= tables(user_db) and not {"lessons", "lesson_state"} & tables(user_db)


def test_a_doubt_left_before_the_rename_is_still_listed_under_its_step(tmp_path):
    user_db = tmp_path / "user.db"
    legacy_database(user_db)

    doubts = list_doubts(user_db)

    assert [(d.flow_id, d.node_id, d.step) for d in doubts] == [("f", "n", "pencil")]


def test_opening_a_migrated_database_again_changes_nothing(tmp_path):
    user_db = tmp_path / "user.db"
    legacy_database(user_db)

    first = list_steps(user_db, None)
    second = list_steps(user_db, None)

    assert first == second and len(second) == 1


def test_a_flow_saved_before_the_rename_loads_with_its_old_keys(tmp_path):
    user_db = tmp_path / "user.db"
    old = {"nodes": [{"id": "a", "lesson": "pencil", "kind": "lesson", "inputs": []}], "edges": None}
    with closing(sqlite3.connect(user_db)) as db, db:
        db.execute("CREATE TABLE flows (id TEXT PRIMARY KEY, definition TEXT NOT NULL)")
        db.execute("INSERT INTO flows VALUES ('old', ?)", (json.dumps(old),))

    flow = load_flow(user_db, None, "old")

    assert [(n.id, n.kind, n.step) for n in flow.nodes] == [("a", "step", "pencil")]


def test_a_knowledge_file_exported_before_the_rename_still_imports(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    save_step(source, step("pencil", "Pencil"))
    save_flow(source, Flow(id="draw", nodes=[Node("a", "pencil")]))
    exported = json.loads(json.dumps(export_knowledge(source)))
    exported["lessons"] = exported.pop("steps")  # how the earlier version named it
    for flow in exported["flows"]:
        for node in flow["nodes"]:
            node["lesson"] = node.pop("step")
            node["kind"] = "lesson" if node["kind"] == "step" else node["kind"]

    import_knowledge(target, exported)

    assert [s.name for s in list_steps(target, None)] == ["pencil"]
    assert [n.step for n in load_flow(target, None, "draw").nodes] == ["pencil"]


def test_a_read_only_factory_file_that_still_calls_its_table_lessons_is_read(tmp_path):
    factory = tmp_path / "factory.db"
    legacy_database(factory)

    steps = list_steps(tmp_path / "user.db", factory)

    assert [s.name for s in steps] == ["pencil"]


def test_the_old_api_path_still_answers_like_the_new_one(tmp_path):
    save_step(tmp_path / "user.db", step("pencil", "Pencil"))
    server = ApiServer(tmp_path / "user.db", None, lambda app: FakeDesktop(controls=[button("Pencil")]), token="t")
    server.start()
    try:
        def get(path):
            request = urllib.request.Request(server.url + path)
            request.add_header("Authorization", "Bearer t")
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())

        assert get("/api/lessons") == get("/api/steps") and len(get("/api/steps")) == 1
    finally:
        server.stop()


def test_the_old_tutor_tool_name_is_still_offered_next_to_the_new_one(tmp_path):
    server = build_server(tmp_path / "user.db", lambda app: FakeDesktop(controls=[button("Pencil")]))

    async def names():
        async with Client(server) as client:
            return {tool.name for tool in (await client.list_tools()).tools}

    offered = asyncio.run(names())

    assert {"teach_step", "teach_lesson"} <= offered
