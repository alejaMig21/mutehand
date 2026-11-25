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

| scenario | numpy (all) | OpenCV SQDIFF | OpenCV CCOEFF_NORMED |
|---|---|---|---|
| exact | found | found | found |
| brightness +30 | found (score 0.89) | found | found |
| inverted theme | missed | missed | missed |
| scaled 125% | missed | missed | missed |
| 37% of the template covered | found (0.82-0.90) | found | found (0.78) |
| noise sigma 8 | found (0.97) | found | found |

## Verdict

- **Adopt numpy; do not add OpenCV.** The shipped numpy search is within 2x of OpenCV at full HD
  (0.13-0.18 s against 0.08-0.10 s) and needs no 45 MB dependency. The gap does not matter: a
  template search runs once per ladder rung attempt, bounded to one anchor's region and three attempts.
- **The first implementation was a real defect**: scanning every position took 34 s at 1920x1080
  (1.7 s at 400x300). It was replaced in this ticket. Region size is the main cost, so the ladder
  keeps searching only inside an anchor's area, never the whole screen.
- **Sensitivity** (the same for every method tried): a template matches through noise, a lighter or
  darker theme of up to about +30 levels, and a partly covered target. It does **not** match when the
  theme is inverted or the display scale changes. That is why a lesson stores its frame (scale,
  theme) and replays only inside it, and why `min_score` should stay high (default 0.95; a flat
  background already scores about 0.6, so any threshold near that makes every position look ambiguous).
- Ambiguity (the same icon twice) is kept as "no match": two separate places that both score at or
  above the threshold return nothing instead of guessing.

## Impact on the project

`ladder.match_template` now finds candidates with FFTs on a 4x smaller copy (regions above 150 000
pixels), scores each candidate exactly at full size, and keeps the earlier contract (colour counts,
ambiguity is a doubt). Tests: `tests/test_ladder.py` (full HD under 3 s, edges of a large region,
two copies far apart, template absent).
