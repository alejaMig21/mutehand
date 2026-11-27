import asyncio
import json

from mcp.client import Client
from test_knowledge import source_with_templates

from workflow_factory import build_factory, load_flow, save_step
from workflow_factory.flows import flow_summaries
from workflow_factory.mcp_server import build_server

from fake_desktop import FakeDesktop, button, step

EXPECTED_TOOLS = {
    "observe_app", "mark_app_private", "set_study_order", "study_status", "teach_step", "teach_lesson",  # teach_lesson: old name
    "list_open_doubts", "answer_doubt", "record_consent",
    "save_recipe", "list_recipes", "apply_recipe", "mark_step_known",
    "list_known_steps", "create_flow", "flow_status", "list_node_kinds",  # building a chore from a description
}
FORBIDDEN = ("force", "trace", "screenshot", "debug")


def server_for(tmp_path, desktops):
    return build_server(tmp_path / "user.db", lambda app: desktops[app])


def ask(server, tool, arguments=None):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(tool, arguments or {})
    return asyncio.run(go())


def listed_tools(server):
    async def go():
        async with Client(server) as client:
            return (await client.list_tools()).tools
    return asyncio.run(go())


def payload(result):
    return result.structured_content if result.structured_content is not None else json.loads(result.content[0].text)


def test_the_tool_surface_is_exactly_the_tutor_tools_with_no_force_or_trace_option(tmp_path):
    tools = listed_tools(server_for(tmp_path, {}))

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    parameters = [name for tool in tools for name in tool.input_schema.get("properties", {})]
    names = [tool.name for tool in tools] + parameters  # option names, not prose
    assert not [word for word in FORBIDDEN for name in names if word in name.lower()]


def test_observing_a_private_app_through_mcp_returns_roles_and_counts_only(tmp_path):
    desktops = {"telegram.exe": FakeDesktop(controls=[button("Chat with Maria")], app="telegram.exe")}

    result = ask(server_for(tmp_path, desktops), "observe_app", {"app": "telegram.exe"})

    assert payload(result) == {"app": "telegram.exe", "private": True, "roles": {"button": 1}}
    assert "Maria" not in json.dumps(payload(result))


def test_teaching_through_mcp_saves_the_step_and_never_returns_a_secret_value(tmp_path):
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})
    server = server_for(tmp_path, {"paint.exe": desktop})

    first = ask(server, "teach_step", {"app": "paint.exe", "name": "login", "role": "button",
                                         "control_name": "Password", "action": "type_secret",
                                         "secret_ref": "login"})
    ask(server, "record_consent", {"app": "paint.exe", "control": "Password", "action": "type_secret"})
    second = ask(server, "teach_step", {"app": "paint.exe", "name": "login", "role": "button",
                                          "control_name": "Password", "action": "type_secret",
                                          "secret_ref": "login"})

    assert payload(first)["status"] == "consent_required"
    assert payload(second)["status"] == "saved"
    assert "hunter2" not in json.dumps([payload(first), payload(second)])


def test_the_tutor_cannot_grant_a_broad_consent_only_the_user_can(tmp_path):
    server = server_for(tmp_path, {})

    result = ask(server, "record_consent", {"app": "paint.exe", "control": "*", "action": "click"})

    assert result.is_error


def test_adapter_errors_reach_the_tutor_as_a_code_only_never_as_screen_text(tmp_path):
    from workflow_factory.agent_desktop import AgentDesktopError

    def broken(app):
        raise AgentDesktopError("ACTION_FAILED", "could not click 'Chat with Maria'")

    result = ask(build_server(tmp_path / "user.db", broken), "observe_app", {"app": "telegram.exe"})

    assert payload(result) == {"status": "error", "code": "ACTION_FAILED"}
    assert "Maria" not in json.dumps(payload(result))


def test_a_recipe_taught_through_the_tools_is_applied_to_a_second_app(tmp_path):
    desktops = {"a.exe": FakeDesktop(controls=[button("Open"), button("Go")], app="a.exe"),
                "b.exe": FakeDesktop(controls=[button("Open"), button("Start")], app="b.exe")}
    server = server_for(tmp_path, desktops)
    holes = [{"hole": "open", "role": "button", "control_name": "Open"}, {"hole": "go", "role": "button", "control_name": "Go"}]
    ask(server, "save_recipe", {"name": "launch", "holes": holes})

    first = payload(ask(server, "apply_recipe", {"app": "a.exe", "recipe": "launch"}))
    second = payload(ask(server, "apply_recipe", {"app": "b.exe", "recipe": "launch",
                                                  "fills": {"go": {"role": "button", "control_name": "Start"}}}))

    assert first["status"] == "applied" and second["status"] == "applied"
    assert payload(ask(server, "list_recipes"))["result"][0]["name"] == "launch"


# --- building a chore from a description -----------------------------------------------------------------------------------

def taught(tmp_path, *names, app="paint.exe", action="click"):
    for name in names:
        save_step(tmp_path / "user.db", step(name, name.title(), app=app, action=action))


def test_the_tutor_lists_what_the_apprentice_already_knows_of_an_app(tmp_path):
    taught(tmp_path, "open-menu", "save-file")
    taught(tmp_path, "send", app="mail.exe")

    result = payload(ask(server_for(tmp_path, {}), "list_known_steps", {"app": "paint.exe"}))["result"]

    assert sorted(entry["name"] for entry in result) == ["open-menu", "save-file"]
    assert all(set(entry) == {"name", "action", "state"} for entry in result)


def test_a_chore_made_from_steps_the_apprentice_knows_is_saved_ready_and_titled(tmp_path):
    taught(tmp_path, "open-menu", "save-file")
    nodes = [{"id": "a", "step": "open-menu"}, {"id": "b", "step": "save-file"}]

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Morning report", "app": "paint.exe", "nodes": nodes, "edges": [["a", "b"]]}))

    assert made["flow_id"] == "morning-report" and made["ready"] is True and made["missing_steps"] == []
    saved = load_flow(tmp_path / "user.db", None, "morning-report")
    assert [n.step for n in saved.nodes] == ["open-menu", "save-file"] and saved.edges == [("a", "b")]
    assert [f for f in flow_summaries(tmp_path / "user.db", None) if f["id"] == "morning-report"][0]["title"] == "Morning report"


def test_a_chore_that_needs_a_step_not_taught_yet_is_saved_and_says_which_lessons_are_missing(tmp_path):
    taught(tmp_path, "open-menu")
    nodes = [{"id": "a", "step": "open-menu"}, {"id": "b", "step": "send-it"}, {"id": "c", "step": "close-it"}]

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Send report", "app": "paint.exe", "nodes": nodes, "edges": [["a", "b"], ["b", "c"]]}))
    again = payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))

    assert made["ready"] is False and made["why"] == "not_learned"
    assert made["missing_steps"] == ["send-it", "close-it"]
    assert again == {k: made[k] for k in ("flow_id", "ready", "why", "missing_steps")}
    taught(tmp_path, "send-it", "close-it")  # after the lessons, the same chore is ready
    assert payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))["ready"] is True


def test_a_chore_never_replaces_another_one_with_the_same_title(tmp_path):
    taught(tmp_path, "open-menu")
    args = {"title": "Same", "app": "paint.exe", "nodes": [{"id": "a", "step": "open-menu"}], "edges": None}
    server = server_for(tmp_path, {})

    first, second = payload(ask(server, "create_flow", args)), payload(ask(server, "create_flow", args))

    assert first["flow_id"] != second["flow_id"]


def test_a_chore_that_is_not_a_valid_flow_is_refused_and_nothing_is_saved(tmp_path):
    server = server_for(tmp_path, {})

    for nodes in ([{"step": "x"}], [{"id": "a", "kind": "no-such-kind"}], "nope"):
        result = ask(server, "create_flow", {"title": "Bad", "app": "paint.exe", "nodes": nodes, "edges": None})
        assert result.is_error
    assert flow_summaries(tmp_path / "user.db", None) == []


def test_a_node_can_take_many_values_and_give_many_back_through_the_tutor_tool(tmp_path):
    taught(tmp_path, "type-name", action="type_value")
    node = {"id": "a", "step": "type-name", "inputs": [["first", "str"], ["last", "str"], ["age", "int"]]}

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Many values", "app": "paint.exe", "nodes": [node], "edges": None}))

    saved = load_flow(tmp_path / "user.db", None, made["flow_id"])
    assert saved.nodes[0].inputs == (("first", "str"), ("last", "str"), ("age", "int"))


def test_the_tutor_can_ask_which_kinds_of_box_and_data_operations_exist_and_how_a_field_is_written(tmp_path):
    kinds = payload(ask(server_for(tmp_path, {}), "list_node_kinds"))

    assert {"step", "if", "join", "loop", "trigger", "foreach", "wait", "stop", "data"} <= set(kinds["kinds"])
    assert kinds["data_operations"]["math"] == {"required": ["a", "b", "operation"], "optional": []}
    assert kinds["data_operations"]["split"]["optional"] == ["trim"]
    assert {"value", "ref", "expression"} == {form["form"] for form in kinds["field_forms"]}


def test_a_data_box_written_from_the_listed_operations_is_saved_and_a_misspelled_one_is_refused(tmp_path):
    taught(tmp_path, "open-menu")
    good = {"id": "d", "kind": "data", "op": "math", "fields": {"a": {"value": 1}, "b": {"value": 2}, "operation": {"value": "add"}}}
    bad = {"id": "d", "kind": "data", "op": "mathh", "fields": {}}
    server = server_for(tmp_path, {})

    saved = payload(ask(server, "create_flow", {"title": "Sum", "app": "paint.exe", "nodes": [good], "edges": None}))
    refused = ask(server, "create_flow", {"title": "Typo", "app": "paint.exe", "nodes": [bad], "edges": None})

    assert saved["flow_id"] == "sum" and refused.is_error


def test_the_known_steps_of_a_private_app_are_counted_and_never_named(tmp_path):
    taught(tmp_path, "send-it", "pick-chat", app="telegram.exe")
    server = server_for(tmp_path, {})
    ask(server, "mark_app_private", {"app": "telegram.exe"})

    result = payload(ask(server, "list_known_steps", {"app": "telegram.exe"}))["result"]

    assert result == [{"private": True, "count": 2}]
    assert "send-it" not in json.dumps(result)


def test_what_the_factory_already_knows_counts_when_a_chore_is_made_through_the_tutor_tools(tmp_path):
    build_factory(tmp_path / "factory.db", source_with_templates())
    server = build_server(tmp_path / "user.db", lambda app: None, factory_db=tmp_path / "factory.db")

    known = payload(ask(server, "list_known_steps", {"app": "paint.exe"}))["result"]
    made = payload(ask(server, "create_flow", {"title": "From the factory", "app": "paint.exe",
                                               "nodes": [{"id": "a", "step": "open-menu"}], "edges": None}))

    assert [entry["name"] for entry in known] == ["open-menu"]
    assert made["ready"] is True and made["missing_steps"] == []
