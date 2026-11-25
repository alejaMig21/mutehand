"""Locator ladder: accessibility identity, then derived geometry, then bounded template search.

Absolute screen coordinates never appear here: a point is always a fraction of an anchor
control found by accessibility, and only the adapter turns it into pixels. A lesson says
which rungs it has; a rung it lacks is never improvised, the flow stops and queues a doubt.
"""

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from workflow_factory.desktop import Control, Desktop
from workflow_factory.lessons import Endpoint, Locator, Template


@dataclass(frozen=True)
class Target:
    control: Control
    point: tuple[float, float] | None = None  # fractions (0..1) of the control, None = its centre


def _find(desktop: Desktop, locator: Locator) -> Control | None:
    return desktop.find(locator.role, locator.name, locator.automation_id)


def match_template(region: np.ndarray, template: np.ndarray, min_score: float):
    """The one match of the template in the region as (fx, fy) of its centre, else None.

    Colour counts (per-channel difference). Two separate places that both score at or above
    min_score are ambiguous, so nothing is returned rather than guessing.

    ponytail: mean absolute difference scanned row by row; slow on big regions and sensitive to
    theme, scale and occlusion. Research ticket 21 decides the faster method.
    """
    height, width = template.shape[:2]
    if height > region.shape[0] or width > region.shape[1]:
        return None
    windows = sliding_window_view(region, template.shape)[:, :, 0]  # (rows, cols, h, w, channels)
    scores = np.stack([
        1 - np.abs(windows[row].astype(np.int16) - template).mean(axis=(1, 2, 3)) / 255
        for row in range(windows.shape[0])
    ])
    y, x = np.unravel_index(scores.argmax(), scores.shape)
    if scores[y, x] < min_score:
        return None
    rest = scores.copy()
    rest[max(0, y - height + 1):y + height, max(0, x - width + 1):x + width] = 0  # the same spot
    if rest.max() >= min_score:
        return None
    return (x + width / 2) / region.shape[1], (y + height / 2) / region.shape[0]


def _by_template(template: Template, desktop: Desktop) -> tuple[Target | None, str | None]:
    anchor = _find(desktop, template.anchor)
    if anchor is None:
        return None, "control_not_found"
    for _ in range(template.max_attempts):  # bounded: region is the anchor, attempts are capped
        point = match_template(desktop.capture(anchor), template.pixels, template.min_score)
        if point:
            return Target(anchor, point), None
    return None, "template_no_match"


def locate(endpoint: Endpoint, desktop: Desktop) -> tuple[Target | None, str | None]:
    """The target for this endpoint, or the detailed reason no rung produced one."""
    control = _find(desktop, endpoint.locator)
    if control is not None:
        return Target(control), None
    if endpoint.derived:
        anchor = _find(desktop, endpoint.derived.anchor)
        if anchor is not None:
            return Target(anchor, (endpoint.derived.fx, endpoint.derived.fy)), None
    if endpoint.template:
        return _by_template(endpoint.template, desktop)
    return None, "control_not_found"
