"""Reader feedback ingestion and summarization."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ReaderFeedbackCommentRecord


class ReaderFeedbackService:
    """Store and summarize reader comments for a branch."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return ("relation" in message and "does not exist" in message) or "no such table" in message

    @staticmethod
    def _normalize_sentiment(comment_text: str) -> str:
        text = comment_text.lower()
        if any(token in text for token in ["好", "爽", "喜欢", "期待", "想看"]):
            return "positive"
        if any(token in text for token in ["慢", "拖", "无聊", "弃", "看不懂", "突兀", "乱"]):
            return "negative"
        return "mixed"

    @staticmethod
    def _signal_from_text(comment_text: str) -> str:
        text = comment_text.lower()
        if any(token in text for token in ["节奏", "慢", "拖"]):
            return "pacing_slow"
        if any(token in text for token in ["逻辑", "不通", "看不懂", "突兀"]):
            return "logic_confusion"
        if any(token in text for token in ["角色", "人设", "性格"]):
            return "character_ooc"
        if any(token in text for token in ["期待", "想看", "继续"]):
            return "reader_hook_strong"
        if any(token in text for token in ["更新", "短", "太少"]):
            return "update_frequency"
        return "general_feedback"

    def record_comment(
        self,
        branch_id: str,
        comment_text: str,
        *,
        chapter_index: int = 0,
        source: str = "manual",
        sentiment: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ReaderFeedbackCommentRecord:
        record = ReaderFeedbackCommentRecord(
            branch_id=branch_id,
            chapter_index=chapter_index,
            source=source,
            comment_text=comment_text,
            sentiment=sentiment or self._normalize_sentiment(comment_text),
            metadata_json=metadata or {},
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def import_comments(
        self,
        branch_id: str,
        comments: list[dict[str, Any]],
    ) -> dict[str, object]:
        created = []
        for item in comments:
            if not isinstance(item, dict):
                continue
            text = str(item.get("comment_text", "")).strip()
            if not text:
                continue
            record = self.record_comment(
                branch_id,
                text,
                chapter_index=int(item.get("chapter_index", 0) or 0),
                source=str(item.get("source", "manual")),
                sentiment=str(item.get("sentiment", "") or "") or None,
                metadata={k: v for k, v in item.items() if k not in {"comment_text", "chapter_index", "source", "sentiment"}},
            )
            created.append(record.id)
        return {
            "contract_version": "reader-feedback-import.v1",
            "created_count": len(created),
            "created_ids": created,
        }

    def summarize_branch_feedback(self, branch_id: str, *, limit: int = 10) -> dict[str, object]:
        try:
            rows = self.session.scalars(
                select(ReaderFeedbackCommentRecord)
                .where(ReaderFeedbackCommentRecord.branch_id == branch_id)
                .where(ReaderFeedbackCommentRecord.deleted_at.is_(None))
                .order_by(ReaderFeedbackCommentRecord.created_at.desc())
            ).all()
        except (OperationalError, ProgrammingError) as exc:
            if self._is_missing_relation_error(exc):
                return {
                    "contract_version": "reader-feedback-summary.v1",
                    "degraded": True,
                    "reason": "reader_feedback_table_unavailable_for_current_runtime",
                    "comment_count": 0,
                    "signals": [],
                    "pain_point_hypotheses": [],
                    "revision_recommendations": [],
                }
            raise

        comment_texts = [str(row.comment_text).strip() for row in rows if str(row.comment_text).strip()]
        signals = [self._signal_from_text(text) for text in comment_texts]
        signal_counts = Counter(signals)
        top_signals = [item for item, _ in signal_counts.most_common(limit)]
        pain_point_hypotheses = []
        if signal_counts.get("pacing_slow"):
            pain_point_hypotheses.append("读者可能认为当前章节节奏偏慢。")
        if signal_counts.get("logic_confusion"):
            pain_point_hypotheses.append("读者可能对部分逻辑/衔接存在疑惑。")
        if signal_counts.get("character_ooc"):
            pain_point_hypotheses.append("读者可能感到人物反应与既有人设不一致。")
        if signal_counts.get("reader_hook_strong"):
            pain_point_hypotheses.append("读者对后续情节仍有持续追读意愿。")
        if not pain_point_hypotheses and comment_texts:
            pain_point_hypotheses.append("当前反馈更偏通用体验反馈，未出现明显结构性阻断。")
        revision_recommendations = []
        if signal_counts.get("pacing_slow"):
            revision_recommendations.append("压缩中段铺垫，增强行动推进密度。")
        if signal_counts.get("logic_confusion"):
            revision_recommendations.append("补足前因后果和转折证据，降低理解门槛。")
        if signal_counts.get("character_ooc"):
            revision_recommendations.append("回看角色卡与动机树，修正角色反应。")
        if signal_counts.get("reader_hook_strong"):
            revision_recommendations.append("保留章尾钩子并加强下一章期待。")
        return {
            "contract_version": "reader-feedback-summary.v1",
            "degraded": False,
            "comment_count": len(comment_texts),
            "signals": top_signals,
            "signal_counts": dict(signal_counts),
            "pain_point_hypotheses": pain_point_hypotheses[:limit],
            "revision_recommendations": revision_recommendations[:limit],
            "sample_comments": comment_texts[:limit],
        }
