# 25: One-click launcher and desktop shortcut

**What to build:** Opening the product is one double click: a launcher starts the local server without a console window, opens the editor in the default browser, reuses a running instance on a second click, and has a Quit button. A one-time installer script creates the shortcut.

**Blocked by:** none

**Status:** resolved. The person does not like shortcuts, so the front door is the file `Workflow Factory.cmd` in the project folder; `Install.cmd` is optional and is never run for them.

- [x] A second launch while one runs opens the same editor and starts nothing new
- [x] A Quit button in the editor stops the server and the process
- [x] The launcher writes no console output when it has no console
- [ ] A shortcut is created on the Desktop and in the Start Menu by a double-click installer, only when the person approves
