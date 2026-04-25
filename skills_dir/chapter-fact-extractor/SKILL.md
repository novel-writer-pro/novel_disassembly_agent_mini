---
name: chapter-fact-extractor
description: Extract factual layer JSON for a chapter, including characters, events, relations, conflicts, and foreshadowing without inventing unsupported plot facts.
---

# Chapter Fact Extractor

Use this skill when a chapter needs factual extraction before any higher-level literary analysis.

## Inputs
- Intake output JSON
- Optional prior chapter facts/window summary

## Outputs
- Character mentions
- Event list
- Relations
- Conflict records
- Foreshadowing candidates
- Explicit worldbuilding facts

## Rules
- Prefer direct textual evidence.
- Do not fabricate plot details not present in the chapter.
- Separate explicit facts from tentative guesses.
- If uncertain, lower confidence instead of expanding the claim.
