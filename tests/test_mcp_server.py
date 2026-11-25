import asyncio
import json

from mcp.client import Client

from workflow_factory.mcp_server import build_server

from fake_desktop import FakeDesktop, button

EXPECTED_TOOLS = {
    "observe_app", "mark_app_private", "set_study_order", "study_status", "teach_lesson",
    "list_open_doubts", "answer_doubt", "record_consent",
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


def test_teaching_through_mcp_saves_the_lesson_and_never_returns_a_secret_value(tmp_path):
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})
    server = server_for(tmp_path, {"paint.exe": desktop})

    first = ask(server, "teach_lesson", {"app": "paint.exe", "name": "login", "role": "button",
                                         "control_name": "Password", "action": "type_secret",
                                         "secret_ref": "login"})
    ask(server, "record_consent", {"app": "paint.exe", "control": "Password", "action": "type_secret"})
    second = ask(server, "teach_lesson", {"app": "paint.exe", "name": "login", "role": "button",
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
