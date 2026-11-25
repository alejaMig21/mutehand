# Research 19: launching and reading Telegram

Date: 2026-11-25. Question: how to launch Telegram reliably (a launch by absolute path found no window)
and what accessibility exposes, using only structure and counts so private text is not read.

## Method

Telegram Desktop 7.2.9 (`%APPDATA%\Telegram Desktop\Telegram.exe`) was not running. The person's account
was **not opened**: I started an instance of my own with an isolated data folder, which shows the login
screen and holds no account, no chats and no private text. Window found by pid, moved to the secondary
monitor without activation, read, then stopped by its command line (my data folder) and the folder removed.

```text
agent-desktop launch "<path>\Telegram.exe" --arg=-workdir --arg=<scratch>\tgwork --arg=-many --timeout 30000
agent-desktop list-windows --app Telegram.exe            # window of that pid appears within ~10 s
agent-desktop snapshot --window-id <w-id> --max-depth 30
```

`--activate` was not used: it brings the app forward and takes the person's focus.

## Results

| Probe | Result |
|---|---|
| `agent-desktop launch` with the absolute path, no `--activate` | `ok`; returned `pid`, `window` and `process_instance`; the window was listed 11 s later, visible, not minimized |
| `-workdir <dir>` and `-many` | a separate instance with its own data folder; it did not touch the person's profile |
| Login screen, `snapshot -i` and `--max-depth 30` | the same 25 nodes: 11 groups, 7 buttons, 2 static texts, 2 windows, 1 menu, 1 menu item, 1 status; 24 refs; `complete: true`; 13 nodes with a name |
| Controls reachable by name | title-bar buttons (Minimize, Maximize, Close), the "Start Messaging" button and the welcome labels; each carries the Qt class chain (`Intro::Widget`, `Ui::RoundButton`, `Ui::FlatLabel`) as its native id |
| Actions offered | `Click` (and `SetValue` listed on custom buttons) |

## Verdict

- **A working launch route exists**: `agent-desktop launch "<absolute path>" --arg=...`. The earlier "no
  window" most plausibly comes from Telegram starting **minimized to the tray** (a setting of the person's
  profile, not tested here because it would need their profile): a tray-only Telegram has no top-level
  window until it is raised. A flow must therefore wait for a window after launch and, if none appears,
  say so as a doubt instead of waiting forever. The launch must not use `--activate` unless the person
  allows taking the focus.
- **Accessibility reaches Telegram's own widgets** (Qt exposes name, role and class), so buttons and
  labels of the login and settings screens can be located at rung 1 by name or class.
- **Not established** (needs the person's logged-in profile, which I did not open): whether the chat list,
  the message box and the message history are reachable. Telegram draws parts of its chat view itself, so
  the message box may need the lower ladder rungs. This part needs the person's explicit go-ahead to
  start their own Telegram and read only roles and counts.

## Impact on the "Vivaldi to Word to Telegram" example flow

The Telegram step can launch reliably and its fixed controls are reachable. Sending the text (finding the
message box, typing, pressing send) is untested; typing is an acting node (research 20, ticket 24), so it
runs alone under the input lock and pauses while the person is working.
