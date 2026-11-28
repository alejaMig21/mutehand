"""Home, the first screen: the person's flows, how each went, and Run now. Driven in the built editor. Opt-in: `pytest -m web`."""

import json
import re
import sqlite3
import time
from contextlib import closing, contextmanager

import pytest
from fake_scheduler import FakeScheduler
from test_editor_e2e import DIST, open_page
from test_editor_safety_e2e import CONTRAST

from workflow_factory import Flow, Node, load_flow, reject_step, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.desktop import DesktopError
from workflow_factory.queue import answer_doubt, list_doubts, record_run
from workflow_factory.steps import record_app_name, revalidate_changed_versions
from workflow_factory.tutor import mark_private

from fake_desktop import FakeDesktop, button, save_flow_on, save_legacy_flow, step

pytestmark = pytest.mark.web


@contextmanager
def home(tmp_path, desktop=None, desktop_for=None):
    """A page on the built editor as a person first finds it: (page, desktop)."""
    from playwright.sync_api import sync_playwright

    desktop = desktop or FakeDesktop(controls=[button("Alpha"), button("Beta")])
    server = ApiServer(tmp_path / "user.db", tmp_path / "factory.db", desktop_for or (lambda app: desktop),
                       token="e2e-token", web_dir=DIST, schedule_runner=FakeScheduler())
    server.start()
    try:
        with sync_playwright() as playwright:
            browser, page = open_page(playwright, server, screen=None)
            page.set_default_timeout(8_000)
            yield page, desktop
            browser.close()
    finally:
        server.stop()


def put_flow(tmp_path, flow_id, title, *steps, app="paint.exe"):
    flow = Flow(id=flow_id, nodes=[Node(f"n{i}", name) for i, name in enumerate(steps, 1)])
    save_flow_on(tmp_path / "user.db", flow, title, app)
    return load_flow(tmp_path / "user.db", None, flow_id)  # as stored: its nodes say which program they act on


def put_flows(tmp_path):
    """Two learned actions and a flow that uses both."""
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))
    save_step(tmp_path / "user.db", step("save-file", "Beta"))
    return put_flow(tmp_path, "morning", "Morning report", "open-menu", "save-file")


def row(page, flow_id):
    return page.get_by_test_id(f"flow-{flow_id}")


def says(page, flow_id, words):
    row(page, flow_id).filter(has_text=re.compile(words)).wait_for()


def test_home_is_the_first_screen_and_apps_is_the_only_other_place(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.get_by_role("heading", name="Your flows").wait_for()
        assert page.title() == "Home · Mutehand"
        for tab, title in (("apps", "Apps"), ("home", "Home")):
            page.get_by_test_id(f"tab-{tab}").click()
            page.wait_for_function("(t) => document.title.startsWith(t)", arg=title)
            assert page.get_by_test_id(f"tab-{tab}").get_attribute("aria-current") == "page"
        page.get_by_role("heading", name="Your flows").wait_for()


def test_each_flow_shows_its_name_its_app_and_how_the_last_run_went(tmp_path):
    db = tmp_path / "user.db"
    morning = put_flows(tmp_path)
    save_step(db, step("close-message", "Missing"))
    weekly = put_flow(tmp_path, "weekly", "Weekly export", "open-menu", "close-message")
    put_flow(tmp_path, "monthly", "Monthly numbers", "open-menu")
    record_app_name(db, FakeDesktop(controls=[], product_name="Quill Paint").app_key())
    run_flow(weekly, desktop=FakeDesktop(controls=[button("Alpha"), button("Missing")]), user_db=db)  # an older, good run
    run_flow(weekly, desktop=FakeDesktop(controls=[button("Alpha")]), user_db=db)
    run_flow(morning, desktop=FakeDesktop(controls=[button("Alpha"), button("Beta")]), user_db=db)
    record_run(db, "monthly#test:n1", "2026-01-01T07:00:00Z", "2026-01-01T07:00:01Z", "finished", None, [])  # one node tested

    with home(tmp_path) as (page, _):
        says(page, "morning", r"Worked .+ at \d\d:\d\d")
        text = row(page, "morning").inner_text()
        assert "Morning report" in text and "Quill Paint" in text and ".exe" not in text
        says(page, "weekly", r"Stopped .+ at \d\d:\d\d")
        assert "Worked" not in row(page, "weekly").inner_text()
        says(page, "monthly", "Never run")


def test_with_no_flows_home_says_so_and_offers_a_new_one(tmp_path):
    save_step(tmp_path / "user.db", step("open-menu", "Alpha"))  # nothing learned at all is the first day: test_first_day_e2e
    with home(tmp_path) as (page, _):
        page.get_by_test_id("no-flows").wait_for()
        page.get_by_test_id("new-flow").wait_for()


def run_button(page, flow_id):
    return page.get_by_test_id(f"run-now-{flow_id}")


def clicked(desktop):
    return [c.name for c in desktop.clicks]


def test_run_now_runs_the_flow_and_reports_on_its_row(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, desktop):
        says(page, "morning", "Never run")
        assert run_button(page, "morning").inner_text().strip() == "Run now"
        run_button(page, "morning").click()
        says(page, "morning", r"Worked .+ at \d\d:\d\d")
        run_button(page, "morning").filter(has_text="Run now").wait_for()
        assert clicked(desktop) == ["Alpha", "Beta"]


def test_a_running_flow_offers_stop_which_ends_it(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.5
    with home(tmp_path, desktop) as (page, _):
        run_button(page, "morning").click()
        says(page, "morning", "Running now")
        run_button(page, "morning").filter(has_text="Stop").click()
        says(page, "morning", r"You stopped it .+ at \d\d:\d\d")
        run_button(page, "morning").filter(has_text="Run now").wait_for()
        assert clicked(desktop) == ["Alpha"]


def test_a_double_press_on_run_now_does_not_stop_the_run(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 0.4
    with home(tmp_path, desktop) as (page, _):
        posted = []
        page.on("request", lambda r: posted.append(r.url) if r.method == "POST" else None)
        run_button(page, "morning").dblclick()
        says(page, "morning", "Worked")
        assert clicked(desktop) == ["Alpha", "Beta"] and [url.rsplit("/", 1)[1] for url in posted] == ["run"]


def test_a_run_that_waits_for_the_person_says_why(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 0.5
    desktop.on_action = [desktop.user_acts]
    desktop.on_sleep = [lambda: time.sleep(0.3)]  # the fake clock's wait takes real time, so it is seen
    with home(tmp_path, desktop) as (page, _):
        run_button(page, "morning").click()
        says(page, "morning", "Paused: you moved the mouse")
        says(page, "morning", "Worked")


def gone(app):
    raise DesktopError(f"{app} is not running: secret window title")


@pytest.mark.parametrize("status, words", [(429, "too many runs at once"), (400, "This flow will not start")])
def test_a_start_the_server_refuses_is_said_on_the_row(tmp_path, status, words):
    put_flows(tmp_path)
    with home(tmp_path) as (page, desktop):
        page.route("**/api/flows/morning/run", lambda route: route.fulfill(
            status=status, content_type="application/json", body=json.dumps({"error": words})))
        run_button(page, "morning").click()
        row(page, "morning").get_by_role("alert").filter(has_text=words).wait_for()
        assert run_button(page, "morning").inner_text().strip() == "Run now" and not desktop.clicks


def test_a_run_that_cannot_reach_the_app_says_so_without_the_apps_words(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path, desktop_for=gone) as (page, _):
        run_button(page, "morning").click()
        row(page, "morning").get_by_role("alert").filter(has_text="Check that Paint is open").wait_for()
        assert "secret" not in page.content()


def no_nodes(db):
    save_flow(db, Flow(id="stuck", nodes=[]), "Stuck")


def not_learned(db):
    save_flow_on(db, Flow(id="stuck", nodes=[Node("a", "open-menu"), Node("b", "print-it"), Node("c", "print-it")]), "Stuck", "paint.exe")


def learned_for_another_app(db):
    save_flow_on(db, Flow(id="stuck", nodes=[Node("a", "open-menu")]), "Stuck", "word.exe")


def never_learned_at_all(db):
    save_flow(db, Flow(id="stuck", nodes=[Node("a", "print-it")]), "Stuck")


def rejected(db):
    reject_step(db, "paint.exe", "save-file")
    save_flow_on(db, Flow(id="stuck", nodes=[Node("a", "save-file")]), "Stuck", "paint.exe")


def app_updated(db):
    revalidate_changed_versions(db, "paint.exe", "2.0")  # what a run records when it meets another version
    save_flow_on(db, Flow(id="stuck", nodes=[Node("a", "open-menu")]), "Stuck", "paint.exe")


def an_expression(db):
    node = Node("a", "open-menu", fields={"text": {"expression": "1 + 1"}})
    save_flow_on(db, Flow(id="stuck", nodes=[node]), "Stuck", "paint.exe")


def unreadable(db):
    save_flow_on(db, Flow(id="stuck", nodes=[]), "Stuck", "paint.exe")
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute("UPDATE flows SET definition = ? WHERE id = 'stuck'", ('{"nodes": [{"id": "a", "kind": "from-the-future"}]}',))


@pytest.mark.parametrize("trouble, why", [
    (no_nodes, "It has no steps yet. Open it to add some."),
    (not_learned, "“print-it” is not learned for Paint yet."),
    (learned_for_another_app, "“open-menu” is not learned for Word yet."),
    (never_learned_at_all, "“print-it” is not learned yet."),
    (rejected, "“save-file” is blocked. To run this flow, press “Allow again”: on Home, in “Needs your attention”, or on Apps."),
    (app_updated, "Paint was updated: “open-menu” has to be learned again."),
    (an_expression, "It uses an expression, which cannot run yet."),
    (unreadable, "It cannot be read."),
], ids=lambda value: getattr(value, "__name__", ""))
def test_a_flow_that_cannot_run_says_so_on_its_button_and_why(tmp_path, trouble, why):
    put_flows(tmp_path)
    trouble(tmp_path / "user.db")
    with home(tmp_path) as (page, desktop):
        pressed = []
        page.on("request", lambda r: pressed.append(r.url) if r.method == "POST" else None)
        button_ = run_button(page, "stuck")
        button_.filter(has_text="Not ready yet").wait_for()
        assert button_.is_disabled()
        assert page.get_by_test_id("flow-why-stuck").inner_text().strip() == why
        # the reason is read with the button, which stays reachable by the keyboard
        assert page.get_by_test_id("flow-why-stuck").get_attribute("id") == button_.get_attribute("aria-describedby")
        button_.focus()
        page.keyboard.press("Enter")
        button_.click(force=True)
        page.wait_for_timeout(300)
        assert pressed == [] and desktop.clicks == []
        # one flow's trouble is its own, unless it is about an action the other flow uses too
        assert run_button(page, "morning").is_disabled() == (trouble in (rejected, app_updated))


def test_a_run_that_stops_leaves_the_flow_waiting_and_saying_why(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha")])  # the second action finds nothing
    with home(tmp_path, desktop) as (page, _):
        run_button(page, "morning").click()
        says(page, "morning", r"Stopped .+ at \d\d:\d\d")
        run_button(page, "morning").filter(has_text="Try again").wait_for()  # a stopped flow is tried again, not run
        page.get_by_test_id("attention-morning").wait_for()
        doubt = list_doubts(tmp_path / "user.db", "open")[0]
        answer_doubt(tmp_path / "user.db", doubt.id, "done")  # in another window
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        run_button(page, "morning").filter(has_text="Run now").wait_for()


def test_an_action_learned_again_after_an_update_can_run(tmp_path):
    db = tmp_path / "user.db"
    put_flows(tmp_path)
    revalidate_changed_versions(db, "paint.exe", "1.0")  # the last version a run met
    save_step(db, step("open-menu", "Alpha", version="2.0"))  # taught since on a newer one, which no run has met yet
    save_step(db, step("save-file", "Beta", version="2.0"))
    with home(tmp_path, FakeDesktop(controls=[button("Alpha"), button("Beta")], version="2.0")) as (page, desktop):
        run_button(page, "morning").click()
        says(page, "morning", "Worked")


def test_a_factory_action_of_an_older_version_waits_to_be_learned_again(tmp_path):
    put_flows(tmp_path)
    save_step(tmp_path / "factory.db", step("print-it", "Print", origin="factory"))
    revalidate_changed_versions(tmp_path / "user.db", "paint.exe", "2.0")
    put_flow(tmp_path, "printing", "Printing", "print-it")
    with home(tmp_path) as (page, _):
        says(page, "printing", "Paint was updated: “print-it” has to be learned again.")


def at_home(page):
    page.get_by_role("heading", name="Your flows").wait_for()


def on_the_flow_screen(page, title, nodes):
    page.get_by_test_id("flow-title").wait_for()
    page.wait_for_function("(t) => document.querySelector('[data-testid=flow-title]').value === t", arg=title)
    page.wait_for_function("(n) => document.querySelectorAll('.react-flow__node').length === n", arg=nodes)


def add_wait(page):
    page.get_by_test_id("search").fill("wait")
    page.get_by_test_id("system-wait").click()
    page.get_by_test_id("search").fill("")


def test_a_flows_row_opens_the_flow_screen_which_leads_back_home(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    with home(tmp_path) as (page, desktop):
        rect = row(page, "morning").get_by_text("Paint", exact=True).bounding_box()
        page.mouse.click(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)  # anywhere on the row, not only its name
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("back-home").click()
        at_home(page)
        page.get_by_role("button", name="Weekly export", exact=True).click()
        on_the_flow_screen(page, "Weekly export", 1)
        assert desktop.clicks == []  # opening runs nothing


def test_new_flow_opens_an_empty_flow_screen_under_a_name_of_its_own(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "my-flow", "New flow", "open-menu")
    with home(tmp_path) as (page, _):
        page.get_by_test_id("new-flow").click()
        on_the_flow_screen(page, "New flow 2", 0)  # the flow screen had read nothing before this
        page.get_by_test_id("back-home").click()
        page.get_by_role("button", name="Morning report", exact=True).click()
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("back-home").click()
        page.get_by_test_id("new-flow").click()
        on_the_flow_screen(page, "New flow 2", 0)


def test_changes_survive_home_and_what_cannot_be_kept_is_never_dropped_without_asking(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    with home(tmp_path) as (page, _):
        asked, accept = [], {"now": False}
        page.on("dialog", lambda d: (asked.append(d.message), d.accept() if accept["now"] else d.dismiss()))
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        add_wait(page)
        page.get_by_test_id("back-home").click()
        page.get_by_test_id("open-flow-morning").click()  # the same flow: still as it was left, nothing to ask
        on_the_flow_screen(page, "Morning report", 3)
        assert asked == []
        page.get_by_test_id("run-status").filter(has_text="Saved").wait_for()  # it was kept by itself
        page.get_by_test_id("back-home").click()
        page.get_by_test_id("open-flow-weekly").click()  # kept, so leaving it asks nothing
        on_the_flow_screen(page, "Weekly export", 1)
        assert asked == []
        page.get_by_test_id("back-home").click()
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 3)

        page.get_by_test_id("search").fill("two paths")  # a choice with no yes path cannot be kept yet
        page.get_by_test_id("system-if").click()
        page.get_by_test_id("run-status").filter(has_text="Not saved").wait_for()
        page.get_by_test_id("back-home").click()
        for other in ("open-flow-weekly", "new-flow"):
            page.get_by_test_id(other).click()
            page.wait_for_timeout(300)
            at_home(page)  # refused: the person stays where they were
        assert len(asked) == 2 and "Morning report" in asked[0]
        accept["now"] = True
        page.get_by_test_id("open-flow-weekly").click()
        on_the_flow_screen(page, "Weekly export", 1)


def test_a_flow_opened_from_home_after_a_reload_is_not_replaced_by_the_one_open_before(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    with home(tmp_path) as (page, _):
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("back-home").click()
        page.reload()
        at_home(page)  # a reload keeps the screen
        page.get_by_test_id("open-flow-weekly").click()
        on_the_flow_screen(page, "Weekly export", 1)
        page.wait_for_timeout(800)
        assert page.get_by_test_id("flow-title").input_value() == "Weekly export"


def test_a_flow_that_could_not_be_opened_says_so(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        page.route("**/api/flows/morning", lambda route: route.abort())
        page.get_by_test_id("open-flow-morning").click()
        page.get_by_test_id("error").filter(has_text="Cannot reach").wait_for()
        page.get_by_test_id("back-home").click()
        at_home(page)


@pytest.mark.parametrize("lost", ["the answer to Run now", "the first question after a reload", "a question during the run"])
def test_a_run_stays_followed_when_a_request_is_lost(tmp_path, lost):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 2.0
    with home(tmp_path, desktop) as (page, _):
        missed = []

        def lose(pattern, answered_first=False):
            def route(asked):
                if missed:
                    return asked.continue_()
                missed.append(asked.request.url)
                if answered_first:
                    asked.fetch()  # the server did get it and did it
                asked.abort()

            page.route(re.compile(pattern), route)

        if lost == "the answer to Run now":
            lose(r"/run$", answered_first=True)
        elif lost == "a question during the run":
            lose(r"/api/runs/\w+$")
        run_button(page, "morning").click()
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        if lost == "the first question after a reload":
            lose(r"/api/runs$")
            page.reload()
            run_button(page, "morning").filter(has_text="Stop").wait_for()
        says(page, "morning", "Worked")
        run_button(page, "morning").filter(has_text="Run now").wait_for()
        assert missed and clicked(desktop) == ["Alpha", "Beta"]
        assert row(page, "morning").get_by_role("alert").count() == 0


def test_the_flow_screen_follows_a_run_whose_answer_was_lost(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 2.0
    with home(tmp_path, desktop) as (page, _):
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        page.route(re.compile(r"/run$"), lambda asked: (asked.fetch(), asked.abort()))
        page.get_by_test_id("run").click()
        page.get_by_test_id("stop").wait_for()
        page.get_by_test_id("run-status").filter(has_text="Finished").wait_for()


def test_leaving_the_flow_screen_as_a_run_ends_leaves_the_nodes_in_sight(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.0
    with home(tmp_path, desktop) as (page, _):
        complaints = []
        page.on("console", lambda m: complaints.append(m.text) if m.type == "error" else None)
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        # the way back is pressed the moment the screen says the run ended, before the canvas has fitted itself again
        page.evaluate("""() => new MutationObserver((_, watching) => {
            if (!document.querySelector('[data-testid=run-status]').textContent.includes('Finished')) return
            watching.disconnect()
            document.querySelector('[data-testid=back-home]').click()
        }).observe(document.body, { subtree: true, childList: true, characterData: true })""")
        page.get_by_test_id("run").click()
        says(page, "morning", "Worked")
        page.wait_for_timeout(500)
        page.get_by_test_id("open-flow-morning").click()  # the flow screen is reached from its row
        page.wait_for_timeout(500)
        assert complaints == []
        canvas = page.locator(".canvas").bounding_box()
        for rect in page.locator(".react-flow__node").all():
            drawn = rect.bounding_box()
            assert canvas["x"] <= drawn["x"] and drawn["y"] + drawn["height"] <= canvas["y"] + canvas["height"]


def test_a_run_stays_followed_across_screens_and_a_reload(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 3.0
    with home(tmp_path, desktop) as (page, _):
        run_button(page, "morning").click()
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        page.get_by_test_id("open-flow-morning").click()
        page.get_by_test_id("stop").wait_for()  # the flow screen follows the same run
        page.get_by_test_id("back-home").click()
        page.get_by_test_id("tab-apps").click()
        page.get_by_test_id("tab-home").click()
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        page.reload()
        run_button(page, "morning").filter(has_text="Stop").click()
        says(page, "morning", "You stopped it")
        assert clicked(desktop) == ["Alpha"]


def test_a_run_started_on_the_flow_screen_or_in_another_window_shows_on_home(tmp_path):
    put_flows(tmp_path)
    put_flow(tmp_path, "weekly", "Weekly export", "open-menu")
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 2.0
    with home(tmp_path, desktop) as (page, _):
        page.get_by_test_id("open-flow-morning").click()
        on_the_flow_screen(page, "Morning report", 2)
        page.get_by_test_id("run").click()
        page.get_by_test_id("stop").wait_for()
        page.get_by_test_id("back-home").click()
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        says(page, "morning", "Worked")
        page.evaluate("""() => fetch('/api/flows/weekly/run', { method: 'POST', body: JSON.stringify({ app: 'paint.exe' }),
            headers: { Authorization: 'Bearer e2e-token', 'Content-Type': 'application/json' } })""")
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")  # the person comes back to this window
        run_button(page, "weekly").filter(has_text="Stop").wait_for()
        says(page, "weekly", "Worked")


@pytest.mark.parametrize("answer", ["the run goes on", "the run is not known any more"])
def test_home_says_when_it_cannot_reach_the_program_until_it_answers(tmp_path, answer):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.0
    with home(tmp_path, desktop) as (page, _):
        questions = re.compile(r"/api/runs/\w+$")
        page.route(questions, lambda asked: asked.abort())
        run_button(page, "morning").click()
        unreachable = page.get_by_role("status").filter(has_text="Cannot reach Mutehand")
        unreachable.wait_for()
        page.unroute(questions)
        if answer == "the run goes on":
            says(page, "morning", "Worked")
        else:
            page.route(questions, lambda asked: asked.fulfill(status=404, content_type="application/json", body='{"error": "no such run"}'))
            says(page, "morning", r"The run was lost \(no such run\)")
        unreachable.wait_for(state="detached")


def test_a_lost_reading_of_the_list_takes_neither_the_flows_nor_stop_away(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.5
    with home(tmp_path, desktop) as (page, _):
        run_button(page, "morning").click()
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        lost = []
        page.route("**/api/flow-overview", lambda asked: (lost.append(1), asked.abort()))
        page.evaluate("() => window.dispatchEvent(new Event('focus'))")
        page.wait_for_timeout(300)
        assert lost and run_button(page, "morning").inner_text().strip() == "Stop"
        page.unroute("**/api/flow-overview")
        says(page, "morning", "Worked")


def test_a_list_that_never_arrived_says_so_and_can_be_asked_again(tmp_path):
    put_flows(tmp_path)
    with home(tmp_path) as (page, _):
        at_home(page)
        page.route("**/api/flow-overview", lambda asked: asked.abort())
        page.reload()
        page.get_by_test_id("load-error").wait_for()
        assert page.get_by_test_id("no-flows").count() == 0
        page.unroute("**/api/flow-overview")
        page.get_by_test_id("retry").click()
        says(page, "morning", "Never run")


def test_no_screen_content_of_a_private_app_reaches_home(tmp_path):
    db = tmp_path / "user.db"
    save_step(db, step("open-chat", "Chat with Ana Ruiz", app="telegram.exe"))
    put_flow(tmp_path, "greet", "Say hello", "open-chat", app="telegram.exe")
    mark_private(db, "telegram.exe")
    desktop = FakeDesktop(controls=[button("Bank code 4471")], app="telegram.exe")
    with home(tmp_path, desktop) as (page, _):
        said = []
        page.on("response", lambda r: said.append(r) if "/api/" in r.url else None)
        run_button(page, "greet").click()
        page.get_by_test_id("attention-greet").wait_for()
        page.wait_for_timeout(300)
        sent = [r.text() for r in said if "/api/flow-overview" in r.url or "/api/runs" in r.url or "/api/attention" in r.url]
        assert any("greet" in text for text in sent)
        shown = page.content() + "".join(sent)
        assert "Ana Ruiz" not in shown and "4471" not in shown


FOCUSED = "() => document.activeElement.dataset.testid"


def tab_to(page, test_id):
    for _ in range(40):
        if page.evaluate(FOCUSED) == test_id:
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"{test_id} cannot be reached with Tab")


def test_home_works_with_the_keyboard_alone(tmp_path):
    put_flows(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.2
    with home(tmp_path, desktop) as (page, _):
        at_home(page)
        says(page, "morning", "Never run")
        tab_to(page, "tab-home")
        tab_to(page, "new-flow")  # then each row: its name, then its Run now
        page.keyboard.press("Tab")
        assert page.evaluate(FOCUSED) == "open-flow-morning"
        assert page.evaluate("() => getComputedStyle(document.activeElement, '::after').outlineStyle") == "solid"  # seen on the row
        page.keyboard.press("Tab")
        assert page.evaluate(FOCUSED) == "run-now-morning"
        page.keyboard.press("Enter")
        run_button(page, "morning").filter(has_text="Stop").wait_for()
        page.wait_for_function("() => !document.activeElement.hasAttribute('aria-disabled')")  # Stop has armed
        assert page.evaluate(FOCUSED) == "run-now-morning"  # the focus stayed on the button through its changes
        assert run_button(page, "morning").get_attribute("aria-label") == "Stop: Morning report"
        page.keyboard.press("Space")
        says(page, "morning", "You stopped it")
        assert page.evaluate(FOCUSED) == "run-now-morning" and clicked(desktop) == ["Alpha"]
        page.keyboard.press("Shift+Tab")
        page.keyboard.press("Enter")
        on_the_flow_screen(page, "Morning report", 2)
        page.wait_for_function("() => document.activeElement !== document.body")
        page.get_by_test_id("back-home").press("Enter")
        at_home(page)
        page.wait_for_function("() => document.activeElement.dataset.testid === 'open-flow-morning'")  # back where they were
        page.keyboard.press("Shift+Tab")
        assert page.evaluate(FOCUSED) == "new-flow"
        page.keyboard.press("Enter")
        on_the_flow_screen(page, "New flow", 0)
        page.wait_for_function("() => document.activeElement !== document.body")
        page.get_by_test_id("back-home").press("Enter")  # a flow never saved has no row
        page.wait_for_function("() => document.activeElement.dataset.testid === 'new-flow'")
        page.get_by_test_id("tab-apps").click()
        page.get_by_test_id("tab-home").click()
        says(page, "morning", "You stopped it")
        assert page.evaluate(FOCUSED) == "tab-home"  # choosing a screen leaves the focus on its tab


# every button shown on Home, and what reaches past the window or is too small to press
BUTTONS = """(width) => [...document.querySelectorAll('.home button')].map((b) => {
    const rect = b.classList.contains('flow-open') ? b.closest('li').getBoundingClientRect() : b.getBoundingClientRect()
    return [b.innerText.trim(), rect.left >= 0 && rect.right <= width && rect.height >= 44
      && (b.classList.contains('flow-open') || b.scrollWidth <= b.clientWidth)]
  }).filter(([, fits]) => !fits)"""
NO_SIDEWAYS_SCROLL = """() => [document.documentElement, document.querySelector('main')].every((el) => el.scrollWidth <= el.clientWidth)"""


@pytest.mark.parametrize("width,height", [(1280, 800), (683, 384), (390, 740)])
def test_home_fits_a_narrow_window_and_stays_readable(tmp_path, width, height):
    db = tmp_path / "user.db"
    put_flows(tmp_path)
    long = "Weekly-report-" + "x" * 80
    put_flow(tmp_path, "long-1", long, "open-menu", "save-file")
    put_flow(tmp_path, "long-2", long, "print-" + "y" * 60)  # twins, and one that cannot run for a long reason
    record_app_name(db, FakeDesktop(controls=[], product_name="Quill Ledger Professional Accounting " + "z" * 50).app_key())
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    desktop.click_seconds = 1.0

    def fine():
        assert page.evaluate(NO_SIDEWAYS_SCROLL)
        assert page.evaluate(BUTTONS, width) == []
        assert page.evaluate(CONTRAST) == []

    with home(tmp_path, desktop) as (page, _):
        page.set_viewport_size({"width": width, "height": height})
        run_button(page, "long-2").filter(has_text="Not ready yet").wait_for()
        fine()
        run_button(page, "long-1").click()
        run_button(page, "long-1").filter(has_text="Stop").wait_for()
        page.wait_for_timeout(700)
        fine()
        # the row's button never lies over its words
        for flow_id in ("long-1", "long-2", "morning"):
            words, pressed = row(page, flow_id).locator(".flow-words").bounding_box(), run_button(page, flow_id).bounding_box()
            assert words["x"] + words["width"] <= pressed["x"] or words["y"] + words["height"] <= pressed["y"], flow_id
        says(page, "long-1", "Worked")
        fine()
        page.get_by_test_id("open-flow-long-1").click()
        back = page.get_by_test_id("back-home").bounding_box()
        assert back["x"] >= 0 and back["x"] + back["width"] <= width and back["y"] >= 0
        assert page.evaluate(CONTRAST) == []


def test_an_app_remembered_in_another_spelling_runs_on_the_taught_one(tmp_path):
    put_flows(tmp_path)
    save_legacy_flow(tmp_path / "user.db", Flow(id="morning", nodes=[Node("n1", "open-menu"), Node("n2", "save-file")]), app="PAINT")
    asked = []
    desktop = FakeDesktop(controls=[button("Alpha"), button("Beta")])
    with home(tmp_path, desktop_for=lambda app: asked.append(app) or desktop) as (page, _):
        run_button(page, "morning").click()
        says(page, "morning", "Worked")
        assert set(asked) == {"paint.exe"}
