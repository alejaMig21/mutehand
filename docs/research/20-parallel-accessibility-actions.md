# Research 20: parallel accessibility actions on different windows

Date: 2026-11-25. Question: do accessibility actions on two windows at the same time interfere with
each other or with the user's focus, and can nodes without physical input safely overlap?

## Method

Two throw-away WinForms windows of my own (A and B, each with a plain box and a password box) on the
secondary monitor, driven with `agent-desktop` from two threads. 30 rounds; each round per window:
`snapshot`, `set-value` on the plain box, `set-value` on the password box. Rounds ran serially
(A then B) and in parallel (A and B at the same time, barrier per round). After every round both
boxes were read back through Win32 `WM_GETTEXT` (outside agent-desktop) and the foreground window and
cursor position were sampled. A second experiment ran one command at a time, from a state where the
foreground was not my window, and stopped at the first change of the foreground window. Dummy values only.

## Results

| Measure (30 rounds, 2 windows) | Serial | Parallel |
|---|---|---|
| Command errors | 0 | 0 |
| Values crossed or lost (read back from the real boxes) | 0 | 0 |
| Cursor moved | never | never |
| Wall time | 68.2 s | 47.4 s (about 30 % less: the CLI overlaps only partly) |

**Foreground window** (command run from a state where the foreground was not the target):

| Command | Took the foreground? |
|---|---|
| `snapshot`, `list-windows`, `get ... --property value` | no |
| `set-value` on a text field (WinForms edit, and Notepad's editor) | **yes** |
| `click` (`InvokePattern.Invoke`) on a WinForms button | **yes** |

The CLI reports only a semantic step for these (`ValuePattern.SetValue` / `InvokePattern.Invoke`,
default headless mode, no `--headed`), and the control reports `focused` afterwards. So the foreground
change comes from the target application reacting to the action, not from a mouse or keyboard event.
Measured on two toolkits (WinForms, Notepad); other toolkits were not run.

## Verdict

- **Data does not interfere**: two windows can be read and written at the same time with no crossed
  values, no errors and no cursor movement (30 of 30 rounds in both modes).
- **Reads are safe to overlap and never disturb the user**: `snapshot`, `find`, `get`, `list-windows`
  and screen capture do not change the foreground.
- **Writes are not "no physical input"**: any `click` or `set-value` can pull the target window to the
  foreground, in the user's way, even in the default headless mode. The engine currently treats only
  drags, typing and coordinate rungs as physical input (`Lesson.uses_physical_input`), so an
  accessibility `click` node may overlap other nodes and skips the user-coexistence pause. That
  assumption is false for foreground. See ticket 24 for the decision.
- On this PC the live-testing rule "windows on the secondary monitor" does not prevent the theft: the
  window is activated wherever it is, taking keyboard focus away from the app the user is in.

## Impact

No code changed here. The decision on what overlaps is ticket 24.
