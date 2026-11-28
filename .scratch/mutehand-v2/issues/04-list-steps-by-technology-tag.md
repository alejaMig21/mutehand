# 04: The tutor lists steps by technology, tag or text

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** `list_known_steps` takes an optional technology and an optional tag or query and returns each step's name, action, tags, technologies and state. One search function matches a query against names and tags, ignoring capitals and accents and matching word beginnings; the node panel will use the same rule. A private technology's steps are counted, never named. Universal steps match only on name or pattern tags. (Spec stories 34, 35, 40.)

**Blocked by:** 03

**Status:** resolved

- [x] Listing by technology, by tag and by text each return the expected steps; a query "sav" finds "Save"; accents and capitals are ignored
- [x] A step known on several technologies appears once with all of them
- [x] A private technology contributes counts and no names or tags
- [x] The same search rule is exposed to the HTTP API's step listing so the panel can use it
- [x] Behaviour is proven by MCP and API tests, red before green

## Answer

`list_known_steps(technology, tag, query)` returns one entry per step name with tags, technologies and state, with one shared search rule (a Python rule and a web port tested with the same vectors); a private technology is counted, never named. `GET /api/steps` takes `q` and `tech`. Later review fix: the step list shows no control name of a private technology.
Commits: 3a19b7f, 92d4465.
