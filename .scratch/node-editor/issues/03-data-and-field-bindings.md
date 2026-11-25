# 03: Data and field bindings in the engine

**What to build:** Every node takes in and gives out Data (named fields); a node's field is stored as a fixed value, a reference to another node's output, or an expression kept for later. The run context becomes the Data a workday starts with; typed inputs give way to Data.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Data flows from one node to the next in a run and is checkpointed
- [ ] A saved flow with fixed and referenced fields loads, runs and round-trips
- [ ] The stored field form has room for expressions without a migration
