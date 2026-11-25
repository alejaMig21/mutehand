"""A read step takes a text out of a control and gives it out as Data. Reading acts on nothing, so it needs no input
lock and does not wait for the person; a private app lets it read only with consent; values never reach a report."""

import pytest

from workflow_factory import Flow, Node, grant_consent, run_flow, save_flow, save_step
from workflow_factory.workday import main

from fake_desktop import FakeDesktop, button, step


def teach(user_db, app="paint.exe"):
    save_step(user_db, step("read-title", "Title", action="read_value", app=app))
    save_step(user_db, step("typer", "Notes", action="type_value", app=app))


def desktop_with(texts, app="paint.exe", controls=("Title", "Notes"), **kw):
    desktop = FakeDesktop(controls=[button(name) for name in controls], app=app, **kw)
    desktop.texts = texts
    return desktop


def read_then_type():
    ref = {"ref": {"node": "r", "field": "value"}}
    return Flow(id="f", nodes=[Node("r", "read-title"), Node("t", "typer", fields={"text": ref})])


def test_a_read_step_gives_the_control_text_out_as_data_for_a_later_node(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with({"Title": "Quarterly report"})

    result = run_flow(read_then_type(), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and result.outputs["r"]["value"] == "Quarterly report"
    assert [text for _, text in desktop.typed] == ["Quarterly report"]


def test_reading_takes_no_input_lock_and_does_not_wait_for_the_person(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with({"Title": "x"})
    desktop._last_input = desktop._seconds()  # the person is typing right now

    result = run_flow(Flow(id="f", nodes=[Node("r", "read-title")]), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished" and desktop.slept_total == 0 and desktop.reads == ["Title"]
    assert desktop.clicks == [] and desktop.typed == []


def test_a_control_with_no_text_reads_as_an_empty_value(tmp_path):
    teach(tmp_path / "user.db")

    result = run_flow(Flow(id="f", nodes=[Node("r", "read-title")]), desktop=desktop_with({}), user_db=tmp_path / "user.db")

    assert result.outputs["r"]["value"] == ""


def test_a_private_app_is_read_only_after_the_person_consents(tmp_path):
    user_db = tmp_path / "user.db"
    teach(user_db, app="telegram.exe")
    desktop = desktop_with({"Title": "secret chat"}, app="telegram.exe")
    flow = Flow(id="f", nodes=[Node("r", "read-title")])

    blocked = run_flow(flow, desktop=desktop, user_db=user_db)

    assert blocked.status == "stopped" and blocked.blocked == {"r": "no_consent"} and desktop.reads == []

    from workflow_factory import answer_doubt
    answer_doubt(user_db, 1)
    grant_consent(user_db, "telegram.exe", "Title", "read_value")

    allowed = run_flow(flow, desktop=desktop, user_db=user_db)

    assert allowed.status == "finished" and allowed.outputs["r"]["value"] == "secret chat"


def test_an_app_that_is_not_private_is_read_without_consent(tmp_path):
    teach(tmp_path / "user.db")
    desktop = desktop_with({"Title": "ok"})

    result = run_flow(Flow(id="f", nodes=[Node("r", "read-title")]), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.status == "finished"


def test_a_password_field_is_never_read(tmp_path):
    teach(tmp_path / "user.db")
    desktop = FakeDesktop(controls=[button("Title", secure=True)])
    desktop.texts = {"Title": "hunter2"}

    result = run_flow(Flow(id="f", nodes=[Node("r", "read-title")]), desktop=desktop, user_db=tmp_path / "user.db")

    assert result.blocked == {"r": "unreadable"} and desktop.reads == []


def test_the_report_of_a_workday_never_holds_what_was_read(tmp_path):
    teach(tmp_path / "user.db")
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=read_then_type().nodes))
    desktop = desktop_with({"Title": "Salary 99,000"})

    code = main(["--flow", "morning", "--app", "paint.exe", "--user-db", str(tmp_path / "user.db"),
                 "--report-dir", str(tmp_path / "reports"), "--no-hotkey", "--with-values"], desktop_for=lambda app: desktop)

    (path,) = (tmp_path / "reports").glob("*.json")
    assert code == 0 and "Salary" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("action, physical", [("read_value", False), ("click", True), ("type_value", True)])
def test_only_a_read_step_is_free_of_the_input_lock(action, physical):
    assert step("s", "C", action=action).uses_physical_input is physical
