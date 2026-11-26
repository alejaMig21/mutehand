"""Local HTTP API for the flow editor.

Bound to loopback only and guarded by a token. The built editor (static files) holds no data, so it
is served without the token; every /api/ route needs it. No CORS header is ever sent, and the Host
header must be a loopback name with this server's port (against DNS rebinding).
"""

import hmac
import json
import re
import secrets
import subprocess
import threading
import time
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from workflow_factory import schedule
from workflow_factory.checks import mark_seen, run_checks, seen_before
from workflow_factory.consent import consents, effective_sensitivity, is_permitted, revoke_consent
from workflow_factory.desktop import Desktop, DesktopError
from workflow_factory.flow import clear_emergency_stop, emergency_stop, rejected_steps, run_flow
from workflow_factory.flows import flow_from_dict, flow_to_dict, list_flows, load_flow, save_flow
from workflow_factory.knowledge import duplicate_flow
from workflow_factory.nodedata import present, single_node_flow, snapshot
from workflow_factory.paths import default_user_db
from workflow_factory.queue import answer_doubt, dismiss_doubt, list_doubts, list_runs
from workflow_factory.recipes import adapted_from, recipes_overview
from workflow_factory.steps import (
    find_step,
    list_steps,
    reject_step,
    restore_step,
    step_report,
)
from workflow_factory.tutor import _is_private

LOOPBACK_HOSTS = ("127.0.0.1", "localhost")  # the only names this server can be bound to
MAX_BODY_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 10
MAX_NOTE_CHARS = 500
MAX_LOG_EVENTS = 200
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml", ".json": "application/json", ".map": "application/json"}


class ApiServer:
    def __init__(self, user_db: Path, factory_db: Path | None, desktop_for: Callable[[str], Desktop],
                 token: str | None = None, host: str = "127.0.0.1", port: int = 0,
                 web_dir: Path | None = None, max_active_runs: int = 4, max_kept_runs: int = 50,
                 schedule_runner=subprocess.run):
        if host not in LOOPBACK_HOSTS:
            raise ValueError("the editor API only binds to the loopback interface")
        self.user_db, self.factory_db, self.desktop_for = user_db, factory_db, desktop_for
        self.token = token or secrets.token_urlsafe(32)
        self.web_dir = web_dir
        self.schedule_runner = schedule_runner  # how schtasks is called: tests give a stand-in
        self.max_active_runs, self.max_kept_runs = max_active_runs, max_kept_runs
        self._runs: dict[str, dict] = {}
        self._runs_lock = threading.Lock()
        self._node_data: dict[str, dict] = {}  # flow id -> node id -> {in, out}: the latest, in memory only
        self.quit_requested = threading.Event()  # set by POST /api/quit; whoever started the server waits on it
        self._http = ThreadingHTTPServer((host, port), self._handler())
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

    def _start_run(self, flow_id: str, app: str, context: dict) -> tuple[int, str | None]:
        """(202, run id) when started; 404 no such flow; 409 already running; 429 too many runs."""
        flow = load_flow(self.user_db, self.factory_db, flow_id)
        if flow is None:
            return 404, None
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
        if refused:  # a rejected step is never run: name them all before anything starts
            names = ", ".join(f"'{step}'" for _, step in refused)
            raise ValueError(f"This flow will not start: {names} {'is' if len(refused) == 1 else 'are'} rejected. "
                             "Restore the step in the Steps screen first.")
        return self._launch(flow, flow_id, flow_id, app, context)

    def _launch(self, flow, run_key: str, data_key: str, app: str, context: dict) -> tuple[int, str | None]:
        """Run `flow` in the background. `run_key` says what may not run twice at once; `data_key` is the flow whose
        node data this run updates (a test of one node updates the data of the flow it belongs to)."""
        run_id = uuid.uuid4().hex
        record = {"flow_id": run_key, "status": "running", "stopped": None,
                  "nodes": {n.id: "pending" for n in flow.nodes}, "log": []}
        with self._runs_lock:
            active = [run for run in self._runs.values() if run["status"] == "running"]
            if any(run["flow_id"] == run_key for run in active):
                return 409, None  # two runs of one flow would race on its checkpoint
            if len(active) >= self.max_active_runs:
                return 429, None
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
        return self._launch(alone, f"{flow_id}#test:{node_id}", flow_id, app, context)

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
                return json.loads(self.rfile.read(size) or b"{}")

            def _dispatch(self, method: str):
                if not self._host_ok():
                    return self._send(403, {"error": "unexpected Host header"})
                url = urllib.parse.urlsplit(self.path)
                path, self.query = url.path, urllib.parse.parse_qs(url.query)
                if path.startswith("/api/lessons"):  # the name an earlier editor used
                    path = "/api/steps" + path[len("/api/lessons"):]
                if not path.startswith("/api/"):
                    return self._static(path) if method == "GET" else self._send(405, {"error": "method"})
                if not self._authorised():
                    return self._send(401, {"error": "missing or wrong token"})
                try:
                    self._route(method, path)
                except (ValueError, TypeError, KeyError) as error:
                    self._send(400, {"error": str(error)})
                except Exception:  # noqa: BLE001 - details could echo private content: say nothing
                    self._send(500, {"error": "internal error"})

            def _route(self, method: str, path: str):
                if method == "POST" and path == "/api/quit":
                    api.quit_requested.set()
                    return self._send(202, {"ok": True})
                if method == "GET" and path == "/api/steps":
                    return self._send(200, [{**_step_view(step), **_safety(api.user_db, step)} for step in
                                            list_steps(api.user_db, api.factory_db)])
                if method == "GET" and path == "/api/checks":
                    data_dir = api.user_db.parent
                    return self._send(200, {"first_run": not seen_before(data_dir), "checks": run_checks(data_dir)})
                if method == "POST" and path == "/api/checks/seen":
                    mark_seen(api.user_db.parent)
                    return self._send(200, {"seen": True})
                if path == "/api/schedules":
                    return self._schedules(method)
                if method == "GET" and path == "/api/recipes":
                    return self._send(200, recipes_overview(api.user_db))
                if method == "GET" and path == "/api/flows":
                    return self._send(200, list_flows(api.user_db, api.factory_db))
                flow_match = re.fullmatch(r"/api/flows/([\w.-]+)", path)
                if flow_match and method == "GET":
                    flow = load_flow(api.user_db, api.factory_db, flow_match[1])
                    return self._send(200, flow_to_dict(flow)) if flow else self._send(404, {"error": "no such flow"})
                if flow_match and method == "PUT":
                    flow = flow_from_dict(flow_match[1], self._body())
                    save_flow(api.user_db, flow)
                    return self._send(200, flow_to_dict(flow))
                copy_match = re.fullmatch(r"/api/flows/([\w.-]+)/duplicate", path)
                if copy_match and method == "POST":
                    copy = duplicate_flow(api.user_db, api.factory_db, copy_match[1], self._body()["new_id"])
                    return self._send(201, flow_to_dict(copy))
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
                run_match = re.fullmatch(r"/api/flows/([\w.-]+)/run", path)
                if run_match and method == "POST":
                    body = self._body()
                    code, run_id = api._start_run(run_match[1], body["app"], body.get("context") or {})
                    if code == 202:
                        return self._send(202, {"run_id": run_id})
                    return self._send(code, {"error": {404: "no such flow", 409: "this flow is already running",
                                                       429: "too many runs at once"}[code]})
                if method == "GET" and path == "/api/library":
                    return self._send(200, [
                        {**_step_view(step), **step_report(api.user_db, step)}
                        for step in list_steps(api.user_db, api.factory_db)])
                mark = re.fullmatch(r"/api/steps/([\w.-]+)/([\w.-]+)/(reject|restore)", path)
                if mark and method == "POST":
                    if find_step(api.user_db, api.factory_db, mark[1], mark[2]) is None:
                        return self._send(404, {"error": "no such step"})
                    (reject_step if mark[3] == "reject" else restore_step)(api.user_db, mark[1], mark[2])
                    return self._send(200, {"step": mark[2], "action": mark[3]})
                if path == "/api/consents" and method == "GET":
                    return self._send(200, [asdict(consent) for consent in consents(api.user_db)])
                if path == "/api/consents" and method == "DELETE":  # revoke only: granting happens at teaching time
                    body = self._body()
                    if not revoke_consent(api.user_db, body["app"], body["control"], body["action"]):
                        return self._send(404, {"error": "no such consent"})
                    return self._send(200, {"revoked": True})
                if path == "/api/doubts" and method == "GET":
                    status = (self.query.get("status") or [None])[0]
                    return self._send(200, [
                        {**asdict(doubt), "reason": str(doubt.reason)} for doubt in list_doubts(api.user_db, status)])
                doubt = re.fullmatch(r"/api/doubts/(\d+)/(answer|dismiss)", path)
                if doubt and method == "POST":
                    if doubt[2] == "answer":
                        note = str(self._body().get("note") or "")[:MAX_NOTE_CHARS] or None
                        answer_doubt(api.user_db, int(doubt[1]), note)
                    else:
                        dismiss_doubt(api.user_db, int(doubt[1]))
                    return self._send(200, {"doubt": int(doubt[1]), "action": doubt[2]})
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
                    extra = ["--user-db", str(api.user_db)] if api.user_db != default_user_db() else []
                    try:
                        schedule.create_schedule(name, flow_id, app, at, extra, runner=runner)
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
                    schedule.delete_schedule(name, runner=runner)
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


def _safety(user_db: Path, step) -> dict:
    """What the editor marks on a step: how far it is trusted, whether its app is private, whether consent is given."""
    sensitive = effective_sensitivity(step) is not None
    return {"state": step_report(user_db, step)["state"], "private": _is_private(user_db, step.app),
            "adapted_from": adapted_from(user_db, step.app, step.name),
            "consent": ("given" if is_permitted(user_db, step) else "missing") if sensitive else "none"}


def _step_view(step) -> dict:
    """What the palette needs: never the secret reference, never pixels."""
    view = asdict(step.locator)
    return {"app": step.app, "name": step.name, "origin": str(step.origin), "action": step.action,
            "sensitive": str(step.sensitive) if step.sensitive else None,
            "locator": view}
