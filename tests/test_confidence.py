from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import Flow, Node, Status, restore_lesson, run_flow, save_lesson

FLOW = Flow(nodes=[Node(id="n1", lesson="open-menu")])


def working_desktop():
    """Click reveals a control, matching the lesson's taught effect."""
    return FakeDesktop(controls=[button("Menu")], reveals={("button", "Menu"): [button("Next")]})


def failing_desktop():
    """Click changes nothing: measured effect is no_change, not the taught 'revealed'."""
    return FakeDesktop(controls=[button("Menu")])


def teach_factory(factory_db, **counters):
    save_lesson(factory_db, lesson("open-menu", "Menu", origin="factory", effect="revealed", **counters))


def status_after_run(desktop, user_db, factory_db):
    return run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db).statuses["n1"]


def test_factory_lesson_with_high_counters_needs_two_own_successes_to_be_trusted(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=50)

    first = status_after_run(working_desktop(), user_db, factory_db)
    second = status_after_run(working_desktop(), user_db, factory_db)

    assert (first, second) == (Status.SUSPECT, Status.TRUSTED)


def test_failures_move_a_lesson_from_suspect_to_rejected_and_rejected_is_not_replayed(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=3)

    statuses = [status_after_run(failing_desktop(), user_db, factory_db) for _ in range(3)]
    desktop = working_desktop()
    result = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert statuses == [Status.SUSPECT, Status.SUSPECT, Status.REJECTED]
    assert desktop.clicks == []
    assert result.blocked == {"n1": "rejected"}


def test_only_an_explicit_human_restore_lets_a_rejected_lesson_run_again(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_successes=3)
    for _ in range(3):
        status_after_run(failing_desktop(), user_db, factory_db)
    # re-teaching or a version bump is not a restore
    save_lesson(user_db, lesson("open-menu", "Menu", effect="revealed", version="1.0"))
    still_blocked = run_flow(FLOW, desktop=working_desktop(), user_db=user_db, factory_db=factory_db)

    restore_lesson(user_db, app="paint.exe", name="open-menu")
    desktop = working_desktop()
    restored = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert still_blocked.blocked == {"n1": "rejected"}
    assert [c.name for c in desktop.clicks] == ["Menu"]
    assert restored.statuses == {"n1": Status.SUSPECT}


def test_a_factory_lesson_rejected_by_its_shipped_counters_can_be_restored_by_a_human(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    teach_factory(factory_db, factory_failures=2)  # confidence 1/8 = 0.125, rejected on arrival
    blocked = run_flow(FLOW, desktop=working_desktop(), user_db=user_db, factory_db=factory_db)

    restore_lesson(user_db, app="paint.exe", name="open-menu")
    desktop = working_desktop()
    run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert blocked.blocked == {"n1": "rejected"}
    assert [c.name for c in desktop.clicks] == ["Menu"]
