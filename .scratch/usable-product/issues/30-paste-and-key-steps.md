# 30: Paste and key steps for apps that refuse set-value

**What to build:** A lesson action that puts text into an app whose page cannot be written by accessibility (Word) by pasting from the clipboard or sending keys, under the input lock, with the foreground check and the clipboard backup and restore found in research 18.

**Blocked by:** none

**Status:** ready-for-agent

- [ ] The step refuses to send keys unless the foreground window is the one the lesson opened
- [ ] The person's clipboard is backed up before and restored after, and the step says what it cannot restore
- [ ] Both routes are tested on a Word page of our own, checked outside accessibility
