# 25: One-click launcher and desktop shortcut

**What to build:** Opening the product is one double click: a launcher starts the local server without a console window, opens the editor in the default browser, reuses a running instance on a second click, and has a Quit button. A one-time installer script creates the shortcut.

**Blocked by:** none

**Status:** done except running the installer on the person's real Desktop and Start Menu, which waits for their approval

- [x] A second launch while one runs opens the same editor and starts nothing new
- [x] A Quit button in the editor stops the server and the process
- [x] The launcher writes no console output when it has no console
- [ ] A shortcut is created on the Desktop and in the Start Menu by a double-click installer, only when the person approves
