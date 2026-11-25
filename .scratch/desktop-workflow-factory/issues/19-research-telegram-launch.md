# 19: Research: launching and reading Telegram

**Type:** research

**What to find out:** How to launch Telegram reliably (the launch by absolute path found no window) and what accessibility exposes, using only structure and counts so private text is not read.

**Blocked by:** 02

**Status:** resolved

- [x] A working launch route recorded, or a verdict that none exists
- [x] Which controls are reachable by accessibility, as roles and counts

## Answer

See `docs/research/19-telegram-launch-and-reading.md`. Launch route works: `agent-desktop launch "<abs path>" --arg=-workdir --arg=<dir> --arg=-many` (own instance, window in about 10 s, no --activate). Accessibility exposes Telegram widgets by name and Qt class (login screen: 25 nodes, 7 buttons). Done with the person's go-ahead on their own scratch chat (folder Nubes, chat Nube): folder and chat are reachable, the compose box takes `set-value` (verified), the send button says "Send" only when there is text and its `click` sends (it is a voice recorder when empty), and the message arrives. A sent message cannot be deleted without physical input, so the test message WF-test-19-0001 stays in that chat.
