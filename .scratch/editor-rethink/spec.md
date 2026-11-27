# Editor rethink: a screen a newcomer can act on, with the node canvas inside it

Status: ready-for-agent

Vocabulary is in `GLOSSARY.md`. Binding decisions: ADR 0002 (consent), ADR 0005 (own editor), ADR 0006 (small steps, the
editor never starts a lesson). The chosen mockups are listed under Further Notes and are the picture the build must match.

## Problem Statement

A person who has never seen the product cannot tell what to do on its screens. The first day ends on an empty canvas that
points to a tool they do not know. Labels such as "On trial", "Rejected" and "Needs a re-check" give no next move. A flow
that failed offers no way to fix it and see whether it worked. Making a flow run every morning needs two unrelated places,
and a Daily trigger node alone schedules nothing. The lists of steps grow without end as more apps are learned. Seven
screens hold information that belongs together. Simulated non-technical users scored it 3 and 4 out of 10.

## Solution

Two places and one flow screen. **Home** says what the product is for, shows only what needs the person, each with the
button that acts on it, and lists their flows with "Run now" and a daily time beside each. **Apps** shows one row per app
and opens it to show what the apprentice can do there, what needs attention, and what it is allowed to do. The **flow
screen** keeps the node canvas, drawn top to bottom, with a panel to add boxes on the right and a strip underneath that
explains the chosen box in plain words and offers its actions. Nothing is shown that the person cannot act on.

On screen the words are: "chore" for a Flow, "box" for a Node, "action" for a Step. The domain terms do not change.

## User Stories

First day
1. As a newcomer, I want one sentence that says what the product does, so that I know whether it is for me.
2. As a newcomer with nothing learned, I want the exact message to send in a chat, with a button that copies it, so that I can start teaching without knowing the vocabulary.
3. As a newcomer, I want to see the three stages (teach, put in order, let it repeat), so that I know what comes after teaching.
4. As a newcomer with actions learned but no flow, I want a "New chore" button, so that I can build my first one.
5. As a newcomer, I want to be told of anything missing from my setup only when something is missing, so that a working setup does not take my attention.

Home: what needs me
6. As a person, I want everything that needs me listed first with a count, so that I see it without looking around.
7. As a person, I want each attention card to say which flow stopped, at which box and why in plain words, so that I understand it without codes.
8. As a person, I want a "Try again" button on a stopped flow, so that I can fix a passing problem myself.
9. As a person, I want to be told whether trying again worked, so that I know if I am done.
10. As a person, I want an "Ask for help" button that shows the message to send to the tutor, with an optional note of mine, so that I can hand the problem over.
11. As a person, I want actions that must be learned again grouped by app, naming the flows they block, so that I know what is affected.
12. As a person, I want a flow blocked by a rejected action to say why it was rejected and let me allow it again, so that I can decide with the facts.
13. As a person, I want no card for states I cannot act on, so that "trusted" and "on trial" never worry me.
14. As a person, I want the attention list to disappear when empty, so that a quiet day looks quiet.

Home: my flows
15. As a person, I want each flow listed with its app by name and its last result and time, so that I know how things went.
16. As a person, I want "Run now" beside each flow, so that one press does the work.
17. As a person, I want the running flow shown with a "Stop", so that I can end it from wherever I am.
18. As a person, I want a flow that cannot run to say so on its button, so that I do not press something that will refuse.
19. As a person, I want "Run every day" beside a flow, with a time, so that scheduling is where the flow is.
20. As a person, I want to see the daily time and change or stop it there, so that I can cancel without finding another screen.
21. As a person, I want to rename a flow with any words, including spaces, so that names mean something to me.
22. As a person, I want to delete a flow and undo it right after, so that a mistake costs nothing.
23. As a person, I want to see what happened in past runs of a flow, so that I can check on a morning I missed.
24. As a person, I want deleting a flow to also stop its daily run, so that nothing runs that I removed.

Flow screen: building
25. As a builder, I want to name the flow at the top, so that I always know which one I am in.
26. As a builder, I want my changes kept without pressing Save and a visible "Saved", so that I cannot lose work.
27. As a builder, I want "Undo", so that I can take back any change.
28. As a builder, I want a notice with "Undo" when a box is removed, so that a stray key does no harm.
29. As a builder, I want to choose the app first and see only its actions, so that the list stays short.
30. As a builder, I want to search the actions by plain words, so that I find one quickly.
31. As a builder, I want a new box to join after the chosen or last box by itself, so that the order is what I clicked.
32. As a builder, I want boxes laid out top to bottom with lines between them, so that I read the flow in order.
33. As a builder, I want to drag boxes and lines as on any automation canvas, so that I can shape complex behaviour.
34. As a builder, I want "Two paths: yes or no", "Repeat for each" and "Wait a while" in plain words, so that logic is reachable without jargon.
35. As a builder, I want each path out of a decision labelled, so that I know which is which.
36. As an advanced builder, I want every system node and data operation still available, so that nothing the canvas could do is lost.
37. As a builder, I want recipes still offered, so that a known pattern can be dropped in.
38. As a builder, I want the first box to say when the flow runs and let me set a daily time there, so that the picture shows the whole truth.
39. As a builder, I want setting that time to create the daily run and removing it to cancel it, so that the box and Windows never disagree.
40. As a builder, I want to be offered how to teach a missing action, so that a gap does not stop me.

Flow screen: the explanation strip
41. As a person, I want choosing a box to show underneath what it does in a sentence, so that I understand it without opening anything.
42. As a person, I want a healthy box to say how often it has worked, so that I know how reliable it is.
43. As a person, I want "Test this box" with a warning that it takes my mouse and keyboard, so that I try it safely.
44. As a person, I want a failed box outlined, chosen and explained, with "Try again" and "Ask for help", so that the problem and the way out are together.
45. As a person, I want to remove the chosen box from the strip, so that I do not hunt for the key.
46. As a builder, I want a "Settings" button on boxes that have settings, opening the data in, settings and data out, so that detail is there when wanted.
47. As a person, I want boxes to show done, stopped, running and not reached, with a mark and a word, so that colour is not the only signal.

Running
48. As a person, I want to watch the boxes light up as they run, so that I see progress.
49. As a person, I want a double press on "Run now" not to stop the run, so that impatience does no harm.
50. As a person, I want a run to stay followed after I reload, change screen or lose the connection, so that I can always stop it.
51. As a person, I want to be told when the run paused because I used the mouse, so that I understand the wait.

Apps
52. As a person, I want one row per app with its number of actions, so that many apps stay readable.
53. As a person, I want a row to show a note only when something there needs me, so that problems stand out.
54. As a person, I want to search for what I want to do across all apps, so that I need not know which app it is in.
55. As a person, I want to open an app and see its actions by name, so that I know what it can do.
56. As a person, I want actions with a problem listed first with their button, so that I fix them where I find them.
57. As a person, I want to see what an app is allowed to do (such as press Send) and take it back after confirming, so that I keep control.
58. As a person, I want the message to send for teaching another action in that app, so that I can extend it.
59. As a person with dozens of apps, I want the rest folded behind "Show more", so that the screen does not become endless.
60. As a person, I want apps called by their product name, never by a file name, so that I recognise them.

Everyone
61. As a keyboard or screen reader user, I want every action reachable, named and focused in order, so that I can use the product without a mouse.
62. As a person with a narrow window or large zoom, I want everything to fit without sideways scrolling, so that nothing hides.
63. As a person, I want confirmations only before what cannot be undone, so that they mean something.
64. As a person, I want the messages shown to me to contain no screen content from private apps, so that pasting them is safe.
65. As a person, I want a "Close the program" control that says how to open it again, so that closing is not a dead end.

## Implementation Decisions

Screens and navigation
- Navigation is Home, Apps and "Close the program". The Steps, Tutor queue, Run history, Schedules, Consents and Setup check screens disappear; their abilities move: doubts into attention cards, history into each flow, schedules onto each flow and its first box, consents into each app, setup checks into attention cards shown only when something is missing.
- A flow screen is reached from Home or "New chore", and returns to Home.
- The dark identity already in use (ground, surfaces, cyan accent, the three status colours, the Segoe type stack) is inherited, with the larger type and targets of the mockups: buttons at least 44 px high.

What needs the person
- The server gives one list of attention items, so that Home, Apps and tests agree. Kinds: a flow stopped with an open doubt; actions to revalidate (grouped by app, with the flows they block); a rejected step that blocks a flow; a required setup check that fails. Steps that block no flow appear only inside their app.
- Trusted and suspect are never shown as labels. The explanation strip may say how many times a box has worked.
- "Try again" is a person's action: it closes the flow's open doubt as tried again, lifts the rejection of a step the same run needs when a failed check rejected it, and runs the flow, which resumes from its checkpoint. A step the person rejected themselves offers "Allow again" instead and is never lifted by "Try again". The result is reported as fixed, or as the same or a new problem.
- A step whose effect differs from the taught one stops the flow with a doubt, like any other failed box, and the box's failure setting applies. The action has already happened, so "Try again" performs it again, and so does a "retry" setting while that failure has not rejected the step.
- "Ask for help" shows a ready message naming the flow, the box and the plain reason, and keeps the person's optional note on the doubt. The doubt stays open. Dismissing a doubt is no longer offered on screen.
- The editor never starts a lesson. It only shows text for the person to send in a chat. This clarifies ADR 0006; the existing rule that the editor shows no lesson wording is replaced by "nothing in the editor starts a lesson".

Flows
- A flow gets a title (free text, shown everywhere) separate from its identifier (restricted characters, used in addresses, checkpoints, history and Windows tasks). Existing flows take their identifier as title.
- A flow remembers the app it runs on, stored with it. Existing flows take the app most of their steps belong to. A flow still runs on one app.
- Renaming changes only the title. Deleting removes the flow and its daily run and can be undone while the notice shows, restoring both.
- The flow is saved automatically after each change, with the existing revision check: a change made elsewhere is shown and the person chooses. A value a field cannot hold is not saved and the box says so. Run and test always use what is on screen.
- Undo covers canvas and settings changes of the open flow.
- A flow has at most one daily time. The first box is that fact: with a time it is a daily trigger node and a Windows task exists; without it the task is removed. Home and the box read the same source. "Run now" starts the flow either way.

Canvas
- Boxes are laid out top to bottom, with connection points above and below. Positions the person sets are kept. Positions stored by the left-to-right editor are ignored once.
- A new box joins after the chosen box, or after the last one. The "not connected" notice and its button remain only for wires the person removes.
- The decision, repeat and wait entries use plain names; the other system nodes and recipes stay available in the same panel under their own heading.
- The explanation strip is derived from the node: for a step, a sentence built from its action, control name and app (never a typed value or secret); its success count; and for a failed box the doubt's reason. The strip is generic: no rule depends on one app.

Apps
- The app's display name is the product name its executable declares, recorded when seen, falling back to the file name without its extension. No table of names for particular apps.
- Search matches action names and app names.

Interfaces
- New or changed API abilities: attention list; flow summary list (title, app, last run, daily time, whether it can run and why not); title, app, delete and restore of a flow; set and clear a flow's daily time; try again; app list with counts, problems and permissions. The API stays loopback-only, token-protected, and sends no screen content of private apps.
- Data created by earlier versions keeps working; new columns and tables are added on first use, as existing migrations do.

## Testing Decisions

- A good test drives the product as a person does and checks what they would see or what changed in the stored knowledge or the stand-in desktop and scheduler. It does not assert component structure or styling beyond what the person perceives (readable contrast, nothing off screen, focus visible).
- Main seam, confirmed by the person: the built editor in a hidden browser against the real API, with the stand-in desktop and the stand-in Windows scheduler. Every user story is tested here. Prior art: the browser tests of the editor and the tests born from the market tests.
- Supporting seam: the API, for rules a screen cannot show well (attention list contents, privacy of messages, migrations, daily-time consistency). Prior art: the API and screen API tests.
- Pure functions (layout, sentences) may use the existing JavaScript test runner where a browser test would be slow or vague.
- Browser tests of removed screens are rewritten to the new places, keeping the behaviour they protect: never destroy work without asking, never lose a run, never hide what a button does.
- Acceptance after each large wave: the non-technical personas of the market test (casual user, child, elephant), seeing only pictures and given no vocabulary.

## Out of Scope

- A ready-made example flow on the first day. A step only runs on the app version it was learned on, so a shipped example would ask to be learned again on most computers.
- Telling the person which file or document a flow produced: the apprentice does not know it.
- Flows that span several apps.
- A teach button that starts a lesson.
- Translating the interface; on-screen text stays English.
- A light theme.

## Further Notes

- Chosen mockups, in `mockups/` beside this file: A first day (without its example card), B Home, D Apps, E flow screen with a stopped box, F flow screen with a healthy box chosen. Their sources are in `design/editor-rethink/`.
- Two things go beyond the mockups: the "Settings" button in the explanation strip (needed to reach field settings), and the history of past runs, which was not drawn.
- Where a mockup and this text differ, this text wins; the person has not judged the two additions above.
- The glossary needs the on-screen words (chore, box, action) recorded beside their domain terms.
