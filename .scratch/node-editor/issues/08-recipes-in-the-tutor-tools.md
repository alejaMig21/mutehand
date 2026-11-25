# 08: Recipes in the tutor tools

**What to build:** The tutor can save a recipe (ordered steps with holes), apply it to a new app by filling the holes with that app's controls, and mark a step as already known. The apprentice measures each filled hole and leaves a doubt on any that fails.

**Blocked by:** 02

**Status:** resolved

- [x] A recipe taught on one app is applied to a second fake app by teaching only the differing controls
- [x] A failing hole leaves a doubt that names the hole
- [x] The tutor tools and their documentation list the new calls

## Answer

`src/workflow_factory/recipes.py` plus four tutor tools. A recipe is an ordered list of holes; each hole holds the control the recipe was
first taught on (role, control_name, automation_id?, action, sensitive?).
- `save_recipe(name, holes)` / `list_recipes()`.
- `apply_recipe(app, recipe, fills?)` teaches one step per hole in order, named `<recipe>-<hole>`, measuring each. `fills` names only the
  holes whose control differs on this app; the others are tried on the recipe's own control. Steps the app already has are not repeated.
- A hole that fails (control not found, unreadable, secure field) leaves a doubt whose `node_id` is the hole, `flow_id` is `recipe:<name>`
  and `step` is `<recipe>-<hole>`; the recipe stops there and the later holes are `not_tried`. The tutor answers it with the existing
  `answer_doubt` and applies again: finished holes are `already_known`.
- A sensitive hole without consent returns `consent_required` (nothing acted, no doubt): ask the person, `record_consent`, apply again.
- `mark_step_known(app, recipe, hole, step)` binds a step the app already has to a hole without acting on the app.
- `teach_step` now also teaches a `read_value` step (it proves the control answers; nothing is clicked).
Bindings (`recipe_bindings`) are what the editor will use to expand a recipe into nodes (ticket 12).
Tests: `tests/test_recipes.py` (14) and one through the MCP tools; README lists the calls.
