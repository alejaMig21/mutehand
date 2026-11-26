# 08: Explanation strip under the canvas

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** Choosing a box explains it underneath: a sentence of what it does, how often it has worked, "Test this box", "Settings" when it has any, and "Remove box". Mockup F. (Spec stories 41-43, 45, 46.)

**Blocked by:** 07

**Status:** resolved

- [ ] The sentence is built from the node's kind, action, control and app, never from a typed value or secret
- [ ] Every node kind and action has a sentence; no rule depends on one app
- [ ] "Test this box" warns that it takes the mouse and keyboard before doing it
- [ ] "Settings" opens data in, settings and data out; a box with nothing to set has no such button
- [ ] No trust label such as "trusted" or "on trial" is shown
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message

## Answer

The chosen box is explained under the canvas in one strip: a sentence of what it does, how often it has worked, Test this box, Settings and Remove box; it replaces the old node panel.
Commits: a3356e4, 74672c6, 19de41a.
