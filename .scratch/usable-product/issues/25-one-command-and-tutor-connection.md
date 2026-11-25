# 25: One command and the tutor connection

**What to build:** `uv run workflow-factory` starts everything from the project folder (the editor by default; run, schedule, knowledge and the tutor server as subcommands), reuses a running editor, stops with Ctrl+C or Quit, and the folder's `.mcp.json` lets Claude Code find the tutor with one approval.

**Blocked by:** none

**Status:** resolved

- [x] One command in the project folder opens the editor; a second run reuses it
- [x] Ctrl+C or the Quit button stops it and leaves no state behind
- [x] The other tools are subcommands of the same command
- [x] Claude Code finds the tutor from `.mcp.json` (verified with a real MCP handshake: eight tools)

## Answer

The first version used a `.cmd` file, a shortcut installer and a Teach button idea; the person rejected all three (see `preference/product-direction` in engram), so they were removed.
