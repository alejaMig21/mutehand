# Research 21: template search speed at 1920x1080

Date: 2026-11-25. Question: how fast and how robust is bounded template search on a full-screen
capture, with only numeric arrays versus an image library, and which one to adopt for the
locator ladder's third rung?

## Method

`scripts/bench_template_search.py` (synthetic frames, nothing touches the screen). Best of 3 runs on
this PC (Python 3.14, numpy 2.5.5). OpenCV 5.1 was installed only in a throw-away environment
outside the repo to compare.

```text
uv run python scripts/bench_template_search.py            # numpy and the shipped code
<python-with-opencv-headless> scripts/bench_template_search.py   # adds OpenCV
```

## Results: time per search (seconds)

| method | 400x300 | 800x600 | 1920x1080 |
|---|---|---|---|
| **row scan** (the first implementation) | 1.66 | 7.64 | **34.3** |
| numpy FFT, every position | 0.03 | 0.10 | 0.6 |
| numpy coarse-to-fine (4x smaller copy, then refine) | 0.003 | 0.008 | 0.03 |
| **shipped `ladder.match_template`** (coarse-to-fine + exact refinement + ambiguity check) | 0.03 | 0.05 | 0.13-0.18 |
| OpenCV `TM_SQDIFF` | 0.009 | 0.022 | 0.08 |
| OpenCV `TM_CCOEFF_NORMED` | 0.008 | 0.025 | 0.10 |

## Results: does it find the template? (1920x1080, 32x32 template planted at (1234, 567))

Score is 1 - mean absolute difference / 255 at the reported spot (OpenCV `TM_SQDIFF` has no such score:
the script prints a constant 1.00 for it, so ignore that number; `TM_CCOEFF_NORMED` is its own scale).
A frame scaled to 125 % moves the template to about (1542, 708); the check accepts that spot.

| scenario | shipped `match_template` score | OpenCV SQDIFF | OpenCV CCOEFF_NORMED |
|---|---|---|---|
| exact | 1.00, found | found | found |
| brightness +30 | 0.89 | found | found |
| inverted theme | 0.00, missed | missed | missed |
| scaled 125% | 0.76 at best, missed | missed | missed |
| 37% of the template covered | 0.90 | found | found (0.78) |
| noise sigma 8 | 0.98, found | found | found |

## Verdict

- **Adopt numpy; do not add OpenCV.** The shipped search takes 0.13-0.18 s at full HD against
  0.08-0.10 s for OpenCV: about 2x slower, a gap that does not matter because a template search runs
  once per ladder attempt, inside one anchor's region. It needs no 45 MB dependency. The comparison is
  rough: the shipped code also refines each candidate exactly and checks ambiguity, OpenCV only returns
  its best position; one 32x32 template, one frame.
- **The first implementation was a real defect**: scanning every position took 34 s at 1920x1080
  (1.7 s at 400x300). It was replaced in this ticket. The ladder keeps searching only inside an
  anchor's area, never the whole screen.
- **Sensitivity.** Noise is harmless. A brighter or darker theme (+30 levels) scores 0.89 and partial
  occlusion (37 %) scores about 0.90: both are **below the default `min_score` of 0.95, so they are
  rejected unless a lesson lowers the threshold** (a flat background already scores about 0.6, so keep
  it well above that). An inverted theme and a 125 % scale score 0.00 and 0.76: never a match. That is
  why a lesson stores its frame (scale, theme) and replays only inside it.
- **Ambiguity** (the same icon twice) is kept as "no match": two separate places that both score at or
  above the threshold return nothing instead of guessing.
- **Known limits, covered by tests**: candidates come from a 4x smaller copy, so templates under 16 px
  are searched at full size; more than 6 identical look-alikes are reported ambiguous; inputs must be
  8-bit colour images with equal channels (otherwise `ValueError`); the exact refinement runs one row of
  positions at a time so memory stays small for big templates.

## Impact on the project

`ladder.match_template` now finds candidates with FFTs on a 4x smaller copy (regions above 150 000
pixels), scores each candidate exactly at full size, and keeps the earlier contract (colour counts,
ambiguity is a doubt). Tests: `tests/test_ladder.py` (full HD under 10 s, any offset to the coarse grid, flush to the edges,
thin lines among decoys, look-alikes, both sides of the size guards, invalid inputs, memory).
