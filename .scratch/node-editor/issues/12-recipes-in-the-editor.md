# 12: Recipes in the editor

**What to build:** The search panel lists recipes; dropping one expands it into connected nodes with its holes filled for the chosen app, and a step adapted from another app shows an adapted-from mark.

**Blocked by:** 08, 09

**Status:** resolved

- [x] Dropping a recipe adds its connected nodes
- [x] An adapted step shows where it came from
- [x] A recipe with an unfilled hole cannot run and says which

## Answer

- The search panel has a Recipes section (`GET /api/recipes`: each recipe with its holes, the app it was first applied to, and per app the step that
  fills each hole). Dropping one adds one connected node per hole, in order, on the steps that fill the holes for the app to run on (the "App" in the
  top bar). A node added while another is selected continues from it.
- A step applied to an app other than its recipe's first shows "Adapted from <app>" (`/api/steps` carries `adapted_from`, from `recipe_origin` and the
  bindings). On the original app nothing is marked.
- A hole nobody filled for the app (a failed or never-tried hole) gets the name its step will have and the card says "Hole not filled: <hole>".
  Run flow is off and the notice names every one: "the hole 'compose' of the recipe 'send-message'". More generally any step node with no step
  taught for the app (also after the app is changed, or a flow opened for another app) counts as not taught; the API refuses to start such a flow
  with the step named. Opening a stored flow picks the app that has most of its steps.
- What the editor knows about a step (trust, consent, adapted-from, not taught) is derived from the steps taught for the chosen app, not stored in the node.
Tests: `tests/test_recipes.py` (+2), `tests/test_api_runview.py` (+2), `web/src/catalog.test.js`, `web/src/safety.test.js`, 2 more browser tests.
