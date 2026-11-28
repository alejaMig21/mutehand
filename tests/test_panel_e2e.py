"""The node panel: one search box, sections by node type, and the technology a step node takes from a search. Opt-in:
`pytest -m web`."""

import pytest
from test_canvas_e2e import editor
from test_editor_e2e import SAVED
from test_node_technology_e2e import open_technology

from workflow_factory import load_flow, save_step
from workflow_factory.steps import add_tags

from fake_desktop import step

pytestmark = pytest.mark.web

SECTIONS = ["steps", "components", "triggers", "order", "logic", "data"]
OVERFLOWS = """() => [...document.querySelectorAll('.search-panel, .search-panel *')]
    .filter((e) => e.clientWidth && e.scrollWidth > e.clientWidth).map((e) => e.className || e.tagName)"""
# the colour of the panel's text against what is painted behind it, WCAG AA
CONTRAST = """() => {
  const rgb = (c) => c.match(/[\\d.]+/g).map(Number)
  const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
    .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
  const behind = (el) => { for (; el; el = el.parentElement) { const c = rgb(getComputedStyle(el).backgroundColor)
    if (c.length < 4 || c[3] > 0.5) return c } return [255, 255, 255] }
  return [...document.querySelectorAll('.search-panel summary, .search-panel small, .search-panel .empty, .search-panel .muted')]
    .filter((e) => e.offsetParent && e.innerText.trim()).map((e) => {
      const [a, z] = [lum(rgb(getComputedStyle(e).color)), lum(behind(e))].sort((x, y) => y - x)
      return [e.innerText.trim(), (a + 0.05) / (z + 0.05)]
    }).filter(([, ratio]) => ratio < 4.5)
}"""


def learned(tmp_path):
    """Save for Excel and for Paint (one step, two programs, a pattern tag), and Open menu for Paint only."""
    db = tmp_path / "user.db"
    save_step(db, step("Save", "Save workbook", app="excel.exe"))
    save_step(db, step("Save", "Save picture", app="paint.exe"))
    save_step(db, step("Open menu", "File", app="paint.exe"))
    add_tags(db, "Save", ["file"])
    return db


def is_open(page, key):
    return page.get_by_test_id(f"section-{key}").evaluate("e => e.open")


def announced(page, name):
    """The expanded state the browser gives a screen reader for the section called `name` (None: it announces none)."""
    session = page.context.new_cdp_session(page)
    nodes = session.send("Accessibility.getFullAXTree")["nodes"]
    for node in nodes:
        if node.get("name", {}).get("value") == name and not node.get("ignored"):
            for prop in node.get("properties", []):
                if prop["name"] == "expanded":
                    return prop["value"]["value"]
    return None


def steps_listed(page):
    return page.locator('[data-testid^="palette-"]').evaluate_all("els => els.map(e => e.dataset.testid.slice(8))")


def test_with_the_box_empty_only_steps_and_components_are_open_and_components_say_they_are_empty(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("palette-Save").wait_for()

        assert [key for key in SECTIONS if is_open(page, key)] == ["steps", "components"]
        assert steps_listed(page) == ["Open menu", "Save"]  # each name once, whatever the programs
        assert "No components yet" in page.get_by_test_id("section-components").inner_text()
        assert page.get_by_test_id("search").count() == 1 and page.get_by_test_id("technology-filter").count() == 0
        assert page.get_by_text("Decisions and repeats").count() == 0 and page.get_by_text("Other nodes").count() == 0
        assert page.get_by_test_id("system-wait").is_hidden()  # in Order, which is closed


def test_typing_a_technology_lists_its_steps_and_typing_a_name_lists_it_whatever_the_program(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("palette-Save").wait_for()
        search = page.get_by_test_id("search")

        search.fill("paint")
        page.get_by_test_id("palette-Open menu").wait_for()
        assert steps_listed(page) == ["Open menu", "Save"]  # Save has a locator for Paint too

        search.fill("excel")
        page.get_by_test_id("palette-Open menu").wait_for(state="detached")
        assert steps_listed(page) == ["Save"]

        search.fill("FILE")  # a pattern tag, capitals ignored
        assert steps_listed(page) == ["Save"]

        search.fill("sav")
        assert steps_listed(page) == ["Save"]


def test_while_typing_every_section_with_a_match_opens_and_the_others_are_gone_and_escape_clears(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        search = page.get_by_test_id("search")
        search.fill("w")  # Wait a while (Order) and Write a field (Data)
        page.get_by_test_id("system-wait").wait_for()

        assert [key for key in SECTIONS if page.get_by_test_id(f"section-{key}").count()] == ["order", "data"]
        assert is_open(page, "order") and is_open(page, "data")

        search.press("Escape")
        assert search.input_value() == ""
        page.get_by_test_id("palette-Save").wait_for()
        assert [key for key in SECTIONS if is_open(page, key)] == ["steps", "components"]


def test_a_section_opens_and_closes_from_the_keyboard_and_says_its_name_and_state(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        heading = page.get_by_test_id("section-triggers").locator("summary")
        heading.focus()
        assert "Triggers" in heading.inner_text()

        page.keyboard.press("Enter")
        assert is_open(page, "triggers")
        assert heading.evaluate("e => e.parentElement.open && e === document.activeElement")
        assert announced(page, "Triggers") is True

        heading.focus()
        page.keyboard.press("Space")
        page.wait_for_function("() => !document.querySelector('[data-testid=section-triggers]').open")
        assert announced(page, "Triggers") is False


def test_a_message_says_nothing_matches_and_the_entry_to_teach_stays(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("search").fill("zzz nothing")

        page.get_by_text("Nothing matches").wait_for()
        assert page.get_by_test_id("section-steps").count() == 0
        page.get_by_role("button", name="It is not here: teach it").click()
        assert "zzz nothing" in page.locator(".search-panel").inner_text()


def test_a_step_added_from_a_search_for_a_program_takes_that_program(tmp_path):
    db = learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("flow-title").fill("kept")
        page.get_by_test_id("search").fill("excel save")
        page.get_by_test_id("palette-Save").click()
        page.get_by_test_id("node-n1").wait_for()
        assert page.get_by_test_id("technology-chooser").count() == 0
        page.get_by_test_id("run-status").filter(has_text=SAVED).wait_for()

    assert [n.technology for n in load_flow(db, None, "kept").nodes] == ["excel.exe"]


def test_a_step_with_several_programs_and_no_program_searched_asks_which_and_never_takes_the_first(tmp_path):
    db = learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("flow-title").fill("kept")
        page.get_by_test_id("search").fill("sav")
        page.get_by_test_id("palette-Save").click()

        chooser = page.get_by_test_id("technology-chooser")
        chooser.wait_for()
        assert page.locator(".react-flow__node").count() == 0  # nothing was added yet
        assert page.evaluate("document.activeElement.dataset.testid") == "technology-excel.exe"  # the first choice has the focus
        page.keyboard.press("Tab")  # keyboard friendly: Tab to the next, Enter to take it
        page.keyboard.press("Enter")
        page.get_by_test_id("node-n1").wait_for()
        assert chooser.count() == 0
        assert open_technology(page, "n1").input_value() == "paint.exe"
        page.get_by_test_id("run-status").filter(has_text=SAVED).wait_for()

    assert [n.technology for n in load_flow(db, None, "kept").nodes] == ["paint.exe"]


def test_escape_leaves_the_chooser_without_adding_anything_and_a_step_of_one_program_asks_nothing(tmp_path):
    learned(tmp_path)
    with editor(tmp_path) as page:
        page.get_by_test_id("palette-Save").click()
        page.get_by_test_id("technology-chooser").wait_for()
        page.keyboard.press("Escape")
        page.get_by_test_id("technology-chooser").wait_for(state="detached")
        assert page.locator(".react-flow__node").count() == 0

        page.get_by_test_id("palette-Open menu").click()
        page.get_by_test_id("node-n1").wait_for()
        assert page.get_by_test_id("technology-chooser").count() == 0


@pytest.mark.parametrize("width", [683, 390])
def test_the_panel_fits_a_narrow_window_and_every_word_in_it_can_be_read(tmp_path, width):
    learned(tmp_path)
    with editor(tmp_path, size=(width, 800)) as page:
        page.get_by_test_id("palette-Save").wait_for()
        for key in SECTIONS[2:]:  # the closed ones: every section is open and read
            page.get_by_test_id(f"section-{key}").locator("summary").click()
        page.get_by_test_id("palette-Save").click()
        page.get_by_test_id("technology-chooser").wait_for()
        page.wait_for_timeout(300)

        assert page.evaluate(OVERFLOWS) == []
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.evaluate(CONTRAST) == []
