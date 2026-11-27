"""The playbook is followed end to end through the real MCP protocol on a simple app, and what it taught shows up for the editor."""

import asyncio
import json
import re
from pathlib import Path

from mcp.client import Client
from test_api import call

from workflow_factory import Flow, Node, run_flow
from workflow_factory.api import ApiServer
from workflow_factory.mcp_server import build_server

from fake_desktop import FakeDesktop, button

ROOT = Path(__file__).resolve().parent.parent


def ask(server, tool, arguments=None):
    async def go():
        async with Client(server) as client:
            result = await client.call_tool(tool, arguments or {})
            return result.structured_content if result.structured_content is not None else json.loads(result.content[0].text)
    return asyncio.run(go())


def tool_names(server):
    async def go():
        async with Client(server) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
    return asyncio.run(go())


def test_the_playbook_names_every_tutor_tool_so_it_cannot_drift_from_the_server(tmp_path):
    playbook = (ROOT / "docs" / "agents" / "tutor.md").read_text(encoding="utf-8")

    missing = [name for name in tool_names(build_server(tmp_path / "user.db", lambda app: None)) if name not in playbook]

    assert missing == []


def tool_arguments(server):
    async def go():
        async with Client(server) as client:
            return {t.name: set(t.input_schema.get("properties", {})) for t in (await client.list_tools()).tools}
    return asyncio.run(go())


def test_every_call_the_playbook_writes_names_a_real_tool_with_exactly_its_arguments(tmp_path):
    playbook = (ROOT / "docs" / "agents" / "tutor.md").read_text(encoding="utf-8")
    tools = tool_arguments(build_server(tmp_path / "user.db", lambda app: None))
    calls = re.findall(r"`([a-z]+(?:_[a-z]+)+)\(([^)]*)\)`", playbook)

    unknown = [name for name, _ in calls if name not in tools]
    wrong = [(name, args) for name, args in calls if name in tools
             and {a.strip().rstrip("?") for a in args.split(",") if a.strip()} != tools[name]]
    unwritten = [name for name in tools if name not in [n for n, _ in calls]]

    assert (unknown, wrong, unwritten) == ([], [], [])


def test_claude_md_only_points_to_the_playbook_and_never_repeats_how_to_teach():
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    playbook_tools = ("teach_step", "apply_recipe", "record_consent", "answer_doubt", "observe_app")

    assert "docs/agents/tutor.md" in claude
    assert not [name for name in playbook_tools if name in claude]


def test_a_session_that_follows_the_playbook_leaves_steps_the_editor_lists_and_a_flow_can_use(tmp_path):
    notes = FakeDesktop(controls=[button("New note"), button("Title"), button("Send to team")], app="notes.exe")
    notes.texts = {"Title": "Quarterly report"}
    server = build_server(tmp_path / "user.db", lambda app: notes)

    observed = ask(server, "observe_app", {"app": "notes.exe"})  # step 3: look first
    assert observed["private"] is False

    ask(server, "set_study_order", {"app": "notes.exe", "steps": [  # step 4: plan before teaching
        {"name": "Open note", "role": "button", "control_name": "New note"},
        {"name": "Read title", "role": "button", "control_name": "Title"}]})
    assert ask(server, "study_status", {"app": "notes.exe"})["next"]["name"] == "Open note"

    taught = ask(server, "teach_step", {"app": "notes.exe", "name": "Open note", "role": "button", "control_name": "New note"})
    assert taught["status"] == "saved"
    read = ask(server, "teach_step", {"app": "notes.exe", "name": "Read title", "role": "button", "control_name": "Title",
                                      "action": "read_value"})
    assert read["status"] == "saved"
    assert ask(server, "study_status", {"app": "notes.exe"})["done"] == 2  # resumable: both are saved

    sending = {"app": "notes.exe", "name": "Send", "role": "button", "control_name": "Send to team"}
    needs = ask(server, "teach_step", sending)  # step 5: a sensitive action asks first
    assert needs["status"] == "consent_required" and notes.clicks[-1].name == "New note"  # nothing was clicked for it
    ask(server, "record_consent", {"app": "notes.exe", "control": "Send to team", "action": "click"})
    assert ask(server, "teach_step", sending)["status"] == "saved"

    api = ApiServer(tmp_path / "user.db", None, lambda app: notes, token="secret-token")
    api.start()
    try:
        listed = {s["name"]: s for s in call(api, "/api/steps")[1]}  # step 7: they are the nodes the editor offers
    finally:
        api.stop()
    assert set(listed) == {"Open note", "Read title", "Send"} and listed["Send"]["consent"] == "given"
    assert listed["Read title"]["action"] == "read_value"

    flow = Flow(id="f", nodes=[Node("a", "Open note"), Node("b", "Read title"), Node("c", "Send")])
    result = run_flow(flow, desktop=notes, user_db=tmp_path / "user.db")
    assert result.status == "finished" and result.outputs["b"]["value"] == "Quarterly report"
