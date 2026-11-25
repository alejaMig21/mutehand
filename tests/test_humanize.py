import math
import random
from itertools import pairwise

from workflow_factory.humanize import MAX_STEP_PIXELS, STEP_DELAY_SECONDS, generate_bezier_curve, glide


def curve(seed=7, **kw):
    return generate_bezier_curve((10, 20), (900, 500), rng=random.Random(seed), **kw)


def test_the_curve_starts_and_ends_exactly_where_it_was_asked_to():
    path = curve()

    assert path[0] == (10, 20) and path[-1] == (900, 500)


def test_the_same_seed_gives_the_same_curve_and_another_seed_gives_another():
    assert curve(seed=1) == curve(seed=1)
    assert curve(seed=1) != curve(seed=2)


def test_the_curve_stays_inside_the_bounds_when_given_some():
    path = curve(bounds=(0, 0, 1000, 600))

    assert all(0 <= x <= 1000 and 0 <= y <= 600 for x, y in path)


def test_no_two_neighbouring_points_are_further_apart_than_max_step():
    path = curve(max_step=25)

    assert max(math.dist(a, b) for a, b in pairwise(path)) <= 25 + 2  # +2: integer rounding


def test_glide_walks_from_start_to_destination_in_small_steps_pausing_after_each():
    moved, pauses = [], []

    glide((0, 0), (300, 200), moved.append, rng=random.Random(3), sleep=pauses.append)

    assert moved[0] == (0, 0) and moved[-1] == (300, 200)
    assert max(math.dist(a, b) for a, b in pairwise(moved)) <= MAX_STEP_PIXELS + 2
    assert pauses == [STEP_DELAY_SECONDS] * len(moved)
