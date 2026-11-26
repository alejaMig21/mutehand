# 11: Apps screen

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** One row per app with its number of actions and a note only when something needs the person; opening it shows its actions, problems first, its permissions with "Take back", and the message to teach another. Search covers all apps. Mockup D. (Spec stories 52-59.)

**Blocked by:** 03, 10

**Status:** ready-for-agent

- [ ] With 25 apps the screen shows the first rows and "Show more"
- [ ] Search by words finds actions across apps
- [ ] An open app lists actions with problems first, each with its button
- [ ] "Take back" asks first, removes that consent only, and says what stops working
- [ ] Listing 900 steps stays under half a second
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
