# 07: Steps that read values out of an app

**What to build:** A basic operation that reads text or a value from a control and gives it out as Data, so a later node can use it. Private apps give only what the person allows.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] Reading is free of the input lock and never prints values into reports unless enabled
- [ ] The consent gate covers reading from a private app
- [ ] A read step's output is checked by a test on a fake desktop
