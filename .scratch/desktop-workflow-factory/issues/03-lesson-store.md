# 03: Lesson store with lookup order and app key

**What to build:** Lessons persist with precondition, action, measured effect, origin (factory or local) and status. The apprentice looks up lessons in the user database first, then the factory database. An app is identified by process name plus executable version; when the version changes its lessons become "to revalidate" and are kept.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A local lesson shadows a factory lesson for the same situation
- [ ] The factory database is opened read-only and is never written
- [ ] A version change marks that app's lessons to revalidate; nothing is deleted
- [ ] Lessons whose status is to revalidate are not replayed until re-measured
- [ ] Tests run through the public entry point with a fake desktop and temp SQLite files
