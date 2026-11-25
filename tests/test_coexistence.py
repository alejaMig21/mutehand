from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import (
    USER_IDLE_SECONDS,
    Flow,
    Node,
    answer_doubt,
    clear_emergency_stop,
    emergency_stop,
    list_doubts,
    run_flow,
    save_lesson,
)


def two_physical_nodes(user_db):
    save_lesson(user_db, lesson("a", "Alpha"))
    save_lesson(user_db, lesson("b", "Beta"))
    return Flow(id="f", nodes=[Node("a", "a", exclusive_input=True), Node("b", "b", exclusive_input=True)])


def clicked(desktop):
    return [c.name for c in desktop.clicks]


# --- the user and the apprentice share the PC -------------------------------------------------

def test_user_input_after_our_last_action_pauses_the_flow_until_the_user_is_idle(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.on_action.append(lambda: desktop.user_acts() if len(desktop.clicks) == 1 else None)

    result = run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert result.stopped is None and clicked(desktop) == ["Alpha", "Beta"]
    assert desktop.slept_total >= USER_IDLE_SECONDS  # it waited for the person to stop


def test_the_first_physical_action_also_waits_if_the_user_is_active_right_now(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.user_acts()

    run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert desktop.slept_total >= USER_IDLE_SECONDS and clicked(desktop) == ["Alpha", "Beta"]


def test_without_user_activity_nothing_waits(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert desktop.slept_total == 0


def test_after_the_idle_wait_preconditions_are_re_verified_before_resuming(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.on_action.append(lambda: desktop.user_acts() if len(desktop.clicks) == 1 else None)
    desktop.on_sleep.append(desktop.screen_changes)  # the screen changed while we waited

    result = run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert result.stopped == "b" and clicked(desktop) == ["Alpha"]
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]


def test_a_user_who_never_stops_ends_in_a_doubt_instead_of_waiting_forever(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.user_acts()
    desktop.on_sleep.append(desktop.user_acts)  # still busy every time we look

    result = run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert result.stopped == "a" and result.blocked == {"a": "user_active"} and desktop.clicks == []


# --- keys only go to the right window ------------------------------------------------------------

def typing_flow(user_db):
    save_lesson(user_db, lesson("typer", "Notes", action="type_value"))
    return Flow(id="t", nodes=[Node("t", "typer", inputs=(("text", "str"),))])


def test_keys_are_not_sent_when_the_target_window_is_not_in_the_foreground(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Notes")])
    desktop.foreground = "telegram.exe"  # the person switched to a chat

    result = run_flow(typing_flow(user_db), desktop=desktop, user_db=user_db, context={"text": "hi"})

    assert result.blocked == {"t": "wrong_window"} and desktop.typed == []
    assert [d.reason for d in list_doubts(user_db)] == ["precondition_not_met"]


def test_keys_are_sent_when_the_target_window_is_in_the_foreground(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Notes")])

    run_flow(typing_flow(user_db), desktop=desktop, user_db=user_db, context={"text": "hi"})

    assert [text for _, text in desktop.typed] == ["hi"]


# --- emergency stop ---------------------------------------------------------------------------------

def three_nodes(user_db):
    for name, control in (("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")):
        save_lesson(user_db, lesson(name, control))
    return Flow(id="f", nodes=[Node("a", "a"), Node("b", "b"), Node("c", "c")])


def test_the_emergency_stop_halts_the_flow_and_it_resumes_from_its_checkpoint_afterwards(tmp_path):
    user_db = tmp_path / "user.db"
    flow = three_nodes(user_db)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    desktop.on_action.append(lambda: emergency_stop() if len(desktop.clicks) == 1 else None)

    result = run_flow(flow, desktop=desktop, user_db=user_db)

    assert result.emergency is True and result.stopped is None and clicked(desktop) == ["Alpha"]
    assert list_doubts(user_db) == []  # a human stop is not a doubt for the tutor

    clear_emergency_stop()
    resumed = FakeDesktop(controls=[button("Alpha"), button("Beta"), button("Gamma")])
    after = run_flow(flow, desktop=resumed, user_db=user_db)

    assert after.emergency is False and clicked(resumed) == ["Beta", "Gamma"]


def test_the_emergency_stop_stops_every_running_flow_not_just_one(tmp_path):
    user_db = tmp_path / "user.db"
    flow = three_nodes(user_db)
    other = Flow(id="other", nodes=[Node("a", "a")])
    emergency_stop()
    first, second = FakeDesktop(controls=[button("Alpha")]), FakeDesktop(controls=[button("Alpha")])

    one = run_flow(flow, desktop=first, user_db=user_db)
    two = run_flow(other, desktop=second, user_db=user_db)

    assert one.emergency and two.emergency and first.clicks == [] and second.clicks == []


def test_waiting_for_the_user_never_holds_the_physical_input_lock(tmp_path):
    from workflow_factory.flow import PHYSICAL_INPUT

    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.user_acts()
    held_while_waiting = []
    desktop.on_sleep.append(lambda: held_while_waiting.append(PHYSICAL_INPUT.locked()))

    run_flow(two_physical_nodes(user_db), desktop=desktop, user_db=user_db)

    assert held_while_waiting and not any(held_while_waiting)  # other nodes are not starved
