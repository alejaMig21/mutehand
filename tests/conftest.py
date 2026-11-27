import subprocess

import pytest

from workflow_factory import agent_desktop, clear_emergency_stop


@pytest.fixture(autouse=True)
def _no_leaked_emergency_stop():
    clear_emergency_stop()
    yield
    clear_emergency_stop()


@pytest.fixture(autouse=True)
def _never_move_the_real_mouse(request, monkeypatch):
    """Only opt-in live tests may touch the person's cursor; everything else must inject a mover."""
    if request.node.get_closest_marker("live"):
        return

    def refuse(*args, **kwargs):
        raise AssertionError("a default test tried to move the real mouse: inject move_cursor")

    monkeypatch.setattr(agent_desktop, "_set_cursor_pos", refuse)


@pytest.fixture(autouse=True)
def _never_change_real_scheduled_tasks(request, monkeypatch):
    """The editor server uses the real schtasks unless given a stand-in: a default test must not change Windows tasks."""
    if request.node.get_closest_marker("live"):
        return
    start = subprocess.Popen.__init__

    def guarded(self, args, *rest, **kwargs):
        command = [args] if isinstance(args, str) else [str(a) for a in args]
        if command[0].lower().startswith("schtasks") and any(a.lower() in ("/create", "/delete", "/change", "/run") for a in command):
            raise AssertionError("a default test tried to change a real scheduled task: inject FakeScheduler")
        start(self, args, *rest, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", guarded)


@pytest.fixture(autouse=True)
def _editor_server_never_reads_the_real_scheduler(request, monkeypatch):
    """A server made without a scheduler stand-in gets an empty one, so no default test reads this machine's tasks."""
    if request.node.get_closest_marker("live"):
        return
    from fake_scheduler import FakeScheduler

    monkeypatch.setattr("workflow_factory.api._real_scheduler", FakeScheduler())


@pytest.fixture(autouse=True)
def _a_working_setup(monkeypatch):
    """Home lists a missing required program as needing the person: what this PC has installed must not decide a test."""
    monkeypatch.setattr("workflow_factory.attention.run_checks", lambda data_dir: [])
