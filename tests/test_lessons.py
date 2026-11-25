from fake_desktop import FakeDesktop, button, lesson
import pytest
from workflow_factory import (
    Flow,
    LessonNotFound,
    Node,
    Status,
    answer_doubt,
    find_lesson,
    run_flow,
    save_lesson,
)


def flow_for(lesson_name):
    return Flow(nodes=[Node(id="n1", lesson=lesson_name)])


def test_local_lesson_shadows_factory_lesson_for_the_same_situation(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, lesson("open-menu", "Factory menu", origin="factory"))
    save_lesson(user_db, lesson("open-menu", "My menu"))
    desktop = FakeDesktop(controls=[button("Factory menu"), button("My menu")])

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert [c.name for c in desktop.clicks] == ["My menu"]


def test_factory_database_is_only_read_never_written(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, lesson("open-menu", "Menu", origin="factory"))
    before = factory_db.read_bytes()
    desktop = FakeDesktop(controls=[button("Menu")])

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert factory_db.read_bytes() == before


def test_version_change_marks_lessons_to_revalidate_keeps_them_and_blocks_replay(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-menu", "Menu", version="1.0"))
    save_lesson(user_db, lesson("other", "Other", version="1.0"))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert desktop.clicks == []
    assert result.blocked == {"n1": "to_revalidate"}
    kept = [find_lesson(user_db, None, "paint.exe", n) for n in ("open-menu", "other")]
    assert [k.status for k in kept] == [Status.TO_REVALIDATE, Status.TO_REVALIDATE]


def test_lesson_replays_again_once_it_is_re_measured_on_the_new_version(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-menu", "Menu", version="1.0"))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")
    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)
    assert desktop.clicks == []

    save_lesson(user_db, lesson("open-menu", "Menu", version="2.0"))
    answer_doubt(user_db, 1)
    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert result.blocked == {}


def test_factory_lesson_measured_on_another_version_is_not_replayed_or_written(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, lesson("open-menu", "Menu", version="1.0", origin="factory"))
    before = factory_db.read_bytes()
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    result = run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert desktop.clicks == []
    assert result.blocked == {"n1": "to_revalidate"}
    assert factory_db.read_bytes() == before


def test_unknown_lesson_stops_the_flow_without_clicking(tmp_path):
    desktop = FakeDesktop(controls=[button("Menu")])

    with pytest.raises(LessonNotFound):
        run_flow(flow_for("never-taught"), desktop=desktop, user_db=tmp_path / "user.db")

    assert desktop.clicks == []


def test_version_change_does_not_lift_a_rejection(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-menu", "Menu", version="1.0", status=Status.REJECTED))
    desktop = FakeDesktop(controls=[button("Menu")], version="2.0")

    run_flow(flow_for("open-menu"), desktop=desktop, user_db=user_db)

    assert find_lesson(user_db, None, "paint.exe", "open-menu").status == Status.REJECTED


def test_missing_factory_database_means_no_factory_lessons(tmp_path):
    desktop = FakeDesktop(controls=[button("Menu")])

    with pytest.raises(LessonNotFound):
        run_flow(flow_for("open-menu"), desktop=desktop, user_db=tmp_path / "user.db",
                 factory_db=tmp_path / "absent-factory.db")
