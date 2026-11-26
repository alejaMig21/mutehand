# Editor rethink: exploration for implementers

Worktree `D:\Projects\AI\desktop-workflow-factory\.claude\worktrees\editor-rethink` (branch `editor-rethink`, HEAD 68ea507).
Paths are relative to it. Static reading only: nothing was installed, built, run or modified.
Graph project: `dwf-editor-rethink` (fast mode; JS tests, `docs/`, `scripts/`, `web/dist` not indexed).
Checked by calling worktree functions with a fake runner: the 284-char refusal (0.1) and the `if`/`foreach` refusals (0.3).

## 0. Read first

1. **Scheduler path limit.** `schedule.py:19,58` caps the task command at 261 chars. It embeds `sys.executable` and, for a
   non-default db, `--user-db` (`api.py` `_schedules`, :391). Computed for pytest `tmp_path`: **284 chars in this worktree**, 251 in
   the main checkout. Existing schedule tests that expect 201 should fail here. Fix for the environment: short venv, e.g.
   `UV_PROJECT_ENVIRONMENT=$TEMP/wfv` (about 243 chars), set for every `uv` call and hook; one per worktree.
2. **Default `schedule_runner` is the real `schtasks`** (`api.py:65`). `editor`/`serve`/`make_server` fixtures do not pass a fake.
   Once Home, attention or delete call the scheduler, tests would query or DELETE real tasks. First step of ticket 02/04: pass
   `FakeScheduler()` in every fixture and add an autouse guard in `tests/conftest.py` (like `_never_move_the_real_mouse`).
3. **Autosave cannot store half-built flows.** `Node.__post_init__` / `Flow.__post_init__` (`flow.py:128-250`) reject an `if` with no
   `then` and a `foreach` with no `body`; a freshly added box is exactly that, so `PUT` answers 400 (ticket 06 and 07).
4. **Any node or edge change drops the checkpoint** (`flow.py:252`, `queue.py:141`: `repr((nodes, all_edges))`). Adding, changing or
   removing the daily trigger on a stopped flow makes "Try again" restart from the top and repeat actions (Send twice). Adding a
   field to `Node` invalidates every stored checkpoint.
5. **`web/dist` is tracked in git** (3 files, hashed names). Every web change needs a rebuild and commit; parallel branches will
   conflict there. Resolve by rebuilding, never by hand.
6. **Positional inserts**: `flows.py:41`, `flows.py:78`, `steps.py:336` use `INSERT OR REPLACE ... VALUES (?, ?)`. Adding a column
   breaks them, and `OR REPLACE` wipes other columns. Name columns and upsert, or use side tables.

## 1. Server

Routes: all in `src/workflow_factory/api.py` `_route` (:286-389). Handlers: `_schedules` :391, `_static` :423, `_safety` :462.

| Route | Line | Notes |
|---|---|---|
| POST `/api/quit` | 287 | sets `quit_requested` |
| GET `/api/steps` | 290 | steps + trust/private/consent. **Used by `app.py:30-40` to detect a running editor; keep it a list** |
| GET `/api/checks`, POST `/api/checks/seen` | 294 | `checks.py` |
| GET/POST/DELETE `/api/schedules` | 300 -> 391 | cap 20, name `<flow> daily HHMM` |
| GET `/api/recipes`, GET `/api/flows` | 302 | flows listing is `{id, origin}` only |
| GET/PUT `/api/flows/{id}` | 306 | `_save` :192, revision = hash of view :186; 409 on stale `base` |
| POST `.../duplicate`, GET `.../data`, POST `.../nodes/{n}/test`, POST `.../run` | 312-338 | `_start_run` :109, `_launch` :132 |
| GET `/api/library` | 340 | counts, `why` |
| POST `/api/steps/{app}/{name}/(reject|restore)` | 344 | |
| GET/DELETE `/api/consents` | 351 | |
| GET `/api/doubts`, POST `/api/doubts/{id}/(answer|dismiss)` | 358-368 | |
| GET `/api/history` | 370 | `?flow=` |
| GET `/api/runs`, GET `/api/runs/{id}`, POST `.../stop` | 372-388 | runs are in memory only |

New `/api/flows/{id}/...` routes: only `/api/flows/` paths are URL-unquoted; add regexes beside the existing ones. No
DELETE for flows exists (unquote is at :270). Errors: `ValueError` -> 400 with its text; 500 says nothing.

Storage (one user SQLite file; factory file read-only, same table names):

| Data | Table, module | Migration style |
|---|---|---|
| Flows | `flows(id, definition JSON)` `flows.py:12` | lazy `CREATE IF NOT EXISTS`; no title, app, delete |
| Canvas positions | `flow_layout(id, positions)` `flows.py:14` | no layout version |
| Schedules | only in Windows Task Scheduler `schedule.py` (read back from XML :82-110) | none in db |
| Doubts, history, locks, checkpoints | `doubts`, `run_history`, `run_nodes`, `run_locks`, `checkpoints` `queue.py:26-65` | `_connect` :80: `migrate_names` + `add_text_column` |
| Steps, counters | `steps`, `step_state(.. rejected, restored, why)` `steps.py:18-57` | `_prepare` :284 |
| App names/versions | `app_seen(app, version)` `steps.py:58`, written only by a run (`flow.py:876`) | no display name |
| Consents | `consents(app, control, action)` `consent.py:14` | create on use |
| Private apps, study order | `tutor.py:32` | names without `.exe` |
| Recipes | `recipes.py:19` | |
| Setup check seen | file `checked.json` beside the db `checks.py:13,52` | |
| Editor address | `app.json`, `app.log` in data dir `app.py` | |

Migration helpers: `legacy.py` (`add_text_column` is race-safe; TEXT only). Compatibility tests: `tests/test_rename_compat.py`.
Other writers of the same file: `workday.py` (scheduled run), `mcp_server.py`/`tutor.py` (tutor), `knowledge.py` (export/import,
`build_factory`, `duplicate_flow` :113 must carry any new flow metadata).

Engine facts: `run_flow` `flow.py:855` returns `waiting` while any open doubt exists (not recorded in history; `busy` neither).
`block` :579 records the doubt; `DOUBT_REASON` :280-299, detail code kept in `doubts.detail`. Rejection: `record_outcome`
`steps.py:368` writes `why.kind="different_effect"`; `reject_step` :464 writes `"person"`; `restore_step` :404 zeroes counters.
One failure rejects an unproven step (1/5 < 0.30). `_fired_triggers` `flow.py:723`: manual with no manual trigger fires all;
**daily with only a manual trigger skips every trigger** (and what hangs from it).

## 2. Web editor (`web/src`)

- `main.jsx` -> `App.jsx` (82): no router. `SCREENS` :10, screen in `sessionStorage` `wf-screen`; Editor stays mounted (`active`);
  first run jumps to `checks`; quit/closed/locked pages; `unsaved` flows up via `onUnsaved`.
- `Editor.jsx` (614): all flow-screen state. `refresh` :69, `onConnect` :132, `addNode` :152, `addRecipe` :183, `deleteSelected`
  :211, `show` :223, `save` :294, `ensureStored` :327, `run` :336, `stop` :358, `viewNodes` :381. App is typed in `app-name`;
  guessed by `guessApp` (`catalog.js`). Run following (`useRuns`) lives here: **must move to App** for Home (ticket 02).
- Children: `NodeCard` (marks, handles Left/Right :45,:68), `NodePanel` (keyboard wiring + delete), `NodeDetail` (modal, test with
  warning), `FieldEditor`, `SearchPanel` (add panel, drag), `RunLog`.
- List screens on `Screen.jsx` + `useLoad.js` (`useLoad`, `useAction`: load/empty/error, single-flight): `Library`, `Queue`,
  `History`, `Schedules`, `Consents`, `Checks`.
- `api.js`: token from `#token=` into `sessionStorage`; 401 -> locked event; error with `status` = server answered.
- `useRuns.js`: runs keyed by flow id, re-attaches via `/api/runs`, Stop arms after 500 ms, survives lost requests. Reuse.
- Styles: single `styles.css` (250 lines), tokens :root lines 2-6, one breakpoint `max-width: 860px` (:238). Spec wants 44 px
  buttons and 390 px width. `icons.jsx` holds icons.
- Pure modules with `node --test` files: `flowjson` (14 tests), `catalog` (6), `bindings` (7), `words` (7), `safety` (4).
- Build: `vite.config.js` (`base './'`, `dist`). Served by `_static` from `parents[2]/web/dist` (`editor.py:19`), override
  `WORKFLOW_FACTORY_WEB_DIR` (only `editor.py`, not `app.py`).
- Mockups: `.scratch/editor-rethink/mockups/*.png`. HTML sources are gitignored, only in the main checkout:
  `D:\Projects\AI\desktop-workflow-factory\design\editor-rethink\` (read only).

## 3. Tests

Fresh worktree (currently no `.venv`, no `web/node_modules`; `dist` present from git). Not executed here; read from config:

```bash
export UV_PROJECT_ENVIRONMENT="$TEMP/wfv"        # see 0.1
uv sync                                          # try --offline first (metered connection)
(cd web && npm ci && npm run build)              # try --prefer-offline
(cd web && npm test)
uv run pytest -q                                 # excludes live and web; test_app/test_editor_main need web/dist
uv run pytest -q -m web                          # headless browser
uv run ruff check                                # pre-commit hook .githooks/pre-commit needs the synced env
```

- **Never `-m live`** (real Paint, Word, clipboard, credential store, scheduler). `-m "live or web"` neither.
- Browser: do not run `playwright install`. Playwright 1.65.2 wants headless shell 1255; only 1248 is cached and works because
  `test_editor_e2e.py:30` globs it and passes `executable_path`. New browser tests must use `open_page` (:180) / `serve` (:520).
- Do not junction `node_modules` from the main checkout (removing the worktree could follow it).
- Harness: `tests/fake_desktop.py` (`FakeDesktop`, `button`, `step`; `click_seconds`, `user_acts`, fake clock),
  `fake_clipboard.py`, `fake_scheduler.py` (holds a foreign task), isolation via `tmp_path`;
  `conftest.py` clears the emergency stop and blocks the real mouse; `pyproject.toml` `tmp_path_retention_policy="none"`.
- Fixtures patch `workflow_factory.api.seen_before` (autouse `not_the_first_run`). `CONTRAST` JS check at
  `test_editor_safety_e2e.py:89`. `tests` import each other (`from test_editor_e2e import ...`, `from test_api import call`).

Tests protecting screens to remove (rewrite, keep the behaviour):

| File: test (prefix) | Protects |
|---|---|
| e2e `the_four_other_screens...` :188 | reject/restore, revoke, answer doubt, history words |
| e2e `a_schedule_is_added_listed_and_removed` :679 | schedules, foreign task hidden |
| e2e `the_first_run_opens_on_the_setup_check` :711 | checks |
| e2e `quit_button_asks_first` :270 | quit |
| e2e `rejected_step_says_which_one` :556, `cards_say_how_far...trusted` :583 | safety marks, no answer/dismiss; trust labels go away |
| e2e `nothing_in_the_editor_starts_a_lesson` :377 | bans words lesson/teach/learn/study: rewrite (ticket 12) |
| safety `every_button_on_every_screen_can_be_read` :102 | contrast over `SCREENS` |
| safety :200 cannot start -> Tutor queue; :231 changes from other screens; :243 undoable actions ask first | queue, steps, consents |
| safety :268 restore keeps scroll; :290 failed load never says "empty" | list behaviour |
| safety :331 double zoom (`tab-checks`, `quit`, `save`); :342 plain words history/steps; :450 states legend | |
| safety :499 schedule takes flow app; :510 typed note and place survive reload; :547 closed page says how to reopen | |
| safety :118,:139,:149,:216 | replaced by titles/autosave: keep "never destroy without asking", "bad value not stored" |
| `test_api_schedules.py`, `test_api_editing.py`, `test_screens_api.py`, `test_checks.py` | API behaviour behind those screens |

Most e2e tests also drive `flow-id`, `save`, `open-flows`, `palette-*`, `app-name`: tickets 01/02/06/07 will touch many.

## 4. Safety

- User db: `paths.py`: `WORKFLOW_FACTORY_USER_DB`, else `%LOCALAPPDATA%\workflow-factory\user.db` (`.` if unset). Reports:
  `WORKFLOW_FACTORY_REPORT_DIR`. No such vars set in this shell. Tests pass `tmp_path` explicitly; `test_editor_main` sets the env var.
- `app.run()` without `data_dir` = real db; without `open_browser` = visible browser; reuses a running real editor.
  `uv run workflow-factory` and `python -m workflow_factory.editor` use real `AgentDesktop` and real `schtasks`, and register the
  global hotkey (unless `--no-hotkey`). **Live testing: a scratch script building `ApiServer(tmp db, ..., FakeDesktop,
  web_dir=..., schedule_runner=FakeScheduler())`**, headless browser.
- Real scheduler: `test_schedule.py:184` `main(["list"])` reads it in the default suite (read only). Real tasks created from a
  worktree would point at the worktree Python and the real flow names.
- Real clipboard/mouse/keys: only through `AgentDesktop` (`clipboard.WindowsClipboard`). Always inject `FakeDesktop`.
  "Copy this message" tests: stub `navigator.clipboard.writeText` via `add_init_script` (whether headless Chromium touches the
  Windows clipboard was not verified).
- `test_agent_desktop_adapter.py:482-544` registers the global hotkey briefly in the default suite (fails if the key is taken,
  for example by a running editor).
- Privacy: no value from `outputs`/context or secret in messages; for private apps (`tutor.is_private`) a locator control name
  may be screen content, so the strip sentence and help message need a rule for it (ticket 08/09).

## 5. Per ticket: files and traps

**01 title + app.** `flows.py`, `api.py` (`_save`, `_flow_view`, listing, duplicate), `knowledge.py`, `Editor.jsx`, `words.js`
(`nameProblem`, `freshName`), `History.jsx`, `Schedules.jsx`, `catalog.js` (`guessApp` needs a server twin for backfill).
Traps: 0.6; title inside the revision means rename -> 409 for an open editor; generated ids must be `[\w.-]+`, unique ignoring
case (Windows task names are case-insensitive, SQLite and `FakeScheduler` are not) and short (about 50, see 0.1); factory flows
have no title; normalise app with `appKey`/`_app_name`; do not put title/app into `Flow.definition`.

**02 Home.** New component, `App.jsx`, `useRuns.js` lifted, flow summary API. Traps: "cannot run + why" logic is split between
`api._start_run` and `safety.js whyNotRunnable`: make the server the one source; `_start_run` swallows `DesktopError` (app closed);
`desktop_for` per flow per listing calls the real CLI, so avoid `app_key()` in summaries (use `app_seen`); last result =
newest `run_history` row, `error` rows included, `#test:` and `recipe:` ids excluded; `wf-screen` default; many fixtures wait for
`palette-open-menu` at load and will break once Home is first.

**03 app names.** `agent_desktop.py` (`version_of_pid` :73 reads only `\`; product name needs `\VarFileInfo\Translation` +
`StringFileInfo\...\ProductName`), `desktop.py` protocol, `fake_desktop.py`, `steps.py` (`app_seen`), `tutor.py`, `catalog.js`
`appLabel`. Traps: positional insert `steps.py:336`; record at observe/teach too, not only runs; empty name falls back; keep
`AppKey` equality unchanged; keys stay process names (consents, private apps, steps).

**04 daily time.** `schedule.py`, `api.py`, `flows.py`, Home, first box, `flow.py` triggers. Traps: 0.1, 0.2, 0.4; today a flow
can hold several tasks (collapse to one); old schedules have a task but maybe no trigger node, and a manual trigger plus a daily
task runs nothing; create the task first, then save the node (or roll back) so a refusal leaves nothing; server edits to the flow
change the revision under an open editor; `edges: null` flows chain by order, so inserting a trigger rewires; the task keeps its
own `--app`; `delete_schedule` ignores failures (return code unchecked); tasks of another data dir are listed too (XML holds
`--user-db`); `describe_schedules` is one `schtasks` call per task.

**05 rename/delete/history.** `flows.py`, `queue.py`, `api.py`, UI. Traps: soft delete so Undo restores layout, checkpoint,
doubts, schedule time; a reused id would inherit history/doubts, so reserve deleted ids; hide their doubts from attention;
deleting a user copy that shadows a factory flow reveals the factory one; running check must include `run_locks` (scheduled
process) not only `_runs`; **history box names**: `run_nodes.step` is NULL for system nodes and node ids are reused
(`nextNodeId`), so store the box name at record time, both in `flow.py` final `record_run` and the exception path.

**06 autosave/undo.** `Editor.jsx`, `api._save`, `flows.py`. Traps: 0.3 (store drafts or relax validation only for saving, never
for running); serialise PUTs and carry the new revision forward; each save of a node change clears resume (0.4); layout-only
changes must save too; invalid drafts (`data.drafts`) are not saved and block "Saved"; undo must not push on selection or fit;
`mayLeave`, `beforeunload`, quit text, `ensureStored` all assume manual save; do not create stored flows just by opening
"New chore" unless intended.

**07 canvas.** `flowjson.js` + test (`autoLayout`, `layout`, labels true/false -> yes/no), `NodeCard.jsx` handles,
`Editor.jsx` offsets :155,:186,:191 and `fit` padding :22, `SearchPanel.jsx`, `catalog.js` titles (`catalog.test.js`,
`bindings.js` uses `SYSTEM_NODES`), `styles.css`. Traps: "ignore old positions once" needs a stored layout version
(`flow_layout` positional insert, `duplicate` copies layout); default = append after chosen **or last**, and with `if`/`foreach`
the wire takes the free branch (`withBranch`); a `foreach` body must be a step with no other wires.

**08 strip.** New pure sentence module + test, replaces `NodePanel.jsx` (**keep keyboard connect/disconnect**, safety test :302),
opens `NodeDetail`. Success counts from `step_reports`. Traps: cover every kind/op and action in `steps.ACTIONS`; never read
`fields` values; test action dismisses old `#test:` doubts; private control names (section 4).

**09 stopped flow.** `queue.py`, `api.py`, `steps.py`, `tutor.py`, Home, strip, `words.js`. Traps: `doubts.status` has a CHECK
(`queue.py:34`): "tried again" needs a table rebuild or a separate column; never use `dismiss_doubt` (deletes checkpoint);
close **all** open doubts of the flow (parallel branches); lift only `why.kind == "different_effect"` (`NULL` why is unknown,
person is never lifted) before `_start_run`, which refuses rejected steps; note on an open doubt needs a new write, and
`_close_doubt` overwrites `note` with NULL when the tutor answers; `list_open_doubts` (`tutor.py:184`) does not return `note`,
so the tutor never sees it; "same or new problem" compare node + detail; `effect_mismatch` retry repeats the action.

**10 other attention.** API list, `steps.py`, `checks.py`. Traps: `to_revalidate` is derived from `app_seen` vs step version;
"blocks a flow" needs flow app + step names (and `foreach` bodies); `run_checks` depends on the machine (`which`, `cwd/.mcp.json`):
**make it injectable in `ApiServer`** or tests differ per machine; `claude-code` is not `optional` although running does not need
it: decide whether it counts as "required"; `data_dir` = db parent.

**11 Apps.** API app list, UI, `catalog.js` search. Traps: under 0.5 s with 900 steps: `list_steps` decodes capture/template
blobs, `find_step` opens the db per call (existing test counts connections, `test_api_editing.py:137`); consent scope is
`automation_id or name`, `*` covers all; "take back" uses the exact triple; apps may exist only in consents or flows.

**12 first day.** Home. Traps: replace lesson-word test and README sentence; clipboard stub; "nothing learned" includes factory
steps; message text must not start anything.

**13 removal.** Delete 6 screens + `Screen.jsx` if unused, `safety.js`/`words.js` leftovers, `App.jsx`. Traps: keep
`/api/steps`; `app.py:73` message says "Quit in the editor" and `test_app.py` asserts "Quit"; error text `api.py:129` "Restore the
step in the Steps screen"; `safety.js:37` and `Editor.jsx:501` "Open Steps"; `NodeDetail` "ask the tutor" wording; `README.md`; `GLOSSARY.md` (chore,
box, action) and ADR 0006 note; paused notice currently only in Editor.

## Order and overlap

`api.py`, `Editor.jsx`, `App.jsx`, `styles.css`, `test_editor_*` and `web/dist` are touched by nearly every ticket: prefer serial
integration. Dependency graph allows 01 and 03 first, in parallel.
