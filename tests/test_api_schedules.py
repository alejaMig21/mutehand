"""Schedules from the screen: only what this product created is listed or removable."""

import pytest
from fake_scheduler import FOREIGN, FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, save_flow, save_step
from workflow_factory.api import ApiServer

from fake_desktop import step


@pytest.fixture
def served(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=[Node("a", "open-menu")]))
    scheduler = FakeScheduler()
    server = ApiServer(tmp_path / "user.db", None, lambda app: None, token="secret-token", schedule_runner=scheduler)
    server.start()
    yield server, scheduler
    server.stop()


def test_a_schedule_is_created_listed_and_removed_through_the_api(served):
    server, scheduler = served

    code, made, _ = call(server, "/api/schedules", "POST", {"flow": "morning", "app": "mspaint.exe", "at": "09:30"})

    assert code == 201 and made == {"name": "morning daily 0930", "flow": "morning", "app": "mspaint.exe", "at": "09:30"}
    assert call(server, "/api/schedules")[1] == [made]
    assert call(server, "/api/schedules", "DELETE", {"name": "morning daily 0930"})[0] == 200
    assert call(server, "/api/schedules")[1] == [] and list(scheduler.tasks) == [FOREIGN]


def test_tasks_the_product_did_not_create_are_never_listed_or_removable(served):
    server, scheduler = served

    assert call(server, "/api/schedules")[1] == []  # the foreign task exists but is invisible
    assert call(server, "/api/schedules", "DELETE", {"name": FOREIGN})[0] == 404
    assert call(server, "/api/schedules", "DELETE", {"name": "Microsoft\\Windows\\Defrag\\ScheduledDefrag"})[0] == 404
    assert FOREIGN in scheduler.tasks


@pytest.mark.parametrize("body", [
    {"flow": "morning", "app": "mspaint.exe", "at": "9:30"}, {"flow": "morning & calc", "app": "mspaint.exe", "at": "09:30"},
    {"flow": "morning", "app": "paint.exe | whoami", "at": "09:30"}, {"flow": "morning", "app": "mspaint.exe"},
])
def test_a_bad_schedule_is_refused_before_anything_reaches_the_scheduler(served, body):
    server, scheduler = served

    assert call(server, "/api/schedules", "POST", body)[0] == 400
    assert not [c for c in scheduler.calls if c[1] == "/Create"]


def test_a_schedule_for_a_flow_that_does_not_exist_is_refused(served):
    server, _ = served

    code, body, _ = call(server, "/api/schedules", "POST", {"flow": "ghost", "app": "mspaint.exe", "at": "09:30"})

    assert code == 404 and "flow" in body["error"]


def test_a_scheduler_that_fails_is_an_error_the_screen_can_show(tmp_path):
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=[Node("a", "open-menu")]))

    def failing(args, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="Access is denied")

    server = ApiServer(tmp_path / "user.db", None, lambda app: None, token="secret-token", schedule_runner=failing)
    server.start()
    try:
        code, body, _ = call(server, "/api/schedules", "POST", {"flow": "morning", "app": "mspaint.exe", "at": "09:30"})
    finally:
        server.stop()

    assert code == 502 and "schtasks" in body["error"]


def test_the_scheduled_command_points_at_this_data_folder_when_it_is_not_the_default(served):
    server, scheduler = served

    call(server, "/api/schedules", "POST", {"flow": "morning", "app": "mspaint.exe", "at": "09:30"})

    arguments = scheduler.tasks["\\Workflow factory - morning daily 0930"]["arguments"]
    assert "--user-db" in arguments and "user.db" in arguments  # otherwise the task would open someone else's database
