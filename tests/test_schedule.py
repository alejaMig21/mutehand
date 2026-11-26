import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from workflow_factory.schedule import (
    SCHEDULE_PREFIX,
    create_schedule,
    delete_schedule,
    list_schedules,
    workday_command,
)


class Recorder:
    """Stands in for subprocess.run: records the argument lists, never starts anything."""

    def __init__(self, returncode=0):
        self.calls = []
        self.returncode = returncode

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        assert kwargs.get("shell") is not True  # never through a shell
        return subprocess.CompletedProcess(args, self.returncode, stdout="", stderr="")


def test_the_task_runs_the_workday_module_with_the_flow_and_the_app_and_fires_the_daily_triggers():
    command = workday_command("morning", "mspaint.exe")

    assert re.fullmatch(r'"[^"]+" -m workflow_factory\.workday --flow morning --app mspaint\.exe --fired daily', command)


def test_paths_with_spaces_are_quoted_in_the_command():
    command = workday_command("morning", "mspaint.exe", extra=["--report-dir", r"C:\My Reports\daily"])

    assert command.endswith(r'--report-dir "C:\My Reports\daily"')


@pytest.mark.parametrize("flow, app", [
    ("morning & calc", "mspaint.exe"), ("morning", "paint.exe | whoami"), ("../x", "mspaint.exe"),
    ('a" --flow other', "mspaint.exe"), ("", "mspaint.exe"),
])
def test_a_flow_or_app_name_that_could_inject_into_the_command_is_refused(flow, app):
    with pytest.raises(ValueError):
        workday_command(flow, app)


def test_creating_a_daily_task_builds_one_schtasks_call_without_a_shell():
    runner = Recorder()

    create_schedule("Workflow factory - morning", "morning", "mspaint.exe", daily_at="09:30", runner=runner)

    (call,) = runner.calls
    assert call[:2] == ["schtasks", "/Create"]
    assert call[call.index("/TN") + 1] == "Workflow factory - morning"
    assert call[call.index("/SC") + 1] == "DAILY" and call[call.index("/ST") + 1] == "09:30"
    assert "workflow_factory.workday" in call[call.index("/TR") + 1] and "/F" in call


@pytest.mark.parametrize("when", ["9:30", "25:00", "09:60", "morning", "09:30; calc"])
def test_a_time_that_is_not_a_clock_time_is_refused(when):
    with pytest.raises(ValueError, match="HH:MM"):
        create_schedule("morning-workday", "morning", "mspaint.exe", daily_at=when, runner=Recorder())


@pytest.mark.parametrize("name", ["", "bad/name", "a" * 121, 'x"y'])
def test_a_task_name_with_odd_characters_is_refused(name):
    with pytest.raises(ValueError, match="schedule name"):
        create_schedule(name, "morning", "mspaint.exe", daily_at="09:00", runner=Recorder())


def test_a_command_longer_than_windows_allows_is_refused_with_the_limit_in_the_message():
    runner = Recorder()

    with pytest.raises(ValueError, match="261"):
        create_schedule("morning-workday", "morning", "mspaint.exe", daily_at="09:00", extra=["--report-dir", "C:\\" + "x" * 300],
                    runner=runner)

    assert runner.calls == []  # nothing was sent to schtasks


def test_a_failing_schtasks_call_is_an_error_not_silence():
    with pytest.raises(RuntimeError, match="schtasks"):
        create_schedule("morning-workday", "morning", "mspaint.exe", daily_at="09:00", runner=Recorder(returncode=1))


def test_deleting_a_task_is_one_schtasks_call():
    runner = Recorder()

    delete_schedule("morning-workday", runner=runner)

    assert runner.calls == [["schtasks", "/Delete", "/TN", SCHEDULE_PREFIX + "morning-workday", "/F"]]


@pytest.mark.live
def test_windows_task_scheduler_really_launches_a_workday_without_any_ui():
    """Creates a throw-away task, runs it once, reads its last result and deletes it again.

    The flow does not exist in a temp database, so the workday exits 4 without touching any app.
    """
    import shutil
    import tempfile

    name = f"{SCHEDULE_PREFIX}dwf-live-test-{uuid.uuid4().hex[:8]}"
    projects = Path(tempfile.gettempdir()) / "live-tests" / "desktop-workflow-factory"
    short = projects / uuid.uuid4().hex[:8]  # short: the scheduler accepts at most 261 characters of command
    short.mkdir(parents=True)
    extra = ["--data-dir", str(short), "--no-hotkey"]
    try:
        create_schedule(name, "no-such-flow", "mspaint.exe", daily_at="03:00", extra=extra)
        subprocess.run(["schtasks", "/Run", "/TN", name], check=True, capture_output=True, timeout=30)
        query = ["powershell", "-NoProfile", "-Command",
                 f"$i = Get-ScheduledTaskInfo -TaskName '{name}'; $s = (Get-ScheduledTask -TaskName '{name}').State; "
                 "\"$($i.LastTaskResult) $s\""]
        result = ""
        for _ in range(40):  # up to ~20 s for the process to start and exit
            time.sleep(0.5)
            result = subprocess.run(query, capture_output=True, text=True, timeout=30).stdout.strip()
            code, _, state = result.partition(" ")
            if state == "Ready" and code != "267011":  # 267011: the task has never run yet
                break
    finally:
        delete_schedule(name)
        shutil.rmtree(short, ignore_errors=True)
        for folder in (projects, projects.parent):  # leave no residue: remove the shared roots if empty
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()

    assert result.startswith("4 "), result  # the workday's own exit code, relayed by the scheduler


def test_every_schedule_this_tool_makes_carries_its_prefix_so_it_can_be_listed_and_removed_safely():
    runner = Recorder()

    create_schedule("morning", "morning", "mspaint.exe", daily_at="09:00", runner=runner)
    delete_schedule("morning", runner=runner)
    delete_schedule(SCHEDULE_PREFIX + "morning", runner=runner)  # already prefixed: not doubled

    assert runner.calls[0][runner.calls[0].index("/TN") + 1] == SCHEDULE_PREFIX + "morning"
    assert runner.calls[1] == ["schtasks", "/Delete", "/TN", SCHEDULE_PREFIX + "morning", "/F"]
    assert runner.calls[2] == runner.calls[1]


def test_listing_shows_only_the_schedules_made_by_this_tool():
    csv = ('"\\Workflow factory - morning","N/A","Ready"\n"\\Microsoft\\Windows\\Other","N/A","Ready"\n'
           '"\\Workflow factory - evening","N/A","Disabled"\n')

    def runner(args, **kwargs):
        assert args[:2] == ["schtasks", "/Query"]
        return subprocess.CompletedProcess(args, 0, stdout=csv, stderr="")

    assert list_schedules(runner=runner) == ["Workflow factory - morning", "Workflow factory - evening"]


def test_a_schedule_is_described_by_its_flow_app_and_daily_time_not_just_its_name():
    from fake_scheduler import FakeScheduler

    from workflow_factory.schedule import describe_schedules

    scheduler = FakeScheduler()
    create_schedule("morning", "morning", "mspaint.exe", daily_at="09:30", runner=scheduler)

    assert describe_schedules(runner=scheduler) == [{"name": "morning", "flow": "morning", "app": "mspaint.exe", "at": "09:30"}]


def test_a_schedule_whose_details_cannot_be_read_is_still_listed_by_name():
    from workflow_factory.schedule import describe_schedules

    def runner(args, **kwargs):
        if "/XML" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="no")
        return subprocess.CompletedProcess(args, 0, stdout='"\\Workflow factory - odd","N/A","Ready"\n', stderr="")

    assert describe_schedules(runner=runner) == [{"name": "odd", "flow": None, "app": None, "at": None}]


def test_the_command_line_can_list_schedules_too(capsys):
    from workflow_factory.schedule import main

    assert main(["list"]) in (0, 1)  # reads the real scheduler: only checks that the subcommand exists


@pytest.mark.live
def test_the_real_task_scheduler_gives_back_the_flow_app_and_time_of_a_schedule_this_tool_made():
    from workflow_factory.schedule import describe_schedules

    name = f"{SCHEDULE_PREFIX}dwf-live-describe-{uuid.uuid4().hex[:8]}"
    try:
        create_schedule(name, "describe-me", "mspaint.exe", daily_at="03:07")
        found = [s for s in describe_schedules() if SCHEDULE_PREFIX + s["name"] == name]
    finally:
        delete_schedule(name)

    assert found == [{"name": name.removeprefix(SCHEDULE_PREFIX), "flow": "describe-me", "app": "mspaint.exe", "at": "03:07"}]
    assert not [s for s in describe_schedules() if SCHEDULE_PREFIX + s["name"] == name]  # and it is gone
