"""`python -m workflow_factory.editor`: start the local flow editor.

Prints one line, `Editor: http://127.0.0.1:PORT/#token=...`, and serves until interrupted. It also
registers the global emergency hotkey so one key press stops every running flow.
"""

import argparse
import os
import sys
import threading
from pathlib import Path

from workflow_factory.agent_desktop import AgentDesktop
from workflow_factory.api import ApiServer
from workflow_factory.flow import clear_emergency_stop, emergency_stop
from workflow_factory.hotkey import EmergencyHotkey
from workflow_factory.paths import default_user_db

DEFAULT_WEB_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Local flow editor (loopback only, token protected)")
    parser.add_argument("--port", type=int, default=0, help="loopback port (default: any free one)")
    parser.add_argument("--no-hotkey", action="store_true", help="do not register the emergency hotkey")
    args = parser.parse_args(argv)

    user_db = default_user_db()
    user_db.parent.mkdir(parents=True, exist_ok=True)
    factory = os.environ.get("WORKFLOW_FACTORY_FACTORY_DB")
    web_dir = Path(os.environ.get("WORKFLOW_FACTORY_WEB_DIR", DEFAULT_WEB_DIR))

    clear_emergency_stop()  # a new session starts with no stop pending
    hotkey = None
    if not args.no_hotkey:
        hotkey = EmergencyHotkey(emergency_stop)
        try:
            hotkey.start()
        except RuntimeError as error:  # keep the editor usable even if the key is taken
            print(f"Warning: {error}", file=sys.stderr)
            hotkey = None

    server = ApiServer(user_db, Path(factory) if factory else None, AgentDesktop,
                       port=args.port, web_dir=web_dir)
    server.start()
    print(f"Editor: {server.url}/#token={server.token}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
        if hotkey:
            hotkey.stop()


if __name__ == "__main__":
    main()
