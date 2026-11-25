"""Research ticket 21: how fast and how robust is template search at 1920x1080?

Run with the project environment for numpy (and the current ladder.match_template):
    uv run python scripts/bench_template_search.py
Run again with any Python that has opencv-python-headless for the OpenCV numbers:
    <python-with-cv2> scripts/bench_template_search.py
Nothing here touches the screen: frames are synthetic arrays.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))  # the shipped matcher is timed even from an environment without the project installed
import time

import numpy as np

RNG = np.random.default_rng(0)
TEMPLATE_SIZE = 32
SIZES = [(400, 300), (800, 600), (1920, 1080)]  # width, height of the searched region


def make_frame(width, height):
    """UI-like background: flat panels plus mild noise."""
    base = np.full((height, width, 3), 235, dtype=np.int16)
    base[:, : width // 5] = 245
    base += RNG.integers(-3, 4, base.shape, dtype=np.int16)
    return np.clip(base, 0, 255).astype(np.uint8)


def make_template():
    """A small icon-like patch with real structure (not flat)."""
    patch = RNG.integers(0, 255, (TEMPLATE_SIZE, TEMPLATE_SIZE, 3), dtype=np.uint8)
    patch[8:24, 8:24] = (30, 90, 200)
    return patch


def plant(frame, template, x, y):
    out = frame.copy()
    out[y : y + TEMPLATE_SIZE, x : x + TEMPLATE_SIZE] = template
    return out


# ------------------------------------------------------------------ the methods

def fft_ssd(region, template):
    """numpy only: sum of squared differences for every position, through FFTs and integral images."""
    height, width, channels = region.shape
    th, tw = template.shape[:2]
    region_f, template_f = region.astype(np.float64), template.astype(np.float64)
    correlation = np.zeros((height - th + 1, width - tw + 1))
    for c in range(channels):
        spectrum = np.fft.rfft2(region_f[:, :, c]) * np.conj(np.fft.rfft2(template_f[:, :, c], s=(height, width)))
        correlation += np.fft.irfft2(spectrum, s=(height, width))[: height - th + 1, : width - tw + 1]
    squares = (region_f ** 2).sum(axis=2)
    integral = np.zeros((height + 1, width + 1))
    integral[1:, 1:] = squares.cumsum(axis=0).cumsum(axis=1)
    window = (integral[th:, tw:] - integral[:-th, tw:] - integral[th:, :-tw] + integral[:-th, :-tw])
    ssd = window - 2 * correlation + (template_f ** 2).sum()
    y, x = np.unravel_index(ssd.argmin(), ssd.shape)
    score = 1 - np.sqrt(max(ssd[y, x], 0) / template.size) / 255
    return (int(x), int(y)), float(score)


def coarse_to_fine(region, template, factor=4):
    """numpy only: search a 1/4 size copy with FFTs, then refine around the candidate at full size."""
    small = region[::factor, ::factor]
    small_template = template[::factor, ::factor]
    (sx, sy), _ = fft_ssd(small, small_template)
    cx, cy = sx * factor, sy * factor
    pad = 2 * factor
    x0, y0 = max(0, cx - pad), max(0, cy - pad)
    x1 = min(region.shape[1], cx + template.shape[1] + pad)
    y1 = min(region.shape[0], cy + template.shape[0] + pad)
    (rx, ry), score = fft_ssd(region[y0:y1, x0:x1], template)
    return (x0 + rx, y0 + ry), score


def current_mad(region, template):
    from workflow_factory.ladder import match_template

    point = match_template(region, template, 0.75)  # above what a flat background scores (~0.6), or everything is "ambiguous"
    if point is None:
        return None, 0.0
    th, tw = template.shape[:2]
    x, y = round(point[0] * region.shape[1] - tw / 2), round(point[1] * region.shape[0] - th / 2)
    found = region[y: y + th, x: x + tw].astype(np.int16)
    return (x, y), float(1 - np.abs(found - template.astype(np.int16)).mean() / 255)


def opencv_sqdiff(region, template):
    import cv2

    result = cv2.matchTemplate(region, template, cv2.TM_SQDIFF)
    _, _, location, _ = cv2.minMaxLoc(result)
    return location, 1.0


def opencv_ccoeff(region, template):
    import cv2

    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    return location, float(score)


def available_methods():
    methods = {"prototype fft_ssd": fft_ssd, "prototype coarse_to_fine": coarse_to_fine}  # pre-ship forks, kept for comparison
    try:
        from workflow_factory.ladder import match_template  # noqa: F401

        methods["shipped ladder.match_template"] = current_mad
    except Exception:  # noqa: BLE001 - running outside the project environment
        pass
    try:
        import cv2  # noqa: F401

        methods["opencv TM_SQDIFF"] = opencv_sqdiff
        methods["opencv TM_CCOEFF_NORMED"] = opencv_ccoeff
    except Exception:  # noqa: BLE001
        pass
    return methods


# ------------------------------------------------------------------ the experiments

def timing(methods, budget_seconds=60):
    """Prints a Markdown table; paste it into the research note as is, never retype a figure."""
    print("\n## Time per search (seconds, best of 3; a method whose first run exceeds the budget is timed once)")
    print("| method | " + " | ".join(f"{w}x{h}" for w, h in SIZES) + " |")
    print("|---|" + "---|" * len(SIZES))
    template = make_template()
    results = {}
    for name, method in methods.items():
        row = []
        for width, height in SIZES:
            region = plant(make_frame(width, height), template, width // 2, height // 2)
            started = time.perf_counter()
            method(region, template)
            best = time.perf_counter() - started
            if best <= budget_seconds:
                for _ in range(2):
                    started = time.perf_counter()
                    method(region, template)
                    best = min(best, time.perf_counter() - started)
            row.append(best)
        results[name] = row
        print(f"| {name} | " + " | ".join(f"{v:.3f}" for v in row) + " |")
    shipped = results.get("shipped ladder.match_template")
    opencv = [v for k, v in results.items() if k.startswith("opencv")]
    if shipped and opencv:  # the ratio the verdict quotes, computed here so a note cannot misquote it
        best_cv = [min(column) for column in zip(*opencv)]
        print("\nshipped / fastest OpenCV: " + ", ".join(f"{w}x{h} {a / b:.2f}x" for (w, h), a, b in zip(SIZES, shipped, best_cv)))


DEFAULT_MIN_SCORE = 0.95  # the default threshold of the ladder; `weak` = right place, score below it, so the ladder would reject it


def robustness(methods):
    print("\n## Does it find the template? (1920x1080 frame, template planted at (1234, 567))")
    width, height, at = 1920, 1080, (1234, 567)
    template = make_template()
    clean = plant(make_frame(width, height), template, *at)

    def brighter(image):
        return np.clip(image.astype(np.int16) + 30, 0, 255).astype(np.uint8)

    def inverted(image):
        return 255 - image

    def scaled(image, factor=1.25):
        ys = (np.arange(int(height * factor)) / factor).astype(int)
        xs = (np.arange(int(width * factor)) / factor).astype(int)
        return image[ys][:, xs][:height, :width]

    def occluded(image):
        out = image.copy()
        out[at[1] : at[1] + TEMPLATE_SIZE, at[0] : at[0] + 12] = 128  # 37% of the template covered
        return out

    def noisy(image):
        return np.clip(image.astype(np.int16) + RNG.normal(0, 8, image.shape), 0, 255).astype(np.uint8)

    # Where the template should be reported: a scaled frame moves it (the template itself stays at 100 %).
    scaled_at = (int(at[0] * 1.25), int(at[1] * 1.25))
    scenarios = {"exact": (clean, at), "brighter +30": (brighter(clean), at), "inverted theme": (inverted(clean), at),
                 "scaled 125%": (scaled(clean), scaled_at), "37% occluded": (occluded(clean), at),
                 "noise sigma 8": (noisy(clean), at)}
    print("| scenario | " + " | ".join(methods) + " |")
    print("|---|" + "---|" * len(methods))
    for scenario, (image, expected) in scenarios.items():
        cells = []
        for name, method in methods.items():
            location, score = method(image, template)
            right_place = location is not None and abs(location[0] - expected[0]) <= 3 and abs(location[1] - expected[1]) <= 3
            verdict = "found" if right_place and score >= DEFAULT_MIN_SCORE else "weak" if right_place else "missed"
            cells.append(f"{verdict} {score:.2f}")
        print(f"| {scenario} | " + " | ".join(cells) + " |")

if __name__ == "__main__":
    chosen = available_methods()
    print(f"python {sys.version.split()[0]}, numpy {np.__version__}; methods: {', '.join(chosen)}")
    timing(chosen)
    robustness(chosen)
