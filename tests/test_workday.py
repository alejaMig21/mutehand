import json

import pytest

from workflow_factory import (
    Flow,
    Node,
    emergency_stop,
    save_flow,
    save_step,
)
from workflow_factory.desktop import DesktopError
from workflow_factory.queue import acquire_run_lock
from workflow_factory.workday import (
    EXIT_BUSY,
    EXIT_EMERGENCY,
    EXIT_ERROR,
    EXIT_FINISHED,
    EXIT_STOPPED,
    EXIT_WAITING,
    main,
    write_report,
)

from fake_desktop import FakeDesktop, button, step


def setup(tmp_path, nodes=None, steps=(("open-menu", "Alpha"), ("save-file", "Beta"))):
    for name, control in steps:
        save_step(tmp_path / "user.db", step(name, control))
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=nodes or [Node("a", "open-menu"), Node("b", "save-file")]))
    return tmp_path


def run(tmp_path, desktop, *extra, flow="morning"):
    argv = ["--flow", flow, "--app", "paint.exe", "--user-db", str(tmp_path / "user.db"),
            "--report-dir", str(tmp_path / "reports"), "--no-hotkey", *extra]
    return main(argv, desktop_for=lambda app: desktop)


def reports(tmp_path):
    return sorted((tmp_path / "reports").glob("*.json"))


def test_a_finished_workday_exits_zero_and_writes_a_report_of_what_ran(tmp_path, capsys):
    setup(tmp_path)

    code = run(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Beta")]))

    (path,) = reports(tmp_path)
    report = json.loads(path.read_text(encoding="utf-8"))
    assert code == EXIT_FINISHED == 0
    assert report["flow"] == "morning" and report["status"] == "finished" and report["stopped_node"] is None
    assert [(n["node_id"], n["status"]) for n in report["nodes"]] == [("a", "done"), ("b", "done")]
    assert capsys.readouterr().out.strip() == f"status=finished report={path}"


def test_a_workday_that_stops_exits_one_and_says_what_stopped_and_why(tmp_path):
    setup(tmp_path)

    code = run(tmp_path, FakeDesktop(controls=[button("Alpha")]))  # Beta is missing

    report = json.loads(reports(tmp_path)[0].read_text(encoding="utf-8"))
    assert code == EXIT_STOPPED == 1
    assert report["status"] == "stopped" and report["stopped_node"] == "b"
    assert report["nodes"][1] == {"node_id": "b", "status": "blocked", "reason": "control_not_found", "effect": None,
                                  "step": "save-file"}
    assert [(d["node_id"], d["reason"], d["detail"]) for d in report["open_doubts"]] == [
        ("b", "control_not_found", "control_not_found")]


def test_a_flow_waiting_for_the_tutor_exits_two_without_acting(tmp_path):
    setup(tmp_path)
    run(tmp_path, FakeDesktop(controls=[button("Alpha")]))  # stops and leaves a doubt
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    code = run(tmp_path, desktop)

    assert code == EXIT_WAITING == 2 and desktop.clicks == []


def test_the_emergency_stop_exits_three(tmp_path):
    setup(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.on_action.append(emergency_stop)

    code = run(tmp_path, desktop)

    assert code == EXIT_EMERGENCY == 3


def test_a_stop_pressed_in_an_earlier_session_does_not_block_a_new_workday(tmp_path):
    setup(tmp_path)
    emergency_stop()  # left over from before

    code = run(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Beta")]))

    assert code == EXIT_FINISHED


def test_an_unknown_flow_exits_four_and_says_so(tmp_path, capsys):
    setup(tmp_path)

    code = run(tmp_path, FakeDesktop(controls=[]), flow="nope")

    assert code == EXIT_ERROR == 4
    assert "no flow named" in capsys.readouterr().err


def test_an_app_that_is_not_running_exits_four_and_leaves_an_error_report(tmp_path):
    setup(tmp_path)

    def app_not_running(app):
        raise DesktopError("APP_NOT_FOUND")

    code = main(["--flow", "morning", "--app", "paint.exe", "--user-db", str(tmp_path / "user.db"),
                 "--report-dir", str(tmp_path / "reports"), "--no-hotkey"], desktop_for=app_not_running)

    (path,) = reports(tmp_path)
    assert code == EXIT_ERROR
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "error"


def test_values_stay_out_of_the_report_unless_the_person_asks(tmp_path):
    setup(tmp_path, nodes=[Node("t", "typer", inputs=(("text", "str"),))], steps=(("typer", "Notes"),))
    save_step(tmp_path / "user.db", step("typer", "Notes", action="type_value"))
    context = json.dumps({"text": "hunter2"})

    run(tmp_path, FakeDesktop(controls=[button("Notes")]), "--context", context)
    default_text = reports(tmp_path)[0].read_text(encoding="utf-8")
    run(tmp_path, FakeDesktop(controls=[button("Notes")]), "--context", context, "--with-values")
    asked_text = reports(tmp_path)[-1].read_text(encoding="utf-8")

    assert "hunter2" not in default_text and '"context"' not in default_text
    assert json.loads(asked_text)["context"] == {"text": "hunter2"}


def test_one_data_dir_flag_places_the_database_and_the_reports_together(tmp_path, capsys):
    folder = tmp_path / "data"
    folder.mkdir()
    setup(folder)  # saves steps and flow into folder/user.db
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    code = main(["--flow", "morning", "--app", "paint.exe", "--data-dir", str(folder), "--no-hotkey"],
                desktop_for=lambda app: desktop)

    assert code == EXIT_FINISHED and len(list((folder / "reports").glob("*.json"))) == 1
    assert capsys.readouterr().out.startswith("status=finished report=" + str(folder / "reports"))


def test_an_invalid_context_is_refused_before_anything_runs(tmp_path, capsys):
    setup(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    code = run(tmp_path, desktop, "--context", "{not json")

    assert code == EXIT_ERROR and desktop.clicks == [] and "context" in capsys.readouterr().err


def error_reports(tmp_path):
    return [json.loads(p.read_text(encoding="utf-8")) for p in reports(tmp_path)]


def test_an_unexpected_failure_exits_four_not_one_and_names_only_the_error_class(tmp_path):
    setup(tmp_path)

    class Broken(FakeDesktop):
        def snapshot(self):
            raise RuntimeError("secret screen text must never be copied")

    code = run(tmp_path, Broken(controls=[button("Alpha"), button("Beta")]))

    (report,) = error_reports(tmp_path)
    assert code == EXIT_ERROR  # 1 is "stopped": a crash must not look like one
    assert report["status"] == "error" and report["error"] == "RuntimeError"
    assert "secret screen text" not in json.dumps(report)


def test_failures_before_the_flow_loads_still_leave_a_report_because_pythonw_has_no_stderr(tmp_path):
    setup(tmp_path)

    run(tmp_path, FakeDesktop(controls=[]), flow="nope")
    run(tmp_path, FakeDesktop(controls=[]), "--context", "{broken")

    assert [r["error"] for r in error_reports(tmp_path)] == ["NO_SUCH_FLOW", "BAD_CONTEXT"] or \
        sorted(r["error"] for r in error_reports(tmp_path)) == ["BAD_CONTEXT", "NO_SUCH_FLOW"]


def test_typed_values_can_come_from_a_context_file_so_a_scheduled_command_needs_no_quotes(tmp_path):
    setup(tmp_path, nodes=[Node("t", "typer", inputs=(("text", "str"),))], steps=(("typer", "Notes"),))
    save_step(tmp_path / "user.db", step("typer", "Notes", action="type_value"))
    values = tmp_path / "values.json"
    values.write_text(json.dumps({"text": "from a file"}), encoding="utf-8")
    desktop = FakeDesktop(controls=[button("Notes")])

    code = run(tmp_path, desktop, "--context-file", str(values))

    assert code == EXIT_FINISHED and [text for _, text in desktop.typed] == ["from a file"]


def test_only_the_newest_reports_are_kept(tmp_path):
    folder = tmp_path / "reports"
    for n in range(4):
        write_report(folder, {"flow": "f", "status": "finished"}, n + 1, keep=2)

    assert [p.name.split("-")[-1] for p in sorted(folder.glob("*.json"), key=lambda p: int(p.stem.split("-")[-1]))] == [
        "3.json", "4.json"]


def test_a_flow_id_can_never_carry_path_characters_into_a_report_name(tmp_path):
    with pytest.raises(ValueError, match="letters"):
        Flow(id="..\\x", nodes=[Node("a", "open-menu")])


def test_a_workday_of_a_flow_that_is_already_running_exits_five_without_acting(tmp_path):
    setup(tmp_path)
    assert acquire_run_lock(tmp_path / "user.db", "morning")  # another run of this flow is alive (this process)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    code = run(tmp_path, desktop)

    assert code == EXIT_BUSY == 5 and desktop.clicks == []


def two_trigger_nodes():
    def trigger(node_id, mode, at=None):
        fields = {"mode": {"value": mode}, **({"at": {"value": at}} if at else {})}
        return Node(node_id, kind="trigger", fields=fields)

    return [trigger("m", "manual"), trigger("d", "daily", "09:00"), Node("a", "open-menu"), Node("b", "save-file")]


@pytest.mark.parametrize("extra, clicked", [((), ["Alpha"]), (("--fired", "daily"), ["Beta"])], ids=["by hand", "scheduled"])
def test_a_workday_fires_the_trigger_it_was_started_by(tmp_path, extra, clicked):
    setup(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=two_trigger_nodes(), edges=[("m", "a"), ("d", "b")]))
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])

    code = run(tmp_path, desktop, *extra)

    assert code == EXIT_FINISHED and [c.name for c in desktop.clicks] == clicked


def test_the_report_never_holds_the_data_a_data_node_gave_out(tmp_path):
    setup(tmp_path)
    nodes = [Node("d", kind="data", op="fixed", fields={"value": {"value": "secret-page-text-1234"}})]
    save_flow(tmp_path / "user.db", Flow(id="morning", nodes=nodes))

    code = run(tmp_path, FakeDesktop(controls=[]), "--with-values")  # even with values enabled: those are the run's input

    (path,) = reports(tmp_path)
    assert code == EXIT_FINISHED and "secret-page-text-1234" not in path.read_text(encoding="utf-8")
