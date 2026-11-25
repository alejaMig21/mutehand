import pytest
from fake_desktop import FakeDesktop, button, lesson
from workflow_factory import (
    Consent,
    Flow,
    answer_doubt,
    Node,
    Sensitivity,
    consents,
    grant_consent,
    revoke_consent,
    run_flow,
    save_lesson,
)

FLOW = Flow(nodes=[Node(id="n1", lesson="send-message")])


def sensitive_lesson(**kw):
    return lesson("send-message", "Send", sensitive=Sensitivity.OUTWARD_ACTION, **kw)


def run(user_db, desktop=None, factory_db=None):
    desktop = desktop or FakeDesktop(controls=[button("Send")])
    return desktop, run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)


def test_sensitive_lesson_without_consent_is_blocked_before_reaching_the_desktop(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, sensitive_lesson())

    desktop, result = run(user_db)

    assert result.blocked == {"n1": "no_consent"}
    assert desktop.calls == []


def test_granted_consent_is_stored_with_its_scope_and_the_lesson_then_runs(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, sensitive_lesson())

    grant_consent(user_db, app="paint.exe", control="Send", action="click")
    desktop, result = run(user_db)

    assert consents(user_db) == [Consent(app="paint.exe", control="Send", action="click")]
    assert result.blocked == {}
    assert [c.name for c in desktop.clicks] == ["Send"]


def test_revoking_a_consent_blocks_the_lesson_again(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, sensitive_lesson())
    grant_consent(user_db, app="paint.exe", control="Send", action="click")

    revoke_consent(user_db, app="paint.exe", control="Send", action="click")
    desktop, result = run(user_db)

    assert result.blocked == {"n1": "no_consent"}
    assert desktop.calls == []
    assert consents(user_db) == []


def test_broad_consent_covers_any_control_of_the_app_for_that_action(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, sensitive_lesson())
    grant_consent(user_db, app="paint.exe", control="*", action="click")

    desktop, result = run(user_db)

    assert result.blocked == {}
    assert [c.name for c in desktop.clicks] == ["Send"]


def test_an_unreadable_control_is_blocked_even_with_a_broad_consent(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, sensitive_lesson())
    grant_consent(user_db, app="paint.exe", control="*", action="click")

    desktop, result = run(user_db, FakeDesktop(controls=[button("Send", readable=False)]))

    assert result.blocked == {"n1": "unreadable"}
    assert desktop.clicks == []


def test_factory_lesson_in_a_sensitive_category_ships_without_consent(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, sensitive_lesson(origin="factory"))

    _, blocked = run(user_db, factory_db=factory_db)
    grant_consent(user_db, app="paint.exe", control="Send", action="click")
    answer_doubt(user_db, 1)
    desktop, allowed = run(user_db, factory_db=factory_db)

    assert blocked.blocked == {"n1": "no_consent"}
    assert allowed.blocked == {}
    assert [c.name for c in desktop.clicks] == ["Send"]


def secret_lesson():
    return lesson("send-message", "Password", action="type_secret", secret_ref="login",
                  sensitive=Sensitivity.PASSWORD_FIELD)


def test_secret_reaches_the_target_by_reference_and_never_appears_in_recorded_calls(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, secret_lesson())
    grant_consent(user_db, app="paint.exe", control="Password", action="type_secret")
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})

    run_flow(FLOW, desktop=desktop, user_db=user_db)

    assert desktop.delivered == [("Password", "hunter2")]  # the target did receive it
    assert "hunter2" not in repr(desktop.calls)
    assert b"hunter2" not in user_db.read_bytes()  # lessons hold only the reference


def test_secret_lesson_without_consent_types_nothing(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, secret_lesson())
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})

    result = run_flow(FLOW, desktop=desktop, user_db=user_db)

    assert result.blocked == {"n1": "no_consent"}
    assert desktop.delivered == []


def test_a_lesson_that_types_a_secret_must_be_marked_as_a_password_field(tmp_path):
    with pytest.raises(ValueError, match="secret"):
        save_lesson(tmp_path / "user.db", lesson("x", "Password", action="type_secret", secret_ref="login"))


def test_an_unreadable_control_blocks_even_a_non_sensitive_lesson(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("send-message", "Send"))

    desktop, result = run(user_db, FakeDesktop(controls=[button("Send", readable=False)]))

    assert result.blocked == {"n1": "unreadable"}
    assert desktop.clicks == []


def test_typing_a_secret_needs_consent_even_when_a_factory_lesson_forgot_the_label(tmp_path):
    factory_db, user_db = tmp_path / "factory.db", tmp_path / "user.db"
    save_lesson(factory_db, lesson("send-message", "Password", origin="factory",
                                   action="type_secret", secret_ref="login",
                                   sensitive=Sensitivity.PASSWORD_FIELD))
    # the shipped row loses its label (factory files are written outside save_lesson's guard)
    import sqlite3
    with sqlite3.connect(factory_db) as db:
        db.execute("UPDATE lessons SET sensitive = NULL")
    desktop = FakeDesktop(controls=[button("Password")], secrets={"login": "hunter2"})

    result = run_flow(FLOW, desktop=desktop, user_db=user_db, factory_db=factory_db)

    assert result.blocked == {"n1": "no_consent"}
    assert desktop.delivered == []
