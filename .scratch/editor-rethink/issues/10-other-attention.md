# 10: Other things that need the person

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** Home also shows actions to learn again grouped by app with the flows they block, rejected actions that block a flow with why and "Allow again", and required setup checks that fail. (Spec stories 5, 11-13.)

**Blocked by:** 09

**Status:** resolved

- [ ] An app update shows one card naming the app and the blocked flows, with the message to send
- [ ] A rejected step that blocks a flow says why, and "Allow again" lifts it
- [ ] A step that blocks no flow raises no card
- [ ] A missing required setup piece shows how to fix it; a working setup shows nothing
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message

## Answer

Home also lists apps to learn again with the chores they block, rejected actions that block a chore with "Allow again", and failed required setup checks with how to fix them.
Commits: 8d2cc3d.
