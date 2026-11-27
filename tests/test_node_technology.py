"""A step node records the technology it acts on: each node runs on its own technology, and one that has no locator
for its technology is refused before anything is touched."""

import pytest

from workflow_factory import Flow, Node, run_flow, save_step
from workflow_factory.flow import missing_locators
from workflow_factory.queue import list_doubts

from fake_desktop import FakeDesktop, button, step


def two_technologies(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    desktops = {
        "excel.exe": FakeDesktop(controls=[button("Save workbook")], app="excel.exe"),
        "paint.exe": FakeDesktop(controls=[button("Save picture")], app="paint.exe"),
    }
    return db, desktops


def test_each_node_runs_on_its_own_technology_in_order(tmp_path):
    db, desktops = two_technologies(tmp_path)
    flow = Flow(nodes=[Node(id="a", step="save", technology="excel.exe"),
                       Node(id="b", step="save", technology="paint.exe")])

    result = run_flow(flow, desktop=desktops.__getitem__, user_db=db)

    assert result.status == "finished"
    assert [c.name for c in desktops["excel.exe"].clicks] == ["Save workbook"]
    assert [c.name for c in desktops["paint.exe"].clicks] == ["Save picture"]


def test_a_step_not_learned_on_its_technology_is_refused_before_any_action(tmp_path):
    db, desktops = two_technologies(tmp_path)
    flow = Flow(id="mixed", nodes=[Node(id="a", step="save", technology="excel.exe"),
                                   Node(id="b", step="save", technology="word.exe")])

    result = run_flow(flow, desktop=lambda tech: desktops.get(tech, desktops["excel.exe"]), user_db=db)

    assert result.status == "stopped" and result.stopped == "b"
    assert result.blocked == {"b": "step_missing"}
    assert all(d.calls == [] for d in desktops.values())  # nothing was touched, not even the Excel node
    [doubt] = list_doubts(db, "open")
    assert (doubt.node_id, doubt.step, doubt.technology) == ("b", "save", "word.exe")


def test_a_step_node_with_no_technology_is_refused_when_the_run_has_no_default(tmp_path):
    db, desktops = two_technologies(tmp_path)
    flow = Flow(nodes=[Node(id="a", step="save")])

    result = run_flow(flow, desktop=desktops.__getitem__, user_db=db)

    assert result.blocked == {"a": "step_missing"}
    assert all(d.calls == [] for d in desktops.values())


def test_a_single_desktop_serves_nodes_without_a_technology(tmp_path):
    db, desktops = two_technologies(tmp_path)
    flow = Flow(nodes=[Node(id="a", step="save")])

    result = run_flow(flow, desktop=desktops["paint.exe"], user_db=db)

    assert result.status == "finished"
    assert [c.name for c in desktops["paint.exe"].clicks] == ["Save picture"]


def test_missing_locators_names_node_step_and_technology(tmp_path):
    db, _ = two_technologies(tmp_path)
    flow = Flow(nodes=[Node(id="a", step="save", technology="excel.exe"),
                       Node(id="b", step="save", technology="word.exe"),
                       Node(id="c", step="open", technology="excel.exe")])

    assert missing_locators(flow, db, None) == [("b", "save", "word.exe"), ("c", "open", "excel.exe")]


def test_consent_is_asked_per_technology(tmp_path):
    from workflow_factory import Sensitivity, grant_consent

    db = tmp_path / "user.db"
    save_step(db, step("send", "Send", app="excel.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("send", "Send", app="paint.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    grant_consent(db, app="excel.exe", control="Send", action="click")
    desktops = {tech: FakeDesktop(controls=[button("Send")], app=tech) for tech in ("excel.exe", "paint.exe")}
    flow = Flow(nodes=[Node(id="a", step="send", technology="excel.exe"),
                       Node(id="b", step="send", technology="paint.exe")])

    result = run_flow(flow, desktop=desktops.__getitem__, user_db=db)

    assert result.blocked == {"b": "no_consent"}
    assert len(desktops["excel.exe"].clicks) == 1 and desktops["paint.exe"].calls == []


def test_a_node_without_a_technology_still_loads_and_dumps_the_field():
    from workflow_factory.flows import flow_from_dict, flow_to_dict

    flow = flow_from_dict("f", {"nodes": [{"id": "n", "step": "save"}]})
    assert flow.nodes[0].technology == ""
    assert flow_to_dict(flow)["nodes"][0]["technology"] == ""


@pytest.mark.parametrize("kind", ["wait", "stop"])
def test_a_system_node_needs_no_technology(tmp_path, kind):
    fields = {"seconds": {"value": 1}} if kind == "wait" else {}
    run = run_flow(Flow(nodes=[Node(id="n", kind=kind, fields=fields)]),
                   desktop=lambda tech: FakeDesktop(controls=[]), user_db=tmp_path / "user.db")
    assert run.status == "finished"
