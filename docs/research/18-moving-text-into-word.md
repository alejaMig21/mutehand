# Research 18: moving text into Word (partial)

Date: 2026-11-25. Question: does setting a value through accessibility work in Word, or is the clipboard
route needed, and what does each cost in physical input?

Status: **partial**. The accessibility routes were measured; the two routes that need real keyboard or the
person's clipboard were **not run** (see "Not run").

## Method

Word was started by the guarded helper as a new, blank instance (`WINWORD.EXE /w /q`; no Word process existed
before, so nothing of the person's was open). One window, placed on the secondary monitor, read with
`snapshot --max-depth 30`, and closed normally afterwards. Nothing was typed, so the document stayed
unmodified: the close needed no dialog and left no recovery file.

## Results

| Probe | Result |
|---|---|
| Controls of the blank document window | `document` (actions `Scroll`, `SetFocus`; state `focused`) and a `textfield` with automation id `Body` (action `ScrollTo` only), plus the ribbon (47 buttons, 9 tabs, a Tell Me box) |
| `set-value` on `Body` | `ACTION_NOT_SUPPORTED`: "SetValue is not available" |
| `set-value` on `document` | `ACTION_NOT_SUPPORTED`: "role document is not editable", "SetValue is not available" |
| `type` on `Body` without `--headed` | `POLICY_DENIED`: "semantic action is unavailable and focus fallback is denied" |
| Text boxes that do accept `SetValue` | only ribbon fields (the Tell Me box and two combo-like fields), not the page |

## Verdict so far

- **Setting a value through accessibility does not work in the Word page.** Neither the document element nor
  its `Body` exposes `SetValue`, and a semantic insert is refused without focus. A node that must put text
  into a Word page cannot be a silent accessibility action.
- The remaining routes both need real input: (1) typing with real keystrokes into the focused page, which
  takes the keyboard and the foreground window; (2) pasting from the clipboard (`Ctrl+V`), which also takes
  the keyboard and the foreground window and **overwrites the person's clipboard**. In both cases the node
  would need exclusive physical input (research 20, ticket 24: every acting node already takes the input
  lock and pauses while the person is active).

## Not run, and why

- Real typing (`--headed type`): the permission system blocked the command, and I did not work around it.
- The clipboard route: the clipboard belongs to the person; it needs their explicit permission and a plan to
  save and restore what it holds.
Both are waiting for the person's decision.

## Impact on the "Vivaldi to Word to Telegram" example flow

The Word step cannot be a silent node. It needs exclusive physical input in the Word window; the text must
be handed over through the run context (research 17), and a flow should avoid the clipboard unless the person
allows it.
