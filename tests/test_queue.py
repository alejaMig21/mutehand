import sqlite3
from contextlib import closing

import pytest

from workflow_factory import (
    Doubt,
    Flow,
    Node,
    Sensitivity,
    answer_doubt,
    dismiss_doubt,
    list_doubts,
    run_flow,
    save_step,
)
from workflow_factory.desktop import Frame

from fake_desktop import FakeDesktop, button, field, step


def flow(flow_id, *step_names):
    return Flow(id=flow_id, nodes=[Node(id=f"n{i}", step=n) for i, n in enumerate(step_names, 1)])


def test_a_stop_writes_one_open_doubt_with_a_structural_capture(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    desktop = FakeDesktop(controls=[button("Other"), button("Another"), field("Private diary text")])

    result = run_flow(flow("morning", "open-menu"), desktop=desktop, user_db=user_db)

    assert result.stopped == "n1"
    assert list_doubts(user_db) == [Doubt(
        id=1, flow_id="morning", node_id="n1", step="open-menu", reason="control_not_found",
        capture={"button": 2, "textfield": 1}, status="open", detail="control_not_found")]


def test_the_structural_capture_holds_no_text_content(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    desktop = FakeDesktop(controls=[field("Private diary text")])

    run_flow(flow("morning", "open-menu"), desktop=desktop, user_db=user_db)

    assert "Private diary text" not in repr(list_doubts(user_db))
    assert b"Private diary text" not in user_db.read_bytes()


def test_an_independent_flow_keeps_running_while_another_is_stopped(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    save_step(user_db, step("save-file", "Save"))
    stuck = run_flow(flow("a", "open-menu"), desktop=FakeDesktop(controls=[]), user_db=user_db)
    desktop = FakeDesktop(controls=[button("Save")])

    other = run_flow(flow("b", "save-file"), desktop=desktop, user_db=user_db)
    again = run_flow(flow("a", "open-menu"), desktop=FakeDesktop(controls=[button("Menu")]), user_db=user_db)

    assert stuck.stopped == "n1" and other.stopped is None
    assert [c.name for c in desktop.clicks] == ["Save"]
    assert again.waiting is True  # still stopped: the doubt is open


def test_an_answered_doubt_lets_the_stopped_flow_resume_from_its_last_checkpoint(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    save_step(user_db, step("save-file", "Save"))
    first = FakeDesktop(controls=[button("Menu")])  # "Save" is missing: stops at n2
    run_flow(flow("a", "open-menu", "save-file"), desktop=first, user_db=user_db)

    answer_doubt(user_db, 1)
    second = FakeDesktop(controls=[button("Menu"), button("Save")])
    result = run_flow(flow("a", "open-menu", "save-file"), desktop=second, user_db=user_db)

    assert [c.name for c in first.clicks] == ["Menu"]
    assert [c.name for c in second.clicks] == ["Save"]  # n1 was not repeated
    assert result.stopped is None and result.waiting is False


def test_a_finished_flow_starts_from_the_beginning_next_time(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    run_flow(flow("a", "open-menu"), desktop=FakeDesktop(controls=[button("Menu")]), user_db=user_db)
    desktop = FakeDesktop(controls=[button("Menu")])

    run_flow(flow("a", "open-menu"), desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]


def test_doubt_status_moves_only_among_open_answered_and_dismissed(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    for flow_id in ("a", "b"):
        run_flow(flow(flow_id, "open-menu"), desktop=FakeDesktop(controls=[]), user_db=user_db)

    answer_doubt(user_db, 1)
    dismiss_doubt(user_db, 2)

    assert [d.status for d in list_doubts(user_db)] == ["answered", "dismissed"]
    assert list_doubts(user_db, status="open") == []
    with pytest.raises(ValueError):  # a closed doubt is not reopened or re-answered
        answer_doubt(user_db, 2)
    with closing(sqlite3.connect(user_db)) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE doubts SET status = 'pending' WHERE id = 1")


@pytest.mark.parametrize(
    "step_kw, desktop_kw, expected",
    [
        ({"sensitive": Sensitivity.OUTWARD_ACTION}, {}, "no_consent"),
        ({}, {"controls": []}, "control_not_found"),
        ({}, {"controls": [button("Menu", readable=False)]}, "control_not_found"),
        ({"frame": Frame(scale=1.25), "mask": ("scale",)}, {"frame": Frame(scale=2.0)},
         "precondition_not_met"),
        ({"version": "1.0"}, {"version": "2.0"}, "precondition_not_met"),
    ],
    ids=["no consent", "control missing", "control unreadable", "out of frame", "app updated"],
)
def test_every_stop_uses_one_of_the_fixed_reasons(tmp_path, step_kw, desktop_kw, expected):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", **step_kw))
    desktop = FakeDesktop(**{"controls": [button("Menu")], **desktop_kw})

    run_flow(flow("a", "open-menu"), desktop=desktop, user_db=user_db)

    assert [d.reason for d in list_doubts(user_db)] == [expected]


def test_a_dismissed_doubt_abandons_the_stopped_run_so_the_next_run_starts_over(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    save_step(user_db, step("save-file", "Save"))
    run_flow(flow("a", "open-menu", "save-file"), desktop=FakeDesktop(controls=[button("Menu")]),
             user_db=user_db)

    dismiss_doubt(user_db, 1)
    desktop = FakeDesktop(controls=[button("Menu"), button("Save")])
    run_flow(flow("a", "open-menu", "save-file"), desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu", "Save"]  # from the beginning, not resumed


def test_a_checkpoint_of_a_different_flow_definition_is_not_resumed(tmp_path):
    user_db = tmp_path / "user.db"
    for name, control in (("open-menu", "Menu"), ("save-file", "Save"), ("close", "Close")):
        save_step(user_db, step(name, control))
    run_flow(flow("a", "open-menu", "save-file"), desktop=FakeDesktop(controls=[button("Menu")]),
             user_db=user_db)
    answer_doubt(user_db, 1)

    edited = flow("a", "close", "open-menu", "save-file")  # nodes n1..n3 now mean other steps
    desktop = FakeDesktop(controls=[button("Menu"), button("Save"), button("Close")])
    run_flow(edited, desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Close", "Menu", "Save"]


def test_flows_built_without_an_id_do_not_share_doubts_or_checkpoints(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    save_step(user_db, step("save-file", "Save"))
    stuck = Flow(nodes=[Node(id="n1", step="open-menu")])
    other = Flow(nodes=[Node(id="m1", step="save-file")])
    run_flow(stuck, desktop=FakeDesktop(controls=[]), user_db=user_db)

    desktop = FakeDesktop(controls=[button("Save")])
    result = run_flow(other, desktop=desktop, user_db=user_db)

    assert result.waiting is False and [c.name for c in desktop.clicks] == ["Save"]
