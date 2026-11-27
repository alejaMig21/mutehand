"""The finished editor on a made-up person's data, for persona testers: no real desktop, mouse, clipboard, database or
Windows scheduler is ever touched.

    uv run python tests/acceptance_server.py <first-day|everyday|many-apps> <state-dir>

Prints `READY http://127.0.0.1:<port>` and serves until killed. Open `<url>/#token=acceptance-token`. The state dir
must not hold a database yet and its path must be short (Windows limits a scheduled command to 261 characters).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fake_scheduler import FakeScheduler  # noqa: E402

from workflow_factory import Flow, Node, grant_consent, reject_step, run_flow  # noqa: E402
from workflow_factory.api import ApiServer  # noqa: E402
from workflow_factory.desktop import AppKey  # noqa: E402
from workflow_factory.flows import save_flow  # noqa: E402
from workflow_factory.steps import add_tags, record_app_name, revalidate_changed_versions, save_step  # noqa: E402

from fake_desktop import FakeDesktop, button, step  # noqa: E402

DIST = Path(__file__).resolve().parent.parent / "src" / "workflow_factory" / "web"
TOKEN = "acceptance-token"
NAMES: dict[str, str] = {}  # technology (process name) -> the name the program calls itself
STEPS: dict[str, list[str]] = {}  # technology -> the steps learned on it
TAGS = {  # pattern tags, kept by step name: the same step on two programs shares them
    "Open file": ["file"],
    "Save": ["file"],
    "Print": ["file"],
    "Save as PDF": ["file"],
    "Export as PDF": ["file"],
    "Update totals": ["text"],
    "Fill in name": ["text"],
    "Add a line": ["text"],
    "Find and replace": ["text"],
    "Add a table": ["mouse"],
    "Insert a picture": ["mouse"],
    "Zoom in": ["mouse"],
}


def learn(db, technology, name, steps, version="1.0"):
    """Teach `steps` (named by what they do, one locator for this technology each) on one program."""
    NAMES[technology], STEPS[technology] = name, list(steps)
    for name_of_step in steps:
        save_step(db, step(name_of_step, name_of_step, app=technology, version=version))
        add_tags(db, name_of_step, TAGS.get(name_of_step, []))
    record_app_name(db, AppKey(technology, version, name))


def desktop_for(app, missing=()):
    return FakeDesktop(controls=[button(a) for a in STEPS.get(app, []) if a not in missing], app=app, product_name=NAMES.get(app, ""))


def on(technology, *steps):
    return [(technology, name) for name in steps]


def put_flow(db, flow_id, title, nodes, run=True):
    """A flow whose nodes each name their technology. `run`: True it works, False it never ran, a list of step names the
    screen lacks, so it stops at the first of them."""
    flow = Flow(id=flow_id, nodes=[Node(f"n{i}", name, technology) for i, (technology, name) in enumerate(nodes, 1)])
    save_flow(db, flow, title)
    if run is not False:
        run_flow(flow, desktop=lambda app: desktop_for(app, () if run is True else run), user_db=db, fired="daily")


def everyday(db, server):
    learn(db, "excel.exe", "Microsoft Excel", ["Open file", "Update totals", "Save", "Print"])
    learn(db, "winword.exe", "Microsoft Word", ["Open file", "Fill in name", "Save", "Save as PDF"])
    learn(db, "notepad.exe", "Notepad", ["Open file", "Add a line", "Save"])
    put_flow(db, "morning-report", "Morning report", on("excel.exe", "Open file", "Update totals", "Save"))
    put_flow(db, "weekly-export", "Weekly export", on("excel.exe", "Open file", "Print", "Save"), run=["Print"])
    put_flow(db, "send-invoices", "Send the invoices", on("winword.exe", "Open file", "Fill in name", "Save as PDF"), run=False)
    put_flow(db, "monthly-numbers", "Monthly numbers", on("excel.exe", "Open file", "Update totals"))
    put_flow(db, "shopping", "Shopping list", on("notepad.exe", "Open file", "Add a line", "Save"))
    put_flow(db, "totals-letter", "Totals letter",  # one flow, two programs: the numbers in Excel, the letter in Word
             on("excel.exe", "Open file", "Update totals", "Save") + on("winword.exe", "Open file", "Fill in name", "Save as PDF"))
    grant_consent(db, "winword.exe", "Save as PDF", "click")  # one thing it may do without asking, to take back
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
    put_flow(db, "morning-report", "Morning report", on("sheets01.exe", "Open a file", "Add a table", "Save"))
    put_flow(db, "send-letters", "Send the letters", on("writer00.exe", "Open a file", "Find and replace", "Export as PDF"))
    put_flow(db, "photo-album", "Photo album", on("photos02.exe", "Open a file", "Add a table", "Save"), run=False)
    put_flow(db, "weekly-backup", "Weekly backup", on("mail03.exe", "Open a file", "Share it", "Save"))
    put_flow(db, "month-end", "Month end", on("bank09.exe", "Open a file", "Print", "Save"))
    put_flow(db, "sheet-to-letter", "Sheet to letter",  # one flow, two programs
             on("sheets01.exe", "Open a file", "Save") + on("writer00.exe", "Open a file", "Export as PDF"))
    reject_step(db, "bank09.exe", "Print")  # blocks Month end
    app = "notes04.exe"  # updated since it was learned: its steps must be learned again
    learn(db, app, NAMES[app], STEPS[app], version="0.9")
    revalidate_changed_versions(db, app, "1.0")
    grant_consent(db, "mail03.exe", "Share it", "click")  # permissions to take back: on a Mail app and on the Photos app
    grant_consent(db, "photos02.exe", "Print", "click")
    result = server._daily_change("send-letters", "18:00")
    assert result[0] == 200, result


def first_day(db, server):
    pass


def data_folder_present(state: Path) -> bool:
    """The folder is what a cleanup can delete; the first day creates no database in it, so the folder is what is watched."""
    return state.is_dir()


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
    while data_folder_present(state):  # a cleaned-up temp folder would turn every answer into a 500: stop, and say why
        time.sleep(5)
    sys.exit(f"{state} is gone (the folder was deleted): the server stopped. Start it again on an empty folder.")


if __name__ == "__main__":
    main(sys.argv[1:])
