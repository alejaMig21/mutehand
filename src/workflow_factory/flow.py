"""Run a flow: a graph of nodes with branching, IF on a measured effect, joins and capped loops.

Nodes whose predecessors are done run together in waves; physical input (mouse, keyboard,
focus) is one machine-wide resource, so nodes that need it take PHYSICAL_INPUT and never overlap,
while accessibility-only nodes may. A blocked node leaves a doubt and halts its own branch only:
the other branches finish, and the flow then waits for the tutor. State is checkpointed after
every node and every loop iteration, so a stopped flow resumes where it was.

Unverified risk (research ticket 20): whether accessibility actions on different windows are
really safe to run in parallel has not been measured on this machine. Known limit: a flow drives
one app, and an effect is a before/after snapshot of it, so two accessibility-only nodes acting at
once on that same app can disturb each other's measured effect.
"""

import hashlib
import re
import sqlite3
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, nullcontext
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

from workflow_factory.consent import is_permitted
from workflow_factory.data import RUN, MissingData, check_binding, expressions, references, resolve
from workflow_factory.dataops import DataError, apply, check_op
from workflow_factory.desktop import Desktop, DesktopError
from workflow_factory.ladder import locate
from workflow_factory.queue import (
    Reason,
    acquire_run_lock,
    clear_checkpoint,
    has_open_doubt,
    load_checkpoint,
    record_doubt,
    record_run,
    release_run_lock,
    save_checkpoint,
)
from workflow_factory.steps import (
    Status,
    current_status,
    find_step,
    record_app_name,
    record_outcome,
    refused_write,
    revalidate_changed_versions,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS node_results (
    node_id TEXT NOT NULL,
    effect TEXT NOT NULL,
    finished_at TEXT NOT NULL
)
"""

KINDS = ("step", "if", "join", "loop", "trigger", "foreach", "wait", "stop", "data")
RETRY_PAUSE_SECONDS = 2.0  # first pause before a retry; doubles each time, capped
MAX_RETRY_PAUSE_SECONDS = 60.0
MAX_RETRIES = 10
FAILURE_POLICIES = ("stop", "retry", "continue")
WAIT_SLICE_SECONDS = 1.0  # a wait sleeps in slices so the emergency stop is heard within a second
CLOCK_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
INPUT_TYPES = {"str": str, "int": int, "float": float, "bool": bool}
MAX_LOOP_SECONDS = 8 * 3600
MAX_PARALLEL_NODES = 4
PHYSICAL_INPUT = threading.Lock()  # one mouse, one keyboard, one focus for the whole machine
USER_IDLE_SECONDS = 5.0  # how long the person must leave mouse and keyboard alone before we resume
MAX_USER_WAIT_SECONDS = 600.0  # a person who never stops ends in a doubt, not an endless wait
# ponytail: fixed wait, the app gives no sign that it read the clipboard; raise it if a slower app pastes the old content
PASTE_READ_SECONDS = 1.0
SELECT_SETTLE_SECONDS = 0.5  # let the app close its editor before the effect is measured
KEY_ACTIONS = ("type_value", "type_secret", "paste_text", "press_keys")  # real keys: the foreground window must be the app's
TEXT_ACTIONS = ("type_value", "paste_text", "press_keys")  # they write the text of the node
EMERGENCY_STOP = threading.Event()  # set by the global hotkey: every running flow stops at once


def emergency_stop() -> None:
    EMERGENCY_STOP.set()


def clear_emergency_stop() -> None:
    EMERGENCY_STOP.clear()


_USER_ACTIVE = object()  # _replay found the person at the mouse or keyboard: pause, then retry


class _EmergencyStop(Exception):
    """Raised inside a node when the emergency stop is on; the flow stops without a doubt."""


class Effect(StrEnum):
    """Closed vocabulary of measured effects (see GLOSSARY.md)."""

    CLOSED_DIALOG = "closed_dialog"
    REVEALED = "revealed"
    VALUE_CHANGED = "value_changed"
    NO_CHANGE = "no_change"
    PIXELS_CHANGED = "pixels_changed"


@dataclass(frozen=True)
class Node:
    id: str
    step: str = ""  # step and loop nodes: the step to replay
    kind: str = "step"  # step | if | join | loop | trigger | foreach | wait | stop | data
    inputs: tuple[tuple[str, str], ...] = ()  # (name, type) values the run context must hold
    on: str | None = None  # if: the node whose measured effect is tested
    equals: str | None = None
    then: str | None = None
    otherwise: str | None = None
    max_iterations: int | None = None  # loop: capped by iterations AND by time
    max_seconds: int | None = None
    stop_after_failures: int = 3  # loop: consecutive failures that stop it and queue a doubt
    stop_when_effect: str | None = None  # loop: ends normally when an iteration measures this
    exclusive_input: bool = False  # needs the mouse, keyboard or focus: never overlaps another such node
    fields: dict = field(default_factory=dict, hash=False)  # field name -> binding (see data.py)
    body: str | None = None  # foreach: the one node it repeats, once per item
    op: str | None = None  # data: which operation (see dataops.py)
    on_failure: str = "stop"  # stop (leaves a doubt) | retry (after a pause, up to `retries` times) | continue (empty result)
    retries: int = 3

    def __post_init__(self):
        if self.on_failure not in FAILURE_POLICIES:
            raise ValueError(f"on_failure must be one of {FAILURE_POLICIES}")
        if self.on_failure == "retry" and not (type(self.retries) is int and 1 <= self.retries <= MAX_RETRIES):
            raise ValueError(f"retries must be a whole number from 1 to {MAX_RETRIES}")
        for name, binding in self.fields.items():
            check_binding(name, binding)
        if self.kind not in KINDS:
            raise ValueError(f"unknown node kind {self.kind!r}")
        for name, type_name in self.inputs:
            if type_name not in INPUT_TYPES:
                raise ValueError(f"input {name!r} has unknown type {type_name!r}")
        if self.kind in ("step", "loop") and not self.step:
            raise ValueError(f"a {self.kind} node needs a step")
        if self.kind == "if" and "condition" in self.fields:
            if not self.then:
                raise ValueError("an if node needs then")
        elif self.kind == "if" and not (self.on and self.equals and self.then):
            raise ValueError("an if node needs on, equals and then")
        vocabulary = {effect.value for effect in Effect}
        for effect_name in (self.equals, self.stop_when_effect):
            if effect_name is not None and effect_name not in vocabulary:
                raise ValueError(f"{effect_name!r} is not an effect; use one of {sorted(vocabulary)}")
        if self.kind == "loop":
            if self.max_iterations is None or self.max_seconds is None:
                raise ValueError("a loop needs both caps: max_iterations and max_seconds")
            if self.max_iterations < 1 or self.max_seconds < 1 or self.stop_after_failures < 1:
                raise ValueError("loop caps must be at least 1")
            if self.max_seconds > MAX_LOOP_SECONDS:
                raise ValueError("a loop may run for at most 8 hours")
        _check_system_node(self)


def _check_system_node(node: Node) -> None:
    """The settings a system node cannot work without."""
    fields = node.fields
    if node.kind == "trigger":
        mode = fields.get("mode")
        if not mode or "value" not in mode or mode["value"] not in ("manual", "daily"):
            raise ValueError("a trigger needs a fixed mode: manual or daily")
        if mode["value"] == "daily":
            at = fields.get("at")
            if not at or "value" not in at or not isinstance(at["value"], str) or not CLOCK_TIME.fullmatch(at["value"]):
                raise ValueError("a daily trigger needs a fixed time written HH:MM")
    elif node.kind == "foreach":
        if not node.body:
            raise ValueError("a foreach node needs a body: the node it repeats")
        if "items" not in fields:
            raise ValueError("a foreach node needs an items field")
    elif node.kind == "data":
        check_op(node.op, fields)
    elif node.kind == "wait":
        binding = fields.get("seconds")
        if binding is None:
            raise ValueError("a wait node needs a seconds field")
        if "value" in binding and not _good_seconds(binding["value"]):
            raise ValueError(f"seconds must be a number above 0 and at most {MAX_LOOP_SECONDS}")


def _good_seconds(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and 0 < value <= MAX_LOOP_SECONDS


@dataclass(frozen=True)
class Flow:
    nodes: list[Node]
    id: str | None = None  # None: derived from the definition, so unrelated flows never share state
    edges: list[tuple[str, str]] | None = None  # None: the nodes run one after another
    trial: str | None = None  # a test of part of a flow: the name its doubts, history and checkpoint go under

    def __post_init__(self):
        if self.id is not None and not re.fullmatch(r"[\w.-]+", self.id):
            raise ValueError("a flow id may only use letters, digits, '_', '.' and '-'")
        ids = [node.id for node in self.nodes]
        known = set(ids)
        for node in self.nodes:
            for name, target in references(node.fields):
                if target == node.id:
                    raise ValueError(f"field {name!r} of node {node.id!r} points at itself")
                if target not in known and target != RUN:
                    raise ValueError(f"field {name!r} of node {node.id!r} points at an unknown node {target!r}")
        by_id = {node.id: node for node in self.nodes}
        for node in self.nodes:
            if node.kind == "foreach":
                if node.body not in known:
                    raise ValueError(f"foreach {node.id!r} has a body that names an unknown node {node.body!r}")
                if by_id[node.body].kind != "step":
                    raise ValueError(f"the body of foreach {node.id!r} must be a step node")
        for source, target in self.all_edges:
            if source in self.owned or target in self.owned:
                raise ValueError(f"the body of a foreach cannot have edges of its own ({source!r} -> {target!r})")
            if source not in known or target not in known:
                raise ValueError(f"edge {source!r} -> {target!r} names an unknown node")
        remaining, edges = list(ids), self.all_edges
        while remaining:  # Kahn: nodes without unresolved predecessors leave first
            free = [n for n in remaining if not any(d == n and s in remaining for s, d in edges)]
            if not free:
                raise ValueError("the flow has a cycle")
            remaining = [n for n in remaining if n not in free]

    @property
    def owned(self) -> set[str]:
        """The nodes a foreach repeats: they run only inside it, never on their own."""
        return {node.body for node in self.nodes if node.kind == "foreach" and node.body}

    @property
    def all_edges(self) -> list[tuple[str, str]]:
        edges = (list(self.edges) if self.edges is not None
                 else [(a.id, b.id) for a, b in pairwise(n for n in self.nodes if n.id not in self.owned)])
        for node in self.nodes:
            if node.kind == "if":  # it routes to its targets, and waits for the node it tests
                edges += [(node.id, target) for target in (node.then, node.otherwise) if target]
                if node.on:
                    edges.append((node.on, node.id))
        owner = {node.body: node.id for node in self.nodes if node.kind == "foreach" and node.body}
        for node in self.nodes:  # a reference means "wait for that node"; a foreach body waits as its foreach does
            consumer = owner.get(node.id, node.id)
            for _, target in references(node.fields):
                source = owner.get(target, target)
                if target != RUN and source != consumer:
                    edges.append((source, consumer))
        return list(dict.fromkeys(edges))

    @property
    def definition(self) -> str:
        return repr((self.nodes, self.all_edges))

    @property
    def key(self) -> str:
        return self.trial or self.id or "flow-" + hashlib.sha1(self.definition.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class RunResult:
    effects: dict[str, Effect]
    blocked: dict[str, str]  # node id -> why it did not run (detailed reason)
    statuses: dict[str, Status]  # node id -> step status after the run
    stopped: str | None = None  # first node that stopped and left a doubt
    waiting: bool = False  # the flow has an open doubt, so it did not run
    emergency: bool = False  # a human pressed the emergency stop; the checkpoint allows resuming
    run_id: int | None = None  # the run history row of this run, when one was recorded
    busy: bool = False  # another live run of this flow holds it, so this one did not start
    halted_by: str | None = None  # the stop node that ended the flow early, on purpose
    continued: dict = field(default_factory=dict)  # node id -> why it failed and the flow went on without it
    outputs: dict = field(default_factory=dict)  # node id -> the Data it gave out; in memory, never written to a report

    @property
    def status(self) -> str:
        return ("busy" if self.busy else "emergency" if self.emergency else "waiting" if self.waiting
                else "stopped" if self.stopped else "finished")


# Detailed block reason -> the fixed doubt vocabulary
DOUBT_REASON = {
    "no_consent": Reason.NO_CONSENT,
    "control_not_found": Reason.CONTROL_NOT_FOUND,
    "unreadable": Reason.CONTROL_NOT_FOUND,
    "out_of_frame": Reason.PRECONDITION_NOT_MET,
    "rejected": Reason.PRECONDITION_NOT_MET,
    "to_revalidate": Reason.PRECONDITION_NOT_MET,
    "template_no_match": Reason.TEMPLATE_NO_MATCH,
    "missing_input": Reason.PRECONDITION_NOT_MET,
    "bad_data": Reason.PRECONDITION_NOT_MET,
    "unsendable_text": Reason.PRECONDITION_NOT_MET,
    "cell_requires_paste_text": Reason.PRECONDITION_NOT_MET,
    "effect_mismatch": Reason.PRECONDITION_NOT_MET,
    "step_missing": Reason.PRECONDITION_NOT_MET,
    "action_failed": Reason.PRECONDITION_NOT_MET,
    "wrong_window": Reason.PRECONDITION_NOT_MET,
    "user_active": Reason.PRECONDITION_NOT_MET,
}


@dataclass
class _State:
    """What survives a stop: it is saved as the flow's checkpoint."""

    done: set = field(default_factory=set)
    skipped: set = field(default_factory=set)
    effects: dict = field(default_factory=dict)  # node id -> last measured effect
    choices: dict = field(default_factory=dict)  # if node id -> the target it routed to
    loops: dict = field(default_factory=dict)  # loop node id -> {"iteration", "failures"}
    context: dict = field(default_factory=dict)  # the Data a workday starts with
    outputs: dict = field(default_factory=dict)  # node id -> the Data the node gave out

    def dump(self) -> dict:
        return {"done": sorted(self.done), "skipped": sorted(self.skipped), "effects": self.effects,
                "choices": self.choices, "loops": self.loops, "context": self.context, "outputs": self.outputs}

    @classmethod
    def load(cls, data: dict) -> _State:
        return cls(set(data["done"]), set(data["skipped"]), data["effects"], data["choices"],
                   data["loops"], data["context"], data.get("outputs", {}))


def _gate(step, user_db, key, desktop):
    """Why this node may not run, or the targets to act on when it may."""
    status = current_status(user_db, step, key.version)
    if status in (Status.REJECTED, Status.TO_REVALIDATE):
        return str(status), None
    if not is_permitted(user_db, step):  # before any desktop call
        return "no_consent", None
    if step.frame and not step.frame.matches(desktop.frame(), step.mask):
        return "out_of_frame", None
    endpoints = [step.endpoint] + ([step.drag_to] if step.action == "drag" else [])
    targets = []
    for endpoint in endpoints:  # a drag needs both ends
        target, reason = locate(endpoint, desktop)
        if reason:
            return reason, None
        if not target.control.readable:  # unreadable means blocked, whatever the consent
            return "unreadable", None
        if target.control.secure and step.action != "type_secret":  # password fields take secrets only
            return "unreadable", None
        targets.append(target)
    return None, targets


def effect_of(before, after) -> Effect:
    if after - before:
        return Effect.REVEALED
    if before - after:
        return Effect.CLOSED_DIALOG
    return Effect.NO_CHANGE


def _text_of(node: Node, state) -> str:
    """The text a type_value node types: its `text` field, else its first typed input."""
    if "text" in node.fields:
        return str(resolve(node.fields["text"], state.outputs, state.context))
    return str(state.context[node.inputs[0][0]])


# Keys the product knows by name. Anything else is pasted, not typed: a key name nobody tested could hit the wrong key.
def _keys_for(text: str) -> list[str] | None:
    keys = []
    for ch in text:
        if ch == "\n":
            keys.append("return")
        elif ch == " ":
            keys.append("space")
        elif ch.isascii() and ch.isalpha():
            keys.append(f"shift+{ch.lower()}" if ch.isupper() else ch)
        elif ch.isascii() and ch.isdigit():
            keys.append(ch)
        else:
            return None
    return keys


def _input_problem(node: Node, step, state) -> str | None:
    """A node does not start while a bound field points at nothing, or a typed input is missing or of the wrong type."""
    context = state.context
    if refused_write(step.action, step.locator.role):  # a step saved or imported before teaching refused it
        return "cell_requires_paste_text"
    if step.action in TEXT_ACTIONS and not node.inputs and "text" not in node.fields:
        return "missing_input"
    for binding in node.fields.values():
        try:
            resolve(binding, state.outputs, context)
        except MissingData:
            return "missing_input"
    if step.action == "press_keys" and _keys_for(_text_of(node, state)) is None:
        return "unsendable_text"  # letters, digits, spaces and new lines only: paste anything else
    for name, type_name in node.inputs:
        if name not in context:
            return "missing_input"
        value, expected = context[name], INPUT_TYPES[type_name]
        if expected is float:
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok = isinstance(value, expected) and not (expected is int and isinstance(value, bool))
        if not ok:
            return "missing_input"
    return None


def select(desktop, app: str, control, point=None, before_key=lambda: None) -> str | None:
    """Click, then Escape: the control stays selected and any editor the click opened is closed.

    "wrong_window" when the app is no longer in front after the click: no key is pressed."""
    if point:
        desktop.click_at(control, *point)
    else:
        desktop.click(control)
    if desktop.foreground_app().lower() != app:  # a key goes to whatever window is in front
        return "wrong_window"
    before_key()
    desktop.press_key("escape")
    desktop.sleep(SELECT_SETTLE_SECONDS)
    return None


def _differs(step, effect) -> bool:
    """The screen changed in another way than when the step was learned. Nothing taught: nothing to compare."""
    return bool(step.effect) and effect != step.effect


def _store_effect(user_db: Path, node_id: str, effect: Effect, finished_at: str) -> None:
    with closing(sqlite3.connect(user_db)) as db, db:  # short-lived: other writers share this file
        db.execute(SCHEMA)
        db.execute("INSERT INTO node_results VALUES (?, ?, ?)", (node_id, effect.value, finished_at))


def _seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


class _Run:
    """One call of run_flow: everything a node needs, so helpers stay short."""

    def __init__(self, flow, desktop, user_db, factory_db, state, progress=None):
        self.flow, self.desktop, self.user_db, self.factory_db, self.state = (
            flow, desktop, user_db, factory_db, state)
        self.progress = progress or (lambda node_id, status: None)  # live per-node status for the editor
        self.key = desktop.app_key()
        self.effects, self.blocked, self.statuses = {}, {}, {}
        self.lock = threading.RLock()  # parallel nodes share the state and its checkpoint
        self.baseline = None  # cursor and last-input time right after our own last physical action
        self.node_status = {}  # node id -> (status, reason): what the run history will show
        self.emergency = False
        self.halted = None  # the id of the stop node that ended the flow
        self.attempts = {}  # node id -> retries used so far
        self.retrying = set()  # nodes whose last failure asked for a pause and another try
        self.continued = {}
        self.nodes = {node.id: node for node in flow.nodes}

    def save(self) -> None:
        with self.lock:
            save_checkpoint(self.user_db, self.flow.key, self.state.dump(), self.flow.definition)

    def attempt(self, node: Node):
        """One replay of the node's step: (blocked reason or None, effect, step)."""
        step = find_step(self.user_db, self.factory_db, self.key.process, node.step)
        if step is None:  # a flow naming a step nobody taught: a doubt, not a crash
            return "step_missing", None, None
        lock = PHYSICAL_INPUT if node.exclusive_input or step.uses_physical_input else nullcontext()
        while True:
            with lock:
                outcome = self._replay(node, step)
            if outcome is not _USER_ACTIVE:
                return outcome
            # the person is using the PC: wait for idle with the lock free, then verify again
            self.progress(node.id, "paused")
            if not self._wait_for_idle():
                return "user_active", None, step
            self.progress(node.id, "running")

    def _user_active(self) -> bool:
        """Did the person touch mouse or keyboard since our last physical action?"""
        if self.baseline is None:  # nothing of ours to compare with: only recent input counts
            return self.desktop.idle_seconds() < USER_IDLE_SECONDS
        return self.desktop.input_fingerprint() != self.baseline

    def _wait_for_idle(self) -> bool:
        waited = 0.0
        while self.desktop.idle_seconds() < USER_IDLE_SECONDS:
            if EMERGENCY_STOP.is_set():
                raise _EmergencyStop
            if waited >= MAX_USER_WAIT_SECONDS:
                return False
            self.desktop.sleep(1.0)
            waited += 1.0
        self.baseline = self.desktop.input_fingerprint()
        return True

    def _paste(self, node: Node) -> str | None:
        """Put the text on the clipboard, paste it, and put the person's own clipboard back whatever happens."""
        desktop = self.desktop
        saved = desktop.clipboard_backup()
        refused = False
        try:
            desktop.clipboard_set(_text_of(node, self.state))
            if desktop.foreground_app().lower() != self.key.process:  # the window may have changed since the check
                refused = True
            else:
                desktop.press_key("ctrl+v")
                desktop.sleep(PASTE_READ_SECONDS)  # the key returns first; the app reads the clipboard afterwards
        finally:
            lost = desktop.clipboard_restore(saved)
        with self.lock:
            self.state.outputs[node.id] = {"not_restored": list(lost)}  # what the person's clipboard lost, by name
        return "wrong_window" if refused else None

    @staticmethod
    def _stop_if_asked() -> None:
        if EMERGENCY_STOP.is_set():
            raise _EmergencyStop

    def _type_keys(self, node: Node) -> str | None:
        """One real key at a time, looking at the foreground window before every key."""
        for key in _keys_for(_text_of(node, self.state)) or []:
            if self.desktop.foreground_app().lower() != self.key.process:
                return "wrong_window"
            self._stop_if_asked()  # looked at last, right before the key goes out
            self.desktop.press_key(key)
        return None

    def _replay(self, node: Node, step):
        desktop = self.desktop
        physical = node.exclusive_input or step.uses_physical_input
        if EMERGENCY_STOP.is_set():
            raise _EmergencyStop
        reason = _input_problem(node, step, self.state)
        if reason is None:
            reason, targets = _gate(step, self.user_db, self.key, desktop)
        if reason:
            return reason, None, step
        if physical and self._user_active():
            return _USER_ACTIVE
        if step.action in KEY_ACTIONS and desktop.foreground_app().lower() != self.key.process:
            return "wrong_window", None, step  # keys must never land in another app
        if EMERGENCY_STOP.is_set():
            raise _EmergencyStop
        target = targets[0]
        before = set(desktop.snapshot())
        if step.action == "read_value":
            with self.lock:
                self.state.outputs[node.id] = {"value": desktop.read_text(target.control)}
        elif step.action == "paste_text":
            reason = self._paste(node)
            if reason:
                return reason, None, step
        elif step.action == "press_keys":
            reason = self._type_keys(node)
            if reason:
                return reason, None, step
        elif step.action == "type_secret":
            desktop.type_secret(target.control, step.secret_ref)  # the value never enters the core
        elif step.action == "type_value":
            desktop.type_text(target.control, _text_of(node, self.state))
        elif step.action == "drag":
            desktop.drag(target.control, target.point, targets[1].control, targets[1].point)
        elif step.action == "select":
            reason = select(desktop, self.key.process, target.control, target.point, self._stop_if_asked)
            if reason:
                return reason, None, step
        elif target.point:
            desktop.click_at(target.control, *target.point)
        else:
            desktop.click(target.control)
        if physical:
            self.baseline = desktop.input_fingerprint()
        effect = effect_of(before, set(desktop.snapshot()))
        self.effects[node.id] = effect
        if step.effect:  # nothing taught to compare against means nothing to count
            self.statuses[node.id] = record_outcome(
                self.user_db, step, effect == step.effect, got=str(effect), at=desktop.now())
        _store_effect(self.user_db, node.id, effect, desktop.now())
        return None, effect, step

    def block(self, node: Node, reason: str, owner: Node | None = None) -> str:
        """A node failed. Returns what happens next: "retry", "continue" or "stop" (a doubt is queued).

        `owner` is the node whose policy applies when `node` is only its body (for each)."""
        policy = owner or node
        ran = reason == "effect_mismatch"  # the action happened: what it measured is real
        spent = ran and self.statuses.get(node.id) == Status.REJECTED  # a retry could only be refused, hiding the cause
        with self.lock:
            if policy.on_failure == "retry" and not spent and self.attempts.get(policy.id, 0) < policy.retries:
                self.attempts[policy.id] = self.attempts.get(policy.id, 0) + 1
                self.retrying.add(policy.id)
                return "retry"
            if policy.on_failure == "continue":
                self.continued[policy.id] = reason
                self.node_status[policy.id] = ("continued", reason)
                if owner is None:
                    if not ran:  # an empty result: whoever needs a field of it stops instead of guessing
                        self.state.outputs[node.id] = {}
                    self.state.done.add(node.id)
                    self.progress(node.id, "continued")
                    self.save()
                return "continue"
        try:
            capture = dict(Counter(c.role for c in self.desktop.snapshot()))  # roles and counts only
        except DesktopError:
            capture = {}  # the desktop is what failed: nothing to summarise
        with self.lock:
            self.blocked[node.id] = reason
            self.node_status[node.id] = ("blocked", reason)
            self.progress(node.id, "blocked")
            record_doubt(self.user_db, self.flow.key, node.id, node.step, DOUBT_REASON[reason], capture, reason)
            self.save()
        return "stop"

    def finish(self, node: Node) -> None:
        with self.lock:
            self.state.done.add(node.id)
            self.node_status[node.id] = ("done", None)
            self.progress(node.id, "done")
            self.save()


def _record_effect(run: _Run, node_id: str, effect: Effect) -> None:
    with run.lock:
        run.state.effects[node_id] = str(effect)
        run.state.outputs[node_id] = {**run.state.outputs.get(node_id, {}), "effect": str(effect)}


def _run_step(run: _Run, node: Node) -> None:
    reason, effect, step = run.attempt(node)
    if reason:
        run.block(node, reason)
        return
    _record_effect(run, node.id, effect)  # even on a mismatch: whoever goes on can read it
    if _differs(step, effect):  # later steps would work on a wrong result
        run.block(node, "effect_mismatch")
        return
    run.finish(node)


def _run_trigger(run: _Run, node: Node) -> None:
    with run.lock:
        run.state.outputs[node.id] = dict(run.state.context)  # what the workday started with
    run.finish(node)


def _run_wait(run: _Run, node: Node) -> None:
    try:
        seconds = resolve(node.fields["seconds"], run.state.outputs, run.state.context)
    except MissingData:
        seconds = None
    if not _good_seconds(seconds):
        run.block(node, "missing_input")
        return
    with run.lock:
        progress = run.state.loops.setdefault(node.id, {"elapsed": 0.0})  # a resume waits only the rest
    while progress["elapsed"] < seconds:
        if EMERGENCY_STOP.is_set():
            raise _EmergencyStop
        slice_ = min(WAIT_SLICE_SECONDS, seconds - progress["elapsed"])
        run.desktop.sleep(slice_)
        progress["elapsed"] += slice_
        run.save()
    with run.lock:
        run.state.outputs[node.id] = {"waited": seconds}
    run.finish(node)


def _run_foreach(run: _Run, node: Node) -> None:
    body = run.nodes[node.body]
    try:
        items = resolve(node.fields["items"], run.state.outputs, run.state.context)
    except MissingData:
        items = None
    if not isinstance(items, list):
        run.block(node, "missing_input")
        return
    with run.lock:
        progress = run.state.loops.setdefault(node.id, {"iteration": 0})
    while progress["iteration"] < len(items):
        index = progress["iteration"]
        with run.lock:
            run.state.outputs[node.id] = {"item": items[index], "index": index, "count": len(items)}
        run.progress(body.id, "running")
        reason, effect, step = run.attempt(body)  # consent, the input lock and the user pause apply to every item
        if reason is None:
            _record_effect(run, body.id, effect)
            if _differs(step, effect):
                reason = "effect_mismatch"
        if reason:
            verdict = run.block(body, reason, owner=node)  # a stop leaves the doubt on the body's step
            if verdict == "retry":
                return  # the pause and the new try are _guarded's; the saved item is where it resumes
            if verdict == "continue":  # this item is given up, the next one goes on
                with run.lock:
                    progress["iteration"] += 1
                    if reason == "effect_mismatch":
                        progress["mismatch"] = True  # gone on past it: the history still has to say so
                run.attempts.pop(node.id, None)
                run.save()
                continue
            with run.lock:
                run.blocked[node.id] = reason
                run.node_status[node.id] = ("blocked", reason)
                run.progress(node.id, "blocked")
            return
        with run.lock:
            progress["iteration"] += 1
            run.attempts.pop(node.id, None)  # the retries are per item
        run.save()  # a checkpoint per item
    with run.lock:
        run.state.outputs[node.id] = {"count": len(items)}
        run.state.done.add(body.id)
        run.node_status[body.id] = ("done", "effect_mismatch" if progress.get("mismatch") else None)
        run.progress(body.id, "done")
    run.finish(node)


def _run_stop(run: _Run, node: Node) -> None:
    with run.lock:
        run.halted = node.id
    run.finish(node)


def _fired_triggers(flow: Flow, fired: str) -> set[str]:
    """The triggers this run starts from. Pressing Run on a flow with no manual trigger starts every trigger."""
    triggers = [node for node in flow.nodes if node.kind == "trigger"]
    chosen = {node.id for node in triggers if node.fields["mode"]["value"] == fired}
    return chosen or ({node.id for node in triggers} if fired == "manual" else set())


def _run_data(run: _Run, node: Node) -> None:
    try:
        args = {name: resolve(binding, run.state.outputs, run.state.context) for name, binding in node.fields.items()}
    except MissingData:
        run.block(node, "missing_input")
        return
    try:
        out = apply(node.op, args)
    except DataError as error:
        with run.lock:
            run.state.outputs[node.id] = {"error": str(error)}  # the message never holds the value
        run.block(node, "bad_data")
        return
    with run.lock:
        run.state.outputs[node.id] = out
    run.finish(node)


def _run_if(run: _Run, node: Node) -> None:
    if "condition" in node.fields:
        try:
            matched = resolve(node.fields["condition"], run.state.outputs, run.state.context)
        except MissingData:
            run.block(node, "missing_input")
            return
        if not isinstance(matched, bool):
            with run.lock:
                run.state.outputs[node.id] = {"error": "condition must be true or false"}
            run.block(node, "bad_data")
            return
        with run.lock:
            run.state.choices[node.id] = node.then if matched else node.otherwise
        run.finish(node)
        return
    if node.on not in run.state.effects:  # the tested node never ran
        run.block(node, "missing_input")
        return
    matched = run.state.effects[node.on] == node.equals
    with run.lock:
        run.state.choices[node.id] = node.then if matched else node.otherwise
    run.finish(node)


def _run_loop(run: _Run, node: Node) -> None:
    with run.lock:
        progress = run.state.loops.setdefault(
            node.id, {"iteration": 0, "failures": 0, "elapsed": 0.0, "effect": str(Effect.NO_CHANGE)})
    while progress["iteration"] < node.max_iterations and progress["elapsed"] < node.max_seconds:
        began = run.desktop.now()
        reason, effect, step = run.attempt(node)  # preconditions are re-verified every iteration
        progress["elapsed"] += _seconds_between(began, run.desktop.now())  # time counts across stops
        wanted = reason is None and effect == node.stop_when_effect
        if reason is None:
            progress["iteration"] += 1
            progress["effect"] = str(effect)
            progress["mismatch"] = progress.get("mismatch", False) or _differs(step, effect)
            if _differs(step, effect) and not wanted:
                reason = "effect_mismatch"
        progress["failures"] = progress["failures"] + 1 if reason else 0
        run.save()  # a checkpoint per iteration
        if progress["failures"] >= node.stop_after_failures:
            progress["failures"] = 0
            run.block(node, reason)
            return
        if wanted:
            break
    with run.lock:
        run.state.effects[node.id] = progress["effect"]
    run.finish(node)
    if progress.get("mismatch"):
        with run.lock:
            run.node_status[node.id] = ("done", "effect_mismatch")


def _verdict(node_id: str, flow: Flow, nodes: dict, state: _State) -> str:
    """'wait' while a predecessor is unresolved, 'skip' if no live edge reaches it, else 'run'."""
    sources = [s for s, d in flow.all_edges if d == node_id]
    if not sources:
        return "run"
    live = False
    for source in sources:
        if source in state.done:
            routed = nodes[source].kind != "if" or state.choices.get(source) == node_id
            live = live or routed
        elif source not in state.skipped:
            return "wait"  # pending, or blocked and waiting for the tutor
    return "run" if live else "skip"


def _guarded(run: _Run, node: Node, runner) -> None:
    """A typed desktop failure stops this node with a doubt; it never takes the flow down."""
    while True:
        run.progress(node.id, "running")
        try:
            runner(run, node)
        except _EmergencyStop:
            run.emergency = True
        except DesktopError:
            run.block(node, "action_failed")
        if node.id not in run.retrying or run.emergency:
            return
        run.retrying.discard(node.id)
        pause = min(RETRY_PAUSE_SECONDS * 2 ** (run.attempts[node.id] - 1), MAX_RETRY_PAUSE_SECONDS)
        run.desktop.sleep(pause)  # the precondition is checked again by the runner on the next pass
        if EMERGENCY_STOP.is_set():
            run.emergency = True
            return


def rejected_steps(flow: Flow, desktop: Desktop, user_db: Path, factory_db: Path | None) -> tuple:
    """((node id, step name), ...) of every step node whose step is rejected right now.

    The editor refuses to start such a flow. A scheduled run still starts and stops at that node with a doubt, so the
    tutor hears about it."""
    key = desktop.app_key()
    found = []
    for node in flow.nodes:
        if node.kind not in ("step", "loop"):
            continue
        step = find_step(user_db, factory_db, key.process, node.step)
        if step is not None and current_status(user_db, step, key.version) == Status.REJECTED:
            found.append((node.id, node.step))
    return tuple(found)


def _named(node: Node) -> dict:
    """What the history keeps to say which box this was: node ids are reused when a flow is rebuilt."""
    return {"step": node.step or None, "kind": node.kind, "op": node.op}


def run_flow(
    flow: Flow, desktop: Desktop, user_db: Path, factory_db: Path | None = None,
    context: dict | None = None, progress=None, fired: str = "manual",
) -> RunResult:
    for node in flow.nodes:
        if expressions(node.fields):
            raise ValueError(f"node {node.id!r} uses an expression, which is stored but not run yet")
    if EMERGENCY_STOP.is_set():
        return RunResult({}, {}, {}, emergency=True)
    if has_open_doubt(user_db, flow.key):  # a stopped flow waits for the tutor
        return RunResult({}, {}, {}, waiting=True)
    if not acquire_run_lock(user_db, flow.key):  # two runs of one flow would race on its checkpoint
        return RunResult({}, {}, {}, busy=True)
    try:
        return _run_locked(flow, desktop, user_db, factory_db, context, progress, fired)
    finally:
        release_run_lock(user_db, flow.key)


def _run_locked(flow, desktop, user_db, factory_db, context, progress, fired="manual") -> RunResult:
    key = desktop.app_key()
    revalidate_changed_versions(user_db, key.process, key.version)
    record_app_name(user_db, key)
    saved = load_checkpoint(user_db, flow.key, flow.definition)
    state = _State.load(saved) if saved else _State()
    state.context.update(context or {})
    run = _Run(flow, desktop, user_db, factory_db, state, progress)
    started_at = desktop.now()
    nodes = {node.id: node for node in flow.nodes}
    runners = {"step": _run_step, "loop": _run_loop, "if": _run_if, "trigger": _run_trigger, "foreach": _run_foreach,
               "wait": _run_wait, "stop": _run_stop, "data": _run_data, "join": lambda current, node: current.finish(node)}
    fire = _fired_triggers(flow, fired)
    try:
        progressed = True
        while progressed and not run.emergency:
            progressed = False
            if EMERGENCY_STOP.is_set():
                run.emergency = True
                break
            wave = []
            for node in flow.nodes:
                if node.id in state.done or node.id in state.skipped or node.id in run.blocked or node.id in flow.owned:
                    continue
                verdict = "skip" if node.kind == "trigger" and node.id not in fire else _verdict(node.id, flow, nodes, state)
                if verdict == "wait":
                    continue
                progressed = True
                if verdict == "skip":
                    state.skipped.add(node.id)
                    run.node_status[node.id] = ("skipped", None)
                    run.progress(node.id, "skipped")
                else:
                    wave.append(node)
            if wave:  # everything ready together; PHYSICAL_INPUT serialises the nodes that need it
                with ThreadPoolExecutor(max_workers=min(len(wave), MAX_PARALLEL_NODES)) as pool:
                    list(pool.map(lambda node: _guarded(run, node, runners[node.kind]), wave))
            if run.halted:  # a stop node ran: nothing that has not run yet will
                for node in flow.nodes:
                    if node.id not in state.done and node.id not in state.skipped and node.id not in run.blocked:
                        state.skipped.add(node.id)
                        run.node_status[node.id] = ("skipped", None)
                        run.progress(node.id, "skipped")
                break
    except Exception:
        # a bug or a failure we do not handle: the run still leaves a trace, then the error goes on
        record_run(user_db, flow.key, started_at, desktop.now(), "error", None, [
            {"node_id": node.id, "status": run.node_status[node.id][0], "reason": run.node_status[node.id][1], **_named(node)}
            for node in flow.nodes if node.id in run.node_status])
        raise
    effects = {node_id: Effect(effect) for node_id, effect in run.effects.items()}
    if run.emergency:  # no doubt, no cleanup: the checkpoint lets the flow resume after the stop
        result = RunResult(effects, run.blocked, run.statuses, emergency=True, outputs=run.state.outputs, continued=run.continued)
    elif run.blocked:
        first = next(node.id for node in flow.nodes if node.id in run.blocked)  # flow order, not timing
        result = RunResult(effects, run.blocked, run.statuses, stopped=first, outputs=run.state.outputs, continued=run.continued)
    else:
        clear_checkpoint(user_db, flow.key)
        result = RunResult(effects, {}, run.statuses, halted_by=run.halted, outputs=run.state.outputs, continued=run.continued)
    run_id = record_run(user_db, flow.key, started_at, desktop.now(), result.status, result.stopped, [
        {"node_id": node.id, "status": run.node_status[node.id][0], "reason": run.node_status[node.id][1],
         "effect": str(effects[node.id]) if node.id in effects else None, **_named(node)}
        for node in flow.nodes if node.id in run.node_status])
    return replace(result, run_id=run_id)
