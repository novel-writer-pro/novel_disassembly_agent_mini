---
name: imitation-constraint-pack
description: Gather branch context, rule constraints, relationship state, unresolved threads, and carry-over memory into a machine-readable imitation constraint pack before draft generation.
---

# Imitation Constraint Pack

Use this skill before any imitation draft is generated.

## Inputs
- Source imitation plan
- Branch context / state summary
- Optional mapping pack
- Optional previous carry-over state

## Outputs
- Hard constraints
- Soft constraints
- Forbidden transformations
- Continuity memory pack

## Rules
- Prefer evidence-backed constraints over speculative guidance.
- Keep world-rule and relationship constraints explicit.
- Surface continuity debt rather than hiding it.
