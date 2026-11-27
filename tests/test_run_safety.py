"""The run view's engine side: which steps are rejected, and a pause for the person is visible."""

from workflow_factory import Flow, Node, list_doubts, reject_step, run_flow, save_step
from workflow_factory.flow import rejected_steps

from fake_desktop import FakeDesktop, button, step


def teach(user_db):
    save_step(user_db, step("open-menu", "Alpha"))
    save_step(user_db, step("save-file", "Beta"))


def flow():
    return Flow(id="f", nodes=[Node("a", "open-menu"), Node("b", "save-file")])


def test_a_scheduled_run_still_starts_and_stops_at_a_rejected_step_leaving_a_doubt_the_tutor_will_see(tmp_path):
    teach(tmp_path / "user.db")
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")

    result = run_flow(flow(), desktop=FakeDesktop(controls=[button("Alpha"), button("Beta")]), user_db=tmp_path / "user.db")

    assert result.status == "stopped" and result.blocked == {"b": "rejected"}
    assert [(d.node_id, d.step) for d in list_doubts(tmp_path / "user.db")] == [("b", "save-file")]


def test_every_rejected_step_is_named_not_only_the_first(tmp_path):
    teach(tmp_path / "user.db")
    for name in ("open-menu", "save-file"):
        reject_step(tmp_path / "user.db", "paint.exe", name)

    found = rejected_steps(flow(), FakeDesktop(controls=[]), tmp_path / "user.db", None)

    assert found == (("a", "open-menu", "paint.exe"), ("b", "save-file", "paint.exe"))


def test_a_restored_step_lets_the_flow_start_again(tmp_path):
    from workflow_factory import restore_step
    teach(tmp_path / "user.db")
    reject_step(tmp_path / "user.db", "paint.exe", "save-file")
    restore_step(tmp_path / "user.db", "paint.exe", "save-file")

    result = run_flow(flow(), desktop=FakeDesktop(controls=[button("Alpha"), button("Beta")]), user_db=tmp_path / "user.db")

    assert result.status == "finished"


def test_a_flow_that_names_a_step_nobody_taught_is_not_refused_it_stops_with_a_doubt_as_before(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))

    result = run_flow(flow(), desktop=FakeDesktop(controls=[button("Alpha")]), user_db=tmp_path / "user.db")

    assert result.status == "stopped" and result.blocked == {"b": "step_missing"}


def test_a_pause_because_the_person_is_using_the_pc_is_reported_and_then_the_node_runs_again(tmp_path):
    teach(tmp_path / "user.db")
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.user_acts()  # the person is moving the mouse right now
    events = []

    result = run_flow(flow(), desktop=desktop, user_db=tmp_path / "user.db",
                      progress=lambda node, status: events.append((node, status)))

    assert result.status == "finished"
    assert ("a", "paused") in events
    assert events.index(("a", "paused")) < events.index(("a", "done"))
    assert events[events.index(("a", "paused")) + 1] == ("a", "running")
