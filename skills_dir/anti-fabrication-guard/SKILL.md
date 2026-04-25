---
name: anti-fabrication-guard
description: Review chapter JSON for unsupported inferences, weak evidence coverage, and possible fabricated plot claims.
---

# Anti Fabrication Guard

Use this skill as a quality gate after fact and analysis generation.

## Inputs
- Fact-layer JSON
- Analysis-layer JSON
- Optional writer-learning JSON

## Outputs
- Unsupported inferences
- Ambiguous points
- Overclaim flags
- Human review recommendation

## Rules
- Flag unsupported claims.
- Prefer omission over invention.
- Emit review notes in deterministic JSON.
- Keep facts and interpretations separate.
