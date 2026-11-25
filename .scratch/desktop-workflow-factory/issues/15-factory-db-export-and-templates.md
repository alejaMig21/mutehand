# 15: Factory database, export/import and templates

**What to build:** A build step produces the read-only factory database with pre-taught lessons and template flows. Users can duplicate a template into their own layer, and export or import flows and lessons as JSON for review and git. A product update replaces only the factory file.

**Blocked by:** 03, 10

**Status:** resolved

- [x] Replacing the factory file leaves the user database untouched
- [x] Duplicating a template creates an editable copy in the user layer
- [x] Export then import round-trips lessons and flows unchanged
- [x] Exported JSON never contains secret values
