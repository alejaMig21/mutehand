"""MCP server that exposes the tutor tools to Claude Code.

The tool surface is the whole of what the tutor can do: there is deliberately no `force` option,
no screenshot or trace option, and no tool that returns a secret value (ADR 0002).
"""

import functools
from collections.abc import Callable
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from workflow_factory import recipes, tutor
from workflow_factory.agent_desktop import AgentDesktop, AgentDesktopError
from workflow_factory.desktop import Desktop
from workflow_factory.paths import default_user_db
from workflow_factory.steps import Locator, Sensitivity


def _code_only(tool):
    """CLI error text can echo what is on screen (private apps): the tutor gets the code alone."""

    @functools.wraps(tool)
    def guarded(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except AgentDesktopError as error:
            return {"status": "error", "code": error.code}

    return guarded


def build_server(user_db: Path, desktop_for: Callable[[str], Desktop]) -> MCPServer:
    server = MCPServer("workflow-factory-tutor")

    @server.tool(name="observe_app")
    @_code_only
    def observe_app(app: str) -> dict:
        """Summarised snapshot of an app. Private apps (chats, browsers) give roles and counts only."""
        return tutor.observe(user_db, desktop_for(app))

    @server.tool(name="mark_app_private")
    def mark_app_private(app: str) -> None:
        """Treat this app's content as private: observations are reduced to roles and counts."""
        tutor.mark_private(user_db, app)

    @server.tool(name="set_study_order")
    def set_study_order(app: str, steps: list[dict]) -> None:
        """Order in which to explore the app. Each step: name, role, control_name, automation_id?."""
        tutor.set_study_order(user_db, app, [
            tutor.StudyStep(s["name"], Locator(s["role"], s["control_name"], s.get("automation_id")))
            for s in steps
        ])

    @server.tool(name="study_status")
    def study_status(app: str) -> dict:
        """How many planned controls have a saved step and which one is next (resume after interruption)."""
        return tutor.study_status(user_db, app)

    @server.tool(name="teach_step")
    @_code_only
    def teach_step(
        app: str, name: str, role: str, control_name: str, automation_id: str | None = None,
        action: str = "click", sensitive: str | None = None, secret_ref: str | None = None,
    ) -> dict:
        """Do the action once, measure its effect and save the step at once. An action that writes
        text only checks that the control can be reached: nothing is clicked or written. A sensitive
        action returns consent_required: ask the user, then call record_consent and teach again."""
        return tutor.teach_step(
            user_db, desktop_for(app), name, Locator(role, control_name, automation_id), action,
            Sensitivity(sensitive) if sensitive else None, secret_ref)

    @server.tool(name="teach_lesson")
    @_code_only
    def teach_lesson(
        app: str, name: str, role: str, control_name: str, automation_id: str | None = None,
        action: str = "click", sensitive: str | None = None, secret_ref: str | None = None,
    ) -> dict:
        """The old name of teach_step: same arguments, same effect."""
        return teach_step(app, name, role, control_name, automation_id, action, sensitive, secret_ref)

    @server.tool(name="list_open_doubts")
    def list_open_doubts() -> list[dict]:
        """Doubts the apprentice left that nobody has answered yet."""
        return tutor.list_open_doubts(user_db)

    @server.tool(name="answer_doubt")
    @_code_only
    def answer_doubt(
        app: str, doubt_id: int, name: str, role: str, control_name: str,
        automation_id: str | None = None, action: str = "click",
        sensitive: str | None = None, secret_ref: str | None = None,
    ) -> dict:
        """Answer a doubt by teaching or fixing its step; the doubt closes once the step is saved."""
        return tutor.answer_doubt_by_teaching(
            user_db, desktop_for(app), doubt_id, name, Locator(role, control_name, automation_id),
            action=action, sensitive=Sensitivity(sensitive) if sensitive else None,
            secret_ref=secret_ref)

    @server.tool(name="save_recipe")
    def save_recipe(name: str, holes: list[dict]) -> None:
        """Save a recipe: the ordered holes of a pattern. Each hole: hole (its name), role, control_name,
        automation_id?, action? (click by default), sensitive?. The control is the one the first app uses."""
        recipes.save_recipe(user_db, name, holes)

    @server.tool(name="list_recipes")
    def list_recipes() -> list[dict]:
        """The saved recipes with their holes."""
        return recipes.list_recipes(user_db)

    @server.tool(name="apply_recipe")
    @_code_only
    def apply_recipe(app: str, recipe: str, fills: dict | None = None) -> dict:
        """Teach a recipe's steps on this app, one per hole in order, measuring each. `fills` gives only the
        holes whose control differs here: {hole: {role, control_name, automation_id?}} or {hole: {known_step}}.
        A hole that fails leaves a doubt naming it and the recipe stops there. A sensitive hole returns
        consent_required: ask the user, call record_consent, then apply again (finished holes are not repeated)."""
        return recipes.apply_recipe(user_db, desktop_for(app), recipe, fills)

    @server.tool(name="mark_step_known")
    def mark_step_known(app: str, recipe: str, hole: str, step: str) -> None:
        """This app already has a step for the hole: bind it, without acting on the app."""
        recipes.mark_step_known(user_db, app, recipe, hole, step)

    @server.tool(name="record_consent")
    def record_consent(app: str, control: str, action: str) -> None:
        """Record the user's yes for one sensitive action. Only call it after the user agreed.
        A broad consent (control '*') can only be granted by the user, never through this tool."""
        if control == "*":
            raise ValueError("a broad consent can only be granted by the user, not through the tutor tools")
        tutor.record_consent(user_db, app, control, action)

    return server


def main() -> None:
    user_db = default_user_db()
    user_db.parent.mkdir(parents=True, exist_ok=True)
    build_server(user_db, AgentDesktop).run()


if __name__ == "__main__":
    main()
