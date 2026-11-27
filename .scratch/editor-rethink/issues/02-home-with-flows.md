# 02: Home with my flows

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** A new Home sits beside the old screens and lists the person's flows with app, last result and time, "Run now" and "Stop". "New chore" and a flow's row open the flow screen, which leads back to Home. Mockup B, flow list. (Spec stories 4, 15-18, 49, 50.)

**Blocked by:** 01

**Status:** resolved

- [ ] Home is the first screen shown; the old screens stay reachable
- [ ] Each flow shows its title, app, last result and when, or "Never run"
- [ ] "Run now" runs it and reports the result on the row; while running the row offers "Stop"
- [ ] A flow that cannot run says so on its button and why
- [ ] A run stays followed across reload, screen change and a lost request
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message

## Answer

Home lists flows with app, last result and time, "Run now" and "Stop", blocked-flow reasons, runs followed across reload and lost requests.
Commits: 0b49293, 7ef763e, 80babe7, fb676b5.
