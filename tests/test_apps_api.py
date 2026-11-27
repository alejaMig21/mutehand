"""The Apps screen's data (editor rethink, ticket 11): one row per app, a search across all apps, and what one app holds:
its actions with the problems first and the permissions it was given. API side."""

import time

import numpy as np
import pytest
from fake_scheduler import FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, Sensitivity, grant_consent, reject_step, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.desktop import AppKey
from workflow_factory.steps import record_app_name, revalidate_changed_versions
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, step


@pytest.fixture
def server(tmp_path):
    made = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", lambda app: FakeDesktop(controls=[]), token="secret-token",
                     schedule_runner=FakeScheduler())
    made.start()
    yield made
    made.stop()


def rows(server, query=""):
    status, found, _ = call(server, "/api/apps" + query)
    assert status == 200
    return found


def test_one_row_per_app_with_counts_and_the_apps_that_need_the_person_first(tmp_path, server):
    db = tmp_path / "user.db"
    for name in ("open-file", "save-file"):
        save_step(db, step(name, "Alpha", app="paint.exe"))
    save_step(db, step("new-sheet", "Alpha", app="excel.exe"))
    save_step(db, step("add-chart", "Alpha", app="excel.exe"))
    save_step(db, step("write", "Alpha", app="zoom.exe"))
    reject_step(db, "zoom.exe", "write")
    grant_consent(db, "mail.exe", "Send", "click")  # an app known only by a permission it was given
    record_app_name(db, AppKey("excel.exe", "1.0", "Microsoft Excel"))

    found = rows(server)

    assert [(r["app"], r["actions"], r["problems"], r["permissions"]) for r in found] == [
        ("zoom.exe", 1, 1, 0), ("mail.exe", 0, 0, 1), ("excel.exe", 2, 0, 0), ("paint.exe", 2, 0, 0)]  # by name on screen: Microsoft Excel
    assert all(r["private"] is False for r in found)


def test_an_app_updated_since_its_actions_were_learned_has_a_problem_per_action(tmp_path, server):
    db = tmp_path / "user.db"
    for name in ("one", "two", "three"):
        save_step(db, step(name, "Alpha"))
    revalidate_changed_versions(db, "paint.exe", "2.0")

    [row] = rows(server)

    assert (row["actions"], row["problems"]) == (3, 3)


def test_search_finds_actions_across_apps_by_words_in_any_order_and_apps_by_name(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("save-file", "A", app="paint.exe"))
    save_step(db, step("Save spreadsheet", "A", app="excel.exe"))
    save_step(db, step("open-file", "A", app="excel.exe"))
    save_step(db, step("print", "A", app="word.exe"))
    record_app_name(db, AppKey("word.exe", "1.0", "Microsoft Word"))

    assert {r["app"]: r["found"] for r in rows(server, "?q=save")} == {"paint.exe": ["save-file"], "excel.exe": ["Save spreadsheet"]}
    assert {r["app"]: r["found"] for r in rows(server, "?q=FILE%20save")} == {"paint.exe": ["save-file"]}
    assert {r["app"]: r["found"] for r in rows(server, "?q=microsoft")} == {"word.exe": []}  # the app itself, no action
    assert rows(server, "?q=nothing%20like%20this") == []
    assert len(rows(server, "?q=")) == 3  # no words: every app


def test_search_never_matches_or_names_the_actions_of_a_private_app(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    save_step(db, step("open-doc", "A", app="word.exe"))
    mark_private(db, "telegram.exe")

    assert rows(server, "?q=chat") == []
    assert {r["app"]: r["found"] for r in rows(server, "?q=open")} == {"word.exe": ["open-doc"]}
    [telegram] = [r for r in rows(server) if r["app"] == "telegram.exe"]
    assert telegram["private"] is True and telegram["actions"] == 1


def test_an_app_lists_its_actions_with_the_ones_that_have_a_problem_first_and_why(tmp_path, server):
    db = tmp_path / "user.db"
    for name in ("b-open", "a-save", "c-send", "d-old"):
        save_step(db, step(name, "Alpha"))
    reject_step(db, "paint.exe", "c-send")
    save_step(db, step("d-old", "Alpha", version="0.9"))
    revalidate_changed_versions(db, "paint.exe", "1.0")  # the app is at 1.0 now: d-old was learned on 0.9

    status, app, _ = call(server, "/api/apps/paint.exe")

    assert status == 200 and app["app"] == "paint.exe" and app["private"] is False
    assert [(a["name"], a["state"]) for a in app["actions"]] == [
        ("c-send", "rejected"), ("d-old", "to_revalidate"), ("a-save", "suspect"), ("b-open", "suspect")]
    assert app["actions"][0]["why"] == {"kind": "person"}


def test_a_permission_says_which_chores_and_actions_stop_without_it_by_data(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("send-it", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("send-two", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("pay", "Pay", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("open", "Open", app="mail.exe"))
    save_flow(db, Flow(id="report", nodes=[Node("a", "open"), Node("b", "send-it")]), "Weekly report", "mail.exe")
    save_flow(db, Flow(id="pay-flow", nodes=[Node("a", "pay")]), "Pay the rent", "mail.exe")
    save_flow(db, Flow(id="other", nodes=[Node("a", "open")]), "Only opens", "mail.exe")
    grant_consent(db, "mail.exe", "Send", "click")
    grant_consent(db, "mail.exe", "*", "click")  # a broad one covers every control of the app

    status, app, _ = call(server, "/api/apps/mail.exe")

    assert status == 200
    by_control = {p["control"]: p for p in app["permissions"]}
    assert by_control["Send"]["action"] == "click"
    assert by_control["Send"]["stops"] == {"actions": ["send-it", "send-two"], "flows": [{"id": "report", "title": "Weekly report"}]}
    assert by_control["*"]["stops"]["actions"] == ["pay", "send-it", "send-two"]
    assert [f["id"] for f in by_control["*"]["stops"]["flows"]] == ["pay-flow", "report"]


def test_taking_a_permission_back_removes_only_that_consent(tmp_path, server):
    db = tmp_path / "user.db"
    grant_consent(db, "mail.exe", "Send", "click")
    grant_consent(db, "mail.exe", "Reply", "click")
    grant_consent(db, "word.exe", "Send", "click")

    assert call(server, "/api/consents", "DELETE", {"app": "mail.exe", "control": "Send", "action": "click"})[0] == 200

    _, mail, _ = call(server, "/api/apps/mail.exe")
    assert [p["control"] for p in mail["permissions"]] == ["Reply"]
    assert call(server, "/api/apps/word.exe")[1]["permissions"][0]["control"] == "Send"


def test_an_app_nobody_knows_is_not_found(server):
    assert call(server, "/api/apps/nothing.exe")[0] == 404


def test_names_with_a_space_or_a_dot_reach_the_right_app(tmp_path, server):
    save_step(tmp_path / "user.db", step("go", "A", app="My App.v2.exe"))

    assert call(server, "/api/apps/My%20App.v2.exe")[1]["actions"][0]["name"] == "go"


def many_steps(db, apps=30, per_app=30):
    capture = np.zeros((60, 60, 3), dtype=np.uint8)  # the pixels each step really carries
    for a in range(apps):
        for n in range(per_app):
            save_step(db, step(f"action-{n:02}", "Alpha", app=f"app{a:02}.exe", capture=capture))


def test_listing_900_steps_takes_under_half_a_second(tmp_path, server):
    many_steps(tmp_path / "user.db")
    call(server, "/api/apps")  # the first call opens the database file

    timings = {}
    for label, path in (("list", "/api/apps"), ("search", "/api/apps?q=action"), ("open", "/api/apps/app07.exe")):
        began = time.perf_counter()
        status, found, _ = call(server, path)
        timings[label] = time.perf_counter() - began
        assert status == 200 and found

    assert len(rows(server)) == 30
    assert all(seconds < 0.5 for seconds in timings.values()), timings
