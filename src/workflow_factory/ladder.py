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


CANDIDATES = 6  # coarse positions that are refined at full size
COARSE_FACTOR = 4  # big regions are first searched on a copy this many times smaller
BIG_REGION_PIXELS = 150_000


def _pool(array: np.ndarray, factor: int) -> np.ndarray:
    """Average factor x factor blocks (a smaller copy that keeps the structure, unlike plain striding)."""
    height, width = array.shape[0] // factor * factor, array.shape[1] // factor * factor
    return array[:height, :width].astype(np.float64).reshape(height // factor, factor, width // factor, factor, -1).mean(axis=(1, 3))


def _squared_differences(region: np.ndarray, template: np.ndarray) -> np.ndarray:
    """Sum of squared differences of the template against every position, through FFTs (O(N log N))."""
    height, width = region.shape[:2]
    th, tw = template.shape[:2]
    region_f, template_f = region.astype(np.float64), template.astype(np.float64)
    correlation = np.zeros((height - th + 1, width - tw + 1))
    for channel in range(region.shape[2]):
        spectrum = np.fft.rfft2(region_f[:, :, channel]) * np.conj(
            np.fft.rfft2(template_f[:, :, channel], s=(height, width)))
        correlation += np.fft.irfft2(spectrum, s=(height, width))[: height - th + 1, : width - tw + 1]
    integral = np.zeros((height + 1, width + 1))
    integral[1:, 1:] = (region_f ** 2).sum(axis=2).cumsum(axis=0).cumsum(axis=1)
    window = integral[th:, tw:] - integral[:-th, tw:] - integral[th:, :-tw] + integral[:-th, :-tw]
    return window - 2 * correlation + (template_f ** 2).sum()


def _best_positions(squared: np.ndarray, count: int, size: tuple[int, int]) -> list[tuple[int, int]]:
    """The `count` best (x, y) positions, never two on top of each other."""
    squared, found = squared.copy(), []
    for _ in range(count):
        y, x = np.unravel_index(squared.argmin(), squared.shape)
        if not np.isfinite(squared[y, x]):
            break
        found.append((int(x), int(y)))
        squared[max(0, y - size[0] + 1): y + size[0], max(0, x - size[1] + 1): x + size[1]] = np.inf
    return found


def _refine(region: np.ndarray, template: np.ndarray, around: tuple[int, int], radius: int):
    """Exact score (1 - mean absolute difference / 255) at full size near a candidate: (score, x, y)."""
    th, tw = template.shape[:2]
    x0, y0 = max(0, around[0] - radius), max(0, around[1] - radius)
    x1, y1 = min(region.shape[1] - tw, around[0] + radius), min(region.shape[0] - th, around[1] + radius)
    template16 = template.astype(np.int16)
    best = (-1.0, x0, y0)
    for y in range(y0, y1 + 1):  # one row of positions at a time keeps memory small for big templates
        band = region[y: y + th, x0: x1 + tw].astype(np.int16)
        windows = sliding_window_view(band, template.shape)[0, :, 0]  # (positions, h, w, channels)
        scores = 1 - np.abs(windows - template16).mean(axis=(1, 2, 3)) / 255
        x = int(scores.argmax())
        if scores[x] > best[0]:
            best = (float(scores[x]), x0 + x, y)
    return best


def match_template(region: np.ndarray, template: np.ndarray, min_score: float):
    """The one match of the template in the region as (fx, fy) of its centre, else None.

    Colour counts (per-channel difference). Two separate places that both score at or above
    min_score are ambiguous, so nothing is returned rather than guessing.

    Candidates come from FFTs, on a 4x smaller copy for big regions; each candidate is then scored
    exactly at full size. Measured (scripts/bench_template_search.py, research ticket 21): 1920x1080
    in 0.13-0.18 s, where scanning every position took 34 s. Matching still depends on theme, scale
    and occlusion: an inverted theme or a 125% scale will not match.
    """
    for image in (region, template):
        if image.ndim != 3 or image.dtype != np.uint8:
            raise ValueError("the region and the template must be 8-bit colour images (height x width x channels)")
    if region.shape[2] != template.shape[2]:
        raise ValueError("the region and the template must be 8-bit colour images with the same channels")
    th, tw = template.shape[:2]
    if th > region.shape[0] or tw > region.shape[1]:
        return None
    big = region.shape[0] * region.shape[1] > BIG_REGION_PIXELS and min(th, tw) >= 4 * COARSE_FACTOR
    factor = COARSE_FACTOR if big else 1
    coarse_region, coarse_template = (_pool(region, factor), _pool(template, factor)) if big else (region, template)
    squared = _squared_differences(coarse_region, coarse_template)
    positions = _best_positions(squared, CANDIDATES, coarse_template.shape[:2])
    refined = sorted((_refine(region, template, (x * factor, y * factor), 2 * factor) for x, y in positions),
                     reverse=True)
    best_score, x, y = refined[0]
    if best_score < min_score:
        return None
    for score, other_x, other_y in refined[1:]:  # a second, separate place that matches as well: ambiguous
        if score >= min_score and (abs(other_x - x) >= tw or abs(other_y - y) >= th):
            return None
    return (x + tw / 2) / region.shape[1], (y + th / 2) / region.shape[0]


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
