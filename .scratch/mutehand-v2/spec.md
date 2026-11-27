# Mutehand model v2, phase 1: generic steps with tags, a technology per node, one filter

Status: ready-for-agent

Vocabulary is in `GLOSSARY.md` (Step, Technology, Tag, Locator, Universal step, Component, Flow, Node). Binding decisions: ADR 0007
(this spec is its phase 1), ADR 0002 (consent), ADR 0006 (small steps; the editor never starts a lesson; Data is the one format),
ADR 0004 (no absolute coordinates). Phases 2 to 4 are listed under Out of Scope.

## Problem Statement

The first lessons used Excel as a guinea pig, and the model that came out of them does not hold for anything else. A step belongs to
one program, so "Save workbook" in Excel and "Save" in Paint are unrelated, and the editor lists and filters steps by program: a node
that is not tied to any program, such as a mouse move with natural noise, has no place in it. The node panel shows two filters (a program
and a search box), a flat list of learned steps, and a mixed list of system nodes that ignores the groups they already carry. The
screens say "chore", "box" and "action", words nobody asked for, while the person and the platforms they come from say flow, node and
step. A node such as Save exposes nothing about what it needs, and the tutor has no way, when it teaches, to say what a step takes in or
gives out. The person wants to stop hiding this behind a wrapper and start the knowledge model again.

## Solution

Steps become generic: named by what they do ("Save"), never by a program, and holding one locator per technology (Excel, Word, Paint)
they have been learned for. Each step carries tags: technology tags come by themselves from where it was learned, and the tutor adds
pattern tags ("file", "mouse"). A step with no technology is universal. A node that uses a step records the technology it acts on, so a
flow is no longer tied to one program. The node panel has one search box that matches names and tags, and collapsible sections by node
type. The screens say Flow, Node and Step. The tutor's tools speak the same model. The knowledge database starts empty and the old one is
kept as a dated copy.

## User Stories

1. As a person building a flow, I want one search box that finds steps by name or by tag, so that I stop choosing a program before I can search.
2. As a person building a flow, I want to type "Excel" and see the steps learned for Excel, so that I can see what the apprentice can do there.
3. As a person building a flow, I want to type "Save" and see every step called like that whatever the program, so that I can reuse what it already knows.
4. As a person building a flow, I want a step that is not tied to a program to stay out of my results unless its name or tags match, so that a search for Save never shows a mouse move.
5. As a person building a flow, I want the node panel grouped by node type (Steps, Components, Triggers, Order, Logic, Data), so that I find a kind of node without reading a flat list.
6. As a person building a flow, I want those sections to be collapsible, so that I can hide what I do not use.
7. As a person building a flow, I want Steps and Components open and the rest closed when the box is empty, so that the first view is short and useful.
8. As a person building a flow, I want every section that has a match to open while I type, so that I do not miss a result in a closed section.
9. As a person building a flow, I want a message when nothing matches, so that I know it is not my typing.
10. As a person building a flow, I want a step node to show which technology it acts on, so that I know where it will run.
11. As a person building a flow, I want to change the technology of a step node among those the step has been learned for, so that the same Save serves Excel and Word.
12. As a person building a flow, I want a step node I add from a search for "Excel" to take Excel as its technology, so that I do not have to choose twice.
13. As a person building a flow, I want a node I add from a search with no technology to ask me which one when the step has several, so that nothing is guessed.
14. As a person building a flow, I want a flow to be able to contain nodes for different technologies, so that one flow can go from a browser to Word to a chat.
15. As a person running a flow, I want each step node to run on the technology it records, so that Save in an Excel node never clicks in Paint.
16. As a person running a flow, I want a step node whose step has no locator for its technology to say so before it runs, so that I find out before anything is touched.
17. As a person running a flow, I want the run to stop with a doubt that names the node, the step and the technology when a control is missing, so that the tutor knows what to fix.
18. As a person reading the screens, I want them to say Flow, Node and Step, so that the words match the ones I use and the ones other platforms use.
19. As a person reading the screens, I want no "chore", "box" or "action" anywhere, so that there is one vocabulary.
20. As a person with a flow open, I want the flow's own technology setting gone from the header and the panel, so that there is one place where a technology is chosen: the node.
21. As a person opening Home, I want my flows listed under that word and with their titles, so that nothing I know has changed except the name.
22. As a person on the Apps screen, I want it to list the technologies the apprentice knows and the steps learned for each, so that the screen matches the model.
23. As a person on the Apps screen, I want to take back a permission for a step on one technology only, so that consent stays as narrow as it was.
24. As a person on the Apps screen, I want a technology marked private to stay private, so that nothing seen in it is shown or sent.
25. As a person on first day, I want the empty state to say how to teach a first step in the new words, so that I am not sent to a word I do not know.
26. As a person who upgrades, I want my old database kept as a copy named with the date, so that nothing I had is lost.
27. As a person who upgrades, I want a clean knowledge database with no migrated steps, so that no flawed leftover comes with me.
28. As a person who upgrades, I want to be told once, in plain words, where the copy is, so that I can find it.
29. As a tutor, I want to teach a step by the action it does, with no program in the name, so that it can be reused.
30. As a tutor, I want to teach a step I already know on a new technology and have it gain a locator there, so that one step grows to cover more programs.
31. As a tutor, I want to be refused when I name a step with a program in it, with a message that says why, so that the rule is kept by the tool, not by memory.
32. As a tutor, I want to add pattern tags when I teach a step, so that the person can find it by kind.
33. As a tutor, I want technology tags to be set from where I taught, so that I cannot mislabel a step.
34. As a tutor, I want to list the steps known for a technology or tag, with their name, action, tags and state, so that I match a described flow to what exists.
35. As a tutor, I want a private technology's step names to stay hidden from the listing and be counted instead, so that the privacy rule keeps holding.
36. As a tutor, I want to create a flow whose nodes name a step and a technology, so that a described flow can span several programs.
37. As a tutor, I want the answer to say which node lacks a locator for its technology, so that I teach exactly that and nothing else.
38. As a tutor, I want my playbook to describe the new model, the words and what a step takes in and gives out, so that I teach for it from the start.
39. As a person who marks a step sensitive, I want consent to be asked per step and technology, so that a yes for one program is not a yes for another.
40. As a person using the filter, I want matching to ignore capitals and accents and to match the start of words, so that "sav" finds Save.
41. As a person using the filter, I want to press Escape to clear it, and to use it with the keyboard alone, so that it works without a mouse.
42. As a person using a narrow window, I want the panel and its sections to fit and stay readable, so that nothing depends on a wide screen.
43. As a person using a screen reader, I want each section to announce its name and whether it is open, so that the structure is not only visual.
44. As a maintainer, I want the old per-program step table and its readers gone, so that two models do not live side by side.
45. As a maintainer, I want the API, the tutor tools and the screens to speak the same words, so that a word never needs translating.

## Implementation Decisions

- **Step identity.** A step is identified by its name alone, unique among user steps. It holds a set of locators keyed by technology. The technology is the process name of a program, as the apprentice already records it, and it keeps the product name the screens show. A step with an empty set of locators is a universal step.
- **Locators.** Everything a step stores today that depends on a program (the locator, precondition, action target, measured effect, frame, mask, derived geometry, template, drag destination, sensitivity, secret reference, version, counters and rejection state) is stored per locator, because it is learned and measured per technology. What describes the step as a whole is its name, its action kind and its tags.
- **Tags.** Technology tags are not stored: they are the technologies of the step's locators, so they cannot go out of date. Pattern tags are free text, stored with the step, set by the tutor at teaching time and read by the filter.
- **Names.** A step name must say what it does and must not contain a technology name or a program's process name. The check lives in the tool that saves a step and compares against the technologies already known and the one being taught; the refusal says why.
- **Nodes.** A step node records the step name and the technology. A flow no longer has one program: the flow-level program is removed from the data, the API and the screens. A system node has no technology.
- **Running.** A run resolves each step node by step name and the node's technology. A flow with nodes of different technologies runs them one at a time, each on its own technology; the engine still drives one program at a time and does not run two technologies in parallel (see Out of Scope). A node whose step has no locator for its technology is refused before anything is touched.
- **Consent and privacy.** Consent stays per step, control and action, now also per technology. A private technology keeps its current rule: its step names are not shown or searched, and counts replace them. The opaque handles already used for private technologies keep working.
- **Search.** One function matches a query against a step's name and its tags (technology tags included) and against the system nodes' titles and groups. Matching ignores capitals and accents and matches word beginnings. Universal steps match only on name or pattern tags. The function lives with the catalogue and serves the panel, and the same rule serves the tutor's listing so both agree.
- **Panel.** One search box. Sections by node type: Steps, Components (empty in this phase), Triggers, Order, Logic, Data. A section is collapsible; with the box empty only Steps and Components are open; while typing, every section with a match opens. The program selector in the panel and the "decisions and repeats" section are removed. The panel keeps its message for "nothing matches" and its entry to teach.
- **Words.** The screens, the API's user-facing messages and the tutor's messages say Flow, Node and Step. Test ids and code names that already say flow, node and step stay; ones that say chore, box or action are renamed with the words. The glossary and ADR 0007 already carry the vocabulary.
- **Apps screen.** It lists technologies and, for each, its steps. The per-step permission, rejection and relearn flows keep their behaviour, keyed by step and technology.
- **Database.** A new user database schema with the generic step model. On first start of this version, an existing user database is renamed to a dated copy next to it and a new empty one is created; nothing is imported; the person is told once where the copy is. The factory database format gets the same model; the shipped factory knowledge, if any, is rebuilt from the new format.
- **MCP tools.** `teach_step` takes the step name, the technology (the app it is taught on), the control and action as today, plus optional pattern tags; teaching a step name that exists on a new technology adds a locator instead of replacing the step. `list_known_steps` takes an optional technology and an optional tag or query and returns name, action, tags, technologies and state; a private technology's steps are counted. `create_flow` nodes carry the technology; its answer names the nodes that lack a locator. `flow_status` reports the same. The study tools (`set_study_order`, `study_status`, `observe_app`, `mark_app_private`), consent and the recipe tools keep working; recipes are kept as they are in this phase.
- **Tutor playbook.** `docs/agents/tutor.md` is rewritten for the new model and words: naming rule, technologies and tags, adding a locator, what a step takes in and gives out, the new listing.
- **Seams (agreed).** Browser tests against the real HTTP API with the stand-in desktop and scheduler; MCP tests through an in-process client with the stand-in desktop.

## Testing Decisions

- A good test drives behaviour a person or the tutor can see: what the panel shows for a query, what a run touches, what a tool answers. It does not assert table layouts or function names.
- Browser tests (opt-in `web` marker) cover the panel (one box, sections, collapsing, empty and typing states, universal steps), the node's technology (choosing, changing, a flow with two technologies), the words (no chore, box or action on any screen), the Apps screen and the upgrade notice. They reuse the existing helpers that serve the editor over a temp database with the stand-in desktop and scheduler, and the persona harness datasets, which must be rebuilt for the new model.
- MCP tests use the in-process client as today: teaching on two technologies adds a locator, the naming refusal, listing by technology and tag, private counting, creating a flow with technologies, and the missing-locator answer.
- Engine tests run flows through the stand-in desktop: a node runs on its own technology; a missing locator is refused before acting; consent is per technology.
- Database tests cover the upgrade: the old file is kept under a dated name, the new one is empty, a second start does not repeat it.
- The existing suites are the prior art; every test that names the old model is updated with it. The full suites (unit, browser, web unit) and the linter pass at the end of every ticket.

## Out of Scope

- **Phase 2:** components (flows used as nodes) with inputs and outputs, tutor tools to publish them, and the decision on recipes. In this phase the Components section exists and is empty.
- **Phase 3:** program icons read from executables and one icon per node type.
- **Phase 4:** the engine running several technologies in one run at the same time, an "open program" node, and universal steps such as a mouse move with natural noise. In this phase a flow may contain nodes of several technologies but runs them one after another.
- Declaring inputs and outputs of a step beyond what exists (text fields for writing actions) belongs to phase 2, where components are the place for them.
- Importing anything from the old database. Publishing to PyPI.

## Further Notes

- The old per-program lessons (Excel, Paint, Word) are not carried over on purpose: the person asked for a clean start and keeps the dated copy.
- ADR 0006 is superseded only in the part that makes a step belong to one app; everything else in it holds.
- Behaviour that was settled in the editor rethink and is not mentioned here stays: autosave, Undo after delete, Home attention cards, daily time as one fact, the More menu, the first-day guide.
