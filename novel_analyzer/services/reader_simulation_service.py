"""Loom Phase 5: Reader simulation service.

Simulates four reader panel perspectives using existing DB data:
  casual     – readability and engagement (hook density proxy)
  veteran    – genre convention adherence (conflict/surprise balance)
  satisfaction – emotional payoff (climax score proxy)
  editor     – structural quality (tension + style drift)

No new LLM calls required for the heuristic path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from novel_analyzer.services.rhythm_analysis_service import RhythmAnalysisService
from novel_analyzer.services.style_calibration_service import StyleCalibrationService
from novel_analyzer.services.tension_service import TensionService

PANEL_TYPES: frozenset[str] = frozenset({"casual", "veteran", "satisfaction", "editor"})


@dataclass
class ReaderSimSignal:
    panel_type: str
    score: float
    alert_level: str  # "none" | "warn" | "critical"
    feedback: str


@dataclass
class ReaderSatisfactionScore:
    branch_id: str
    chapter_index: int
    overall_score: float
    alert_level: str  # "none" | "warn" | "critical"
    panels: list[ReaderSimSignal] = field(default_factory=list)
    suggestion: str = ""

    def to_reader_satisfaction(self) -> dict[str, object]:
        return {
            "branch_id": self.branch_id,
            "chapter_index": self.chapter_index,
            "overall_score": self.overall_score,
            "alert_level": self.alert_level,
            "suggestion": self.suggestion,
            "panels": [
                {
                    "panel_type": p.panel_type,
                    "score": p.score,
                    "alert_level": p.alert_level,
                    "feedback": p.feedback,
                }
                for p in self.panels
            ],
        }


class ReaderSimulationService:
    """Simulate reader panel perspectives using existing Loom signals."""

    WARN_THRESHOLD: float = 0.50
    CRITICAL_THRESHOLD: float = 0.35

    def __init__(self, session: Session) -> None:
        self.session = session
        self._tension_svc = TensionService(session)
        self._style_svc = StyleCalibrationService(session)
        self._rhythm_svc = RhythmAnalysisService(session)

    def simulate_all_panels(
        self,
        branch_id: str,
        chapter_index: int,
        lookback_n: int = 3,
    ) -> ReaderSatisfactionScore:
        tension = self._tension_svc.compute(branch_id, chapter_index, lookback_n)
        style = self._style_svc.compute_style_drift(branch_id, chapter_index)
        rhythm = self._rhythm_svc.compute(branch_id, chapter_index, lookback_n)

        panels = [
            self._casual_panel(rhythm),
            self._veteran_panel(tension),
            self._satisfaction_panel(rhythm, tension),
            self._editor_panel(tension, style),
        ]

        overall = round(sum(p.score for p in panels) / len(panels), 4)
        alert = self._classify_alert(overall)
        suggestion = self._build_suggestion(panels, alert)

        return ReaderSatisfactionScore(
            branch_id=branch_id,
            chapter_index=chapter_index,
            overall_score=overall,
            alert_level=alert,
            panels=panels,
            suggestion=suggestion,
        )

    def _casual_panel(self, rhythm: object) -> ReaderSimSignal:
        hook_density = float(getattr(rhythm, "hook_density", 0.0))
        score = min(1.0, hook_density / 2.0)
        score = round(score, 4)
        alert = "warn" if score < self.WARN_THRESHOLD else "none"
        feedback = (
            f"爽点密度 {hook_density:.2f}/千字，"
            + ("读者可能感到平淡" if alert == "warn" else "节奏尚可")
        )
        return ReaderSimSignal(panel_type="casual", score=score, alert_level=alert, feedback=feedback)

    def _veteran_panel(self, tension: object) -> ReaderSimSignal:
        conflict_density = float(getattr(tension, "conflict_density", 0.0))
        surprise_index = float(getattr(tension, "surprise_index", 0.0))
        score = round((min(conflict_density / 1.5, 1.0) * 0.5 + surprise_index * 0.5), 4)
        alert = "warn" if score < self.WARN_THRESHOLD else "none"
        feedback = (
            f"冲突密度 {conflict_density:.2f}，新颖度 {surprise_index:.2f}，"
            + ("题材套路感偏强" if alert == "warn" else "符合题材惯例")
        )
        return ReaderSimSignal(panel_type="veteran", score=score, alert_level=alert, feedback=feedback)

    def _satisfaction_panel(self, rhythm: object, tension: object) -> ReaderSimSignal:
        climax_score = float(getattr(rhythm, "climax_score", 0.0))
        tension_score = float(getattr(tension, "tension_score", 0.0))
        score = round((climax_score * 0.6 + tension_score * 0.4), 4)
        alert = "warn" if score < self.WARN_THRESHOLD else "none"
        feedback = (
            f"高潮评分 {climax_score:.2f}，张力 {tension_score:.2f}，"
            + ("爽感不足" if alert == "warn" else "情绪满足度良好")
        )
        return ReaderSimSignal(panel_type="satisfaction", score=score, alert_level=alert, feedback=feedback)

    def _editor_panel(self, tension: object, style: object) -> ReaderSimSignal:
        tension_score = float(getattr(tension, "tension_score", 0.0))
        drift = float(getattr(style, "style_drift_score", 0.0))
        style_score = max(0.0, 1.0 - drift * 2)
        score = round((tension_score * 0.5 + style_score * 0.5), 4)
        alert = "warn" if score < self.WARN_THRESHOLD else "none"
        feedback = (
            f"张力 {tension_score:.2f}，风格漂移 {drift:.2f}，"
            + ("结构或风格需调整" if alert == "warn" else "结构质量良好")
        )
        return ReaderSimSignal(panel_type="editor", score=score, alert_level=alert, feedback=feedback)

    def _classify_alert(self, score: float) -> str:
        if score < self.CRITICAL_THRESHOLD:
            return "critical"
        if score < self.WARN_THRESHOLD:
            return "warn"
        return "none"

    def _build_suggestion(self, panels: list[ReaderSimSignal], alert: str) -> str:
        if alert == "none":
            return ""
        warn_panels = [p.panel_type for p in panels if p.alert_level != "none"]
        if not warn_panels:
            return ""
        return f"以下读者视角评分偏低：{', '.join(warn_panels)}，建议针对性优化"
