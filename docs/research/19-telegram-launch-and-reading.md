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
- **Logged-in window, measured with the person's go-ahead** (their own profile started through the guarded
  helper, window placed on the secondary monitor, read once with `snapshot`, then closed; only roles,
  counts and Qt class names were read, never a name, a message or a value, and no chat was opened):

  | What | Result |
  |---|---|
  | Window state at launch | chat list showing, no chat open |
  | Structure | 224 nodes on the first read; the list grows as Telegram loads more chats, so counts are not fixed |
  | Controls | 9 buttons (3 system buttons and `Ui::IconButton`), 11 `Ui::SideBarButton` options, 2 listboxes (`TabListLayout`, `Dialogs::InnerWidget`), 2 text fields (`Ui::InputField` and its `Inner`), hundreds of rows and options |
  | Chat list | reachable: a listbox with one option per chat, each with a name |
  | Search box | reachable: `Ui::InputField::Inner` offers `SetValue` and `SetFocus` |
  | Message box and send button | **not visible** with no chat open: the compose controls exist only inside an open chat, so they were not checked |
  | `-i` versus `--max-depth 30` | identical output (no truncation here) |

- **Closing:** a normal close (`WindowPattern.Close`) left Telegram running in the **system tray**, so the
  person's Telegram is set to close to the tray. A flow that must end Telegram has to stop the process the
  helper started; a flow that only needs the window has to reopen it from the tray.

## Impact on the "Vivaldi to Word to Telegram" example flow

The Telegram step works end to end through accessibility, tested live in the person's own scratch chat
(their words: a chat "Nube" inside the folder "Nubes", where doing and undoing is allowed):

| Step | How | Result |
|---|---|---|
| Go to the folder | `click` the `Ui::SideBarButton` option named exactly "Nubes" | worked, `InvokePattern.Invoke` |
| Open the chat | `click` the chat option whose name starts with `Group, Nube, ` (the accessible name is "kind, title, status, preview": match the prefix, never the bare title; a second chat "Nube srt" exists) | worked |
| Write the text | `set-value` on the `Ui::InputField::Inner` ("Write a message...") | `delivered_verified`; the send button label changed from "Record Voice Message" to "Send" |
| Send | `click` the `Ui::SendButton` | `delivered_unverified`; the message arrived (found afterwards with `find --value`) |
| Delete the test message | `right-click` on its row or on its option | **not possible without physical input**: `AMBIGUOUS_TARGET` on the row, `POLICY_DENIED` on the option (physical fallback denied). The test message `WF-test-19-0001` stays in the chat until the person deletes it |

Rules that follow for the flow:
- The `Ui::SendButton` is a **voice recorder while the box is empty**. A node must click it only after
  reading that its label is "Send"; it must refuse otherwise.
- Message text is readable through accessibility (the row's `value` and the option's name), including the
  person's private chats: reading it is a consent question for the flow, not a technical limit.
- Refs from a snapshot are not stable and several elements are "not proven unique": locate by `find` with a
  value or by a prefix, and refuse when the match is not exactly one.
- Sending is an acting node (research 20, ticket 24): it runs alone under the input lock and pauses while the
  person is working; the click and `set-value` can pull Telegram to the foreground.
