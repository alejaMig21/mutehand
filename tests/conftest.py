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
