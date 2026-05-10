"""Loom pairwise evaluation service (LLM-as-judge).

Compares two chapter drafts and returns a structured preference verdict
with per-dimension scores.  Output feeds into 0509 session_primary_verdicts
as chapter_quality_score.

When no LLM client is available (e.g. in unit tests) the service falls back
to a heuristic scorer based on risk-checker results and text length.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DimensionResult:
    winner: str          # "A" | "B" | "tie"
    reason: str = ""
    score_diff: float = 0.0


@dataclass
class PairwiseResult:
    pair_id: str
    branch_id: str
    chapter_index: int
    overall_preference: str          # "A" | "B" | "tie"
    overall_reason: str
    confidence: float
    dimensions: dict[str, DimensionResult] = field(default_factory=dict)
    evaluation_method: str = "llm_judge"
    loom_version: str = "1.0"

    # Scalar quality score for the preferred draft (0-1)
    @property
    def quality_score(self) -> float:
        if self.overall_preference == "tie":
            return 0.5
        wins = sum(
            1 for d in self.dimensions.values()
            if d.winner == self.overall_preference
        )
        total = len(self.dimensions) or 1
        base = 0.5 + (wins / total) * 0.4
        return round(min(1.0, base * self.confidence), 4)

    def to_chapter_quality_signal(self) -> dict[str, Any]:
        """Compact dict for 0509 session_primary_verdicts consumption."""
        return {
            "chapter_index": self.chapter_index,
            "branch_id": self.branch_id,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "overall_preference": self.overall_preference,
            "dimensions": {
                k: {"winner": v.winner, "score_diff": v.score_diff}
                for k, v in self.dimensions.items()
            },
            "evaluation_method": self.evaluation_method,
            "loom_version": self.loom_version,
        }


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """\
你是一位专业的小说编辑，正在评估同一章节的两个仿写草案。

【章节目标】
{chapter_goal}

【关键约束】
{key_constraints}

【草案 A】
{draft_a}

【草案 B】
{draft_b}

请从以下五个维度评估哪个草案更好：
1. character_consistency（角色一致性）：角色行为是否符合其性格和动机
2. plot_coherence（情节连贯性）：情节推进是否自然，有无逻辑跳跃
3. style_fidelity（风格忠实度）：是否保持原著风格
4. narrative_tension（叙事张力）：是否有足够的冲突和悬念
5. dialogue_quality（对话质量）：角色说话风格是否有辨识度，对话是否推进情节

严格按以下 JSON 格式输出，不要输出其他内容：
{{
  "overall_preference": "A" 或 "B" 或 "tie",
  "overall_reason": "一句话说明",
  "confidence": 0.0到1.0之间的浮点数,
  "dimensions": {{
    "character_consistency": {{"winner": "A"或"B"或"tie", "reason": "...", "score_diff": 0.0到1.0}},
    "plot_coherence": {{"winner": "A"或"B"或"tie", "reason": "...", "score_diff": 0.0到1.0}},
    "style_fidelity": {{"winner": "A"或"B"或"tie", "reason": "...", "score_diff": 0.0到1.0}},
    "narrative_tension": {{"winner": "A"或"B"或"tie", "reason": "...", "score_diff": 0.0到1.0}},
    "dialogue_quality": {{"winner": "A"或"B"或"tie", "reason": "...", "score_diff": 0.0到1.0}}
  }}
}}
"""

_DIMENSIONS = [
    "character_consistency",
    "plot_coherence",
    "style_fidelity",
    "narrative_tension",
    "dialogue_quality",
]


class PairwiseEvalService:
    """LLM-as-judge pairwise evaluation.

    Parameters
    ----------
    llm_client:
        Any object with a ``chat(prompt: str) -> str`` method.
        Pass ``None`` to use the heuristic fallback (useful in tests).
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        *,
        pair_id: str,
        branch_id: str,
        chapter_index: int,
        draft_a: str,
        draft_b: str,
        chapter_goal: str = "",
        key_constraints: str = "",
        risk_verdict_a: str = "unknown",
        risk_verdict_b: str = "unknown",
    ) -> PairwiseResult:
        """Compare two drafts and return a PairwiseResult."""
        if self._llm is not None:
            return self._llm_evaluate(
                pair_id=pair_id,
                branch_id=branch_id,
                chapter_index=chapter_index,
                draft_a=draft_a,
                draft_b=draft_b,
                chapter_goal=chapter_goal,
                key_constraints=key_constraints,
            )
        return self._heuristic_evaluate(
            pair_id=pair_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            draft_a=draft_a,
            draft_b=draft_b,
            risk_verdict_a=risk_verdict_a,
            risk_verdict_b=risk_verdict_b,
        )

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_evaluate(
        self,
        *,
        pair_id: str,
        branch_id: str,
        chapter_index: int,
        draft_a: str,
        draft_b: str,
        chapter_goal: str,
        key_constraints: str,
    ) -> PairwiseResult:
        prompt = _JUDGE_PROMPT.format(
            chapter_goal=chapter_goal or "（未指定）",
            key_constraints=key_constraints or "（未指定）",
            draft_a=draft_a[:3000],
            draft_b=draft_b[:3000],
        )
        raw = self._llm.chat(prompt)
        return self._parse_llm_response(
            raw,
            pair_id=pair_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
        )

    def _parse_llm_response(
        self,
        raw: str,
        *,
        pair_id: str,
        branch_id: str,
        chapter_index: int,
    ) -> PairwiseResult:
        # Extract JSON block
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return self._fallback_result(pair_id, branch_id, chapter_index, "parse_error")
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return self._fallback_result(pair_id, branch_id, chapter_index, "json_error")

        preference = str(data.get("overall_preference", "tie")).strip()
        if preference not in ("A", "B", "tie"):
            preference = "tie"

        dims: dict[str, DimensionResult] = {}
        raw_dims = data.get("dimensions", {})
        for dim in _DIMENSIONS:
            d = raw_dims.get(dim, {})
            winner = str(d.get("winner", "tie")).strip()
            if winner not in ("A", "B", "tie"):
                winner = "tie"
            dims[dim] = DimensionResult(
                winner=winner,
                reason=str(d.get("reason", "")),
                score_diff=float(d.get("score_diff", 0.0)),
            )

        return PairwiseResult(
            pair_id=pair_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_preference=preference,
            overall_reason=str(data.get("overall_reason", "")),
            confidence=float(data.get("confidence", 0.7)),
            dimensions=dims,
            evaluation_method="llm_judge",
        )

    # ------------------------------------------------------------------
    # Heuristic fallback (no LLM)
    # ------------------------------------------------------------------

    def _heuristic_evaluate(
        self,
        *,
        pair_id: str,
        branch_id: str,
        chapter_index: int,
        draft_a: str,
        draft_b: str,
        risk_verdict_a: str,
        risk_verdict_b: str,
    ) -> PairwiseResult:
        """Simple heuristic: prefer the draft with 'pass' verdict and more content."""
        score_a = self._heuristic_score(draft_a, risk_verdict_a)
        score_b = self._heuristic_score(draft_b, risk_verdict_b)

        if abs(score_a - score_b) < 0.05:
            preference = "tie"
        elif score_a > score_b:
            preference = "A"
        else:
            preference = "B"

        dims = {
            dim: DimensionResult(
                winner=preference,
                reason="heuristic",
                score_diff=round(abs(score_a - score_b), 3),
            )
            for dim in _DIMENSIONS
        }

        return PairwiseResult(
            pair_id=pair_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_preference=preference,
            overall_reason="heuristic fallback (no LLM)",
            confidence=0.5,
            dimensions=dims,
            evaluation_method="heuristic",
        )

    @staticmethod
    def _heuristic_score(draft: str, risk_verdict: str) -> float:
        base = 0.5
        if risk_verdict == "pass":
            base += 0.3
        elif risk_verdict == "revise":
            base -= 0.1
        # Slight preference for longer drafts (more content)
        length_bonus = min(len(draft) / 10000, 0.2)
        return base + length_bonus

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_result(
        pair_id: str, branch_id: str, chapter_index: int, reason: str
    ) -> PairwiseResult:
        return PairwiseResult(
            pair_id=pair_id,
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_preference="tie",
            overall_reason=f"evaluation failed: {reason}",
            confidence=0.0,
            dimensions={
                dim: DimensionResult(winner="tie") for dim in _DIMENSIONS
            },
            evaluation_method="fallback",
        )
