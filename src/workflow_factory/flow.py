"""Run a flow: a graph of nodes with branching, IF on a measured effect, joins and capped loops.

Nodes run one at a time here, in a deterministic order; running independent branches in
parallel is not implemented yet. A blocked node leaves a doubt and halts its own branch only: the other
branches finish, and the flow then waits for the tutor. State is checkpointed after every node
and every loop iteration, so a stopped flow resumes where it was.
"""

import hashlib
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from workflow_factory.consent import is_permitted
from workflow_factory.desktop import Desktop
from workflow_factory.ladder import locate
from workflow_factory.lessons import (
    Status,
    current_status,
    find_lesson,
    record_outcome,
    revalidate_changed_versions,
)
from workflow_factory.queue import (
    Reason,
    clear_checkpoint,
    has_open_doubt,
    load_checkpoint,
    record_doubt,
    save_checkpoint,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS node_results (
    node_id TEXT NOT NULL,
    effect TEXT NOT NULL,
    finished_at TEXT NOT NULL
)
"""

KINDS = ("lesson", "if", "join", "loop")
INPUT_TYPES = {"str": str, "int": int, "float": float, "bool": bool}
MAX_LOOP_SECONDS = 8 * 3600


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
    lesson: str = ""  # lesson and loop nodes: the lesson to replay
    kind: str = "lesson"  # lesson | if | join | loop
    inputs: tuple[tuple[str, str], ...] = ()  # (name, type) values the run context must hold
    on: str | None = None  # if: the node whose measured effect is tested
    equals: str | None = None
    then: str | None = None
    otherwise: str | None = None
    max_iterations: int | None = None  # loop: capped by iterations AND by time
    max_seconds: int | None = None
    stop_after_failures: int = 3  # loop: consecutive failures that stop it and queue a doubt
    stop_when_effect: str | None = None  # loop: ends normally when an iteration measures this

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown node kind {self.kind!r}")
        for name, type_name in self.inputs:
            if type_name not in INPUT_TYPES:
                raise ValueError(f"input {name!r} has unknown type {type_name!r}")
        if self.kind in ("lesson", "loop") and not self.lesson:
            raise ValueError(f"a {self.kind} node needs a lesson")
        if self.kind == "if" and not (self.on and self.equals and self.then):
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


@dataclass(frozen=True)
class Flow:
    nodes: list[Node]
    id: str | None = None  # None: derived from the definition, so unrelated flows never share state
    edges: list[tuple[str, str]] | None = None  # None: the nodes run one after another

    def __post_init__(self):
        ids = [node.id for node in self.nodes]
        known = set(ids)
        for source, target in self.all_edges:
            if source not in known or target not in known:
                raise ValueError(f"edge {source!r} -> {target!r} names an unknown node")
        remaining, edges = list(ids), self.all_edges
        while remaining:  # Kahn: nodes without unresolved predecessors leave first
            free = [n for n in remaining if not any(d == n and s in remaining for s, d in edges)]
            if not free:
                raise ValueError("the flow has a cycle")
            remaining = [n for n in remaining if n not in free]

    @property
    def all_edges(self) -> list[tuple[str, str]]:
        edges = (list(self.edges) if self.edges is not None
                 else [(a.id, b.id) for a, b in zip(self.nodes, self.nodes[1:])])
        for node in self.nodes:
            if node.kind == "if":  # it routes to its targets, and waits for the node it tests
                edges += [(node.id, target) for target in (node.then, node.otherwise) if target]
                edges.append((node.on, node.id))
        return list(dict.fromkeys(edges))

    @property
    def definition(self) -> str:
        return repr((self.nodes, self.all_edges))

    @property
    def key(self) -> str:
        return self.id or "flow-" + hashlib.sha1(self.definition.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class RunResult:
    effects: dict[str, Effect]
    blocked: dict[str, str]  # node id -> why it did not run (detailed reason)
    statuses: dict[str, Status]  # node id -> lesson status after the run
    stopped: str | None = None  # first node that stopped and left a doubt
    waiting: bool = False  # the flow has an open doubt, so it did not run


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
    "effect_mismatch": Reason.PRECONDITION_NOT_MET,
    "lesson_missing": Reason.PRECONDITION_NOT_MET,
}


@dataclass
class _State:
    """What survives a stop: it is saved as the flow's checkpoint."""

    done: set = field(default_factory=set)
    skipped: set = field(default_factory=set)
    effects: dict = field(default_factory=dict)  # node id -> last measured effect
    choices: dict = field(default_factory=dict)  # if node id -> the target it routed to
    loops: dict = field(default_factory=dict)  # loop node id -> {"iteration", "failures"}
    context: dict = field(default_factory=dict)  # typed run context values

    def dump(self) -> dict:
        return {"done": sorted(self.done), "skipped": sorted(self.skipped), "effects": self.effects,
                "choices": self.choices, "loops": self.loops, "context": self.context}

    @classmethod
    def load(cls, data: dict) -> "_State":
        return cls(set(data["done"]), set(data["skipped"]), data["effects"], data["choices"],
                   data["loops"], data["context"])


def _gate(lesson, user_db, key, desktop):
    """Why this node may not run, or the targets to act on when it may."""
    status = current_status(user_db, lesson, key.version)
    if status in (Status.REJECTED, Status.TO_REVALIDATE):
        return str(status), None
    if not is_permitted(user_db, lesson):  # before any desktop call
        return "no_consent", None
    if lesson.frame and not lesson.frame.matches(desktop.frame(), lesson.mask):
        return "out_of_frame", None
    endpoints = [lesson.endpoint] + ([lesson.drag_to] if lesson.action == "drag" else [])
    targets = []
    for endpoint in endpoints:  # a drag needs both ends
        target, reason = locate(endpoint, desktop)
        if reason:
            return reason, None
        if not target.control.readable:  # unreadable means blocked, whatever the consent
            return "unreadable", None
        if target.control.secure and lesson.action != "type_secret":  # password fields take secrets only
            return "unreadable", None
        targets.append(target)
    return None, targets


def effect_of(before, after) -> Effect:
    if after - before:
        return Effect.REVEALED
    if before - after:
        return Effect.CLOSED_DIALOG
    return Effect.NO_CHANGE


def _input_problem(node: Node, lesson, context: dict) -> str | None:
    """A node does not start while a typed input is missing or of the wrong type."""
    if lesson.action == "type_value" and not node.inputs:
        return "missing_input"
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


def _store_effect(user_db: Path, node_id: str, effect: Effect, finished_at: str) -> None:
    with closing(sqlite3.connect(user_db)) as db, db:  # short-lived: other writers share this file
        db.execute(SCHEMA)
        db.execute("INSERT INTO node_results VALUES (?, ?, ?)", (node_id, effect.value, finished_at))


def _seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


class _Run:
    """One call of run_flow: everything a node needs, so helpers stay short."""

    def __init__(self, flow, desktop, user_db, factory_db, state):
        self.flow, self.desktop, self.user_db, self.factory_db, self.state = (
            flow, desktop, user_db, factory_db, state)
        self.key = desktop.app_key()
        self.effects, self.blocked, self.statuses = {}, {}, {}

    def save(self) -> None:
        save_checkpoint(self.user_db, self.flow.key, self.state.dump(), self.flow.definition)

    def attempt(self, node: Node):
        """One replay of the node's lesson: (blocked reason or None, effect, lesson)."""
        lesson = find_lesson(self.user_db, self.factory_db, self.key.process, node.lesson)
        if lesson is None:  # a flow naming a lesson nobody taught: a doubt, not a crash
            return "lesson_missing", None, None
        reason = _input_problem(node, lesson, self.state.context)
        if reason is None:
            reason, targets = _gate(lesson, self.user_db, self.key, self.desktop)
        if reason:
            return reason, None, lesson
        desktop, target = self.desktop, targets[0]
        before = set(desktop.snapshot())
        if lesson.action == "type_secret":
            desktop.type_secret(target.control, lesson.secret_ref)  # the value never enters the core
        elif lesson.action == "type_value":
            desktop.type_text(target.control, str(self.state.context[node.inputs[0][0]]))
        elif lesson.action == "drag":
            desktop.drag(target.control, target.point, targets[1].control, targets[1].point)
        elif target.point:
            desktop.click_at(target.control, *target.point)
        else:
            desktop.click(target.control)
        effect = effect_of(before, set(desktop.snapshot()))
        self.effects[node.id] = effect
        if lesson.effect:  # nothing taught to compare against means nothing to count
            self.statuses[node.id] = record_outcome(self.user_db, lesson, effect == lesson.effect)
        _store_effect(self.user_db, node.id, effect, desktop.now())
        return None, effect, lesson

    def block(self, node: Node, reason: str) -> None:
        self.blocked[node.id] = reason
        capture = dict(Counter(c.role for c in self.desktop.snapshot()))  # roles and counts only
        record_doubt(self.user_db, self.flow.key, node.id, node.lesson, DOUBT_REASON[reason], capture)
        self.save()

    def finish(self, node: Node) -> None:
        self.state.done.add(node.id)
        self.save()


def _run_lesson(run: _Run, node: Node) -> None:
    reason, effect, _ = run.attempt(node)
    if reason:
        run.block(node, reason)
        return
    run.state.effects[node.id] = str(effect)
    run.finish(node)


def _run_if(run: _Run, node: Node) -> None:
    if node.on not in run.state.effects:  # the tested node never ran
        run.block(node, "missing_input")
        return
    matched = run.state.effects[node.on] == node.equals
    run.state.choices[node.id] = node.then if matched else node.otherwise
    run.finish(node)


def _run_loop(run: _Run, node: Node) -> None:
    progress = run.state.loops.setdefault(
        node.id, {"iteration": 0, "failures": 0, "elapsed": 0.0, "effect": str(Effect.NO_CHANGE)})
    while progress["iteration"] < node.max_iterations and progress["elapsed"] < node.max_seconds:
        began = run.desktop.now()
        reason, effect, lesson = run.attempt(node)  # preconditions are re-verified every iteration
        progress["elapsed"] += _seconds_between(began, run.desktop.now())  # time counts across stops
        wanted = reason is None and effect == node.stop_when_effect
        if reason is None:
            progress["iteration"] += 1
            progress["effect"] = str(effect)
            if lesson.effect and effect != lesson.effect and not wanted:
                reason = "effect_mismatch"
        progress["failures"] = progress["failures"] + 1 if reason else 0
        run.save()  # a checkpoint per iteration
        if progress["failures"] >= node.stop_after_failures:
            progress["failures"] = 0
            run.block(node, reason)
            return
        if wanted:
            break
    run.state.effects[node.id] = progress["effect"]
    run.finish(node)


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


def run_flow(
    flow: Flow, desktop: Desktop, user_db: Path, factory_db: Path | None = None,
    context: dict | None = None,
) -> RunResult:
    if has_open_doubt(user_db, flow.key):  # a stopped flow waits for the tutor
        return RunResult({}, {}, {}, waiting=True)
    key = desktop.app_key()
    revalidate_changed_versions(user_db, key.process, key.version)
    saved = load_checkpoint(user_db, flow.key, flow.definition)
    state = _State.load(saved) if saved else _State()
    state.context.update(context or {})
    run = _Run(flow, desktop, user_db, factory_db, state)
    nodes = {node.id: node for node in flow.nodes}
    runners = {"lesson": _run_lesson, "loop": _run_loop, "if": _run_if,
               "join": lambda current, node: current.finish(node)}
    progressed = True
    while progressed:
        progressed = False
        for node in flow.nodes:
            if node.id in state.done or node.id in state.skipped or node.id in run.blocked:
                continue
            verdict = _verdict(node.id, flow, nodes, state)
            if verdict == "wait":
                continue
            progressed = True
            if verdict == "skip":
                state.skipped.add(node.id)
            else:
                runners[node.kind](run, node)
    effects = {node_id: Effect(effect) for node_id, effect in run.effects.items()}
    if run.blocked:
        return RunResult(effects, run.blocked, run.statuses, stopped=next(iter(run.blocked)))
    clear_checkpoint(user_db, flow.key)
    return RunResult(effects, {}, run.statuses)
