"""Apps are called by the product name their executable declares, never by a file name (editor rethink, ticket 03).

The built editor in a headless browser against the real API, with the stand-in desktop and Windows scheduler. The app
names are invented: nothing in the product knows a particular app.
"""

import re

import pytest
from fake_scheduler import FakeScheduler
from test_editor_e2e import DIST, open_page

from workflow_factory import Flow, Locator, Node, Sensitivity, grant_consent, run_flow, save_flow, save_step
from workflow_factory.api import ApiServer
from workflow_factory.desktop import DesktopError
from workflow_factory.tutor import observe, teach_step

from fake_desktop import FakeDesktop, button, step

pytestmark = pytest.mark.web


def closed(app):
    raise DesktopError(f"{app} is not running")


@pytest.fixture
def browse(tmp_path):
    """browse(desktop_for) -> a headless page on the editor over this test's database."""
    from playwright.sync_api import sync_playwright

    servers = []
    with sync_playwright() as playwright:
        def start(desktop_for=closed):
            server = ApiServer(tmp_path / "user.db", None, desktop_for, token="e2e-token", web_dir=DIST,
                               schedule_runner=FakeScheduler())
            server.start()
            servers.append(server)
            _, page = open_page(playwright, server)
            page.set_default_timeout(8_000)
            return page

        try:
            yield start
        finally:
            for server in servers:
                server.stop()


def one_step_flow(folder, app="zzqx.exe"):
    save_step(folder / "user.db", step("open-menu", "Alpha", app=app))
    save_flow(folder / "user.db", Flow(id="morning", nodes=[Node("n1", "open-menu")]))
    return folder / "user.db"


def test_the_name_seen_in_a_run_is_what_the_screens_say_once_the_app_is_closed(tmp_path, browse):
    db = one_step_flow(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha")], app="zzqx.exe", product_name="Quill Ledger")
    run_flow(Flow(id="morning", nodes=[Node("n1", "open-menu")]), desktop, db)

    page = browse()  # the app is closed now
    page.get_by_test_id("palette-open-menu").wait_for()  # the actions of the app chosen beside them
    page.wait_for_function("() => document.querySelector('[data-testid=app-name]').selectedOptions[0].text === 'Quill Ledger'")
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").filter(has_text="Quill Ledger").wait_for()
    assert ".exe" not in page.locator("body").inner_text().lower()


# everything a person can read or hear: text, what the fields hold and suggest, spoken names and tooltips
SHOWN = """() => [document.body.innerText,
    ...[...document.querySelectorAll('input, textarea')].map((e) => e.value),
    ...[...document.querySelectorAll('select')].map((e) => e.selectedOptions[0]?.textContent ?? ''),
    ...[...document.querySelectorAll('option')].map((e) => (e.closest('datalist') ? e.value : '') + ' ' + e.textContent),
    ...[...document.querySelectorAll('[aria-label], [title]')].map((e) => `${e.getAttribute('aria-label')} ${e.title}`),
  ].join('\\n')"""


def assert_no_file_names(page):
    page.wait_for_timeout(300)  # what the screen loads is on it
    assert ".exe" not in page.evaluate(SHOWN).lower()


@pytest.mark.parametrize("product_name, shown", [("", "Zzqx"), ("Quill Ledger", "Quill Ledger")])
def test_no_screen_shows_a_file_name_and_each_calls_the_app_the_same(tmp_path, browse, product_name, shown):
    db = one_step_flow(tmp_path)
    save_step(db, step("press-send", "Send", app="zzqx.exe", sensitive=Sensitivity.OUTWARD_ACTION))
    save_step(db, step("stamp", "Stamp", app="vvrt.exe"))
    save_flow(db, Flow(id="mixed", nodes=[Node("n1", "open-menu"), Node("n2", "stamp")]))  # one step is another app's
    grant_consent(db, "zzqx.exe", "Send", "click")
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name=product_name))

    page = browse()
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-mixed").click()
    page.locator('.react-flow__node[data-id="n2"]').wait_for()
    app = page.get_by_test_id("app-name")
    app.select_option(label=shown)
    assert page.get_by_test_id("node-n1").inner_text().count(shown) == 1
    assert f"for {shown} yet" in page.get_by_test_id("cannot-start").inner_text()
    page.locator('.react-flow__node[data-id="n1"]').click()
    page.get_by_test_id("test-node").click()
    assert f"on {shown}" in page.get_by_test_id("test-warning").inner_text()
    assert shown in page.get_by_test_id("strip-says").inner_text()
    assert_no_file_names(page)

    page.get_by_test_id("tab-apps").click()
    row = page.get_by_test_id("app-row-zzqx.exe")
    row.filter(has_text=shown).wait_for()
    row.click()
    card = page.get_by_test_id("app-card-zzqx.exe")
    card.get_by_role("heading", name=shown).wait_for()
    card.get_by_test_id("app-permission-Send-click").wait_for()
    assert_no_file_names(page)
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("daily-morning").click()
    page.get_by_test_id("daily-set-morning").click()
    flow = page.get_by_test_id("flow-morning")
    flow.filter(has_text="Every day at").wait_for()
    assert shown in flow.inner_text()
    assert_no_file_names(page)


def test_apps_that_declare_the_same_name_can_still_be_told_apart(tmp_path, browse):
    db = one_step_flow(tmp_path)
    save_step(db, step("stamp", "Stamp", app="vvrt.exe"))
    for app in ("zzqx.exe", "vvrt.exe"):
        observe(db, FakeDesktop(controls=[], app=app, product_name="Quill Suite"))

    page = browse()
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").filter(has_text="Quill Suite (Zzqx)").wait_for()
    page.get_by_test_id("app-row-vvrt.exe").filter(has_text="Quill Suite (Vvrt)").wait_for()
    assert_no_file_names(page)


@pytest.mark.parametrize("declared, shown", [("zzqx.exe", "zzqx"), ("  Quill Ledger  ", "Quill Ledger")])
def test_a_declared_name_is_shown_without_an_extension_or_stray_spaces(tmp_path, browse, declared, shown):
    db = one_step_flow(tmp_path)
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name=declared))

    page = browse()
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").locator("b").filter(has_text=re.compile(f"^{shown}$")).wait_for()
    assert_no_file_names(page)


LONG = "Quill Ledger Professional Accounting Workbench for Teams and Families"
# what reaches past the right edge, for the failure message; the canvas and a table scroll on their own
STICKS_OUT = """() => [...document.querySelectorAll('.screen *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 1
    && !e.closest('.react-flow, .table-scroll')).slice(0, 8)
    .map((e) => `${e.tagName}.${e.getAttribute('class')} ${Math.round(e.getBoundingClientRect().right)}`)"""
NOTHING_OVERFLOWS = """(within) => [...document.querySelectorAll(within)]
    .every((e) => e.clientWidth === 0 || e.scrollWidth <= e.clientWidth)"""


@pytest.mark.parametrize("width", [683, 390])
def test_the_app_is_chosen_by_keyboard_and_a_long_name_fits_a_narrow_window(tmp_path, browse, width):
    db = one_step_flow(tmp_path)
    save_step(db, step("stamp", "Stamp", app="vvrt.exe"))
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name=LONG))
    observe(db, FakeDesktop(controls=[], app="vvrt.exe", product_name="Unbroken" * 12))

    page = browse()
    page.set_viewport_size({"width": width, "height": 800})
    chooser = page.get_by_test_id("app-name")
    chooser.locator("option", has_text=LONG).wait_for(state="attached")
    chooser.focus()
    before = chooser.input_value()
    page.keyboard.press("ArrowUp" if before == "zzqx.exe" else "ArrowDown")
    assert chooser.input_value() not in ("", before)
    rect = chooser.bounding_box()
    assert rect["x"] >= 0 and rect["x"] + rect["width"] <= width

    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-morning").click()
    card = page.get_by_test_id("node-n1")
    card.wait_for()
    for app in ("zzqx.exe", "vvrt.exe"):
        page.get_by_test_id("app-name").select_option(app)
    assert card.evaluate("(e) => e.scrollWidth <= e.clientWidth")  # the name stays inside its node
    fits = "() => document.querySelector('.screen').scrollWidth <= innerWidth"
    assert page.evaluate(fits), ("flow screen", page.evaluate(STICKS_OUT))
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").click()
    page.get_by_test_id("app-card-zzqx.exe").wait_for()
    page.wait_for_timeout(300)
    assert page.evaluate(fits), ("apps", page.evaluate(STICKS_OUT))
    page.get_by_test_id("tab-home").click()
    page.get_by_test_id("flow-morning").wait_for()
    page.wait_for_timeout(300)
    assert page.evaluate(fits), ("home", page.evaluate(STICKS_OUT))
    page.get_by_test_id("open-flow-morning").click()
    page.locator(".opening").wait_for(state="detached")  # a node chosen while "Opening…" shows is forgotten when it ends
    assert page.evaluate(NOTHING_OVERFLOWS, ".search-panel .entry")
    page.get_by_test_id("app-name").select_option("vvrt.exe")
    page.locator('.react-flow__node[data-id="n1"]').press("Space")
    page.get_by_test_id("test-node").click()
    page.get_by_test_id("test-warning").wait_for()
    assert page.evaluate(NOTHING_OVERFLOWS, ".strip, .strip *")


def test_the_apps_screen_orders_the_apps_by_the_names_it_shows(tmp_path, browse):
    db = one_step_flow(tmp_path)
    save_step(db, step("stamp", "Stamp", app="vvrt.exe"))
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name="Atlas"))

    page = browse()
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").filter(has_text="Atlas").wait_for()
    assert page.locator(".app-row b").all_inner_texts() == ["Atlas", "Vvrt"]


def test_a_run_from_the_editor_shows_the_name_it_has_just_learned(tmp_path, browse):
    one_step_flow(tmp_path)
    desktop = FakeDesktop(controls=[button("Alpha")], app="zzqx.exe", product_name="Quill Ledger")
    page = browse(lambda app: desktop)
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-morning").click()
    card = page.get_by_test_id("node-n1")
    card.filter(has_text="Zzqx").wait_for()

    page.get_by_test_id("run").click()  # from the keyboard or the mouse, the person never leaves this screen

    card.filter(has_text="Quill Ledger").wait_for()


def test_a_node_already_drawn_takes_the_name_when_it_arrives_late(tmp_path, browse):
    db = one_step_flow(tmp_path)
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name="Quill Ledger"))
    page = browse()
    held = []
    page.route("**/api/app-names", lambda route: held.append(route))  # the names are slow to come
    page.reload()
    page.get_by_test_id("open-flows").click()
    page.get_by_test_id("flow-morning").click()
    card = page.get_by_test_id("node-n1")
    card.filter(has_text="Zzqx").wait_for()
    page.wait_for_timeout(500)  # nothing else is left that would draw the node again

    for route in held:
        route.continue_()

    card.filter(has_text="Quill Ledger").wait_for()


def test_an_app_is_found_by_its_product_name(tmp_path, browse):
    db = one_step_flow(tmp_path)
    save_step(db, step("stamp", "Stamp", app="vvrt.exe"))
    observe(db, FakeDesktop(controls=[], app="zzqx.exe", product_name="Quill Ledger"))

    page = browse()
    page.get_by_test_id("app-name").select_option(label="Quill Ledger")  # the app is chosen by that name
    page.get_by_test_id("search").fill("quill")
    page.get_by_test_id("palette-open-menu").wait_for()
    assert page.get_by_test_id("palette-stamp").count() == 0


@pytest.mark.parametrize("seen_by", [
    pytest.param(lambda db, desktop: observe(db, desktop), id="observing"),
    pytest.param(lambda db, desktop: teach_step(db, desktop, "close-node", Locator("button", "Alpha")), id="teaching"),
])
def test_the_tutor_seeing_an_app_records_its_name(tmp_path, browse, seen_by):
    db = one_step_flow(tmp_path)
    seen_by(db, FakeDesktop(controls=[button("Alpha")], app="zzqx.exe", product_name="Quill Ledger"))

    page = browse()
    page.get_by_test_id("tab-apps").click()
    page.get_by_test_id("app-row-zzqx.exe").filter(has_text="Quill Ledger").wait_for()
