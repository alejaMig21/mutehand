"""Local HTTP API for the flow editor.

Bound to loopback only and guarded by a token. The built editor (static files) holds no data, so it
is served without the token; every /api/ route needs it. No CORS header is ever sent, and the Host
header must be a loopback name with this server's port (against DNS rebinding).
"""

import hashlib
import hmac
import json
import math
import re
import secrets
import subprocess
import threading
import time
import traceback
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from workflow_factory import daily, schedule
from workflow_factory.apps import app_detail, app_rows
from workflow_factory.attention import attention_items, rejected_by_person
from workflow_factory.consent import consents, covers, effective_sensitivity, revoke_consent
from workflow_factory.desktop import Desktop, DesktopError, plain_app
from workflow_factory.flow import clear_emergency_stop, emergency_stop, rejected_steps, run_flow
from workflow_factory.flows import (
    check_positions,
    check_title,
    describe_flow,
    flow_from_dict,
    flow_overview,
    flow_summaries,
    flow_to_dict,
    list_flows,
    load_flow,
    load_layout,
    new_flow_id,
    recently_trashed,
    restore_flow,
    save_flow,
    save_layout,
    set_title,
    stored_info,
    taught_app,
    trash_flow,
    trashed_ids,
)
from workflow_factory.knowledge import duplicate_flow
from workflow_factory.nodedata import present, single_node_flow, snapshot
from workflow_factory.paths import default_user_db
from workflow_factory.queue import (
    close_as_tried_again,
    dismiss_doubt,
    leave_note,
    list_doubts,
    list_runs,
    locked_flows,
)
from workflow_factory.recipes import adaptations, recipes_overview
from workflow_factory.steps import (
    app_names,
    find_step,
    list_steps,
    reject_step,
    restore_step,
    search_matches,
    step_report,
    step_reports,
)
from workflow_factory.tutor import handle, is_private, private_apps, step_context
from workflow_factory.upgrade import dismiss_notice

LOOPBACK_HOSTS = ("127.0.0.1", "localhost")  # the only names this server can be bound to
MAX_BODY_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 10
MAX_NOTE_CHARS = 500
MAX_LOG_EVENTS = 200
MAX_FLOW_NAME_CHARS = 100
MAX_SCHEDULES = 20  # more than a person can manage: a stray client cannot fill Windows Task Scheduler
# the ports from 1024 up that browsers refuse to open ("bad ports" in the Fetch standard)
BROWSER_BLOCKED_PORTS = frozenset({1719, 1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566, 6665, 6666, 6667,
                                   6668, 6669, 6679, 6697, 10080})
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml", ".json": "application/json", ".map": "application/json"}


def _real_scheduler(*args, **kwargs):
    """schtasks itself. Looked up when a server starts, so a test can put a stand-in here."""
    return subprocess.run(*args, **kwargs)


def _listen(host: str, port: int, handler) -> ThreadingHTTPServer:
    """Port 0 lets the system choose, and it may choose one no browser will open: those are held until it offers another."""
    refused = []
    try:
        while True:
            server = ThreadingHTTPServer((host, port), handler)
            if port or server.server_address[1] not in BROWSER_BLOCKED_PORTS:
                return server
            refused.append(server)
    finally:
        for server in refused:
            server.server_close()


class ApiServer:
    def __init__(self, user_db: Path, factory_db: Path | None, desktop_for: Callable[[str], Desktop],
                 token: str | None = None, host: str = "127.0.0.1", port: int = 0,
                 web_dir: Path | None = None, max_active_runs: int = 4, max_kept_runs: int = 50,
                 schedule_runner=None):
        if host not in LOOPBACK_HOSTS:
            raise ValueError("the editor API only binds to the loopback interface")
        self.user_db, self.factory_db, self.desktop_for = user_db, factory_db, desktop_for
        self.token = token or secrets.token_urlsafe(32)
        self.web_dir = web_dir
        self.schedule_runner = schedule_runner or _real_scheduler  # how schtasks is called: tests give a stand-in
        self.max_active_runs, self.max_kept_runs = max_active_runs, max_kept_runs
        self._runs: dict[str, dict] = {}
        self._runs_lock = threading.Lock()
        self._save_lock = threading.Lock()  # "is it unchanged?" and "save it" happen as one
        self._node_data: dict[str, dict] = {}  # flow id -> node id -> {in, out}: the latest, in memory only
        self.quit_requested = threading.Event()  # set by POST /api/quit; whoever started the server waits on it
        self._http = _listen(host, port, self._handler())
        self._thread = threading.Thread(target=self._http.serve_forever, name="editor-api", daemon=True)

    @property
    def address(self) -> tuple[str, int]:
        return self._http.server_address[:2]

    @property
    def url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._http.shutdown()
        self._http.server_close()
        self._thread.join(timeout=5)

    # --- runs -------------------------------------------------------------------------------

    def _trim_runs(self) -> None:
        """Keep only the most recent finished runs (call with the lock held)."""
        finished = [run_id for run_id, run in self._runs.items() if run["status"] != "running"]
        for run_id in finished[: max(0, len(finished) - self.max_kept_runs)]:
            del self._runs[run_id]

    def _start_run(self, flow_id: str, app: str, context: dict, again: bool = False) -> tuple[int, str | None]:
        """(202, run id) when started; 404 no such flow; 409 already running; 429 too many runs.

        `again` is the person pressing "Try again" on a stopped flow: the flow's open doubts close, and a step a failed
        check rejected is lifted so the run can go on from its checkpoint. A step the person rejected is never lifted."""
        flow = load_flow(self.user_db, self.factory_db, flow_id)
        if flow is None:
            return 404, None
        process = ""
        try:
            desktop = self.desktop_for(app)
            refused = rejected_steps(flow, desktop, self.user_db, self.factory_db)
            process = desktop.app_key().process
            untaught = [n.step for n in flow.nodes if n.kind in ("step", "loop")
                        and find_step(self.user_db, self.factory_db, process, n.step) is None]
        except DesktopError:
            refused, untaught = (), []  # the app is not there: the run itself will say so
        if untaught:  # a recipe's hole nobody filled is just a step that was never taught
            names = ", ".join(f"'{step}'" for step in untaught)
            raise ValueError(f"This flow will not start: {names} {'has' if len(untaught) == 1 else 'have'} not been taught "
                             "for this app yet. An agent teaches it in a chat.")
        lift = []
        if again and refused:
            found = {name: find_step(self.user_db, self.factory_db, process, name) for _, name in refused}
            lift = [step for step in found.values() if not rejected_by_person(step_report(self.user_db, step))]
            refused = tuple(r for r in refused if found[r[1]] not in lift)
        if refused:  # a rejected step is never run: name them all before anything starts
            names = ", ".join(f"'{step}'" for _, step in refused)
            many = len(refused) > 1
            if again:
                raise ValueError(f"You rejected {names}, so trying again would not run {'them' if many else 'it'}. "
                                 "Allow it again first, then try again.")
            raise ValueError(f"This flow will not start: {names} {'is' if len(refused) == 1 else 'are'} rejected. "
                             "Allow it again on Home or in Apps first.")

        def prepare() -> None:  # with the run about to start and nothing else holding the flow: doubts close, rejections lift
            for step in lift:
                restore_step(self.user_db, step.app, step.name)
            close_as_tried_again(self.user_db, flow_id)
        return self._launch(flow, flow_id, flow_id, app, context, prepare if again else None)

    def _launch(self, flow, run_key: str, data_key: str, app: str, context: dict, prepare=None) -> tuple[int, str | None]:
        """Run `flow` in the background. `run_key` says what may not run twice at once; `data_key` is the flow whose
        node data this run updates (a test of one node updates the data of the flow it belongs to). `prepare` is called
        once the run is sure to start, and before it does."""
        run_id = uuid.uuid4().hex
        record = {"flow_id": run_key, "status": "running", "stopped": None,
                  "nodes": {n.id: "pending" for n in flow.nodes}, "log": []}
        with self._runs_lock:
            active = [run for run in self._runs.values() if run["status"] == "running"]
            if any(run["flow_id"] == run_key for run in active):
                return 409, None  # two runs of one flow would race on its checkpoint
            if len(active) >= self.max_active_runs:
                return 429, None
            if prepare:
                prepare()
            self._runs[run_id] = record
            self._trim_runs()

        def progress(node_id: str, status: str) -> None:
            with self._runs_lock:
                record["nodes"][node_id] = status
                event = {"at": time.strftime("%H:%M:%S"), "node": node_id, "status": status}
                record["log"] = [*record["log"][-(MAX_LOG_EVENTS - 1):], event]

        def work() -> None:
            try:
                result = run_flow(flow, self.desktop_for(app), self.user_db, self.factory_db,
                                  context=context, progress=progress)
                final = {"status": result.status, "stopped": result.stopped}
                with self._runs_lock:
                    self._node_data.setdefault(data_key, {}).update(snapshot(flow, result.outputs, context))
            except DesktopError as error:  # the code only: its text could echo what is on screen
                final = {"status": "error", "error": getattr(error, "code", "DESKTOP_ERROR")}
            except Exception:  # noqa: BLE001 - a run must always end in a final state
                final = {"status": "error", "error": "INTERNAL"}
            with self._runs_lock:
                record.update(final)  # status last of all fields a poller might read
                self._trim_runs()
                if not any(run["status"] == "running" for run in self._runs.values()):
                    clear_emergency_stop()  # a stop pressed here must not refuse the next run

        threading.Thread(target=work, name=f"run-{run_id[:8]}", daemon=True).start()
        return 202, run_id

    def _start_node_test(self, flow_id: str, node_id: str, app: str, context: dict) -> tuple[int, str | None]:
        """Run one node alone, on the data the last run gave it. ValueError (a 400) says why it cannot be done."""
        flow = load_flow(self.user_db, self.factory_db, flow_id)
        if flow is None:
            return 404, None
        with self._runs_lock:
            last = {n: sides["out"] for n, sides in self._node_data.get(flow_id, {}).items()}
        alone = single_node_flow(flow, node_id, last)
        for doubt in list_doubts(self.user_db, "open"):
            if doubt.flow_id == alone.key:  # a test leaves nothing to resume: the next one starts fresh
                dismiss_doubt(self.user_db, doubt.id)
        return self._launch(alone, alone.key, flow_id, app, context)

    def _flow_view(self, flow) -> dict:
        """A flow as the editor sees it: where its nodes sit, what it is called, the app it runs on, and a revision
        that changes when any of what is stored does."""
        view = {**flow_to_dict(flow), "positions": load_layout(self.user_db, flow.id)}
        info = stored_info(self.user_db, self.factory_db).get(flow.id, {})
        digest = hashlib.sha256(json.dumps({**view, **info}, sort_keys=True).encode()).hexdigest()[:16]
        words = describe_flow(flow.id, info, lambda: flow, lambda: list_steps(self.user_db, self.factory_db))
        return {**view, **words, "revision": digest}

    def _save(self, flow_id: str, body: dict) -> tuple[int, dict]:
        """Save a flow. A body with "base" only replaces what the editor has seen: the revision it loaded, or
        None for "this is a new flow". A body without it replaces whatever is there."""
        if not schedule.SAFE_NAME.fullmatch(flow_id) or not flow_id.strip("."):
            raise ValueError("a flow identifier may only use letters, digits, '_', '.' and '-'")
        if len(flow_id) > MAX_FLOW_NAME_CHARS:
            raise ValueError(f"a flow identifier can have at most {MAX_FLOW_NAME_CHARS} characters")
        parsed = _parse_flow(flow_id, body)
        with self._save_lock:
            stored = load_flow(self.user_db, self.factory_db, flow_id)
            if stored is None and flow_id in trashed_ids(self.user_db):
                return 409, {"error": f"The identifier '{flow_id}' belongs to a flow that was deleted. Undo that, or use another."}
            if stored is None and flow_id.casefold() in (known.casefold() for known in self._flow_ids()):
                return 409, {"error": f"A flow identified as '{flow_id}' already exists, with other capital letters"}
            if "base" in body and stored is not None and body["base"] != (seen := self._flow_view(stored))["revision"]:
                return 409, {"error": f"A flow called '{seen['title']}' already exists" if body["base"] is None else
                             f"'{seen['title']}' was changed somewhere else since you opened it"}
            return self._write_with_daily(stored, *parsed, body, 200)

    def _create(self, body: dict) -> tuple[int, dict]:
        """Save a new flow under an identifier made from its title, so it can never replace another."""
        title = check_title(body["title"])
        with self._save_lock:
            parsed = _parse_flow(new_flow_id(title, self._flow_ids()), body)
            return self._write_with_daily(None, *parsed, body, 201)

    def _flow_ids(self) -> list[str]:
        """Every identifier in use or held for an undo."""
        return [*(entry["id"] for entry in list_flows(self.user_db, self.factory_db)), *trashed_ids(self.user_db)]

    def _running(self, flow_id: str) -> bool:
        """Is the flow, or a test of one of its nodes, running here or in another process (a scheduled run)?"""
        def ours(key: str) -> bool:
            return key == flow_id or key.startswith(f"{flow_id}#test:")
        with self._runs_lock:
            if any(run["status"] == "running" and ours(run["flow_id"]) for run in self._runs.values()):
                return True
        return any(ours(key) for key in locked_flows(self.user_db))

    def _rename(self, flow_id: str, body: dict) -> tuple[int, dict]:
        with self._save_lock:
            flow = load_flow(self.user_db, self.factory_db, flow_id)
            if flow is None:
                return 404, {"error": "no such flow"}
            set_title(self.user_db, flow_id, body["title"])
            return 200, self._flow_view(flow)

    def _schedule_extra(self) -> list[str]:
        return ["--user-db", str(self.user_db)] if self.user_db != default_user_db() else []

    def _delete(self, flow_id: str) -> tuple[int, dict]:
        """Delete the flow and its daily runs, keeping both for `_restore`."""
        with self._save_lock:
            flow = load_flow(self.user_db, self.factory_db, flow_id)
            if flow is None:
                return 404, {"error": "no such flow"}
            if not self._local(flow_id):
                raise ValueError("This is a built-in flow: it cannot be deleted.")
            title = self._flow_view(flow)["title"]
            if self._running(flow_id):
                return 409, {"error": f"“{title}” is running. Stop it first, then delete it."}
            runner = self.schedule_runner
            tasks = daily.tasks_by_flow(self.user_db, runner).get(flow_id, [])
            stopped = []
            try:
                for task in tasks:
                    schedule.delete_schedule(task["name"], runner=runner)
                    stopped.append(task)
            except RuntimeError:  # Windows refused: the flow stays, so what was stopped runs again
                self._recreate(flow_id, stopped)
                return 502, {"error": f"“{title}” was not deleted: its daily run could not be removed from Windows."}
            trash_flow(self.user_db, flow_id, tasks)
            return 200, {"id": flow_id, "title": title, "daily_runs": len(tasks)}

    def _recreate(self, flow_id: str, tasks: list[dict]) -> list[str]:
        """Set the daily runs `tasks` again; the names of those Windows would not take."""
        lost = []
        for task in tasks:
            try:
                schedule.create_schedule(task["name"], flow_id, task["app"], task["at"], self._schedule_extra(),
                                         runner=self.schedule_runner)
            except (ValueError, RuntimeError, TypeError):  # the flow is back; say what did not come back with it
                lost.append(task["name"])
        return lost

    def _restore(self, flow_id: str) -> tuple[int, dict]:
        with self._save_lock:
            if flow_id not in trashed_ids(self.user_db):
                return 404, {"error": "nothing was deleted under this name"}
            if self._local(flow_id):
                return 409, {"error": "A flow with this identifier exists again."}
            tasks = restore_flow(self.user_db, flow_id)
            lost = self._recreate(flow_id, tasks)
            flow = load_flow(self.user_db, self.factory_db, flow_id)
            at = daily.trigger_time(flow)
            if lost and at and at not in [t["at"] for t in tasks if t["name"] not in lost]:
                # a daily node with no task behind it would say "every day" and never run: take it off the flow
                before = load_layout(self.user_db, flow_id)
                self._store(*daily.with_daily(flow, None, before), before)
                flow = load_flow(self.user_db, self.factory_db, flow_id)
                return 200, {**self._flow_view(flow), "daily_run_lost": lost, "daily_node_removed": True}
            view = self._flow_view(flow)
            return 200, {**view, "daily_run_lost": lost} if lost else view

    def _write_with_daily(self, stored, flow, positions: dict | None, body: dict, ok: int) -> tuple[int, dict]:
        """Save `flow` (replacing `stored`, None for a new one). A daily trigger node and the Windows task that runs it exist
        together or not at all: when the save adds, removes or re-times that node, the task follows, or nothing is saved.
        Call with the save lock held."""
        now = daily.trigger_time(flow)
        if (daily.trigger_time(stored) if stored else None) == now:
            return ok, self._write(flow, positions, body)
        return self._with_task(flow.id, flow, now, lambda: self._write(flow, positions, body), ok, body.get("app"))

    def _write(self, flow, positions: dict | None, body: dict) -> dict:
        """Call with the save lock held."""
        save_flow(self.user_db, flow, body.get("title"), body.get("app"))
        if positions is not None:
            save_layout(self.user_db, flow.id, positions)
        return self._flow_view(flow)

    # --- daily time -----------------------------------------------------------------------------

    def _local(self, flow_id: str) -> bool:
        return any(e["id"] == flow_id and e["origin"] == "local" for e in list_flows(self.user_db, self.factory_db))

    def _store(self, flow, positions: dict, before: dict) -> None:
        save_flow(self.user_db, flow)
        if positions != before:
            save_layout(self.user_db, flow.id, positions)

    def _daily_read(self, flow_id: str) -> tuple[int, dict]:
        """The flow's daily time as Windows has it, and as its first node says. Reading changes nothing."""
        with self._save_lock:
            flow = load_flow(self.user_db, self.factory_db, flow_id)
            if flow is None:
                return 404, {"error": "no such flow"}
            tasks = daily.tasks_by_flow(self.user_db, self.schedule_runner).get(flow_id, [])
            at = tasks[0]["at"] if tasks else None
            return 200, {"at": at, "node_at": daily.trigger_time(flow)}

    def _daily_change(self, flow_id: str, at: str | None) -> tuple[int, dict]:
        """Set the flow's daily time, or with None stop it: the task and the first node change together, or neither does."""
        with self._save_lock:
            flow = load_flow(self.user_db, self.factory_db, flow_id)
            if flow is None:
                return 404, {"error": "no such flow"}
            if not self._local(flow_id):
                raise ValueError("This is a template. Make a copy of it to give it a daily time.")
            if at is not None and not (isinstance(at, str) and schedule.CLOCK.fullmatch(at)):
                raise ValueError("The time must be a time of day such as 07:30.")
            before = load_layout(self.user_db, flow_id)
            new_flow, places = daily.with_daily(flow, at, before)

            def commit() -> dict:
                self._store(new_flow, places, before)
                return {"at": at}
            return self._with_task(flow_id, flow, at, commit)

    def _with_task(self, flow_id: str, flow, at: str | None, commit, ok: int = 200, app: str | None = None) -> tuple[int, dict]:
        """Set the flow's Windows task to `at` (None: no task), then `commit()` what goes with it; the answer is
        (ok, what commit gave). The task and what commit stores change together, or neither does. Call with the save lock held."""
        runner = self.schedule_runner
        old = daily.tasks_by_flow(self.user_db, runner).get(flow_id, [])
        if at is None:
            stopped = []
            try:
                for task in old:
                    schedule.delete_schedule(task["name"], runner=runner)
                    stopped.append(task)
                return ok, commit()
            except Exception as error:  # noqa: BLE001 - what was stopped runs again: the node is still there
                self._recreate(flow_id, stopped)
                if isinstance(error, RuntimeError):
                    return 502, {"error": f"The daily run could not be stopped, so it still runs every day. {error}"}
                raise
        steps = list_steps(self.user_db, self.factory_db)
        info = {**stored_info(self.user_db, self.factory_db).get(flow_id, {}), **({"app": app} if app else {})}
        app = taught_app(describe_flow(flow_id, info, lambda: flow, lambda: steps)["app"], steps) \
            or next((t["app"] for t in old if t["app"]), "")
        if not app:
            raise ValueError("Choose which app this flow runs on first: the daily run needs to know it.")
        name = f"{flow_id} daily {at.replace(':', '')}"
        full, kept = schedule.full_name(name), {schedule.full_name(t["name"]) for t in old}
        listed = schedule.list_schedules(runner=runner)
        if len(listed) >= MAX_SCHEDULES and full not in listed:
            return 409, {"error": f"There are already {MAX_SCHEDULES} daily runs in Windows. Stop one first."}
        try:
            schedule.create_schedule(name, flow_id, app, at, self._schedule_extra(), runner=runner)
        except (ValueError, RuntimeError) as error:  # the words are Windows' own or ours: no screen content
            return (502 if isinstance(error, RuntimeError) else 400), {
                "error": f"The daily run was not set, nothing was changed. {error}"}
        try:
            for task in old:
                if schedule.full_name(task["name"]) != full:
                    schedule.delete_schedule(task["name"], runner=runner)
            return ok, commit()
        except Exception as error:  # noqa: BLE001 - whatever failed, the task made a moment ago must not stay alone
            if full not in kept:
                try:
                    schedule.delete_schedule(name, runner=runner)
                except RuntimeError:
                    pass
            if isinstance(error, RuntimeError):
                return 502, {"error": f"The daily time was not changed. {error}"}
            raise

    def _run_view(self, run_id: str) -> dict | None:
        with self._runs_lock:
            record = self._runs.get(run_id)
            return None if record is None else {**record, "nodes": dict(record["nodes"]), "log": list(record["log"])}

    # --- http ----------------------------------------------------------------------------------

    def _handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "workflow-factory"
            timeout = REQUEST_TIMEOUT_SECONDS  # a client that stalls mid-request frees its thread

            def log_message(self, *args):  # quiet: request lines could carry flow names
                pass

            def _send(self, status: int, payload=None, content_type="application/json", raw: bytes | None = None):
                body = raw if raw is not None else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def handle(self):
                try:
                    super().handle()
                except ConnectionError:  # the browser left (closed, reloaded) before the answer: nobody to tell
                    pass

            def _host_ok(self) -> bool:
                name, _, port = (self.headers.get("Host") or "").rpartition(":")
                return name in LOOPBACK_HOSTS and port == str(api.address[1])

            def _authorised(self) -> bool:
                header = self.headers.get("Authorization", "")
                return header.startswith("Bearer ") and hmac.compare_digest(
                    header[7:].encode(), api.token.encode())  # bytes: a non-ASCII value must not raise

            def _body(self) -> dict:
                size = int(self.headers.get("Content-Length") or 0)
                if not 0 <= size <= MAX_BODY_BYTES:
                    raise ValueError("bad Content-Length")
                # a number that is not finite would be sent back as text no browser can read
                body = json.loads(self.rfile.read(size) or b"{}", parse_constant=_finite, parse_float=_finite)
                return _Body(body) if isinstance(body, dict) else body

            def _dispatch(self, method: str):
                if not self._host_ok():
                    return self._send(403, {"error": "unexpected Host header"})
                url = urllib.parse.urlsplit(self.path)
                path, self.query = url.path, urllib.parse.parse_qs(url.query)
                if path.startswith("/api/flows/"):  # flow names may carry accents; they never carry a slash
                    path = urllib.parse.unquote(path)
                if path.startswith("/api/lessons"):  # the name an earlier editor used
                    path = "/api/steps" + path[len("/api/lessons"):]
                if not path.startswith("/api/"):
                    return self._static(path) if method == "GET" else self._send(405, {"error": "method"})
                if not self._authorised():
                    return self._send(401, {"error": "missing or wrong token"})
                try:
                    self._route(method, path)
                except ValueError as error:
                    self._send(400, {"error": str(error)})
                except TypeError:
                    self._send(400, {"error": "that is not a valid request"})
                except Exception:  # noqa: BLE001 - details could echo private content: say nothing to the browser
                    traceback.print_exc()  # but the person running the program can read why, on their own console
                    self._send(500, {"error": "internal error"})

            def _route(self, method: str, path: str):
                if method == "POST" and path == "/api/quit":
                    api.quit_requested.set()
                    return self._send(202, {"ok": True})
                if method == "GET" and path == "/api/steps":
                    steps = list_steps(api.user_db, api.factory_db)
                    context = step_context(api.user_db, steps)  # what the node panel searches: tags and technologies
                    query, tech = (self.query.get("q") or [""])[0], (self.query.get("tech") or [""])[0]
                    rows = []
                    for step, safety in zip(steps, _safety(api.user_db, steps), strict=True):
                        found = context.get(step.name, {"tags": [], "technologies": []})
                        if (not tech or plain_app(step.app) == plain_app(tech)) and search_matches(
                                query, step.name, [*found["tags"], *found["technologies"]]):
                            rows.append({**_step_view(step), **safety, **found})
                    return self._send(200, rows)
                if method == "GET" and path == "/api/attention":
                    return self._send(200, attention_items(api.user_db, api.factory_db, api.user_db.parent))
                notice_match = re.fullmatch(r"/api/notices/([\w.-]+)/dismiss", path)
                if notice_match and method == "POST":
                    dismiss_notice(api.user_db, notice_match[1])
                    return self._send(200, {"ok": True})
                if method == "GET" and path == "/api/apps":
                    return self._send(200, app_rows(api.user_db, api.factory_db, (self.query.get("q") or [""])[0]))
                app_match = re.fullmatch(r"/api/apps/([^/]+)", path)
                if app_match and method == "GET":
                    app = app_detail(api.user_db, api.factory_db, urllib.parse.unquote(app_match[1]))
                    return self._send(200, app) if app else self._send(404, {"error": "no such app"})
                if method == "GET" and path == "/api/app-names":
                    return self._send(200, app_names(api.user_db))
                if path == "/api/schedules":
                    return self._schedules(method)
                if method == "GET" and path == "/api/recipes":
                    return self._send(200, recipes_overview(api.user_db))
                if method == "GET" and path == "/api/flows":
                    return self._send(200, flow_summaries(api.user_db, api.factory_db))
                if method == "POST" and path == "/api/flows":
                    return self._send(*api._create(self._body()))
                if method == "GET" and path == "/api/flow-overview":
                    times = daily.tasks_by_flow(api.user_db, api.schedule_runner)
                    return self._send(200, [{**flow, "daily": times[flow["id"]][0]["at"] if flow["id"] in times else None}
                                            for flow in flow_overview(api.user_db, api.factory_db)])
                if method == "GET" and path == "/api/deleted":  # what Undo can still bring back, e.g. after a reload
                    return self._send(200, recently_trashed(api.user_db))
                flow_match = re.fullmatch(r"/api/flows/([^/]+)", path)
                if flow_match and method == "DELETE":
                    return self._send(*api._delete(flow_match[1]))
                change_match = re.fullmatch(r"/api/flows/([\w.-]+)/(rename|restore)", path)
                if change_match and method == "POST":
                    return self._send(*(api._rename(change_match[1], self._body()) if change_match[2] == "rename"
                                        else api._restore(change_match[1])))
                if flow_match and method == "GET":
                    flow = load_flow(api.user_db, api.factory_db, flow_match[1])
                    return self._send(200, api._flow_view(flow)) if flow else self._send(404, {"error": "no such flow"})
                if flow_match and method == "PUT":
                    return self._send(*api._save(flow_match[1], self._body()))
                daily_match = re.fullmatch(r"/api/flows/([^/]+)/daily", path)
                if daily_match and method == "GET":
                    return self._send(*api._daily_read(daily_match[1]))
                if daily_match and method in ("PUT", "DELETE"):
                    at = str(self._body()["at"]) if method == "PUT" else None  # "None" fails the clock check
                    return self._send(*api._daily_change(daily_match[1], at))
                copy_match = re.fullmatch(r"/api/flows/([\w.-]+)/duplicate", path)
                if copy_match and method == "POST":
                    body = self._body()
                    with api._save_lock:  # choosing a free identifier and taking it happen as one
                        copy = duplicate_flow(api.user_db, api.factory_db, copy_match[1], body.get("new_id"), body.get("title"))
                        save_layout(api.user_db, copy.id, load_layout(api.user_db, copy_match[1]))
                    return self._send(201, api._flow_view(copy))
                data_match = re.fullmatch(r"/api/flows/([\w.-]+)/data", path)
                if data_match and method == "GET":
                    if load_flow(api.user_db, api.factory_db, data_match[1]) is None:
                        return self._send(404, {"error": "no such flow"})
                    with api._runs_lock:
                        latest = dict(api._node_data.get(data_match[1], {}))
                    return self._send(200, present(latest, values=(self.query.get("values") or ["0"])[0] == "1"))
                test_match = re.fullmatch(r"/api/flows/([\w.-]+)/nodes/([\w.-]+)/test", path)
                if test_match and method == "POST":
                    body = self._body()
                    code, run_id = api._start_node_test(test_match[1], test_match[2], body["app"], body.get("context") or {})
                    if code == 202:
                        return self._send(202, {"run_id": run_id})
                    return self._send(code, {"error": {404: "no such flow", 409: "this node is already being tested",
                                                       429: "too many runs at once"}[code]})
                run_match = re.fullmatch(r"/api/flows/([\w.-]+)/(run|try-again)", path)
                if run_match and method == "POST":
                    body = self._body()
                    code, run_id = api._start_run(run_match[1], body["app"], body.get("context") or {}, run_match[2] == "try-again")
                    if code == 202:
                        return self._send(202, {"run_id": run_id})
                    return self._send(code, {"error": {404: "no such flow", 409: "this flow is already running",
                                                       429: "too many runs at once"}[code]})
                mark = re.fullmatch(r"/api/steps/([^/]+)/([^/]+)/(reject|restore)", path)
                if mark and method == "POST":  # a step name is free text: the browser sends it percent-encoded
                    app, name = urllib.parse.unquote(mark[1]), urllib.parse.unquote(mark[2])
                    found = find_step(api.user_db, api.factory_db, app, name) or next(
                        (s for s in list_steps(api.user_db, api.factory_db, light=True)  # a private app's step is named by handle
                         if s.app == app and handle(s.app, s.name) == name), None)
                    if found is None:
                        return self._send(404, {"error": "no such step"})
                    name = found.name
                    (reject_step if mark[3] == "reject" else restore_step)(api.user_db, app, name)
                    return self._send(200, {"step": name, "action": mark[3]})
                if path == "/api/consents" and method == "DELETE":  # revoke only: granting happens at teaching time
                    body = self._body()
                    control = next((c.control for c in consents(api.user_db) if c.app == body["app"]  # a private app's control is a handle
                                    and handle("control", c.control) == body["control"]), body["control"])
                    if not revoke_consent(api.user_db, body["app"], control, body["action"]):
                        return self._send(404, {"error": "no such consent"})
                    return self._send(200, {"revoked": True})
                if path == "/api/doubts" and method == "GET":
                    status = (self.query.get("status") or [None])[0]
                    return self._send(200, [
                        {**asdict(doubt), "reason": str(doubt.reason)} for doubt in list_doubts(api.user_db, status)])
                help_match = re.fullmatch(r"/api/doubts/(\d+)/help", path)
                if help_match and method == "POST":  # the person's note stays on the doubt, which stays open
                    note = str(self._body().get("note") or "")[:MAX_NOTE_CHARS]
                    leave_note(api.user_db, int(help_match[1]), note)
                    return self._send(200, {"doubt": int(help_match[1]), "note": note or None})
                if path == "/api/history" and method == "GET":
                    return self._send(200, list_runs(api.user_db, (self.query.get("flow") or [None])[0]))
                stop_match = re.fullmatch(r"/api/runs/(\w+)/stop", path)
                if stop_match and method == "POST":
                    view = api._run_view(stop_match[1])
                    if view is None:
                        return self._send(404, {"error": "no such run"})
                    if view["status"] != "running":
                        return self._send(409, {"error": "this run is not running"})
                    emergency_stop()  # one mouse and keyboard: every run stops at once
                    return self._send(202, {"stopping": True})
                if path == "/api/runs" and method == "GET":
                    with api._runs_lock:
                        return self._send(200, [{"run_id": run_id, "flow_id": run["flow_id"]}
                                                for run_id, run in api._runs.items() if run["status"] == "running"])
                status_match = re.fullmatch(r"/api/runs/(\w+)", path)
                if status_match and method == "GET":
                    view = api._run_view(status_match[1])
                    return self._send(200, view) if view else self._send(404, {"error": "no such run"})
                self._send(404, {"error": "not found"})

            def _schedules(self, method: str):
                runner = api.schedule_runner
                if method == "GET":
                    return self._send(200, schedule.describe_schedules(runner=runner))
                body = self._body()
                if method == "POST":
                    flow_id, app, at = body["flow"], body["app"], body["at"]
                    if not schedule.SAFE_NAME.fullmatch(str(flow_id)):
                        raise ValueError("a flow name may only use letters, digits, '_', '.' and '-'")
                    if load_flow(api.user_db, api.factory_db, flow_id) is None:
                        return self._send(404, {"error": "no such flow"})
                    name = f"{flow_id} daily {str(at).replace(':', '')}"
                    existing = schedule.list_schedules(runner=runner)
                    if len(existing) >= MAX_SCHEDULES and schedule.full_name(name) not in existing:
                        return self._send(409, {"error": f"There are already {MAX_SCHEDULES} schedules. Remove one first."})
                    try:
                        schedule.create_schedule(name, flow_id, app, at, api._schedule_extra(), runner=runner)
                    except RuntimeError as error:  # schtasks said no: its words, which hold no screen content
                        return self._send(502, {"error": str(error)})
                    return self._send(201, {"name": name, "flow": flow_id, "app": app, "at": at})
                if method == "DELETE":
                    try:
                        name = schedule.full_name(str(body["name"]))
                    except ValueError:  # not a name this product could have made
                        return self._send(404, {"error": "no such schedule"})
                    if name not in schedule.list_schedules(runner=runner):  # only what this product made can be removed
                        return self._send(404, {"error": "no such schedule"})
                    try:
                        schedule.delete_schedule(name, runner=runner)
                    except RuntimeError as error:
                        return self._send(502, {"error": str(error)})
                    return self._send(200, {"removed": body["name"]})
                return self._send(405, {"error": "method"})

            def _static(self, path: str):
                if api.web_dir is None:
                    return self._send(404, {"error": "the editor is not built"})
                root = api.web_dir.resolve()
                target = (root / (path.lstrip("/") or "index.html")).resolve()
                if not (target.is_relative_to(root) and target.is_file()):
                    return self._send(404, {"error": "not found"})
                kind = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
                self._send(200, content_type=kind, raw=target.read_bytes())

            def do_GET(self):
                self._dispatch("GET")

            def do_PUT(self):
                self._dispatch("PUT")

            def do_POST(self):
                self._dispatch("POST")

            def do_DELETE(self):
                self._dispatch("DELETE")

        return Handler


def _parse_flow(flow_id: str, body: dict) -> tuple:
    """(flow, positions or None) from a request body; ValueError when it is not a flow."""
    try:
        flow = flow_from_dict(flow_id, body)
    except (TypeError, KeyError):  # their words would show how the engine is built
        raise ValueError("that is not a valid flow") from None
    return flow, check_positions(body["positions"]) if "positions" in body else None


class _Body(dict):
    """A request body: only a field the request itself lacks is the caller's mistake."""

    def __missing__(self, key):
        raise ValueError(f"the request is missing '{key}'")


def _finite(text: str) -> float:
    number = float(text)
    if not math.isfinite(number):
        raise ValueError("numbers must be finite")
    return number


def _safety(user_db: Path, steps: list) -> list[dict]:
    """What the editor says about each step: whether it may run, how often it has worked (counted only where an effect was
    taught to compare with), whether its app is private, whether consent is given."""
    private, adapted, granted = private_apps(user_db), adaptations(user_db), consents(user_db)
    marks = []
    for step, report in zip(steps, step_reports(user_db, steps), strict=True):
        sensitive = effective_sensitivity(step) is not None
        marks.append({"state": report["state"], "private": is_private(user_db, step.app, private),
                      "successes": report["successes"], "failures": report["failures"], "counted": bool(step.effect),
                      "adapted_from": adapted.get((step.app, step.name)),
                      "consent": ("given" if covers(granted, step) else "missing") if sensitive else "none"})
    return marks


def _step_view(step) -> dict:
    """What the palette needs: never the secret reference, never pixels."""
    view = asdict(step.locator)
    return {"app": step.app, "name": step.name, "origin": str(step.origin), "action": step.action,
            "sensitive": str(step.sensitive) if step.sensitive else None,
            "locator": view}
