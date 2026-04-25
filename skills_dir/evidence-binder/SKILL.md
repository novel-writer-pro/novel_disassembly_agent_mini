---
name: evidence-binder
description: Bind each extracted fact or analysis claim to explicit source evidence spans, offsets, and confidence so unsupported items can be downgraded or removed.
---

# Evidence Binder

Use this skill after fact extraction and before analysis generation.

## Inputs
- Fact extraction JSON
- Cleaned chapter text

## Outputs
- Fact records with evidence spans
- Unsupported item list
- Coverage summary

## Rules
- Every kept item must have at least one evidence snippet.
- If evidence is weak, lower confidence or move item to unsupported.
- Do not create new facts here.
