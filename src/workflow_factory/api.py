"""Local HTTP API for the flow editor.

Bound to loopback only and guarded by a token. The built editor (static files) holds no data, so it
is served without the token; every /api/ route needs it. No CORS header is ever sent, and the Host
header must be a loopback name with this server's port (against DNS rebinding).
"""

import hmac
import json
import re
import secrets
import threading
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from workflow_factory.consent import consents, revoke_consent
from workflow_factory.desktop import Desktop, DesktopError
from workflow_factory.flow import run_flow
from workflow_factory.flows import flow_from_dict, flow_to_dict, list_flows, load_flow, save_flow
from workflow_factory.knowledge import duplicate_flow
from workflow_factory.lessons import (
    find_lesson,
    lesson_report,
    list_lessons,
    reject_lesson,
    restore_lesson,
)
from workflow_factory.queue import answer_doubt, dismiss_doubt, list_doubts, list_runs

LOOPBACK_HOSTS = ("127.0.0.1", "localhost")  # the only names this server can be bound to
MAX_BODY_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 10
MAX_NOTE_CHARS = 500
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
                 ".svg": "image/svg+xml", ".json": "application/json", ".map": "application/json"}


class ApiServer:
    def __init__(self, user_db: Path, factory_db: Path | None, desktop_for: Callable[[str], Desktop],
                 token: str | None = None, host: str = "127.0.0.1", port: int = 0,
                 web_dir: Path | None = None, max_active_runs: int = 4, max_kept_runs: int = 50):
        if host not in LOOPBACK_HOSTS:
            raise ValueError("the editor API only binds to the loopback interface")
        self.user_db, self.factory_db, self.desktop_for = user_db, factory_db, desktop_for
        self.token = token or secrets.token_urlsafe(32)
        self.web_dir = web_dir
        self.max_active_runs, self.max_kept_runs = max_active_runs, max_kept_runs
        self._runs: dict[str, dict] = {}
        self._runs_lock = threading.Lock()
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
        run_id = uuid.uuid4().hex
        record = {"flow_id": flow_id, "status": "running", "stopped": None,
                  "nodes": {n.id: "pending" for n in flow.nodes}}
        with self._runs_lock:
            active = [run for run in self._runs.values() if run["status"] == "running"]
            if any(run["flow_id"] == flow_id for run in active):
                return 409, None  # two runs of one flow would race on its checkpoint
            if len(active) >= self.max_active_runs:
                return 429, None
            self._runs[run_id] = record
            self._trim_runs()

        def progress(node_id: str, status: str) -> None:
            with self._runs_lock:
                record["nodes"][node_id] = status

        def work() -> None:
            try:
                result = run_flow(flow, self.desktop_for(app), self.user_db, self.factory_db,
                                  context=context, progress=progress)
                final = {"status": result.status, "stopped": result.stopped}
            except DesktopError as error:  # the code only: its text could echo what is on screen
                final = {"status": "error", "error": getattr(error, "code", "DESKTOP_ERROR")}
            except Exception:  # noqa: BLE001 - a run must always end in a final state
                final = {"status": "error", "error": "INTERNAL"}
            with self._runs_lock:
                record.update(final)  # status last of all fields a poller might read
                self._trim_runs()

        threading.Thread(target=work, name=f"run-{run_id[:8]}", daemon=True).start()
        return 202, run_id

    def _run_view(self, run_id: str) -> dict | None:
        with self._runs_lock:
            record = self._runs.get(run_id)
            return None if record is None else {**record, "nodes": dict(record["nodes"])}

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
                if method == "GET" and path == "/api/lessons":
                    return self._send(200, [_lesson_view(lesson) for lesson in
                                            list_lessons(api.user_db, api.factory_db)])
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
                        {**_lesson_view(lesson), **lesson_report(api.user_db, lesson)}
                        for lesson in list_lessons(api.user_db, api.factory_db)])
                mark = re.fullmatch(r"/api/lessons/([\w.-]+)/([\w.-]+)/(reject|restore)", path)
                if mark and method == "POST":
                    if find_lesson(api.user_db, api.factory_db, mark[1], mark[2]) is None:
                        return self._send(404, {"error": "no such lesson"})
                    (reject_lesson if mark[3] == "reject" else restore_lesson)(api.user_db, mark[1], mark[2])
                    return self._send(200, {"lesson": mark[2], "action": mark[3]})
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
                status_match = re.fullmatch(r"/api/runs/(\w+)", path)
                if status_match and method == "GET":
                    view = api._run_view(status_match[1])
                    return self._send(200, view) if view else self._send(404, {"error": "no such run"})
                self._send(404, {"error": "not found"})

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


def _lesson_view(lesson) -> dict:
    """What the palette needs: never the secret reference, never pixels."""
    view = asdict(lesson.locator)
    return {"app": lesson.app, "name": lesson.name, "origin": str(lesson.origin), "action": lesson.action,
            "sensitive": str(lesson.sensitive) if lesson.sensitive else None,
            "locator": view}
