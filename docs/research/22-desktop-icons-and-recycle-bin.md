# Research 22: desktop icons and the Recycle Bin through accessibility

Date: 2026-11-25. Question: can the desktop icons and the Recycle Bin be reached by accessibility, so a
"drag a file to the Recycle Bin" lesson can use the locator ladder's first or second rung?

## Method

Read-only probes on this PC (Windows 11 24H2, desktop icons visible, 39 icons on the desktop). Only
counts, roles and class names were read; no icon names, paths or file contents were recorded.
The one window opened was my own Recycle Bin window, placed on the secondary monitor without
activation and closed afterwards (no windows left open).

## Results

| Probe | Result |
|---|---|
| `agent-desktop snapshot --surface desktop` | `INVALID_ARGS`: "not available on this platform". Windows surfaces are only start-menu, taskbar, system-tray, system-tray-overflow, action-center. |
| `agent-desktop find --app explorer.exe --name "Recycle Bin"` | ok, 0 matches |
| `list-windows --app explorer.exe` | 2 windows, none is the desktop; the desktop is not in the window inventory |
| Win32: `Progman` > `SHELLDLL_DefView` > `SysListView32` | present and visible; `LVM_GETITEMCOUNT` = 39 |
| UI Automation on that `SysListView32` | a single `Pane` with **no children**; no element named "Recycle Bin" under `Progman`, `WorkerW` or the list |
| Own Recycle Bin window (`shell:RecycleBinFolder`), minimized at first | `list-windows` shows it as `minimized: true`; after a no-activation restore on the secondary monitor, `snapshot -i` gives 53 refs: 25 buttons, 7 menu buttons, 2 listboxes, 4 text fields, 1 tab list, 3 toolbars, 16 groups |

## Verdict

- **The desktop icons and the desktop Recycle Bin icon are not reachable by accessibility** (rung 1
  fails): the shell publishes the icon list as an empty pane, and agent-desktop has no desktop surface on
  Windows. Rung 2 (geometry derived from an anchor) can work only if the lesson's anchor is the icon
  list pane and the target is a stored fraction of it, but icons move when the user rearranges them.
  So a desktop icon is a **rung 3** target (bounded template search inside the icon list's region,
  now 0.13-0.18 s, see research 21), with a doubt when the template is absent or ambiguous.
- **The Recycle Bin window is fully reachable at rung 1**: its controls come back by role (measured).
  Two ways to get a file into the bin without the desktop icon are candidates; **neither was run here**
  (they need real keyboard focus or a real drag on the user's screen, which live tests must not take):
  1. select the file in its Explorer window and press the Delete key (the Recycle Bin is the default
     target; an accessibility action, no drag at all);
  2. drop onto the open Recycle Bin **window** (reachable by rung 1), instead of the desktop icon.
- A minimized Explorer window is listed as `visible: true, minimized: true`: restore it first or its
  controls cannot be read, which matches how the live tests already place windows.

## Impact on the project

No code change. For the "drag to Recycle Bin" case: a desktop icon target is rung 3 (needs a template and a
frame); the Recycle Bin window is a rung-1 target whose drop behaviour the first lesson that uses it must
check on a machine where the test may take the screen. The desktop surface is never a safe rung-1 anchor on Windows.
