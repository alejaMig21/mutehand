# 22: Research: desktop icons and Recycle Bin via accessibility

**Type:** research

**What to find out:** Whether the Recycle Bin and desktop icons are reachable by accessibility, so the "drag a file to the Recycle Bin" case can use the ladder's first or second rung.

**Blocked by:** 02

**Status:** resolved

- [x] Result recorded for the explorer shell window and desktop icons
- [x] If not reachable, which rung the drag target needs

## Answer

See `docs/research/22-desktop-icons-and-recycle-bin.md`. Desktop icons and the desktop Recycle Bin are NOT reachable by accessibility (UI Automation shows the icon list as one empty pane; agent-desktop has no desktop surface on Windows): they need rung 3 (template search). The Recycle Bin WINDOW is reachable at rung 1 (53 refs); Delete-key and drop-on-window are candidates, not run here (they need real focus or a real drag).
