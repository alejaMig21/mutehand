"""Human-looking mouse movement: a cubic Bezier path with random control points.

Ported from the predecessor project (hubstaff-automation, src/bezier.py); the pacing parameters
below are calibrated here. A seeded `random.Random` makes a path repeatable for tests.
"""

import math
import random
import time
from collections.abc import Callable
from itertools import pairwise

# Starting values, not yet tuned on a real session: a short hop should take ~0.1 s, a long one ~0.4 s.
STEP_DELAY_SECONDS = 0.006  # pause between cursor steps
MAX_STEP_PIXELS = 40  # no two neighbouring points further apart than this, so it never jumps


def generate_bezier_curve(
    start: tuple[int, int],
    destination: tuple[int, int],
    rng=random,
    bounds: tuple[int, int, int, int] | None = None,
    max_step: int | None = None,
) -> list[tuple[int, int]]:
    """Points (x, y) along a randomised Bezier curve from `start` to `destination`.

    `bounds` (left, top, right, bottom) clamps the control points, so the whole curve stays inside
    the box (a Bezier curve lies in the hull of its control points). `max_step` raises the point
    count so no two neighbours are further apart than it (pixels, plus rounding):
    |B'(t)| <= 3 * the longest leg of the control polygon, so steps >= 3 * leg / max_step is enough.
    """
    x0, y0 = start
    x3, y3 = destination

    distance = math.hypot(x3 - x0, y3 - y0)
    max_deviation = max(20, int(distance * 0.2))

    # control points off the straight line
    cx1 = x0 + (x3 - x0) * 0.25 + rng.randint(-max_deviation, max_deviation)
    cy1 = y0 + (y3 - y0) * 0.25 + rng.randint(-max_deviation, max_deviation)
    cx2 = x0 + (x3 - x0) * 0.75 + rng.randint(-max_deviation, max_deviation)
    cy2 = y0 + (y3 - y0) * 0.75 + rng.randint(-max_deviation, max_deviation)
    if bounds is not None:
        left, top, right, bottom = bounds
        cx1, cx2 = (min(max(v, left), right) for v in (cx1, cx2))
        cy1, cy2 = (min(max(v, top), bottom) for v in (cy1, cy2))

    steps = max(15, int(distance / 15))
    if max_step:
        legs = [(x0, y0), (cx1, cy1), (cx2, cy2), (x3, y3)]
        steps = max(steps, math.ceil(3 * max(math.dist(p, q) for p, q in pairwise(legs)) / max_step))
    points = []
    for i in range(steps + 1):
        t = i / steps
        xt = (1 - t) ** 3 * x0 + 3 * (1 - t) ** 2 * t * cx1 + 3 * (1 - t) * t ** 2 * cx2 + t ** 3 * x3
        yt = (1 - t) ** 3 * y0 + 3 * (1 - t) ** 2 * t * cy1 + 3 * (1 - t) * t ** 2 * cy2 + t ** 3 * y3
        points.append((int(xt), int(yt)))
    return points


def glide(
    start: tuple[int, int],
    destination: tuple[int, int],
    move: Callable[[tuple[int, int]], None],
    rng=random,
    sleep: Callable[[float], None] = time.sleep,
    bounds: tuple[int, int, int, int] | None = None,
) -> None:
    """Move the cursor from `start` to `destination` along a curve, pausing between steps."""
    for point in generate_bezier_curve(start, destination, rng=rng, bounds=bounds, max_step=MAX_STEP_PIXELS):
        move(point)
        sleep(STEP_DELAY_SECONDS)
