# 03: App display names

Spec: `../spec.md`. Mockups: `../mockups/`.

**What to build:** Apps are called by the product name their executable declares, recorded when seen, never by a file name. No rule or table names a particular app. (Spec story 60.)

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] No screen shows an extension such as .exe
- [ ] An app whose executable declares no name shows its file name without the extension, capitalised
- [ ] The name is recorded when the app is seen and used when the app is closed
- [ ] Tests use invented app names; nothing in the source branches on one app
- [ ] Behaviour is proven by browser tests against the real API with the stand-in desktop and scheduler, red before green
- [ ] Everything added works from the keyboard and fits a 683 px and a 390 px wide window; button text stays readable
- [ ] Existing tests pass; no screen content of a private app appears in any message
