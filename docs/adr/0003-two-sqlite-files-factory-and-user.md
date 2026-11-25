---
status: accepted
---

# Knowledge lives in two SQLite files: factory (read-only) and user

Each build ships a read-only factory database with pre-taught lessons and template flows, and the user's own lessons, flows, consents, doubts and history live in a separate user database. Lookup goes user first, then factory. This lets end users skip teaching for common apps while a product update can never overwrite what they taught. JSON exists only for export, import and review in git.

## Considered Options

- One database with an origin column: rejected because an update could clobber user rows.
- YAML or JSON files as the primary store: rejected for type-coercion traps and weak querying.
