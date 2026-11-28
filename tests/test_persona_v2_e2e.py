"""What the non-technical personas could not do on the finished model v2 (mutehand-v2 ticket 10), each fixed once and kept fixed.
Driven in the built editor. Opt-in: `pytest -m web`."""

import pytest
from test_flow_more_e2e import more, served
from test_home_e2e import put_flow, put_flows, says

pytestmark = pytest.mark.web


# --- 2: every flow deleted lately has its own Undo ---------------------------------------------------------------------

def test_two_deleted_flows_each_keep_their_undo_and_both_survive_a_reload(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    with served(tmp_path) as (page, _, _):
        says(page, "weekly", "Never run")
        for flow in ("morning", "weekly"):
            more(page, flow)
            page.get_by_test_id(f"more-delete-{flow}").click()
            page.get_by_test_id(f"flow-{flow}").wait_for(state="detached")
        notices = page.get_by_test_id("deleted-notice")
        notices.nth(1).wait_for()
        assert notices.count() == 2
        page.reload()
        notices.nth(1).wait_for()
        assert notices.count() == 2
        notices.filter(has_text="Morning report").get_by_role("button", name="Undo").click()
        page.get_by_test_id("flow-morning").wait_for()
        assert notices.count() == 1 and "Weekly export" in notices.inner_text()
        notices.get_by_role("button", name="Undo").click()
        page.get_by_test_id("flow-weekly").wait_for()
        assert notices.count() == 0
