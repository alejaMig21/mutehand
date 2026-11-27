import pytest

from workflow_factory import (
    Flow,
    Locator,
    Node,
    Sensitivity,
    Status,
    StudyStep,
    answer_doubt_by_teaching,
    find_step,
    list_open_doubts,
    mark_private,
    observe,
    record_consent,
    run_flow,
    save_step,
    set_study_order,
    study_status,
    teach_step,
)
from workflow_factory.desktop import Control

from fake_desktop import FakeDesktop, button, field, step


def test_observe_summarises_a_normal_app_by_roles_and_control_names(tmp_path):
    desktop = FakeDesktop(controls=[button("Save"), field("Notes")], app="paint.exe")

    assert observe(tmp_path / "user.db", desktop) == {
        "app": "paint.exe",
        "private": False,
        "roles": {"button": 1, "textfield": 1},
        "controls": [{"role": "button", "name": "Save", "automation_id": ""},
                     {"role": "textfield", "name": "Notes", "automation_id": ""}],
    }


def test_observing_a_private_app_returns_only_roles_and_counts(tmp_path):
    user_db = tmp_path / "user.db"
    mark_private(user_db, "banking.exe")
    desktop = FakeDesktop(controls=[button("Account 4242"), button("Pay Maria")], app="banking.exe")

    summary = observe(user_db, desktop)

    assert summary == {"app": "banking.exe", "private": True, "roles": {"button": 2}}
    assert "4242" not in repr(summary) and "Maria" not in repr(summary)


def test_telegram_and_browsers_are_private_by_default(tmp_path):
    for app in ("telegram.exe", "vivaldi.exe", "chrome.exe", "msedge.exe"):
        summary = observe(tmp_path / "user.db", FakeDesktop(controls=[button("Chat")], app=app))
        assert summary["private"] is True and "controls" not in summary


def test_a_step_is_saved_as_soon_as_its_effect_is_measured(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Open menu")], reveals={("button", "Open menu"): [button("Save as")]})

    result = teach_step(user_db, desktop, name="open-menu", locator=Locator("button", "Open menu"))

    saved = find_step(user_db, None, "paint.exe", "open-menu")
    assert result == {"status": "saved", "step": "open-menu", "effect": "revealed"}
    assert saved.effect == "revealed" and saved.version == "1.0" and saved.frame == desktop.frame()


@pytest.mark.parametrize("action", ["type_value", "paste_text", "press_keys"])
def test_teaching_a_step_that_writes_text_only_proves_the_control_and_acts_on_nothing(tmp_path, action):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[field("Name field")])
    desktop.fail_on = {"Name field"}  # a real text field refuses a click without real input

    result = teach_step(user_db, desktop, name="write", locator=Locator("textfield", "Name field"), action=action)

    assert result == {"status": "saved", "step": "write", "effect": "no_change"}
    assert desktop.clicks == [] and desktop.typed == [] and desktop.pressed == []
    # nothing was done, so there is no taught effect that a later run could contradict
    assert find_step(user_db, None, "paint.exe", "write").effect == ""


@pytest.mark.parametrize("app", ["excel.exe", "grid.exe"])
def test_a_cell_refuses_a_value_write_in_any_app_because_it_can_report_it_and_stay_empty(tmp_path, app):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[Control(role="cell", name="B2")], app=app)

    refused = teach_step(user_db, desktop, name="write", locator=Locator("cell", "B2"), action="type_value")

    assert refused == {"status": "cell_requires_paste_text"} and find_step(user_db, None, app, "write") is None
    assert teach_step(user_db, desktop, name="write", locator=Locator("cell", "B2"), action="paste_text")["status"] == "saved"


def test_a_select_step_clicks_leaves_any_editor_and_teaches_no_effect(tmp_path):
    user_db = tmp_path / "user.db"
    cell = Control(role="cell", name="B2")
    desktop = FakeDesktop(controls=[cell], app="grid.exe", reveals={("cell", "B2"): [button("Fill handle")]})

    teach_step(user_db, desktop, name="select", locator=Locator("cell", "B2"), action="select")

    assert desktop.clicks == [cell] and desktop.pressed == [("escape", "grid.exe")]
    # what changes on screen depends on what is selected: nothing a later run could contradict
    assert find_step(user_db, None, "grid.exe", "select").effect == ""


def test_teaching_a_select_that_loses_the_window_presses_nothing_and_saves_nothing(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[Control(role="cell", name="B2")], app="grid.exe")
    desktop.on_action.append(lambda: setattr(desktop, "foreground", "chrome.exe"))

    result = teach_step(user_db, desktop, name="select", locator=Locator("cell", "B2"), action="select")

    assert result == {"status": "wrong_window"} and desktop.pressed == []
    assert find_step(user_db, None, "grid.exe", "select") is None


def test_a_click_on_a_cell_is_an_ordinary_click_whatever_the_app_is_called(tmp_path):
    user_db = tmp_path / "user.db"
    cell = Control(role="cell", name="B2")
    desktop = FakeDesktop(controls=[cell], app="excel.exe", reveals={("cell", "B2"): [button("Fill handle")]})

    teach_step(user_db, desktop, name="open", locator=Locator("cell", "B2"))

    assert desktop.clicks == [cell] and desktop.pressed == []
    assert find_step(user_db, None, "excel.exe", "open").effect == "revealed"


def test_selecting_a_control_named_like_an_outward_action_still_asks_for_consent(tmp_path):
    desktop = FakeDesktop(controls=[button("Send")])

    asked = teach_step(tmp_path / "user.db", desktop, name="pick", locator=Locator("button", "Send"), action="select")

    assert asked["status"] == "consent_required" and desktop.clicks == []


def test_an_interrupted_study_resumes_at_the_first_step_without_a_step(tmp_path):
    user_db = tmp_path / "user.db"
    steps = [StudyStep("open-menu", Locator("button", "Menu")),
             StudyStep("save-file", Locator("button", "Save")),
             StudyStep("close", Locator("button", "Close"))]
    set_study_order(user_db, "paint.exe", steps)
    teach_step(user_db, FakeDesktop(controls=[button("Menu")]), name="open-menu",
                 locator=Locator("button", "Menu"))
    # the tutor session dies here; a new session asks where to continue

    assert study_status(user_db, "paint.exe") == {
        "done": 1, "total": 3,
        "next": {"name": "save-file", "role": "button", "control_name": "Save", "automation_id": None}}


def test_a_sensitive_category_stops_the_teaching_and_asks_for_consent_before_saving(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Send")])

    asked = teach_step(user_db, desktop, name="send-message", locator=Locator("button", "Send"),
                         sensitive=Sensitivity.OUTWARD_ACTION)

    assert asked == {"status": "consent_required", "category": "outward_action",
                     "scope": {"app": "paint.exe", "control": "Send", "action": "click"}}
    assert find_step(user_db, None, "paint.exe", "send-message") is None
    assert desktop.clicks == []

    record_consent(user_db, app="paint.exe", control="Send", action="click")  # the user said yes
    saved = teach_step(user_db, desktop, name="send-message", locator=Locator("button", "Send"),
                         sensitive=Sensitivity.OUTWARD_ACTION)

    assert saved["status"] == "saved"
    assert find_step(user_db, None, "paint.exe", "send-message").sensitive == Sensitivity.OUTWARD_ACTION


def test_an_outward_looking_control_asks_for_consent_even_if_the_tutor_did_not_declare_it(tmp_path):
    desktop = FakeDesktop(controls=[button("Send message")])

    asked = teach_step(tmp_path / "user.db", desktop, name="send", locator=Locator("button", "Send message"))

    assert asked["status"] == "consent_required" and asked["category"] == "outward_action"
    assert desktop.clicks == []


def test_a_secure_field_is_recognised_as_a_password_field_and_only_takes_secrets(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Password", secure=True)], secrets={"login": "hunter2"})

    asked = teach_step(user_db, desktop, name="login", locator=Locator("button", "Password"))
    record_consent(user_db, app="paint.exe", control="Password", action="click")
    wrong_action = teach_step(user_db, desktop, name="login", locator=Locator("button", "Password"))
    record_consent(user_db, app="paint.exe", control="Password", action="type_secret")
    saved = teach_step(user_db, desktop, name="login", locator=Locator("button", "Password"),
                         action="type_secret", secret_ref="login")

    assert asked["status"] == "consent_required" and asked["category"] == "password_field"
    assert wrong_action["status"] == "secure_field_requires_type_secret"
    assert saved["status"] == "saved" and desktop.clicks == []


def test_a_control_the_apprentice_cannot_perceive_is_never_taught_and_asks_for_no_consent(tmp_path):
    desktop = FakeDesktop(controls=[button("Ghost", readable=False)])

    result = teach_step(tmp_path / "user.db", desktop, name="ghost", locator=Locator("button", "Ghost"))

    assert result == {"status": "unreadable"} and desktop.clicks == []


def test_teaching_a_secret_returns_only_its_reference(tmp_path):
    user_db = tmp_path / "user.db"
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})
    record_consent(user_db, app="paint.exe", control="Password", action="type_secret")

    result = teach_step(user_db, desktop, name="login", locator=Locator("button", "Password"),
                          action="type_secret", secret_ref="login", sensitive=Sensitivity.PASSWORD_FIELD)

    assert result["status"] == "saved"
    assert "hunter2" not in repr(result) and "hunter2" not in repr(desktop.calls)


def test_only_open_doubts_are_listed_and_answering_by_teaching_lets_the_flow_resume(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    flow = Flow(id="morning", nodes=[Node(id="n1", step="open-menu")])
    run_flow(flow, desktop=FakeDesktop(controls=[button("Main menu")]), user_db=user_db)  # stops

    (doubt,) = list_open_doubts(user_db)
    assert doubt == {"id": 1, "flow_id": "morning", "node_id": "n1", "step": "open-menu",
                     "reason": "control_not_found", "detail": "control_not_found", "capture": {"button": 1},
                     "status": "open", "note": None}

    desktop = FakeDesktop(controls=[button("Main menu")])
    answered = answer_doubt_by_teaching(user_db, desktop, doubt_id=1, name="open-menu",
                                        locator=Locator("button", "Main menu"))

    assert answered["status"] == "answered" and list_open_doubts(user_db) == []
    resumed = FakeDesktop(controls=[button("Main menu")])
    result = run_flow(flow, desktop=resumed, user_db=user_db)
    assert result.stopped is None and [c.name for c in resumed.clicks] == ["Main menu"]


def test_a_step_that_could_not_be_saved_is_never_performed(tmp_path):
    desktop = FakeDesktop(controls=[button("Menu")])

    with pytest.raises(ValueError):  # a secret reference makes no sense for a plain click
        teach_step(tmp_path / "user.db", desktop, name="x", locator=Locator("button", "Menu"),
                     action="click", secret_ref="login")

    assert desktop.calls == []


def test_a_study_step_counts_as_done_only_for_a_current_step_on_the_same_control(tmp_path):
    user_db = tmp_path / "user.db"
    set_study_order(user_db, "paint.exe", [StudyStep("open-menu", Locator("button", "Menu")),
                                           StudyStep("save", Locator("button", "Save"))])
    save_step(user_db, step("open-menu", "Another control"))  # same name, different control
    save_step(user_db, step("save", "Save", status=Status.TO_REVALIDATE))  # app was updated

    assert study_status(user_db, "paint.exe")["done"] == 0


def test_a_doubt_can_only_be_answered_with_its_own_step_and_while_open(tmp_path):
    user_db = tmp_path / "user.db"
    save_step(user_db, step("open-menu", "Menu"))
    run_flow(Flow(id="a", nodes=[Node(id="n1", step="open-menu")]), desktop=FakeDesktop(controls=[]),
             user_db=user_db)
    desktop = FakeDesktop(controls=[button("Other")])

    with pytest.raises(ValueError, match="open-menu"):  # the doubt is about another step
        answer_doubt_by_teaching(user_db, desktop, doubt_id=1, name="something-else",
                                 locator=Locator("button", "Other"))
    with pytest.raises(ValueError):  # no such doubt
        answer_doubt_by_teaching(user_db, desktop, doubt_id=99, name="open-menu",
                                 locator=Locator("button", "Other"))

    assert desktop.calls == [] and len(list_open_doubts(user_db)) == 1


def test_private_apps_are_recognised_by_name_without_exe_suffix_or_case(tmp_path):
    for app in ("Telegram", "TELEGRAM.EXE", "vivaldi"):
        summary = observe(tmp_path / "user.db", FakeDesktop(controls=[button("Chat")], app=app))
        assert summary["private"] is True and "controls" not in summary
