"""Clean start: an old user database is kept as a dated copy and a new empty one begins. Nothing is imported."""

from datetime import date

from test_api import call

from workflow_factory import Flow, Node, list_steps, save_step
from workflow_factory.api import ApiServer
from workflow_factory.attention import attention_items
from workflow_factory.flows import flow_summaries
from workflow_factory.upgrade import dismiss_notice, start_user_db

from fake_desktop import FakeDesktop, button, save_flow_on, step

DAY = date(2026, 11, 27)
COPY = "user-2026-11-27.db"


def old_database(tmp_path):
    """A database as the previous version left it: a step and a flow, no marker of the new model."""
    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_flow_on(db, Flow(id="weekly", nodes=[Node("n1", "open-menu")]), "Weekly export", "paint.exe")
    return db


def notices(db):
    return [item for item in attention_items(db, None) if item["kind"] == "notice"]


def files(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir())


def test_an_old_database_is_kept_under_a_dated_name_and_the_new_one_is_empty(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    assert [s.name for s in list_steps(tmp_path / COPY, None)] == ["open-menu"]  # untouched, still readable
    assert list_steps(db, None) == [] and flow_summaries(db, None) == []


def test_the_notice_says_where_the_copy_is_and_a_second_start_repeats_nothing(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    assert [item["copy"] for item in notices(db)] == [str(tmp_path / COPY)]
    start_user_db(db, today=DAY)
    assert len(notices(db)) == 1 and files(tmp_path) == [COPY, "user.db"]
    assert list_steps(tmp_path / COPY, None)  # the copy was not replaced by the empty one


def test_a_dismissed_notice_does_not_come_back(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    dismiss_notice(db, notices(db)[0]["id"])
    assert notices(db) == []
    start_user_db(db, today=DAY)
    assert notices(db) == []


def test_a_first_ever_start_has_no_notice_and_no_copy(tmp_path):
    db = tmp_path / "user.db"
    start_user_db(db, today=DAY)
    start_user_db(db, today=DAY)
    assert notices(db) == [] and files(tmp_path) == ["user.db"]


def test_work_saved_after_the_upgrade_is_never_mistaken_for_an_old_database(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    save_step(db, step("save-file", "Beta"))
    start_user_db(db, today=DAY)
    assert [s.name for s in list_steps(db, None)] == ["save-file"] and files(tmp_path) == [COPY, "user.db"]


def test_a_second_copy_on_the_same_day_does_not_overwrite_the_first(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    db.unlink()  # an unmarked database shows up again the same day
    old_database(tmp_path)
    start_user_db(db, today=DAY)
    assert list_steps(tmp_path / COPY, None) and list_steps(tmp_path / "user-2026-11-27-2.db", None)


def test_the_notice_is_served_and_dismissed_through_the_api(tmp_path):
    db = old_database(tmp_path)
    start_user_db(db, today=DAY)
    server = ApiServer(db, None, lambda app: FakeDesktop(controls=[button("Alpha")]), token="secret-token")
    server.start()
    try:
        items = [i for i in call(server, "/api/attention")[1] if i["kind"] == "notice"]
        assert [i["copy"] for i in items] == [str(tmp_path / COPY)]
        assert call(server, f"/api/notices/{items[0]['id']}/dismiss", "POST")[0] == 200
        assert [i for i in call(server, "/api/attention")[1] if i["kind"] == "notice"] == []
    finally:
        server.stop()
