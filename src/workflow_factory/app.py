"""The product's front door: start the editor, open it in the browser, reuse one that is already running.

`uv run workflow-factory` runs this. A second run finds the running editor through `app.json` and just opens it
again; Ctrl+C in its terminal or the Quit button in the editor (`POST /api/quit`) ends it.
"""

import json
import os
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path

from workflow_factory.agent_desktop import AgentDesktop
from workflow_factory.api import ApiServer
from workflow_factory.editor import DEFAULT_WEB_DIR
from workflow_factory.flow import clear_emergency_stop, emergency_stop
from workflow_factory.hotkey import EmergencyHotkey
from workflow_factory.paths import default_user_db

STATE_FILE = "app.json"
LOG_FILE = "app.log"


def _log(data_dir: Path, message: str) -> None:
    with (data_dir / LOG_FILE).open("a", encoding="utf-8") as log:
        log.write(message + "\n")


def _running_address(state: Path) -> str | None:
    """The address of an editor that is up, or None. Asked over the network, never by process id, and with the
    token: only this editor answers its own API with it, so another program on a reused port is not mistaken for it."""
    try:
        address = json.loads(state.read_text(encoding="utf-8"))["url"]
        base, token = address.split("#token=")
        request = urllib.request.Request(base + "api/steps")
        request.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(request, timeout=2) as reply:
            return address if reply.status == 200 and isinstance(json.load(reply), list) else None
    except (OSError, ValueError, KeyError):  # no file, a dead address or a damaged file all mean "not running"
        return None


def run(data_dir: Path | None = None, open_browser: Callable[[str], object] = webbrowser.open,
        desktop_for: Callable[[str], object] = AgentDesktop, hotkey: bool = True,
        web_dir: Path = DEFAULT_WEB_DIR, announce: Callable[[str], object] = print) -> None:
    user_db = Path(data_dir) / "user.db" if data_dir else default_user_db()
    data_dir = user_db.parent
    data_dir.mkdir(parents=True, exist_ok=True)
    state = data_dir / STATE_FILE
    running = _running_address(state)
    if running:
        open_browser(running)
        return

    clear_emergency_stop()  # a new session starts with no stop pending
    key = None
    if hotkey:
        key = EmergencyHotkey(emergency_stop)
        try:
            key.start()
        except RuntimeError as error:  # keep the editor usable even if the key is taken
            _log(data_dir, f"emergency hotkey not registered: {error}")
            key = None
    factory = os.environ.get("WORKFLOW_FACTORY_FACTORY_DB")
    server = ApiServer(user_db, Path(factory) if factory else None, desktop_for, web_dir=web_dir)
    server.start()
    address = f"{server.url}/#token={server.token}"
    pending = state.with_suffix(".tmp")
    pending.write_text(json.dumps({"url": address}), encoding="utf-8")
    pending.replace(state)  # a second launch never reads a half-written file
    announce(f"Workflow Factory is running at {address}\n"
             "It opens in your browser. Press Ctrl+C here, or use Quit in the editor, to stop it.")
    try:
        open_browser(address)
        server.quit_requested.wait()
    except KeyboardInterrupt:
        pass
    finally:
        state.unlink(missing_ok=True)
        server.stop()
        if key:
            key.stop()


if __name__ == "__main__":
    run()
