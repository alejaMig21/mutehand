# 03: The tutor teaches generic steps with tags

Spec: `../spec.md`. ADR: `docs/adr/0007-generic-steps-with-tags-and-components.md`.

**What to build:** Through the tutor tools, a step is named by what it does and never by a program. `teach_step` refuses a name that contains a technology name or a program's process name and says why, accepts optional pattern tags, and teaching a step name that already exists on a new technology adds a locator there instead of replacing the step. Technology tags are the technologies of a step's locators; they are not stored. Pattern tags are stored with the step by name. (Spec stories 29 to 33.)

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Teaching "Save" in Paint and then in Excel gives one step with two technologies, each with its own measured effect and counters
- [ ] Teaching "Save workbook" or "Excel save" is refused with a message that names the rule; nothing is saved
- [ ] Pattern tags given when teaching are kept and returned; teaching again on another technology does not lose them
- [ ] Consent and private-technology rules behave as before, per step and technology
- [ ] Behaviour is proven by MCP tests through the in-process client with the stand-in desktop, red before green; existing tutor tests are updated with the model
