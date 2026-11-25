# 09: Tutor MCP tools

**What to build:** The project's own MCP tools let Claude Code observe an app (summarized), set the study order, name and save a lesson (autosaved once its effect is measured), list open doubts, and answer them by teaching or fixing a lesson. Observations of apps marked private are reduced to roles and counts. The tools never expose force or trace screenshots, and never return secret values.

**Blocked by:** 06, 07

**Status:** ready-for-agent

- [ ] Observe returns a summarized snapshot; private apps return roles and counts only
- [ ] A lesson is saved as soon as its effect is measured; an interrupted study resumes
- [ ] Listing doubts returns only open ones; answering marks them answered
- [ ] Meeting a sensitive category stops the tutor flow and asks for consent before saving
- [ ] The tool surface contains no force option and no screenshot-tracing option
