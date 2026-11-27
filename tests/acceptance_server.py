"""The finished editor on a made-up person's data, for persona testers: no real desktop, mouse, clipboard, database or
Windows scheduler is ever touched.

    uv run python tests/acceptance_server.py <first-day|everyday|many-apps> <state-dir>

Prints `READY http://127.0.0.1:<port>` and serves until killed. Open `<url>/#token=acceptance-token`. The state dir
must not hold a database yet and its path must be short (Windows limits a scheduled command to 261 characters).
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fake_scheduler import FakeScheduler  # noqa: E402

from workflow_factory import Flow, Node, reject_step, run_flow, save_flow, save_step  # noqa: E402
from workflow_factory.api import ApiServer  # noqa: E402
from workflow_factory.desktop import AppKey  # noqa: E402
from workflow_factory.steps import record_app_name, revalidate_changed_versions  # noqa: E402

from fake_desktop import FakeDesktop, button, step  # noqa: E402

DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
TOKEN = "acceptance-token"
NAMES: dict[str, str] = {}  # app -> the name the program calls itself
ACTIONS: dict[str, list[str]] = {}  # app -> the actions learned on it


def learn(db, app, name, actions, version="1.0"):
    NAMES[app], ACTIONS[app] = name, list(actions)
    for action in actions:
        save_step(db, step(action, action, app=app, version=version))
    record_app_name(db, AppKey(app, version, name))


def desktop_for(app):
    return FakeDesktop(controls=[button(a) for a in ACTIONS.get(app, [])], app=app, product_name=NAMES.get(app, ""))


def chore(db, flow_id, title, app, *actions, run=True):
    flow = Flow(id=flow_id, nodes=[Node(f"n{i}", a) for i, a in enumerate(actions, 1)])
    save_flow(db, flow, title, app)
    if run is not False:  # True: it works; a list of actions: the screen lacks them, so it stops there
        have = ACTIONS[app] if run is True else [a for a in ACTIONS[app] if a not in run]
        run_flow(flow, desktop=FakeDesktop(controls=[button(a) for a in have], app=app), user_db=db, fired="daily")


def everyday(db, server):
    learn(db, "excel.exe", "Microsoft Excel", ["Open the sheet", "Update the totals", "Save", "Print"])
    learn(db, "winword.exe", "Microsoft Word", ["Open a letter", "Fill in the name", "Save as PDF"])
    learn(db, "notepad.exe", "Notepad", ["Open the shopping list", "Add a line"])
    chore(db, "morning-report", "Morning report", "excel.exe", "Open the sheet", "Update the totals", "Save")
    chore(db, "weekly-export", "Weekly export", "excel.exe", "Open the sheet", "Print", "Save", run=["Print"])
    chore(db, "send-invoices", "Send the invoices", "winword.exe", "Open a letter", "Fill in the name", "Save as PDF", run=False)
    chore(db, "monthly-numbers", "Monthly numbers", "excel.exe", "Open the sheet", "Update the totals")
    chore(db, "shopping", "Shopping list", "notepad.exe", "Open the shopping list", "Add a line")
    result = server._daily_change("morning-report", "07:30")
    assert result[0] == 200, result


KINDS = ["Writer", "Sheets", "Photos", "Mail", "Notes", "Maps", "Music", "Calendar", "Slides", "Bank", "Scanner", "Browser"]
VERBS = [
    "Open a file",
    "Save",
    "Print",
    "Add a table",
    "Find and replace",
    "Export as PDF",
    "Share it",
    "Undo the last change",
    "Add a page",
    "Change the font",
    "Insert a picture",
    "Check the spelling",
    "Zoom in",
    "Close the window",
]


def many_apps(db, server):
    for n in range(34):
        kind = KINDS[n % len(KINDS)]
        learn(
            db,
            f"{kind.lower()}{n:02}.exe",
            f"{kind} {'Pro' if n >= len(KINDS) else 'Home'} {n // len(KINDS) + 1}",
            [f"{v}" for v in VERBS[: 6 + n % 9]],
        )
    chore(db, "morning-report", "Morning report", "sheets01.exe", "Open a file", "Add a table", "Save")
    chore(db, "send-letters", "Send the letters", "writer00.exe", "Open a file", "Find and replace", "Export as PDF")
    chore(db, "photo-album", "Photo album", "photos02.exe", "Open a file", "Add a table", "Save", run=False)
    chore(db, "weekly-backup", "Weekly backup", "mail03.exe", "Open a file", "Share it", "Save")
    chore(db, "month-end", "Month end", "bank09.exe", "Open a file", "Print", "Save")
    reject_step(db, "bank09.exe", "Print")  # blocks Month end
    app = "notes04.exe"  # updated since it was learned: its actions must be learned again
    learn(db, app, NAMES[app], ACTIONS[app], version="0.9")
    revalidate_changed_versions(db, app, "1.0")
    result = server._daily_change("send-letters", "18:00")
    assert result[0] == 200, result


def first_day(db, server):
    pass


DATASETS = {"first-day": first_day, "everyday": everyday, "many-apps": many_apps}


def main(argv):
    if len(argv) != 2 or argv[0] not in DATASETS:
        sys.exit(__doc__)
    state = Path(argv[1])
    state.mkdir(parents=True, exist_ok=True)
    if (state / "user.db").exists():
        sys.exit(f"{state} already holds a database: give an empty folder")
    import workflow_factory.attention as attention

    attention.run_checks = lambda data_dir: []  # what this PC has installed must not decide what Home shows
    server = ApiServer(state / "user.db", state / "factory.db", desktop_for, token=TOKEN, web_dir=DIST, schedule_runner=FakeScheduler())
    DATASETS[argv[0]](state / "user.db", server)
    server.start()
    print(f"READY {server.url}", flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main(sys.argv[1:])
