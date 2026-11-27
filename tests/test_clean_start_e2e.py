"""Clean start, seen on Home: the person is told once where the old data was kept. Opt-in: `pytest -m web`."""

from contextlib import contextmanager
from datetime import date

import pytest
from fake_scheduler import FakeScheduler
from test_editor_e2e import DIST, open_page

from workflow_factory import Flow, Node, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.upgrade import start_user_db

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


@contextmanager
def started(tmp_path):
    """The program starting on data an earlier version left: (page, reopen), where reopen loads Home again."""
    from playwright.sync_api import sync_playwright

    db = tmp_path / "user.db"
    save_step(db, step("open-menu", "Alpha"))
    save_flow(db, Flow(id="weekly", nodes=[Node("n1", "open-menu")]), "Weekly export", "paint.exe")
    start_user_db(db, today=date(2026, 11, 27))
    desktop = FakeDesktop(controls=[button("Alpha")])
    server = ApiServer(db, tmp_path / "factory.db", lambda app: desktop, token="e2e-token", web_dir=DIST,
                       schedule_runner=FakeScheduler())
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server, screen=None)
            page.set_default_timeout(8_000)
            yield page
            browser.close()
    finally:
        server.stop()


def test_home_tells_once_where_the_copy_is_and_it_can_be_dismissed(tmp_path):
    with started(tmp_path) as page:
        card = page.get_by_test_id("attention-notice-clean-start")
        card.wait_for()
        assert str(tmp_path / "user-2026-11-27.db") in card.inner_text()
        assert page.get_by_test_id("chore-weekly").count() == 0  # nothing was imported: no flow from before
        page.get_by_test_id("attention-notice-dismiss-clean-start").click()
        card.wait_for(state="detached")
        page.reload()
        page.get_by_role("heading", name="Your chores").wait_for()
        assert page.get_by_test_id("attention-notice-clean-start").count() == 0
