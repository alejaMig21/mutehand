"""A flow has a title (free text, shown on screen) apart from its identifier, and remembers the app it runs on."""

import sqlite3
from contextlib import closing

import pytest
from test_api import call, make_server

from workflow_factory import Flow, Node, build_factory, export_knowledge, import_knowledge, save_flow, save_step
from workflow_factory.flows import flow_summaries

from fake_desktop import step

ONE = {"nodes": [{"id": "n1", "step": "open-menu"}], "edges": []}


@pytest.fixture
def server(tmp_path):
    running = make_server(tmp_path)
    yield running
    running.stop()


def test_a_title_with_any_words_and_the_app_are_kept_with_the_flow_and_listed(server):
    saved = call(server, "/api/flows/report", "PUT", {**ONE, "title": "  Morning report:  ¿ventas? ", "app": "paint.exe"})
    loaded = call(server, "/api/flows/report")[1]
    listed = call(server, "/api/flows")[1]
    call(server, "/api/flows/report", "PUT", ONE)  # a save that says nothing about them keeps both

    assert saved[0] == 200 and saved[1]["title"] == loaded["title"] == "Morning report: ¿ventas?"
    assert loaded["app"] == "paint.exe"
    assert listed == [{"id": "report", "origin": "local", "title": "Morning report: ¿ventas?", "app": "paint.exe"}]
    assert call(server, "/api/flows/report")[1] == loaded


def test_a_flow_saved_before_titles_takes_its_identifier_and_the_app_of_most_of_its_steps(tmp_path):
    for app, name in (("telegram.exe", "Send"), ("telegram.exe", "Write"), ("whatsapp.exe", "Write"),
                      ("whatsapp.exe", "Open"), ("whatsapp.exe", "Close")):
        save_step(tmp_path / "user.db", step(name, "Alpha", app=app))
    save_flow(tmp_path / "user.db", Flow(id="mostly-whatsapp", nodes=[
        Node("a", "Send"), Node("b", "Open"), Node("c", "Close")]))
    save_flow(tmp_path / "user.db", Flow(id="tie", nodes=[Node("a", "Write")]))
    save_flow(tmp_path / "user.db", Flow(id="empty", nodes=[Node("a", kind="wait", fields={"seconds": {"value": 1}})]))
    server = make_server(tmp_path)
    try:
        listed = {f["id"]: (f["title"], f["app"]) for f in call(server, "/api/flows")[1]}
        loaded = call(server, "/api/flows/mostly-whatsapp")[1]
    finally:
        server.stop()

    assert listed == {"mostly-whatsapp": ("mostly-whatsapp", "whatsapp.exe"), "tie": ("tie", "telegram.exe"),
                      "empty": ("empty", "")}
    assert (loaded["title"], loaded["app"]) == ("mostly-whatsapp", "whatsapp.exe")


def test_a_flow_that_cannot_be_read_does_not_hide_the_others_from_the_list(tmp_path, server):
    call(server, "/api/flows/good", "PUT", {**ONE, "title": "Good"})
    with closing(sqlite3.connect(tmp_path / "user.db")) as db, db:
        db.execute("INSERT INTO flows VALUES ('broken', '{\"nodes\": [{\"bogus\": 1}]}')")

    status, listed, _ = call(server, "/api/flows")

    assert status == 200 and [(f["id"], f["title"], f["app"]) for f in listed] == [("broken", "broken", ""), ("good", "Good", "")]


@pytest.mark.parametrize("extra", [
    {"title": ""}, {"title": "   "}, {"title": "x" * 101}, {"title": 7}, {"title": "a\x00b"}, {"title": "\ud800"},
    {"app": 7}, {"app": "a" * 101}, {"app": "a\x07"},
])
def test_a_title_or_app_that_cannot_be_kept_is_refused_in_words_and_changes_nothing(server, extra):
    call(server, "/api/flows/report", "PUT", {**ONE, "title": "Report", "app": "paint.exe"})
    before = call(server, "/api/flows/report")[1]

    status, answer, _ = call(server, "/api/flows/report", "PUT", {"nodes": [], "edges": [], **extra})

    assert status == 400 and ("flow name" in answer["error"] or "app name" in answer["error"])
    assert call(server, "/api/flows/report")[1] == before


def test_a_rename_made_elsewhere_is_a_change_the_editor_is_told_about(server):
    first = call(server, "/api/flows/report", "PUT", {**ONE, "title": "Report"})[1]
    call(server, "/api/flows/report", "PUT", {**ONE, "title": "Renamed"})

    status, answer, _ = call(server, "/api/flows/report", "PUT", {**ONE, "title": "Report", "base": first["revision"]})

    assert status == 409 and "'Renamed' was changed somewhere else" in answer["error"]


def test_a_new_flow_gets_a_short_identifier_from_its_title_and_never_takes_one_in_use(tmp_path):
    build_factory(tmp_path / "factory.db", {"version": 1, "steps": [], "flows": [{"id": "Informe-Año", **ONE}]})
    server = make_server(tmp_path)
    try:
        made = [call(server, "/api/flows", "POST", {**ONE, "title": title}) for title in
                ("informe año", "INFORME: Año!", "Morning report", "Morning report", "¿?", "word " * 20, "..")]
        listed = {f["id"]: f["title"] for f in call(server, "/api/flows")[1]}
        nameless = call(server, "/api/flows", "POST", ONE)[0]
        taken = call(server, "/api/flows/MORNING-REPORT", "PUT", ONE)
    finally:
        server.stop()

    ids = [body["id"] for status, body, _ in made]
    assert [status for status, _, _ in made] == [201] * 7
    assert ids[:5] == ["informe-año-2", "informe-año-3", "morning-report", "morning-report-2", "flow"]
    assert ids[6] == "flow-2" and len(ids[5]) <= 50 and ids[5].startswith("word-word") and not ids[5].endswith("-")
    assert listed["morning-report"] == listed["morning-report-2"] == "Morning report" and len(listed) == 8
    assert nameless == 400
    assert taken[0] == 409 and "already exists" in taken[1]["error"]


def test_a_copy_and_an_export_carry_the_title_and_the_app(tmp_path):
    build_factory(tmp_path / "factory.db", {"version": 1, "steps": [], "flows": [
        {"id": "template", "title": "The template", "app": "paint.exe", **ONE}]})
    server = make_server(tmp_path)
    try:
        listed = call(server, "/api/flows")[1][0]
        copy = call(server, "/api/flows/template/duplicate", "POST", {"title": "My own copy"})
        plain = call(server, "/api/flows/template/duplicate", "POST", {"new_id": "plain"})
        clash = call(server, "/api/flows/template/duplicate", "POST", {"new_id": "PLAIN"})
    finally:
        server.stop()
    exported = export_knowledge(tmp_path / "user.db")
    import_knowledge(tmp_path / "other.db", exported)
    import_knowledge(tmp_path / "other.db", {"version": 1, "steps": [], "flows": [{"id": "plain", **ONE}]}, overwrite=True)

    assert (listed["title"], listed["app"]) == ("The template", "paint.exe")
    assert copy[0] == 201 and (copy[1]["id"], copy[1]["title"], copy[1]["app"]) == ("my-own-copy", "My own copy", "paint.exe")
    assert (plain[1]["title"], plain[1]["app"]) == ("The template", "paint.exe") and clash[0] == 400
    assert {f["id"]: (f["title"], f["app"]) for f in flow_summaries(tmp_path / "other.db", None)} == {
        "my-own-copy": ("My own copy", "paint.exe"), "plain": ("The template", "paint.exe")}
    with pytest.raises(ValueError, match="flow name"):
        import_knowledge(tmp_path / "third.db", {"version": 1, "steps": [], "flows": [{"id": "bad", "title": 7, **ONE}]})
    assert not flow_summaries(tmp_path / "third.db", None)
