# Research 18: moving text into Word

Date: 2026-11-25. Question: does setting a value through accessibility work in Word, or is the clipboard
route needed, and what does each cost in physical input?

## Method

Word was started by the guarded helper as a new, blank instance of my own (`WINWORD.EXE /w /q`; no Word process
existed before, so nothing of the person's was open), placed on the secondary monitor, and driven with
`agent-desktop`. The person authorized real typing and the clipboard route on that instance. Their clipboard
was backed up first and restored afterwards (see "Clipboard"). Delivery was checked with a screenshot of that
window alone, because Word does not expose the page text (below).

## Results

| Route | Result |
|---|---|
| `set-value` on the page (`Body` text field or `document`) | `ACTION_NOT_SUPPORTED`: neither offers `SetValue`; the document "is not editable" for that command |
| `type` without `--headed` | `POLICY_DENIED`: "semantic action is unavailable and focus fallback is denied" |
| `--headed type` on `Body` | `ACTION_FAILED`: "target element lost focus before physical input delivery"; on `document`: `ACTION_NOT_SUPPORTED` (not editable). `type` cannot target a Word page |
| `focus` on `document` | `POLICY_DENIED`: "SetFocus moves the desktop foreground window on Windows" |
| **Real keys** with `--headed press <key>`, one call per key | **works**: "wfword18" in 8 calls, 0.7 s (about 0.09 s per key), all delivered; the page showed "Wfword18" (Word auto-capitalised the first letter) |
| **Clipboard**: `clipboard-set` then `--headed press ctrl+v` | **works**: the marker appeared on the page; the paste itself took 0.1 s |
| Mouse cursor moved by either route | no |
| Reading the page back | **not possible by accessibility**: `get --property value` returns an empty string and `--property text` returns the label "Page 1 content", never the typed text. Delivery was verified with `desktop-window.ps1 shot` |

Both real-input routes act on **the foreground window**, not on a chosen element: `press` sends keys to
whichever window has the focus. In these runs my Word was already in the foreground.

## Clipboard

The person's clipboard was backed up (text, plus any copied files with their copy or cut flag) before the
test, my marker was placed in it, and afterwards it was restored only after checking that it still held only my
marker, then compared with the backup: identical. Limits: only text and a file list are restored; a richer
format (HTML, an image) would be lost. A dry-run restore done earlier, with no need, had already rewritten the
clipboard as plain text, so a richer format it may have held was lost then.

## Verdict

- **Setting a value through accessibility does not work in a Word page**, and no semantic insert is available.
  Text reaches the page only through real input.
- **Typing** is slow (about 0.09 s per key, so about 90 s per 1000 characters), is changed by Word's autocorrect
  and autoformat (capitalisation, quotes, lists), and cannot send every character as a single key press.
- **Paste** is instant and exact, but it overwrites the person's clipboard, so it needs a backup and restore
  step and loses rich formats. Recommended for any text longer than a few words.
- **Either way the node needs exclusive physical input**: the keys go to the foreground window, so the node must
  first make sure that window is Word (raising it needs `--headed`, which takes the person's focus), then run
  alone under the input lock and pause while the person is working (research 20, ticket 24).
- **A node must refuse to send keys when the foreground window is not the one it opened.** A wrong window
  would receive the text, and the result cannot be read back by accessibility; the check is a screenshot of the
  window or the status bar.

## Side effect and cleanup

Closing a modified Word asks to save; answering "Don't Save" (`InvokePattern.Invoke` on the button) exited
cleanly. Word still leaves a copy of every unsaved document in
`%LOCALAPPDATA%\Microsoft\Office\UnsavedFiles` (`*.asd`), and those files **cannot be deleted by this user**
(`PermissionDenied`), so each test run leaves two or three empty recovery files that Word will offer to recover
at its next start. Do not run Word-driving tests on a machine whose owner will open Word without being told.

## Impact on the "Vivaldi to Word to Telegram" example flow

The Word step is a physical-input node that pastes the text read from Vivaldi (research 17), after backing up
and restoring the clipboard. Reading back what Word received is not possible by accessibility.
