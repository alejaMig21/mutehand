"""Desktop port backed by the real agent-desktop CLI.

Deliberately has no way to pass --force, --trace or screenshot flags (consent
gate, see ADR-0002). Text goes through stdin so it never lands in process args.
"""

import json
import shutil
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from workflow_factory.desktop import Control

Runner = Callable[[list[str], str | None], str]
SNAPSHOT_ATTEMPTS = 5


class AgentDesktopError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def resolve_binary(which=shutil.which) -> str:
    """Path of the real agent-desktop exe. The npm `.cmd` shim is skipped: running it goes
    through cmd.exe, where a control name containing `&` would become a shell command."""
    found = which("agent-desktop")
    if not found:
        raise AgentDesktopError("NOT_INSTALLED", "agent-desktop is not on PATH")
    real = Path(found).parent / "node_modules" / "agent-desktop" / "bin" / "agent-desktop-win32-x64.exe"
    return str(real) if real.exists() else found


def _run_cli(args: list[str], stdin: str | None = None) -> str:
    # exit code 1 still carries a JSON error envelope on stdout, so no check=True
    done = subprocess.run(
        [resolve_binary(), *args], input=stdin, capture_output=True, text=True, encoding="utf-8"
    )
    return done.stdout


def _native_id(raw) -> str:
    # real CLI publishes {"kind": "automation_id", "value": "Save"}
    return raw.get("value", "") if isinstance(raw, dict) else raw or ""


def _walk(node: dict):
    if node.get("role"):
        yield Control(
            role=node["role"],
            name=node.get("name", ""),
            automation_id=_native_id(node.get("native_id")),
            ref=node.get("ref_id", ""),
        )
    for child in node.get("children", []):
        yield from _walk(child)


class AgentDesktop:
    def __init__(self, app: str, runner: Runner = _run_cli, settle_seconds: float = 0.5):
        self._app = app
        self._runner = runner
        self._settle = settle_seconds  # ponytail: fixed pause, poll for stability if apps repaint slower

    def _call(self, args: list[str], stdin: str | None = None) -> dict:
        try:
            reply = json.loads(self._runner(args, stdin))
        except OSError as error:
            raise AgentDesktopError("CLI_UNAVAILABLE", str(error)) from error
        except ValueError as error:
            raise AgentDesktopError("INVALID_RESPONSE", "output is not JSON") from error
        if not reply.get("ok"):
            error = reply.get("error", {})
            raise AgentDesktopError(error.get("code", "UNKNOWN"), error.get("message", ""))
        return reply.get("data", {})

    def find(self, role: str, name: str, automation_id: str | None = None) -> Control | None:
        args = ["find", "--app", self._app, "--role", role, "--name", name, "--exact"]
        if automation_id:
            args += ["--native-id", automation_id]
        matches = self._call(args).get("matches", [])
        if not matches:
            return None
        match = matches[0]
        return Control(
            role=match.get("role", role),
            name=match.get("name", ""),
            automation_id=_native_id(match.get("native_id")) or automation_id or "",
            ref=match.get("ref_id", ""),
        )

    def click(self, control: Control) -> None:
        self._call(["click", control.ref])
        time.sleep(self._settle)  # let the app repaint before the effect is measured

    def type_text(self, control: Control, text: str) -> None:
        self._call(["type", control.ref, "--stdin"], stdin=text)

    def snapshot(self) -> tuple[Control, ...]:
        for attempt in range(1, SNAPSHOT_ATTEMPTS + 1):
            try:
                tree = self._call(["snapshot", "--app", self._app, "-i"]).get("tree")
                if tree is None:
                    raise AgentDesktopError("INVALID_RESPONSE", "snapshot has no tree")
                return tuple(_walk(tree))
            except AgentDesktopError as error:
                # right after an action the app can briefly own two windows
                if error.code != "AMBIGUOUS_TARGET" or attempt == SNAPSHOT_ATTEMPTS:
                    raise
                time.sleep(self._settle)

    def now(self) -> str:
        return datetime.now(UTC).isoformat()
