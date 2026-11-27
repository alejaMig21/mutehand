"""A flow has no program of its own: Home and the editor work from the technology each node records. Opt-in: `pytest -m web`."""

import json
import sqlite3
from contextlib import closing

import pytest
from test_home_e2e import home, row, run_button, says

from workflow_factory import Flow, Node, load_flow, save_flow, save_step

from fake_desktop import FakeDesktop, button, save_legacy_flow, step

pytestmark = pytest.mark.web


def two_programs(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    save_flow(db, Flow(id="both", nodes=[Node("a", "save", technology="excel.exe"), Node("b", "save", technology="paint.exe")]),
              "Both programs")
    return {"excel.exe": FakeDesktop(controls=[button("Save workbook")], app="excel.exe"),
            "paint.exe": FakeDesktop(controls=[button("Save picture")], app="paint.exe")}


def test_home_runs_a_flow_of_two_programs_without_asking_for_one(tmp_path):
    desktops = two_programs(tmp_path)
    with home(tmp_path, desktop_for=desktops.__getitem__) as (page, _):
        bodies = []
        page.on("request", lambda r: bodies.append(r.post_data) if r.method == "POST" and r.url.endswith("/run") else None)
        text = row(page, "both").inner_text()
        assert "Excel" in text and "Paint" in text  # each node's program, none of the flow's own
        run_button(page, "both").click()
        says(page, "both", "Worked")
        assert [json.loads(body) for body in bodies] == [{"context": {}}]
    assert [c.name for c in desktops["excel.exe"].clicks] == ["Save workbook"]
    assert [c.name for c in desktops["paint.exe"].clicks] == ["Save picture"]


def test_home_says_which_program_has_not_learned_a_step_and_touches_nothing(tmp_path):
    desktops = two_programs(tmp_path)
    save_flow(tmp_path / "user.db", Flow(id="both", nodes=[
        Node("a", "save", technology="excel.exe"), Node("b", "save", technology="word.exe")]), "Both programs")
    with home(tmp_path, desktop_for=desktops.__getitem__) as (page, _):
        button_ = run_button(page, "both")
        button_.filter(has_text="Cannot run yet").wait_for()
        assert page.get_by_test_id("flow-why-both").inner_text().strip() == "“save” is not learned for Word yet."
        assert button_.is_disabled()
    assert all(d.calls == [] for d in desktops.values())


def test_a_flow_saved_before_nodes_knew_their_program_still_opens_and_runs(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("save", "Save picture", app="paint.exe"))
    save_legacy_flow(db, Flow(id="old", nodes=[Node("a", "save")]), "Old flow", "paint.exe")
    desktop = FakeDesktop(controls=[button("Save picture")], app="paint.exe")
    with home(tmp_path, desktop_for=lambda tech: desktop) as (page, _):
        assert "Paint" in row(page, "old").inner_text()
        run_button(page, "old").click()
        says(page, "old", "Worked")
    assert [c.name for c in desktop.clicks] == ["Save picture"]


def test_a_step_added_in_the_editor_is_kept_with_the_program_it_was_taught_on(tmp_path):
    from playwright.sync_api import sync_playwright
    from test_editor_e2e import DIST, open_page

    from workflow_factory.api import ApiServer

    db = tmp_path / "user.db"
    save_step(db, step("save", "Save workbook", app="excel.exe"))
    save_step(db, step("save", "Save picture", app="paint.exe"))
    server = ApiServer(db, None, lambda tech: FakeDesktop(controls=[], app=tech), token="e2e-token", web_dir=DIST)
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server)
            page.get_by_test_id("flow-title").fill("kept")
            page.get_by_test_id("app-name").select_option("paint.exe")
            page.get_by_test_id("palette-save").click()
            page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()
            browser.close()
    finally:
        server.stop()

    flow = load_flow(db, None, "kept")
    assert [n.technology for n in flow.nodes] == ["paint.exe"]
    with closing(sqlite3.connect(db)) as con:
        assert con.execute("SELECT app FROM flow_info").fetchall() == [(None,)]  # nothing of a program stays on the flow
