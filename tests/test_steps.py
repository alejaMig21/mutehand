
from workflow_factory import (
    Flow,
    Node,
    Status,
    answer_doubt,
    find_step,
    run_flow,
    save_step,
)

from fake_desktop import FakeDesktop, button, step


def flow_for(step_name):
    return Flow(nodes=[Node(id="n1", step=step_name)])


def test_local_step_shadows_factory_step_for_the_same_situation(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_step(factory_db, step("open-menu", "Factory menu", origin="factory"))
    save_step(user_db, step("open-menu", "My menu"))
    desktop = FakeDesktop(controls=[button("Factory menu"), button("My menu")])

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert [c.name for c in desktop.clicks] == ["My menu"]


def test_factory_database_is_only_read_never_written(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_step(factory_db, step("open-menu", "Menu", origin="factory"))
    before = factory_db.read_bytes()
    desktop = FakeDesktop(controls=[button("Menu")])

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert factory_db.read_bytes() == before


def test_version_change_marks_steps_to_revalidate_keeps_them_and_blocks_replay(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", version="1.0"))
    save_step(user_db, step("other", "Other", version="1.0"))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert desktop.clicks == []
    assert result.blocked == {"n1": "to_revalidate"}
    kept = [find_step(user_db, None, "paint.exe", n) for n in ("open-menu", "other")]
    assert [k.status for k in kept] == [Status.TO_REVALIDATE, Status.TO_REVALIDATE]


def test_step_replays_again_once_it_is_re_measured_on_the_new_version(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", version="1.0"))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")
    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)
    assert desktop.clicks == []

    save_step(user_db, step("open-menu", "Menu", version="2.0"))
    answer_doubt(user_db, 1)
    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert result.blocked == {}


def test_factory_step_measured_on_another_version_is_not_replayed_or_written(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_step(factory_db, step("open-menu", "Menu", version="1.0", origin="factory"))
    before = factory_db.read_bytes()
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert desktop.clicks == []
    assert result.blocked == {"n1": "to_revalidate"}
    assert factory_db.read_bytes() == before


def test_unknown_step_stops_the_flow_without_clicking(tmp_path):
    desktop = FakeDesktop(controls=[button("Menu")])

    result = run_flow(flow_for("never-taught"), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.stopped == "n1" and desktop.clicks == []


def test_version_change_does_not_lift_a_rejection(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu", version="1.0", status=Status.REJECTED))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert find_step(user_db, None, "paint.exe", "open-menu").status == Status.REJECTED


def test_missing_factory_database_means_no_factory_steps(tmp_path):
    desktop = FakeDesktop(controls=[button("Menu")])

    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=tmp_path / "user.db",
                      factory_db=tmp_path / "absent-factory.db")

    assert result.stopped == "n1" and desktop.clicks == []  # no step anywhere, and no crash
