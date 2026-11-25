---
status: accepted
---

# Actions never use absolute screen coordinates; a failed rung becomes a doubt

Every action endpoint is found through the locator ladder: accessibility identity, then geometry derived from a re-located element or window, then bounded template search with a stored template. Absolute coordinates were rejected because targets such as desktop icons and canvases move. When a rung fails the apprentice stops and queues a doubt instead of silently falling to the next rung, so unexpected states are reviewed by the tutor.

## Consequences

Template matching is done by our own code on a screenshot and is sensitive to theme, scale and occlusion. Its speed at 1920x1080 is not yet measured.
