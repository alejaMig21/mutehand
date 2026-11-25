import numpy as np
import pytest

from workflow_factory import (
    Derived,
    Endpoint,
    Flow,
    Locator,
    Node,
    Template,
    find_lesson,
    list_doubts,
    run_flow,
    save_lesson,
)

from fake_desktop import FakeDesktop, button, icon, lesson, pane

FLOW = Flow(nodes=[Node(id="n1", lesson="open-bin")])
BIN = Locator(role="icon", name="Recycle Bin")


def run(user_db, controls, **lesson_kw):
    save_lesson(user_db, lesson("open-bin", "Open Recycle Bin", **lesson_kw))
    desktop = FakeDesktop(controls=controls)
    return desktop, run_flow(FLOW, desktop=desktop, user_db=user_db)


def test_a_control_found_by_accessibility_is_used_without_touching_later_rungs(tmp_path):
    desktop, result = run(tmp_path / "user.db", [button("Open Recycle Bin"), icon("Recycle Bin", 0, 0, 40, 40)],
                          derived=Derived(anchor=BIN, fx=0.5, fy=0.5))

    assert result.stopped is None
    assert desktop.calls == [("find", "button", "Open Recycle Bin", None), ("click", "Open Recycle Bin")]


def test_when_accessibility_fails_the_derived_geometry_the_lesson_defines_is_used(tmp_path):
    desktop, result = run(tmp_path / "user.db", [icon("Recycle Bin", 100, 100, 40, 40)],
                          derived=Derived(anchor=BIN, fx=0.5, fy=0.25))

    assert result.stopped is None
    assert ("click_at", "Recycle Bin", 0.5, 0.25) in desktop.calls
    assert desktop.hits == [(120.0, 110.0)]


def test_a_moved_icon_is_still_resolved_through_its_anchor(tmp_path):
    desktop, _ = run(tmp_path / "user.db", [icon("Recycle Bin", 400, 300, 40, 40)],
                     derived=Derived(anchor=BIN, fx=0.5, fy=0.5))

    assert desktop.hits == [(420.0, 320.0)]  # same lesson, new place


def test_without_a_derived_rung_a_failed_accessibility_lookup_stops_with_a_doubt(tmp_path):
    user_db = tmp_path / "user.db"
    desktop, result = run(user_db, [icon("Recycle Bin", 100, 100, 40, 40)])

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]
    assert not any(call[0] == "click_at" for call in desktop.calls)


def test_a_derived_rung_whose_anchor_is_missing_stops_with_a_doubt(tmp_path):
    user_db = tmp_path / "user.db"
    desktop, result = run(user_db, [], derived=Derived(anchor=BIN, fx=0.5, fy=0.5))

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]


CANVAS = Locator(role="pane", name="Canvas")
TEMPLATE = np.random.default_rng(0).integers(0, 255, (10, 10, 3), dtype=np.uint8)


def canvas_with_template_at(x, y, width=100, height=50):
    pixels = np.full((height, width, 3), 20, dtype=np.uint8)
    pixels[y:y + 10, x:x + 10] = TEMPLATE
    return pixels


def run_with_template(user_db, screen, **template_kw):
    template = Template(anchor=CANVAS, pixels=TEMPLATE, **template_kw)
    save_lesson(user_db, lesson("open-bin", "Brush", template=template))
    desktop = FakeDesktop(controls=[pane("Canvas", 0, 0, 100, 50)], captures={"Canvas": screen})
    return desktop, run_flow(FLOW, desktop=desktop, user_db=user_db)


def test_a_template_found_in_the_anchor_region_resolves_to_a_fraction_of_that_region(tmp_path):
    desktop, result = run_with_template(tmp_path / "user.db", canvas_with_template_at(30, 20))

    assert result.stopped is None
    assert ("click_at", "Canvas", 0.35, 0.5) in desktop.calls  # centre (35, 25) of a 100x50 region
    assert desktop.hits == [(35.0, 25.0)]


def test_a_template_miss_is_bounded_by_attempts_and_queues_a_template_no_match_doubt(tmp_path):
    user_db = tmp_path / "user.db"
    blank = np.full((50, 100, 3), 20, dtype=np.uint8)

    desktop, result = run_with_template(user_db, blank, max_attempts=2)

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["template_no_match"]
    assert [c for c in desktop.calls if c[0] == "capture"] == [("capture", "Canvas")] * 2
    assert not any(call[0] == "click_at" for call in desktop.calls)


def test_template_with_a_missing_region_anchor_stops_with_control_not_found(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-bin", "Brush", template=Template(anchor=CANVAS, pixels=TEMPLATE)))

    result = run_flow(FLOW, desktop=FakeDesktop(controls=[]), user_db=user_db)

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]


DESKTOP_PANE = Locator(role="pane", name="Desktop")


def drag_lesson(**kw):
    return lesson("open-bin", "Report.docx", action="drag", **kw)


def test_a_drag_locates_both_ends_with_the_ladder(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, drag_lesson(drag_to=Endpoint(
        locator=Locator(role="icon", name="Recycle Bin"),
        derived=Derived(anchor=DESKTOP_PANE, fx=0.9, fy=0.95))))
    desktop = FakeDesktop(controls=[button("Report.docx"), pane("Desktop", 0, 0, 1000, 500)])

    result = run_flow(FLOW, desktop=desktop, user_db=user_db)

    assert result.stopped is None
    assert ("drag", "Report.docx", None, "Desktop", (0.9, 0.95)) in desktop.calls


def test_a_drag_stops_with_a_doubt_when_its_destination_cannot_be_located(tmp_path):
    user_db = tmp_path / "user.db"
    save_lesson(user_db, drag_lesson(drag_to=Endpoint(locator=Locator(role="icon", name="Recycle Bin"))))
    desktop = FakeDesktop(controls=[button("Report.docx")])

    result = run_flow(FLOW, desktop=desktop, user_db=user_db)

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["control_not_found"]
    assert not any(call[0] == "drag" for call in desktop.calls)


def test_a_drag_lesson_without_a_destination_is_rejected_when_saved(tmp_path):
    with pytest.raises(ValueError, match="drag"):
        save_lesson(tmp_path / "user.db", drag_lesson())


def test_a_drag_destination_round_trips_through_the_lesson_store(tmp_path):
    user_db = tmp_path / "user.db"
    destination = Endpoint(locator=Locator(role="icon", name="Recycle Bin"),
                           derived=Derived(anchor=DESKTOP_PANE, fx=0.9, fy=0.95),
                           template=Template(anchor=CANVAS, pixels=TEMPLATE, min_score=0.9, max_attempts=2))
    save_lesson(user_db, drag_lesson(drag_to=destination))

    stored = find_lesson(user_db, None, "paint.exe", "open-bin").drag_to

    assert stored == destination and np.array_equal(stored.template.pixels, TEMPLATE)


@pytest.mark.parametrize("fx, fy", [(120, 0.5), (0.5, -1), (1.5, 0.5)])
def test_a_derived_point_outside_the_anchor_is_rejected_so_it_can_never_act_as_an_absolute_coordinate(
        tmp_path, fx, fy):
    with pytest.raises(ValueError, match="fraction"):
        save_lesson(tmp_path / "user.db", lesson("open-bin", "X", derived=Derived(anchor=BIN, fx=fx, fy=fy)))


def test_a_flat_template_is_rejected_because_it_would_match_any_similar_area():
    with pytest.raises(ValueError, match="flat"):
        Template(anchor=CANVAS, pixels=np.zeros((10, 10, 3), dtype=np.uint8))


@pytest.mark.parametrize("kw", [{"min_score": -1.0}, {"min_score": 1.5}, {"max_attempts": 0}])
def test_template_limits_must_make_sense(kw):
    with pytest.raises(ValueError):
        Template(anchor=CANVAS, pixels=TEMPLATE, **kw)


def test_colour_matters_two_patches_with_the_same_brightness_are_not_a_match(tmp_path):
    red = np.zeros((10, 10, 3), dtype=np.uint8)
    red[..., 0] = 90
    red[::2, ::2] = (200, 0, 0)  # some texture so it is not flat
    green = red[..., [1, 0, 2]]  # channels swapped: same grey level, different colour
    screen = np.full((50, 100, 3), 20, dtype=np.uint8)
    screen[20:30, 30:40] = green
    user_db = tmp_path / "user.db"
    save_lesson(user_db, lesson("open-bin", "Brush", template=Template(anchor=CANVAS, pixels=red)))
    desktop = FakeDesktop(controls=[pane("Canvas", 0, 0, 100, 50)], captures={"Canvas": screen})

    result = run_flow(FLOW, desktop=desktop, user_db=user_db)

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["template_no_match"]


def test_a_template_that_appears_twice_is_ambiguous_and_queues_a_doubt_instead_of_guessing(tmp_path):
    screen = canvas_with_template_at(10, 5)
    screen[30:40, 70:80] = TEMPLATE  # the same icon a second time
    user_db = tmp_path / "user.db"

    desktop, result = run_with_template(user_db, screen)

    assert result.stopped == "n1"
    assert [d.reason for d in list_doubts(user_db)] == ["template_no_match"]
    assert not any(call[0] == "click_at" for call in desktop.calls)


# --- template search on a full screen (research ticket 21: the row scan took 34 s at 1920x1080) -----------

def big_region(template, at, width=1920, height=1080):
    rng = np.random.default_rng(11)
    pixels = np.full((height, width, 3), 235, dtype=np.uint8)
    pixels += rng.integers(0, 4, pixels.shape, dtype=np.uint8)  # a lightly noisy flat screen
    x, y = at
    pixels[y:y + template.shape[0], x:x + template.shape[1]] = template
    return pixels


ICON = np.random.default_rng(3).integers(0, 255, (32, 32, 3), dtype=np.uint8)


def test_a_template_is_found_in_a_full_hd_region_in_seconds_not_half_a_minute():
    import time

    from workflow_factory.ladder import match_template

    region = big_region(ICON, (1233, 567))
    started = time.perf_counter()

    point = match_template(region, ICON, 0.95)

    assert time.perf_counter() - started < 10.0  # generous on purpose: it was 34 s with the row scan, now ~0.2 s
    assert point == ((1233 + 16) / 1920, (567 + 16) / 1080)


@pytest.mark.parametrize("at", [(0, 0), (1888, 1048), (5, 1040), (1000, 3)], ids=["top-left", "bottom-right", "bottom", "top"])
def test_a_template_at_the_edges_of_a_large_region_is_still_found_exactly(at):
    from workflow_factory.ladder import match_template

    point = match_template(big_region(ICON, at), ICON, 0.95)

    assert point == ((at[0] + 16) / 1920, (at[1] + 16) / 1080)


def test_two_copies_far_apart_on_a_large_region_are_ambiguous_not_a_guess():
    from workflow_factory.ladder import match_template

    region = big_region(ICON, (300, 200))
    region[800:832, 1500:1532] = ICON

    assert match_template(region, ICON, 0.95) is None


def test_a_template_that_is_not_on_a_large_region_is_not_found():
    from workflow_factory.ladder import match_template

    assert match_template(big_region(ICON, (300, 200)), 255 - ICON, 0.95) is None


# --- edge cases of the fast template search (review of ticket 21) ------------------------------------------

@pytest.mark.parametrize("at", [(1233, 567), (1234, 568), (1235, 569), (1237, 570)], ids=lambda a: f"offset-{a[0] % 4}-{a[1] % 4}")
def test_a_template_off_the_coarse_grid_is_found_whatever_its_offset(at):
    from workflow_factory.ladder import match_template

    assert match_template(big_region(ICON, at), ICON, 0.95) == ((at[0] + 16) / 1920, (at[1] + 16) / 1080)


def test_a_match_flush_against_the_edge_of_a_region_whose_size_is_not_a_multiple_of_four_is_found():
    from workflow_factory.ladder import match_template

    width, height = 1917, 1079
    at = (width - 32, height - 32)

    assert match_template(big_region(ICON, at, width, height), ICON, 0.95) == ((at[0] + 16) / width, (at[1] + 16) / height)


def test_a_template_made_of_thin_lines_is_found_among_look_alike_decoys():
    from workflow_factory.ladder import match_template

    def lines(period):
        patch = np.full((24, 24, 3), 255, dtype=np.uint8)
        patch[:, ::period] = 0  # 1 px vertical lines with this spacing
        patch[4::7, :] = (200, 0, 0)  # and 1 px red rules
        return patch

    region = big_region(lines(6), (900, 400))
    # decoys use another spacing: a shifted copy of the same periodic pattern would BE the template
    for period, spot in zip([5, 7, 8, 9], [(100, 100), (500, 700), (1500, 200), (1700, 900)], strict=True):
        region[spot[1]:spot[1] + 24, spot[0]:spot[0] + 24] = lines(period)

    assert match_template(region, lines(6), 0.95) == ((900 + 12) / 1920, (400 + 12) / 1080)


def test_a_periodic_pattern_that_repeats_with_the_same_spacing_is_ambiguous():
    from workflow_factory.ladder import match_template

    def lines():
        patch = np.full((24, 24, 3), 255, dtype=np.uint8)
        patch[:, ::6] = 0
        return patch

    region = big_region(lines(), (900, 400))
    region[100:124, 101:125] = lines()  # the same pattern, one pixel over: indistinguishable

    assert match_template(region, lines(), 0.95) is None


def test_many_identical_look_alikes_are_ambiguous_not_a_lucky_pick():
    from workflow_factory.ladder import match_template

    region = big_region(ICON, (50, 50))
    for column in range(1, 11):  # eleven identical icons: more than the candidates that get refined
        region[50:82, 50 + column * 150: 82 + column * 150] = ICON

    assert match_template(region, ICON, 0.95) is None


@pytest.mark.parametrize("width, height", [(500, 299), (500, 301)], ids=["just-below-the-coarse-switch", "just-above-it"])
def test_both_sides_of_the_coarse_search_threshold_find_the_template(width, height):
    from workflow_factory.ladder import match_template

    assert match_template(big_region(ICON, (203, 117), width, height), ICON, 0.95) == ((203 + 16) / width, (117 + 16) / height)


@pytest.mark.parametrize("size", [15, 16, 17])
def test_templates_either_side_of_the_coarse_size_guard_are_found(size):
    from workflow_factory.ladder import match_template

    icon = np.random.default_rng(size).integers(0, 255, (size, size, 3), dtype=np.uint8)

    assert match_template(big_region(icon, (777, 333)), icon, 0.95) == ((777 + size / 2) / 1920, (333 + size / 2) / 1080)


def test_a_region_barely_bigger_than_the_template_has_just_one_place_to_look():
    from workflow_factory.ladder import match_template

    assert match_template(big_region(ICON, (1, 1), 33, 33), ICON, 0.95) == ((1 + 16) / 33, (1 + 16) / 33)


@pytest.mark.parametrize("region, template", [
    (np.zeros((50, 50), dtype=np.uint8), np.zeros((5, 5), dtype=np.uint8)),
    (np.zeros((50, 50, 3), dtype=np.uint8), np.zeros((5, 5, 4), dtype=np.uint8)),
    (np.zeros((50, 50, 3), dtype=np.uint16), np.zeros((5, 5, 3), dtype=np.uint16)),
], ids=["grayscale", "channels differ", "not 8 bit"])
def test_a_region_and_template_that_are_not_8_bit_colour_images_of_the_same_kind_are_refused(region, template):
    from workflow_factory.ladder import match_template

    with pytest.raises(ValueError, match="8-bit"):
        match_template(region, template, 0.95)


def test_a_large_template_does_not_need_hundreds_of_megabytes_to_be_refined():
    import tracemalloc

    from workflow_factory.ladder import match_template

    template = np.random.default_rng(9).integers(0, 255, (400, 400, 3), dtype=np.uint8)
    region = big_region(template, (700, 300))
    tracemalloc.start()
    point = match_template(region, template, 0.95)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert point == ((700 + 200) / 1920, (300 + 200) / 1080)
    assert peak < 250 * 1024 * 1024  # refining one row of positions at a time, not every position at once
