# 05: Frame and relevance mask

**What to build:** A frame record (app and version, window state and size, resolution, scale, language, theme) is captured with every lesson, with per-field tolerance and a per-lesson relevance mask. A lesson replays only when the current frame is within tolerance on the masked fields; otherwise it does not run.

**Blocked by:** 03

**Status:** resolved

- [x] A lesson replays when the current frame matches within tolerance on the masked fields
- [x] A change in a masked field (for example scale) prevents replay; a change in an unmasked field does not
- [x] Distance between frames uses a numeric vector view; canvas captures are stored as pixel arrays
- [x] Out-of-frame outcome is observable through the public entry point
