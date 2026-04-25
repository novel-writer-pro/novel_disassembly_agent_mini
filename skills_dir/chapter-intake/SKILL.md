---
name: chapter-intake
description: Normalize one chapter into model-friendly structural units such as cleaned text, paragraph blocks, dialogue candidates, scene candidates, and explicit task constraints before downstream extraction.
---

# Chapter Intake

Use this skill at the very start of chapter processing when a small model needs a constrained, regularized view of raw chapter text.

## Inputs
- Raw chapter text
- Chapter index / normalized title
- Optional previous-chapter summary

## Outputs
- Cleaned text
- Paragraph blocks with stable order
- Dialogue candidate snippets
- Scene block candidates
- Processing constraints for downstream skills

## Rules
- Do not analyze plot or infer motives.
- Preserve order and wording where possible.
- Remove only obvious formatting noise or duplicated headings.
- Prefer omission over accidental rewrite.
