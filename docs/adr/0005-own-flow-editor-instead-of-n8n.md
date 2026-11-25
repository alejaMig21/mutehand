---
status: accepted
---

# Flows are edited in our own React Flow editor, not in n8n

The product needs an n8n-like visual editor, but n8n's Sustainable Use License forbids commercial redistribution. v1 ships its own editor built on React Flow (MIT), served by the Python app on 127.0.0.1 behind a token, with a prebuilt bundle so users need no Node. Flows are stored in SQLite; this adds a TypeScript frontend beside the Python code.
