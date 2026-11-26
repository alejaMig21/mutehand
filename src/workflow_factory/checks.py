"""The first-run check: is what the product needs present? It only reads. It installs nothing, creates nothing and runs no program.

Each missing piece says what it is for and gives one plain way to fix it.
"""

import ctypes
import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path

SEEN_FILE = "checked.json"  # written by the screen after it was shown once, never by the check itself
SM_CMONITORS = 80  # GetSystemMetrics: how many monitors are on the desktop


def monitor_count() -> int:
    try:
        return int(ctypes.windll.user32.GetSystemMetrics(SM_CMONITORS))
    except (AttributeError, OSError):
        return 1  # not Windows: nothing to say about monitors


def _check(check_id: str, title: str, why: str, ok: bool, fix: str, optional: bool = False) -> dict:
    return {"id": check_id, "title": title, "why": why, "ok": ok, "fix": None if ok else fix, "optional": optional}


def run_checks(data_dir: Path, which: Callable[[str], str | None] = shutil.which,
               monitors: Callable[[], int] = monitor_count, project_dir: Path | None = None) -> list[dict]:
    project = Path(project_dir) if project_dir else Path.cwd()
    data_dir = Path(data_dir)
    return [
        _check("agent-desktop", "Desktop control (agent-desktop)", "It is how the apprentice sees and acts on apps.",
               bool(which("agent-desktop")), "Install it with npm: npm install -g agent-desktop"),
        _check("claude-code", "Claude Code", "Teaching happens in a chat with an agent in Claude Code. Running flows does not need it.",
               bool(which("claude")), "Install Claude Code from claude.com/claude-code, then open it in this folder."),
        _check("data-folder", "Data folder", "Your steps, flows, consents and history are kept there.",
               data_dir.is_dir() and os.access(data_dir, os.W_OK),
               "Run uv run workflow-factory once in the project folder; it creates the data folder."),
        _check("tutor-connection", "Teaching connection", "The project file that lets Claude Code find the teaching tools.",
               (project / ".mcp.json").is_file(),
               "Open the terminal in the project folder (the one with .mcp.json) before you start Claude Code."),
        _check("second-monitor", "A second monitor", "Optional. Tests of the product itself run on it so your main screen stays yours.",
               monitors() >= 2, "Nothing to fix if you do not test the product itself; connect a second screen if you do.", optional=True),
    ]


def seen_before(data_dir: Path) -> bool:
    return (Path(data_dir) / SEEN_FILE).is_file()


def mark_seen(data_dir: Path) -> None:
    (Path(data_dir) / SEEN_FILE).write_text(json.dumps({"seen": True}), encoding="utf-8")
