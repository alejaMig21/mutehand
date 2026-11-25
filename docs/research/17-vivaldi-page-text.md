# Research 17: reading Vivaldi page text, CDP versus accessibility

Date: 2026-11-25. Question: does launching Vivaldi with the CDP option give reliable page text where the
accessibility snapshot times out? Record the result and the exact commands.

## Method

The person's own Vivaldi (16 processes, already running) was **not touched**: it was never listed by
title, driven or attached to. I started a second Vivaldi 8.3 (Chrome 156) of my own with a throw-away
profile folder, on the secondary monitor, and loaded a local page served from loopback (`127.0.0.1`):
400 paragraphs with markers at the top, middle and bottom, plus a plain input; then a 5000-paragraph page.
Afterwards I stopped only the processes whose command line held my profile folder, removed the folder and
checked the ports were closed. My Vivaldi window was identified by pid, never by title.

Commands (profile folder and port are examples; the profile must NOT be the default one):

```text
vivaldi.exe --user-data-dir=<scratch>\vprofile --remote-debugging-port=9333 ^
  --remote-debugging-address=127.0.0.1 --no-first-run --no-default-browser-check ^
  --window-position=2000,80 --window-size=1200,800 --new-window http://127.0.0.1:8765/test.html
```

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:                       # no input, no focus change
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9333")
    page = next(pg for ctx in browser.contexts for pg in ctx.pages if "8765" in pg.url)
    text = page.evaluate("document.body.innerText")
```

```text
agent-desktop snapshot --window-id <w-id> --max-depth 30      # not -i, default depth is 10
```

## Results

| Route | 400-paragraph page | 5000-paragraph page |
|---|---|---|
| **CDP** `document.body.innerText` | 0.55 s, 29 031 chars, all 6 markers | 0.17 s, 372 817 chars, all markers, last line included |
| Accessibility, **default** (`-i`, depth 10, 3 s deadline) | 1.6-1.9 s, 73 nodes, **0 markers**: only the browser's own interface | not run |
| Accessibility, all elements, depth 10 | 1.7 s, 80 nodes, 0 markers | not run |
| Accessibility, all elements, **depth 30** | 1.7 s, 940 nodes, 32 k chars, **6/6 markers** | 1.8 s, 946 nodes, 32 k chars, **first and last marker only; line 2500 and line 5000 missing**, yet `complete: true` |
| Accessibility, depth 30, deadline 20 s or 60 s | same result, no slower | same result |
| Accessibility, depth 60 | `INVALID_ARGS`: maximum is 50 | |

- `--force-renderer-accessibility` is **not needed**: depth 30 worked without it and with it, identically.
- **No timeout happened** on these pages, with the default 3 s deadline or longer ones. What failed is
  *depth* and *size*, silently: the default snapshot returns a healthy-looking tree that holds none of the
  page, and a long page is cut at roughly 30 k characters while the tree says `complete: true`.

## Verdict

- **CDP is the reliable way to read page text**: complete, fast (0.2-0.6 s) and it needs no focus or input.
- Accessibility can read short pages **only** with the default overridden (all elements, `--max-depth`
  of 30 or more); it cannot be trusted for long pages, because it truncates without saying so.
- A node that reads page text through accessibility must verify an end marker (or compare the length with
  CDP) instead of trusting `complete`.
- **Costs of CDP:** Vivaldi must be started with the debugging port on a **separate profile**, so the
  person's logins, extensions and open tabs are not there; attaching to the person's running Vivaldi was
  **not tested** (it would mean touching their browser, and recent Chromium refuses the debugging port on
  the default profile). The port must stay on loopback and is a full remote control of that browser.

## Impact on the "Vivaldi to Word to Telegram" example flow

- The Vivaldi step should read through CDP with a dedicated profile for pages that need no login, or the
  person must sign in once inside that profile. Reading a page behind the person's own session needs
  a decision from them (profile copy or an extension), not a silent attach.
- The Word step is parked (research 18: Word is disabled on this PC); the Telegram step was not tested
  (private app, not touched).
- Whatever reads the text must put it where the next node can take it without the clipboard when possible
  (the run context), so the flow does not depend on overwriting the person's clipboard.
