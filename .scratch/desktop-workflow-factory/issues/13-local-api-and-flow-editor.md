# 13: Local API and flow editor

**What to build:** The Python app serves a local HTTP API on `127.0.0.1` behind a token, plus the flow editor screen built with React Flow in `web/`: palette from stored lessons, connect nodes, configure typed inputs, run a flow, and see live per-node status. The bundle is prebuilt so users need no Node.

**Blocked by:** 10

**Status:** ready-for-agent

- [ ] Requests without the token are rejected; the server binds only to loopback
- [ ] The palette lists lessons from the user and factory databases
- [ ] A flow built in the editor is saved to SQLite and runs
- [ ] Live per-node status updates while a flow runs
- [ ] Frontend tested separately against the local API
