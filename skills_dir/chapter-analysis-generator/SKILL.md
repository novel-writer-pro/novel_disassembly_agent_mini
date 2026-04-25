---
name: chapter-analysis-generator
description: Generate the analytical layer for a chapter from the factual layer, including summaries, pacing, themes, emotional curve, and continuity notes.
---

# Chapter Analysis Generator

Use this skill after evidence-bound facts are available.

## Inputs
- Evidence-bound fact JSON
- Optional prior window summary

## Outputs
- Chapter summaries
- Themes
- Pacing
- Emotional curve
- Continuity notes

## Rules
- Build analysis on top of extracted facts.
- Keep JSON output schema-compliant.
- Distinguish interpretation from fact.
- If analysis depends on uncertain facts, carry forward lower confidence.
