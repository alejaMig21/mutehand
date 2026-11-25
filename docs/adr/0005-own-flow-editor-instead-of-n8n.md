---
status: accepted
---

# Flows are edited in our own React Flow editor, not in n8n

The product needs an n8n-like visual editor, but n8n's Sustainable Use License forbids commercial redistribution. v1 ships its own editor built on React Flow (MIT), served by the Python app on 127.0.0.1 behind a token, with a prebuilt bundle so users need no Node. Flows are stored in SQLite; this adds a TypeScript frontend beside the Python code.

## Clarification (ticket 13)

The editor is plain JavaScript with JSX (React 19 + `@xyflow/react`), not TypeScript. It is one small component and a thin API client, and the real contract is the JSON the Python API validates, so a type layer would add a second toolchain without catching more. Revisit if the frontend grows beyond the five screens.
