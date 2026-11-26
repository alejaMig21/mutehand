"""A flow's daily time through the API: its daily trigger node and its Windows task exist together or not at all."""

import subprocess

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, load_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.flows import load_layout, save_layout

from fake_desktop import FakeDesktop, button, step

TASK = "\\Workflow factory - morning daily "


def daily_triggers(flow):
    return [n for n in flow.nodes if n.kind == "trigger" and n.fields["mode"]["value"] == "daily"]


def mine(scheduler):
    return sorted(name for name in scheduler.tasks if name.startswith("\\Workflow factory - "))


@pytest.fixture
def served(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_step(db, step("save-file", "Beta"))
    save_flow(db, Flow(id="morning", nodes=[Node("a", "open-menu"), Node("b", "save-file")]), "Morning report", "mspaint.exe")
    scheduler = FakeScheduler()
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = ApiServer(db, None, lambda app: desktop, token="secret-token", schedule_runner=scheduler)
    server.start()
    yield server, scheduler, db
    server.stop()


def set_time(server, at, flow="morning"):
    return call(server, f"/api/flows/{flow}/daily", "PUT", {"at": at})


def test_setting_a_time_makes_the_windows_task_and_the_first_box_together(served):
    server, scheduler, db = served

    code, body, _ = set_time(server, "07:30")

    assert code == 200 and body["at"] == "07:30"
    assert mine(scheduler) == [TASK + "0730"]
    assert scheduler.tasks[TASK + "0730"]["at"] == "07:30"
    flow = load_flow(db, None, "morning")
    assert [t.fields["at"]["value"] for t in daily_triggers(flow)] == ["07:30"]
    assert [n.id for n in flow.nodes if n.kind != "trigger"] == ["a", "b"]  # the rest of the flow is untouched
    assert call(server, "/api/flows/morning/daily")[1]["at"] == "07:30"


def test_the_trigger_leads_to_the_first_box_whether_wires_are_stored_or_implied(served, tmp_path):
    server, _, db = served
    save_flow(db, Flow(id="wired", nodes=[Node("a", "open-menu"), Node("b", "save-file")], edges=[("a", "b")]), "Wired", "mspaint.exe")

    set_time(server, "07:30")
    set_time(server, "08:00", "wired")

    for flow_id in ("morning", "wired"):
        flow = load_flow(db, None, flow_id)
        (trigger,) = daily_triggers(flow)
        assert (trigger.id, "a") in flow.all_edges and (trigger.id, "b") not in flow.all_edges


def test_a_manual_start_box_becomes_the_daily_one_instead_of_a_second_start(served):
    server, _, db = served
    manual = Node("go", kind="trigger", fields={"mode": {"value": "manual"}})
    save_flow(db, Flow(id="morning", nodes=[manual, Node("a", "open-menu")]), "Morning report", "mspaint.exe")

    set_time(server, "07:30")

    flow = load_flow(db, None, "morning")
    assert [n.id for n in flow.nodes] == ["go", "a"] and [t.id for t in daily_triggers(flow)] == ["go"]


def test_a_new_start_box_is_drawn_above_the_first_box_when_the_flow_has_places(served):
    server, _, db = served
    save_layout(db, "morning", {"a": {"x": 60, "y": 60}, "b": {"x": 60, "y": 220}})

    set_time(server, "07:30")

    (trigger,) = daily_triggers(load_flow(db, None, "morning"))
    assert load_layout(db, "morning")[trigger.id] == {"x": 60, "y": -100}


def test_changing_the_time_leaves_exactly_one_task_and_one_trigger(served):
    server, scheduler, db = served
    set_time(server, "07:30")

    set_time(server, "08:15")

    assert mine(scheduler) == [TASK + "0815"] and scheduler.tasks[TASK + "0815"]["at"] == "08:15"
    assert [t.fields["at"]["value"] for t in daily_triggers(load_flow(db, None, "morning"))] == ["08:15"]
    assert FOREIGN in scheduler.tasks  # what the person made themselves is never touched


def test_stopping_removes_the_task_and_the_trigger_and_nothing_else(served):
    server, scheduler, db = served
    set_time(server, "07:30")

    code, body, _ = call(server, "/api/flows/morning/daily", "DELETE")

    assert code == 200 and body["at"] is None
    assert mine(scheduler) == [] and FOREIGN in scheduler.tasks
    flow = load_flow(db, None, "morning")
    assert daily_triggers(flow) == [] and [n.id for n in flow.nodes] == ["a", "b"]
    assert call(server, "/api/flows/morning/daily")[1]["at"] is None


def test_a_scheduler_that_refuses_leaves_nothing_half_done_and_says_why(served):
    server, scheduler, db = served

    def refusing(args, **kwargs):
        if args[1] == "/Create":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ERROR: Access is denied.")
        return scheduler(args, **kwargs)

    server.schedule_runner = refusing
    code, body, _ = set_time(server, "07:30")

    assert code == 502 and "Access is denied" in body["error"] and "nothing was changed" in body["error"].lower()
    assert mine(scheduler) == [] and daily_triggers(load_flow(db, None, "morning")) == []


def test_a_refused_change_keeps_the_old_time_in_both_places(served):
    server, scheduler, db = served
    set_time(server, "07:30")

    def refusing(args, **kwargs):
        if args[1] == "/Create":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ERROR: Access is denied.")
        return scheduler(args, **kwargs)

    server.schedule_runner = refusing
    assert set_time(server, "09:00")[0] == 502

    assert mine(scheduler) == [TASK + "0730"]
    assert [t.fields["at"]["value"] for t in daily_triggers(load_flow(db, None, "morning"))] == ["07:30"]


def test_a_task_that_cannot_be_removed_keeps_the_trigger_and_says_so(served):
    server, scheduler, db = served
    set_time(server, "07:30")

    def refusing(args, **kwargs):
        if args[1] == "/Delete":
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="ERROR: Access is denied.")
        return scheduler(args, **kwargs)

    server.schedule_runner = refusing
    code, body, _ = call(server, "/api/flows/morning/daily", "DELETE")

    assert code == 502 and "Access is denied" in body["error"]
    assert mine(scheduler) == [TASK + "0730"] and len(daily_triggers(load_flow(db, None, "morning"))) == 1


def test_a_time_that_is_not_a_clock_time_is_refused_before_anything_changes(served):
    server, scheduler, db = served

    for bad in ("7:30", "25:00", "", None, "07:30; calc"):
        assert set_time(server, bad)[0] == 400
    assert mine(scheduler) == [] and daily_triggers(load_flow(db, None, "morning")) == []


def test_a_flow_that_does_not_exist_has_no_daily_time(served):
    server, _, _ = served

    assert set_time(server, "07:30", "ghost")[0] == 404
    assert call(server, "/api/flows/ghost/daily")[0] == 404
    assert call(server, "/api/flows/ghost/daily", "DELETE")[0] == 404


def test_a_flow_with_no_app_says_to_choose_one_first(tmp_path):
    db = tmp_path / "user.db"
    save_flow(db, Flow(id="empty", nodes=[]), "Empty", None)
    scheduler = FakeScheduler()
    server = ApiServer(db, None, lambda app: None, token="secret-token", schedule_runner=scheduler)
    server.start()
    try:
        code, body, _ = set_time(server, "07:30", "empty")
    finally:
        server.stop()

    assert code == 400 and "app" in body["error"].lower() and mine(scheduler) == []


def test_a_factory_template_is_not_changed_by_giving_it_a_time(tmp_path):
    factory = tmp_path / "factory.db"
    save_step(factory, step("open-menu", "Alpha", origin="factory"))
    save_flow(factory, Flow(id="template", nodes=[Node("a", "open-menu")]), "Template", "mspaint.exe")
    scheduler = FakeScheduler()
    server = ApiServer(tmp_path / "user.db", factory, lambda app: None, token="secret-token", schedule_runner=scheduler)
    server.start()
    try:
        code, body, _ = set_time(server, "07:30", "template")
    finally:
        server.stop()

    assert code == 400 and "copy" in body["error"].lower() and mine(scheduler) == []


def test_schedules_made_before_show_on_their_flow_and_on_its_first_box(served):
    server, scheduler, db = served
    # made by the old Schedules screen: a task, and no trigger node on the flow
    assert call(server, "/api/schedules", "POST", {"flow": "morning", "app": "mspaint.exe", "at": "06:45"})[0] == 201
    assert daily_triggers(load_flow(db, None, "morning")) == []

    overview = {f["id"]: f for f in call(server, "/api/flow-overview")[1]}
    assert overview["morning"]["daily"] == "06:45"
    assert call(server, "/api/flows/morning/daily")[1]["at"] == "06:45"  # reading it brings the first box in line
    assert [t.fields["at"]["value"] for t in daily_triggers(load_flow(db, None, "morning"))] == ["06:45"]
    assert len(mine(scheduler)) == 1


def test_several_old_tasks_of_one_flow_collapse_to_one_when_the_time_is_set(served):
    server, scheduler, _ = served
    for at in ("06:45", "18:00"):
        call(server, "/api/schedules", "POST", {"flow": "morning", "app": "mspaint.exe", "at": at})

    set_time(server, "07:30")

    assert mine(scheduler) == [TASK + "0730"]


def test_a_task_of_another_data_folder_is_neither_shown_nor_removed(served):
    server, scheduler, _ = served
    other = TASK + "0900"
    scheduler.tasks[other] = {"command": "python.exe", "at": "09:00",
                              "arguments": "-m workflow_factory.workday --flow morning --app mspaint.exe --fired daily "
                                           "--user-db elsewhere.db"}

    assert call(server, "/api/flow-overview")[1][0]["daily"] is None
    set_time(server, "07:30")
    call(server, "/api/flows/morning/daily", "DELETE")

    assert other in scheduler.tasks and TASK + "0730" not in scheduler.tasks


def test_a_daily_trigger_with_no_task_is_not_called_scheduled(served):
    server, scheduler, db = served
    trigger = Node("t", kind="trigger", fields={"mode": {"value": "daily"}, "at": {"value": "09:00"}})
    save_flow(db, Flow(id="morning", nodes=[trigger, Node("a", "open-menu")]), "Morning report", "mspaint.exe")

    assert call(server, "/api/flow-overview")[1][0]["daily"] is None
    assert call(server, "/api/flows/morning/daily")[1] == {"at": None, "node_at": "09:00"}
    assert mine(scheduler) == []  # reading never creates a Windows task


def test_run_now_starts_a_flow_with_or_without_a_daily_time(served):
    server, _, _ = served

    for before_and_after in range(2):
        code, body, _ = call(server, "/api/flows/morning/run", "POST", {"app": "mspaint.exe"})
        assert code == 202, body
        run_id = body["run_id"]
        while call(server, f"/api/runs/{run_id}")[1]["status"] == "running":
            pass
        if not before_and_after:
            set_time(server, "07:30")


def test_a_full_scheduler_refuses_before_anything_changes(served):
    server, scheduler, _ = served
    for n in range(20):
        scheduler.tasks[f"\\Workflow factory - other{n} daily 0900"] = {
            "command": "p", "arguments": "--flow other --user-db x", "at": "09:00"}

    code, body, _ = set_time(server, "07:30")

    assert code == 409 and "20" in body["error"] and TASK + "0730" not in scheduler.tasks
