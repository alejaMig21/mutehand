# 30: Paste and key steps for apps that refuse set-value

**What to build:** A lesson action that puts text into an app whose page cannot be written by accessibility (Word) by pasting from the clipboard or sending keys, under the input lock, with the foreground check and the clipboard backup and restore found in research 18.

**Blocked by:** none

**Status:** resolved

- [x] The step refuses to send keys unless the foreground window is the one the lesson opened
- [x] The person's clipboard is backed up before and restored after, and the step says what it cannot restore
- [x] Both routes are tested on a Word page of our own, checked outside accessibility

## Answer

Two new step actions, `paste_text` and `press_keys`, in `flow.py` (`_paste`, `_type_keys`), both under the input lock and the pause for the person.
- Foreground: before the keys and again right before each key (and between setting the clipboard and pasting) the foreground window must be the
  app's; otherwise nothing is sent and the node stops with `wrong_window`. The emergency stop is looked at right before every key.
- Paste: `clipboard.py` copies every clipboard format whose bytes can be read (text, rich text, copied files with their copy or cut flag, images) and
  writes them back as they were, in a `finally`, so even a failed paste restores it. A format that gives no bytes (a bitmap handle, delayed rendering)
  is named in the node's output `not_restored`. An empty clipboard stays empty. The text itself never appears in what a run gives out.
- Keys: letters, digits, spaces and new lines only (`shift+x` for capitals, `space`, `return`); anything else is refused before the first key
  (`unsendable_text`): paste it instead, because a key name nobody tested could hit the wrong key.
- Tested with a fake desktop and fake clipboard (`tests/test_paste_and_keys.py` 15, `tests/test_clipboard.py` 5): exact text on the page, clipboard
  restored, wrong window sends nothing, switching window mid-typing stops at that key, emergency stop, failure of the paste still restores.
- Run for real (person's go-ahead, 2026-11-25): `WF_LIVE_WORD=1 uv run pytest -m live tests/test_live_word.py` starts our own Word on the second monitor,
  brings it to the foreground, runs both steps, reads the page back through Word's COM interface (outside accessibility) and checks the real
  clipboard is byte-identical before and after (6 formats). Both routes passed; Word is stopped afterwards. Real findings fixed on the way: the helper
  needs the full path of WINWORD.EXE, agent-desktop calls it `WINWORD.EXE`, the page control is `Page 1 content`, and Windows may refuse to bring a
  second Word to the foreground, in which case the step correctly stops with `wrong_window` (so the test shares one Word).
