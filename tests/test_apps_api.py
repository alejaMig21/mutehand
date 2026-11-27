"""The Apps screen's data (editor rethink, ticket 11): one row per app, a search across all apps, and what one app holds:
its actions with the problems first and the permissions it was given. API side."""

import json
import sqlite3
import time
from contextlib import closing

import numpy as np
import pytest
from fake_scheduler import FakeScheduler
from test_api import call

from workflow_factory import Flow, Node, Sensitivity, grant_consent, reject_step, save_step
from workflow_factory.api import ApiServer
from workflow_factory.desktop import AppKey
from workflow_factory.steps import record_app_name, revalidate_changed_versions
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, save_flow_on, step


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


def test_a_search_of_several_words_falls_back_to_any_meaningful_word_when_no_program_has_them_all(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("Save", "A", app="excel.exe"))
    save_step(db, step("Print", "A", app="word.exe"))
    save_step(db, step("Save picture", "A", app="paint.exe"))

    # no action says "spreadsheet": the words that carry meaning are tried one by one ("a" carries none)
    assert {r["app"]: r["found"] for r in rows(server, "?q=save%20a%20spreadsheet")} == {
        "excel.exe": ["Save"], "paint.exe": ["Save picture"]}
    # words that all match keep their narrow answer: the fallback is only for an empty one
    assert {r["app"] for r in rows(server, "?q=save%20picture")} == {"paint.exe"}
    assert rows(server, "?q=the%20a%20to") == []  # nothing but small words matches nothing
    assert rows(server, "?q=zzz%20qqq") == []


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


def test_a_private_apps_detail_names_no_action_or_control_and_its_buttons_work_from_handles(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("pay-rent", "Transfer", app="vault.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("open-it", "Open", app="vault.exe"))
    mark_private(db, "vault.exe")
    reject_step(db, "vault.exe", "pay-rent")
    with closing(sqlite3.connect(db)) as con, con:  # a check that failed: what it expected and saw is screen content
        con.execute("UPDATE step_state SET why = ? WHERE name = 'pay-rent'",
                    ('{"kind": "different_effect", "expected": "Balance 12", "got": "Balance 9", "at": "x"}',))
    grant_consent(db, "vault.exe", "Transfer", "click")

    status, app, _ = call(server, "/api/apps/vault.exe")

    text = json.dumps(app)
    assert status == 200 and app["private"] is True
    for secret in ("pay-rent", "open-it", "Transfer", "Balance"):
        assert secret not in text
    assert [a["state"] for a in app["actions"]] == ["rejected", "suspect"] and app["actions"][0]["why"] == {"kind": "different_effect"}
    [permission] = app["permissions"]
    assert len(permission["stops"]["actions"]) == 1 and permission["action"] == "click"
    assert call(server, f"/api/steps/vault.exe/{app['actions'][0]['name']}/restore", "POST")[0] == 200
    assert call(server, "/api/apps/vault.exe")[1]["actions"][0]["state"] != "rejected"
    taken = {key: permission[key] for key in ("app", "control", "action")}
    assert call(server, "/api/consents", "DELETE", taken)[0] == 200
    assert call(server, "/api/apps/vault.exe")[1]["permissions"] == []


def test_a_permission_says_which_chores_and_actions_stop_without_it_by_data(tmp_path, server):
    db = tmp_path / "user.db"
    save_step(db, step("send-it", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("send-two", "Send", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("pay", "Pay", app="mail.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("open", "Open", app="mail.exe"))
    save_flow_on(db, Flow(id="report", nodes=[Node("a", "open"), Node("b", "send-it")]), "Weekly report", "mail.exe")
    save_flow_on(db, Flow(id="pay-flow", nodes=[Node("a", "pay")]), "Pay the rent", "mail.exe")
    save_flow_on(db, Flow(id="other", nodes=[Node("a", "open")]), "Only opens", "mail.exe")
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
