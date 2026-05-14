"""Reference-based imitation evaluation service.

Compares a generated draft against the original chapter text using LLM-as-judge.
Unlike pairwise eval (A vs B), this evaluates how well a single draft captures
the original's structure, style, and narrative qualities.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReferenceEvalDimension:
    score: float
    reason: str = ""


@dataclass
class ReferenceEvalResult:
    branch_id: str
    chapter_index: int
    overall_fidelity: float
    confidence: float
    dimensions: dict[str, ReferenceEvalDimension] = field(default_factory=dict)
    evaluation_method: str = "llm_reference_judge"
    suggestion: str = ""

    def to_signal(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "chapter_index": self.chapter_index,
            "overall_fidelity": self.overall_fidelity,
            "confidence": self.confidence,
            "dimensions": {
                k: {"score": v.score, "reason": v.reason}
                for k, v in self.dimensions.items()
            },
            "evaluation_method": self.evaluation_method,
            "suggestion": self.suggestion,
        }


_REFERENCE_JUDGE_PROMPT = """\
你是一位专业的小说编辑，正在评估一篇仿写草案与原文的相似程度。

【原文摘录】
{original_text}

【仿写草案】
{draft_text}

【章节目标】
{chapter_goal}

请从以下六个维度评估仿写草案对原文的还原程度（0.0-1.0，1.0 表示完美还原）：

1. structure_fidelity（结构还原）：场景节拍、推进节奏是否与原文一致
2. character_fidelity（角色还原）：角色行为、语气、动机是否与原文一致
3. style_fidelity（风格还原）：文风、用词习惯、叙事视角是否与原文一致
4. continuity_fidelity（连续性还原）：是否正确承接前文、保持世界观一致
5. tension_fidelity（张力还原）：冲突密度、悬念设置是否与原文水平匹配
6. information_density（信息密度）：每千字推进量是否与原文匹配

严格按以下 JSON 格式输出，不要输出其他内容：
{{
  "overall_fidelity": 0.0到1.0之间的浮点数,
  "confidence": 0.0到1.0之间的浮点数,
  "suggestion": "一句话改进建议",
  "dimensions": {{
    "structure_fidelity": {{"score": 0.0到1.0, "reason": "..."}},
    "character_fidelity": {{"score": 0.0到1.0, "reason": "..."}},
    "style_fidelity": {{"score": 0.0到1.0, "reason": "..."}},
    "continuity_fidelity": {{"score": 0.0到1.0, "reason": "..."}},
    "tension_fidelity": {{"score": 0.0到1.0, "reason": "..."}},
    "information_density": {{"score": 0.0到1.0, "reason": "..."}}
  }}
}}
"""

_DIMENSIONS = [
    "structure_fidelity",
    "character_fidelity",
    "style_fidelity",
    "continuity_fidelity",
    "tension_fidelity",
    "information_density",
]


class ReferenceEvalService:
    """Evaluate imitation draft against original text using LLM-as-judge."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        original_text: str,
        draft_text: str,
        chapter_goal: str = "",
    ) -> ReferenceEvalResult:
        if self._llm is not None:
            try:
                return self._llm_evaluate(
                    branch_id=branch_id,
                    chapter_index=chapter_index,
                    original_text=original_text,
                    draft_text=draft_text,
                    chapter_goal=chapter_goal,
                )
            except Exception:  # noqa: BLE001
                pass
        return self._heuristic_evaluate(
            branch_id=branch_id,
            chapter_index=chapter_index,
            original_text=original_text,
            draft_text=draft_text,
        )

    def _llm_evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        original_text: str,
        draft_text: str,
        chapter_goal: str,
    ) -> ReferenceEvalResult:
        prompt = _REFERENCE_JUDGE_PROMPT.format(
            original_text=original_text[:3000],
            draft_text=draft_text[:3000],
            chapter_goal=chapter_goal or "（未指定）",
        )
        raw = self._llm.chat(prompt)
        return self._parse_response(raw, branch_id=branch_id, chapter_index=chapter_index)

    def _parse_response(
        self, raw: str, *, branch_id: str, chapter_index: int
    ) -> ReferenceEvalResult:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return self._fallback_result(branch_id, chapter_index, "no JSON in response")
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return self._fallback_result(branch_id, chapter_index, "invalid JSON")

        overall = float(data.get("overall_fidelity", 0.5))
        confidence = float(data.get("confidence", 0.5))
        suggestion = str(data.get("suggestion", ""))
        dims_raw = data.get("dimensions", {})
        dimensions: dict[str, ReferenceEvalDimension] = {}
        for dim in _DIMENSIONS:
            d = dims_raw.get(dim, {})
            if isinstance(d, dict):
                dimensions[dim] = ReferenceEvalDimension(
                    score=float(d.get("score", 0.5)),
                    reason=str(d.get("reason", "")),
                )
            else:
                dimensions[dim] = ReferenceEvalDimension(score=0.5)

        return ReferenceEvalResult(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_fidelity=overall,
            confidence=confidence,
            dimensions=dimensions,
            evaluation_method="llm_reference_judge",
            suggestion=suggestion,
        )

    def _heuristic_evaluate(
        self,
        *,
        branch_id: str,
        chapter_index: int,
        original_text: str,
        draft_text: str,
    ) -> ReferenceEvalResult:
        orig_len = len(original_text)
        draft_len = len(draft_text)
        length_ratio = min(draft_len, orig_len) / max(draft_len, orig_len) if max(draft_len, orig_len) > 0 else 0.0

        orig_chars = set(original_text)
        draft_chars = set(draft_text)
        char_overlap = len(orig_chars & draft_chars) / len(orig_chars | draft_chars) if orig_chars | draft_chars else 0.0

        fidelity = round(length_ratio * 0.4 + char_overlap * 0.6, 4)
        dimensions = {
            dim: ReferenceEvalDimension(score=fidelity, reason="heuristic")
            for dim in _DIMENSIONS
        }

        return ReferenceEvalResult(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_fidelity=fidelity,
            confidence=0.3,
            dimensions=dimensions,
            evaluation_method="heuristic_reference",
        )

    @staticmethod
    def _fallback_result(
        branch_id: str, chapter_index: int, reason: str
    ) -> ReferenceEvalResult:
        return ReferenceEvalResult(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_fidelity=0.5,
            confidence=0.0,
            dimensions={
                dim: ReferenceEvalDimension(score=0.5) for dim in _DIMENSIONS
            },
            evaluation_method="fallback",
            suggestion=f"evaluation failed: {reason}",
        )
