# Usable product: from a toolkit to an app you open with one click

## Problem

Everything works but only from a terminal (`uv run python -m workflow_factory.<module>`), and teaching needs a
manually registered MCP server. The person wants a product: open it from the desktop, do everything on screen,
never type a command.

## Decisions (made by the assistant, as the person delegated the organisation)

- Keep the engine. The local web editor already lists lessons, flows, consents, doubts and history and can run a
  flow (`/api/flows/<id>/run`). The product is the shell around it, built in thin slices that each leave something
  usable.
- The product's front door is one desktop shortcut that starts the local server without a console window and opens
  the editor in the default browser. A second click reuses the running instance. A Quit button ends it.
- Teaching stays with Claude Code (the tutor needs a model). The app opens a Claude Code window already wired to
  the tutor tools and its instructions, so the person chats instead of configuring or typing commands.
- Scheduling and a health check ("is everything it needs installed?") move into the screen.
- No packaged `.exe` for now: a bundled Python is a large download on a slow metered connection, and a shortcut to
  the installed environment gives the same one-click result.
- Anything the person does not do on screen is a defect of this feature.

## Out of scope

The example flow Vivaldi to Word to Telegram (it needs a clipboard-paste adapter step, research 17 to 19), a
multi-user or remote mode, and any change to the safety rules (ADR 0002).

## Tickets

25 launcher and shortcut, 26 teach from the app, 27 schedule from the app, 28 first-run health check,
29 paste and key steps for apps that refuse `set-value` (Word).
