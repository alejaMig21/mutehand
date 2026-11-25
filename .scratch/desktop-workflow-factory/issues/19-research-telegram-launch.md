# 19: Research: launching and reading Telegram

**Type:** research

**What to find out:** How to launch Telegram reliably (the launch by absolute path found no window) and what accessibility exposes, using only structure and counts so private text is not read.

**Blocked by:** 02

**Status:** resolved (message box in an open chat not checked)

- [x] A working launch route recorded, or a verdict that none exists
- [x] Which controls are reachable by accessibility, as roles and counts

## Answer

See `docs/research/19-telegram-launch-and-reading.md`. Launch route works: `agent-desktop launch "<abs path>" --arg=-workdir --arg=<dir> --arg=-many` (own instance, window in about 10 s, no --activate). Accessibility exposes Telegram widgets by name and Qt class (login screen: 25 nodes, 7 buttons). Logged-in profile read with the person's go-ahead (roles, counts and Qt classes only): chat list and search box are reachable; the message box and send button appear only inside an open chat, not checked (a click on a chat needs a new go-ahead).
