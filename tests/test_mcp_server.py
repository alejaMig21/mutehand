import asyncio
import json

from mcp.client import Client
from test_knowledge import source_with_templates

from workflow_factory import build_factory, load_flow, save_step
from workflow_factory.flows import flow_summaries
from workflow_factory.mcp_server import build_server
from workflow_factory.steps import add_tags

from fake_desktop import FakeDesktop, button, step

EXPECTED_TOOLS = {
    "observe_app", "mark_app_private", "set_study_order", "study_status", "teach_step", "teach_lesson",  # teach_lesson: old name
    "list_open_doubts", "answer_doubt", "record_consent",
    "save_recipe", "list_recipes", "apply_recipe", "mark_step_known",
    "list_known_steps", "create_flow", "flow_status", "list_node_kinds",  # building a flow from a description
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


def teach(server, app, name, control_name, **more):
    return payload(ask(server, "teach_step", {"app": app, "name": name, "role": "button",
                                                "control_name": control_name, **more}))


def two_technologies(tmp_path):
    paint = FakeDesktop(controls=[button("Save")], app="paint.exe")  # a click that changes nothing
    excel = FakeDesktop(controls=[button("Save as")], app="excel.exe", product_name="Microsoft Excel",
                        reveals={("button", "Save as"): [button("Folder"), button("File name")]})
    return server_for(tmp_path, {"paint.exe": paint, "excel.exe": excel}), paint, excel


def test_teaching_the_same_name_on_another_technology_adds_a_locator_and_keeps_the_first(tmp_path):
    from workflow_factory import find_step, list_steps, step_report
    from workflow_factory.steps import record_outcome

    server, _, _ = two_technologies(tmp_path)
    db = tmp_path / "user.db"

    first = teach(server, "paint.exe", "Save", "Save")
    record_outcome(db, find_step(db, None, "paint.exe", "Save"), True)
    second = teach(server, "excel.exe", "Save", "Save as")

    assert first["status"] == second["status"] == "saved"
    rows = {s.app: s for s in list_steps(db, None)}
    assert set(rows) == {"paint.exe", "excel.exe"} and {s.name for s in rows.values()} == {"Save"}
    assert rows["paint.exe"].locator.name == "Save" and rows["excel.exe"].locator.name == "Save as"
    assert rows["paint.exe"].effect != rows["excel.exe"].effect  # each locator keeps what it measured
    assert step_report(db, rows["paint.exe"])["successes"] == 1  # the counter of one is not the other's
    assert step_report(db, rows["excel.exe"])["successes"] == 0


def test_a_name_with_a_technology_in_it_is_refused_before_the_app_is_touched_and_nothing_is_saved(tmp_path):
    from workflow_factory import list_steps

    server, paint, excel = two_technologies(tmp_path)
    teach(server, "paint.exe", "Save", "Save")  # makes paint a known technology
    excel.calls.clear()

    refused = [teach(server, "excel.exe", name, "Save as") for name in (
        "Save workbook in Excel", "Excel save", "excel.exe save", "Microsoft Excel save", "EXCEL-save")]
    other = teach(server, "excel.exe", "Paint a border", "Save as")  # a technology known from another step

    for answer in (*refused, other):
        assert answer["status"] == "name_has_technology"
        assert "must say what it does" in answer["message"] and "technology" in answer["message"]
    assert excel.calls == []  # the refusal came before the app was touched
    assert [s.app for s in list_steps(tmp_path / "user.db", None)] == ["paint.exe"]


def test_a_name_that_only_looks_like_a_technology_is_taught(tmp_path):
    server, _, _ = two_technologies(tmp_path)

    assert teach(server, "excel.exe", "Excellent save", "Save as")["status"] == "saved"


def test_the_refusal_names_the_rule_and_never_the_screen(tmp_path):
    server, _, _ = two_technologies(tmp_path)

    answer = teach(server, "excel.exe", "Excel save", "Save as")

    assert "Folder" not in json.dumps(answer) and "File name" not in json.dumps(answer)


def test_pattern_tags_are_kept_returned_and_merged_when_taught_on_another_technology(tmp_path):
    server, _, _ = two_technologies(tmp_path)

    first = teach(server, "paint.exe", "Save", "Save", tags=["File", "mouse", " file "])
    second = teach(server, "excel.exe", "Save", "Save as", tags=["disk"])
    third = teach(server, "paint.exe", "Save", "Save")  # no tags given: nothing is lost

    assert first["tags"] == ["file", "mouse"]
    assert second["tags"] == ["disk", "file", "mouse"]
    assert third["tags"] == ["disk", "file", "mouse"]


def test_a_refused_name_keeps_no_tags(tmp_path):
    from workflow_factory.steps import step_tags

    server, _, _ = two_technologies(tmp_path)
    teach(server, "excel.exe", "Excel save", "Save as", tags=["file"])

    assert step_tags(tmp_path / "user.db", "Excel save") == []


# --- building a flow from a description -----------------------------------------------------------------------------------

def taught(tmp_path, *names, app="paint.exe", action="click"):
    for name in names:
        save_step(tmp_path / "user.db", step(name, name.title(), app=app, action=action))


def test_the_tutor_lists_what_the_apprentice_already_knows_of_an_app(tmp_path):
    taught(tmp_path, "open-menu", "save-file")
    taught(tmp_path, "send", app="mail.exe")

    result = payload(ask(server_for(tmp_path, {}), "list_known_steps", {"technology": "paint.exe"}))["result"]

    assert sorted(entry["name"] for entry in result) == ["open-menu", "save-file"]
    assert all(set(entry) == {"name", "action", "tags", "technologies", "state"} for entry in result)


def test_a_flow_made_from_steps_the_apprentice_knows_is_saved_ready_and_titled(tmp_path):
    taught(tmp_path, "open-menu", "save-file")
    nodes = [{"id": "a", "step": "open-menu", "technology": "paint.exe"}, {"id": "b", "step": "save-file", "technology": "paint.exe"}]

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Morning report", "nodes": nodes, "edges": [["a", "b"]]}))

    assert made["flow_id"] == "morning-report" and made["ready"] is True and made["missing_lessons"] == []
    saved = load_flow(tmp_path / "user.db", None, "morning-report")
    assert [n.step for n in saved.nodes] == ["open-menu", "save-file"] and saved.edges == [("a", "b")]
    assert [f for f in flow_summaries(tmp_path / "user.db", None) if f["id"] == "morning-report"][0]["title"] == "Morning report"


def test_a_flow_that_needs_a_step_not_taught_yet_is_saved_and_says_which_lessons_are_missing(tmp_path):
    taught(tmp_path, "open-menu")
    nodes = [{"id": "a", "step": "open-menu", "technology": "paint.exe"}, {"id": "b", "step": "send-it", "technology": "paint.exe"},
             {"id": "c", "step": "close-it", "technology": "paint.exe"}]

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Send report", "nodes": nodes, "edges": [["a", "b"], ["b", "c"]]}))
    again = payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))

    assert made["ready"] is False and made["why"] == "not_learned"
    assert made["missing_lessons"] == [{"node": "b", "step": "send-it", "technology": "paint.exe"},
                                       {"node": "c", "step": "close-it", "technology": "paint.exe"}]
    assert again == {k: made[k] for k in ("flow_id", "ready", "why", "missing_lessons")}
    taught(tmp_path, "send-it", "close-it")  # after the lessons, the same flow is ready
    assert payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))["ready"] is True


# --- flows that name the technology of each node ------------------------------------------------------------------------

def two_program_flow(tmp_path):
    taught(tmp_path, "open-menu", app="paint.exe")
    nodes = [{"id": "a", "step": "open-menu", "technology": "paint.exe"},
             {"id": "b", "step": "open-menu", "technology": "notepad.exe"}]
    return ask(server_for(tmp_path, {}), "create_flow", {"title": "Two programs", "nodes": nodes, "edges": [["a", "b"]]})


def test_a_flow_of_two_programs_is_saved_ready_when_both_are_learned(tmp_path):
    taught(tmp_path, "open-menu", app="paint.exe")
    taught(tmp_path, "open-menu", app="notepad.exe")

    made = payload(two_program_flow(tmp_path))

    assert made["ready"] is True and made["missing_lessons"] == []
    assert [n.technology for n in load_flow(tmp_path / "user.db", None, made["flow_id"]).nodes] == ["paint.exe", "notepad.exe"]


def test_a_flow_of_two_programs_with_one_not_learned_is_saved_and_names_that_node_and_turns_ready_once_taught(tmp_path):
    made = payload(two_program_flow(tmp_path))

    assert made["ready"] is False and made["why"] == "not_learned"
    assert made["missing_lessons"] == [{"node": "b", "step": "open-menu", "technology": "notepad.exe"}]
    assert load_flow(tmp_path / "user.db", None, made["flow_id"]).nodes[1].technology == "notepad.exe"
    status = payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))
    assert status["missing_lessons"] == made["missing_lessons"]
    taught(tmp_path, "open-menu", app="notepad.exe")
    status = payload(ask(server_for(tmp_path, {}), "flow_status", {"flow_id": made["flow_id"]}))
    assert status["ready"] is True and status["missing_lessons"] == []


def test_a_node_naming_a_technology_the_step_does_not_have_is_the_missing_lesson_not_an_error(tmp_path):
    taught(tmp_path, "open-menu", app="paint.exe")
    node = {"id": "a", "step": "open-menu", "technology": "sheet.exe"}

    result = ask(server_for(tmp_path, {}), "create_flow", {"title": "Other program", "nodes": [node], "edges": None})

    assert not result.is_error
    assert payload(result)["missing_lessons"] == [{"node": "a", "step": "open-menu", "technology": "sheet.exe"}]


def test_a_step_node_naming_no_technology_is_refused_and_nothing_is_saved(tmp_path):
    taught(tmp_path, "open-menu")
    server = server_for(tmp_path, {})

    for node in ({"id": "a", "step": "open-menu"}, {"id": "a", "step": "open-menu", "technology": "  "},
                 {"id": "a", "step": "open-menu", "technology": 7}):
        assert ask(server, "create_flow", {"title": "No program", "nodes": [node], "edges": None}).is_error
    assert flow_summaries(tmp_path / "user.db", None) == []


def test_the_flow_level_app_argument_is_gone(tmp_path):
    properties = {t.name: t.input_schema["properties"] for t in listed_tools(server_for(tmp_path, {}))}["create_flow"]

    assert "app" not in properties


def test_a_flow_never_replaces_another_one_with_the_same_title(tmp_path):
    taught(tmp_path, "open-menu")
    args = {"title": "Same", "nodes": [{"id": "a", "step": "open-menu", "technology": "paint.exe"}], "edges": None}
    server = server_for(tmp_path, {})

    first, second = payload(ask(server, "create_flow", args)), payload(ask(server, "create_flow", args))

    assert first["flow_id"] != second["flow_id"]


def test_a_flow_that_is_not_a_valid_flow_is_refused_and_nothing_is_saved(tmp_path):
    server = server_for(tmp_path, {})

    for nodes in ([{"step": "x"}], [{"id": "a", "kind": "no-such-kind"}], "nope"):
        result = ask(server, "create_flow", {"title": "Bad", "nodes": nodes, "edges": None})
        assert result.is_error
    assert flow_summaries(tmp_path / "user.db", None) == []


def test_a_node_can_take_many_values_and_give_many_back_through_the_tutor_tool(tmp_path):
    taught(tmp_path, "type-name", action="type_value")
    node = {"id": "a", "step": "type-name", "technology": "paint.exe", "inputs": [["first", "str"], ["last", "str"], ["age", "int"]]}

    made = payload(ask(server_for(tmp_path, {}), "create_flow", {
        "title": "Many values", "nodes": [node], "edges": None}))

    saved = load_flow(tmp_path / "user.db", None, made["flow_id"])
    assert saved.nodes[0].inputs == (("first", "str"), ("last", "str"), ("age", "int"))


def test_the_tutor_can_ask_which_kinds_of_node_and_data_operations_exist_and_how_a_field_is_written(tmp_path):
    kinds = payload(ask(server_for(tmp_path, {}), "list_node_kinds"))

    assert {"step", "if", "join", "loop", "trigger", "foreach", "wait", "stop", "data"} <= set(kinds["kinds"])
    assert kinds["data_operations"]["math"] == {"required": ["a", "b", "operation"], "optional": []}
    assert kinds["data_operations"]["split"]["optional"] == ["trim"]
    assert {"value", "ref", "expression"} == {form["form"] for form in kinds["field_forms"]}


def test_a_data_node_written_from_the_listed_operations_is_saved_and_a_misspelled_one_is_refused(tmp_path):
    taught(tmp_path, "open-menu")
    good = {"id": "d", "kind": "data", "op": "math", "fields": {"a": {"value": 1}, "b": {"value": 2}, "operation": {"value": "add"}}}
    bad = {"id": "d", "kind": "data", "op": "mathh", "fields": {}}
    server = server_for(tmp_path, {})

    saved = payload(ask(server, "create_flow", {"title": "Sum", "nodes": [good], "edges": None}))
    refused = ask(server, "create_flow", {"title": "Typo", "nodes": [bad], "edges": None})

    assert saved["flow_id"] == "sum" and refused.is_error


def test_the_known_steps_of_a_private_app_are_counted_and_never_named(tmp_path):
    taught(tmp_path, "send-it", "pick-chat", app="telegram.exe")
    server = server_for(tmp_path, {})
    ask(server, "mark_app_private", {"app": "telegram.exe"})

    result = payload(ask(server, "list_known_steps", {"technology": "telegram.exe"}))["result"]

    assert result == [{"private": True, "count": 2}]
    assert "send-it" not in json.dumps(result)


def test_what_the_factory_already_knows_counts_when_a_flow_is_made_through_the_tutor_tools(tmp_path):
    build_factory(tmp_path / "factory.db", source_with_templates())
    server = build_server(tmp_path / "user.db", lambda app: None, factory_db=tmp_path / "factory.db")

    known = payload(ask(server, "list_known_steps", {"technology": "paint.exe"}))["result"]
    made = payload(ask(server, "create_flow", {"title": "From the factory",
                                               "nodes": [{"id": "a", "step": "open-menu", "technology": "paint.exe"}], "edges": None}))

    assert [entry["name"] for entry in known] == ["open-menu"]
    assert made["ready"] is True and made["missing_lessons"] == []


# --- listing steps by technology, tag or text ---------------------------------------------------------------------------

def listing(tmp_path, **arguments):
    return payload(ask(server_for(tmp_path, {}), "list_known_steps", arguments))["result"]


def taught_with_tags(tmp_path):
    taught(tmp_path, "Save", app="paint.exe")
    taught(tmp_path, "Save", "Pick colour", app="notepad.exe")
    taught(tmp_path, "Éxport data", app="sheet.exe")
    add_tags(tmp_path / "user.db", "Save", ["File"])
    add_tags(tmp_path / "user.db", "Pick colour", ["mouse"])


def test_a_step_known_on_several_technologies_is_listed_once_with_all_of_them_and_its_tags(tmp_path):
    taught_with_tags(tmp_path)

    result = {entry["name"]: entry for entry in listing(tmp_path)}

    assert sorted(result) == ["Pick colour", "Save", "Éxport data"]
    assert result["Save"]["technologies"] == ["notepad.exe", "paint.exe"] and result["Save"]["tags"] == ["file"]
    assert set(result["Save"]) == {"name", "action", "tags", "technologies", "state"}


def test_listing_by_technology_by_tag_and_by_text(tmp_path):
    taught_with_tags(tmp_path)

    def names(**arguments):
        return sorted(entry["name"] for entry in listing(tmp_path, **arguments))

    assert names(technology="sheet.exe") == ["Éxport data"]
    assert names(tag="FILE") == ["Save"]
    assert names(query="sav") == ["Save"]  # the start of a word
    assert names(query="EXPORT") == ["Éxport data"]  # capitals and accents are ignored, both ways
    assert names(query="sheet") == ["Éxport data"]  # a technology tag
    assert names(query="mou") == ["Pick colour"]  # a pattern tag
    assert names(query="pick col") == ["Pick colour"] and names(query="pick save") == []  # every word must match
    assert names(technology="notepad.exe", tag="mouse") == ["Pick colour"]


def test_a_private_technology_is_counted_never_named_and_gives_no_tags(tmp_path):
    taught(tmp_path, "send-it", app="telegram.exe")
    taught(tmp_path, "Save", app="paint.exe")
    taught(tmp_path, "Save", app="telegram.exe")
    add_tags(tmp_path / "user.db", "send-it", ["chat"])
    server = server_for(tmp_path, {})
    ask(server, "mark_app_private", {"app": "telegram.exe"})

    everything = payload(ask(server, "list_known_steps", {}))["result"]
    by_tag = payload(ask(server, "list_known_steps", {"tag": "chat"}))["result"]
    by_text = payload(ask(server, "list_known_steps", {"query": "send"}))["result"]

    assert [e["name"] for e in everything if "name" in e] == ["Save"]
    assert everything[0]["technologies"] == ["paint.exe"] and everything[0]["tags"] == []
    assert {"private": True, "count": 1} in everything  # only the step that exists nowhere else counts
    assert by_tag == [] and by_text == []
    assert "telegram" not in json.dumps(everything) and "send-it" not in json.dumps(everything)
