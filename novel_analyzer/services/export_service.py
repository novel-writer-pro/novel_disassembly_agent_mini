"""Export helpers for directly usable branch and chapter bundles."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from novel_analyzer.database.models import (
    ChapterArtifact,
    ClusterReviewRecord,
    ChapterRiskCardRecord,
    FactRecord,
    GateCheckerResultRecord,
    GraphEdge,
    GraphNode,
    RetrievalDocument,
    WindowArtifact,
)
from novel_analyzer.domain.schemas import BranchQAContextOutput, ChapterQAContextOutput
from novel_analyzer.runtime.cluster_review_state import read_cluster_review_state
from novel_analyzer.services.causal_graph_service import CausalGraphService, CAUSAL_EDGE_TYPES
from novel_analyzer.services.cluster_review_service import (
    ClusterReviewService,
    ClusterReviewStorageUnavailable,
)
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.foreshadowing_service import ForeshadowingService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.run_service import RunService
from novel_analyzer.services.status_service import StatusService


class ExportService:
    """Build directly consumable JSON bundles for branches and chapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.status_service = StatusService(session)
        self.chapter_index_service = ChapterIndexService(session)
        self.graph_service = GraphService(session)
        self.run_service = RunService(session)
        self.cluster_review_service = ClusterReviewService(session)
        self.foreshadowing_service = ForeshadowingService(session)
        self.causal_graph = CausalGraphService(session)

    @staticmethod
    def _is_missing_relation_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return ("relation" in message and "does not exist" in message) or "no such table" in message

    @staticmethod
    def _severity_rank(level: str | None) -> int:
        return {
            None: -1,
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3,
        }.get(level, -1)

    @staticmethod
    def _risk_specificity_rank(risk_type: str | None) -> int:
        normalized = str(risk_type or '').strip()
        if normalized in {'human_review_candidate', 'rule_review_candidate', 'logic_review_candidate', 'timeline_review_candidate', 'power_review_candidate'}:
            return 0
        if normalized in {'title_only_inference_candidate'}:
            return -1
        if normalized.endswith('_candidate'):
            return 1
        return 2

    @staticmethod
    def _dedupe_preview(items: list[object], limit: int) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
            if len(result) >= limit:
                break
        return result

    @classmethod
    def _suppress_generic_review_candidates(
        cls,
        risks: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if not risks:
            return []
        has_specific = any(
            cls._risk_specificity_rank(cast(str | None, risk.get('risk_type'))) > 0
            for risk in risks
        )
        if not has_specific:
            return risks
        filtered = [
            risk for risk in risks
            if cls._risk_specificity_rank(cast(str | None, risk.get('risk_type'))) > 0
        ]
        return filtered or risks

    @staticmethod
    def _derive_cluster_status(
        *,
        chapter_count: int,
        max_confidence: float,
        review_priority_value: str,
    ) -> str:
        """Derive a minimal runtime status for one cluster.

        Current semantics are runtime-only heuristics:
        - needs_review: should be surfaced first to humans
        - open: candidate cluster exists but urgency is lower
        - resolved: reserved for future workflow write-back
        """
        if review_priority_value == 'P1':
            return 'needs_review'
        if chapter_count >= 3 or max_confidence >= 0.5:
            return 'needs_review'
        return 'open'

    @staticmethod
    def _cluster_pattern_rank(pattern_label: str | None) -> int:
        return {
            '持续型问题': 2,
            '集中爆发型问题': 1,
            '单点问题': 0,
        }.get(str(pattern_label or '').strip(), -1)

    @staticmethod
    def _review_result_label(review_result: str | None) -> str | None:
        return {
            'confirmed-issue': '确认有问题',
            'confirmed-benign': '确认无问题',
            'needs-escalation': '需要升级处理',
            'deferred': '暂缓判断',
            '': None,
        }.get(str(review_result or '').strip(), str(review_result or '').strip() or None)

    @classmethod
    def _build_review_summary(
        cls,
        *,
        review_candidate_clusters: list[dict[str, object]],
        review_storage_mode: str,
    ) -> dict[str, object]:
        by_status: dict[str, int] = {}
        by_result: dict[str, int] = {}
        by_owner: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        by_latest_event_type: dict[str, int] = {}
        by_workflow_lane: dict[str, int] = {}
        by_queue_priority: dict[str, int] = {}
        by_deadline_level: dict[str, int] = {}
        by_batch_operation_hint: dict[str, int] = {}
        by_escalation_tier: dict[str, int] = {}
        by_auto_next_action_code: dict[str, int] = {}
        by_auto_next_action: dict[str, int] = {}
        by_escalation_reason_code: dict[str, int] = {}
        by_escalation_reason: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_pattern: dict[str, int] = {}
        by_phase2_focus: dict[str, int] = {}
        pending_assignment_count = 0
        pending_escalation_count = 0
        resolved_count = 0
        needs_review_count = 0
        action_required_count = 0
        close_ready_count = 0
        latest_review_at = ""
        latest_review_owner = ""
        latest_review_actor = ""
        latest_review_event_type = ""
        latest_review_result = ""

        for item in review_candidate_clusters:
            status_key = str(item.get('cluster_status') or '').strip()
            result_key = str(item.get('review_result') or '').strip()
            owner_key = str(item.get('review_owner') or '').strip()
            priority_key = str(item.get('review_priority') or '').strip()
            pattern_key = str(item.get('pattern_label') or '').strip()
            workflow_lane_key = str(item.get('workflow_lane') or '').strip()
            queue_priority_key = str(item.get('queue_priority') or '').strip()
            deadline_level_key = str(item.get('suggested_deadline_level') or '').strip()
            batch_operation_hint_key = str(item.get('batch_operation_hint') or '').strip()
            escalation_tier_key = str(item.get('escalation_tier') or '').strip()
            action_required_value = bool(item.get('action_required'))
            close_ready_value = bool(item.get('close_ready_gate'))
            auto_next_action_code_key = str(item.get('auto_next_action_code') or '').strip()
            auto_next_action_key = str(item.get('auto_next_action') or '').strip()
            escalation_reason_code_key = str(item.get('escalation_reason_code') or '').strip()
            escalation_reason_key = str(item.get('escalation_reason') or '').strip()
            latest_event = item.get('latest_review_event')
            actor_key = ''
            event_type_key = ''
            event_created_at = ''
            event_result_key = ''
            event_owner_key = ''
            if isinstance(latest_event, dict):
                actor_key = str(latest_event.get('review_actor') or '').strip()
                event_type_key = str(latest_event.get('event_type') or '').strip()
                event_created_at = str(latest_event.get('created_at') or '').strip()
                event_result_key = str(latest_event.get('review_result') or '').strip()
                event_owner_key = str(latest_event.get('review_owner') or '').strip()
            if status_key:
                by_status[status_key] = by_status.get(status_key, 0) + 1
                if status_key == 'resolved':
                    resolved_count += 1
                if status_key == 'needs_review':
                    needs_review_count += 1
            if result_key:
                by_result[result_key] = by_result.get(result_key, 0) + 1
                if result_key == 'needs-escalation':
                    pending_escalation_count += 1
            if owner_key:
                by_owner[owner_key] = by_owner.get(owner_key, 0) + 1
            if actor_key:
                by_actor[actor_key] = by_actor.get(actor_key, 0) + 1
            if event_type_key:
                by_latest_event_type[event_type_key] = by_latest_event_type.get(event_type_key, 0) + 1
                if event_type_key == 'assignment_update' and status_key != 'resolved':
                    pending_assignment_count += 1
            if workflow_lane_key:
                by_workflow_lane[workflow_lane_key] = by_workflow_lane.get(workflow_lane_key, 0) + 1
            if queue_priority_key:
                by_queue_priority[queue_priority_key] = by_queue_priority.get(queue_priority_key, 0) + 1
            if deadline_level_key:
                by_deadline_level[deadline_level_key] = by_deadline_level.get(deadline_level_key, 0) + 1
            if batch_operation_hint_key:
                by_batch_operation_hint[batch_operation_hint_key] = (
                    by_batch_operation_hint.get(batch_operation_hint_key, 0) + 1
                )
            if escalation_tier_key:
                by_escalation_tier[escalation_tier_key] = (
                    by_escalation_tier.get(escalation_tier_key, 0) + 1
                )
            if action_required_value:
                action_required_count += 1
            if close_ready_value:
                close_ready_count += 1
            if auto_next_action_code_key:
                by_auto_next_action_code[auto_next_action_code_key] = (
                    by_auto_next_action_code.get(auto_next_action_code_key, 0) + 1
                )
            if auto_next_action_key:
                by_auto_next_action[auto_next_action_key] = (
                    by_auto_next_action.get(auto_next_action_key, 0) + 1
                )
            if escalation_reason_code_key:
                by_escalation_reason_code[escalation_reason_code_key] = (
                    by_escalation_reason_code.get(escalation_reason_code_key, 0) + 1
                )
            if escalation_reason_key:
                by_escalation_reason[escalation_reason_key] = (
                    by_escalation_reason.get(escalation_reason_key, 0) + 1
                )
            if priority_key:
                by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
            if pattern_key:
                by_pattern[pattern_key] = by_pattern.get(pattern_key, 0) + 1
            phase2_focus_key = cls._phase2_risk_focus_bucket(
                cast(list[str], item.get('risk_types', []))
            )
            if phase2_focus_key:
                by_phase2_focus[phase2_focus_key] = by_phase2_focus.get(phase2_focus_key, 0) + 1
            if event_created_at and event_created_at >= latest_review_at:
                latest_review_at = event_created_at
                latest_review_owner = event_owner_key
                latest_review_actor = actor_key
                latest_review_event_type = event_type_key
                latest_review_result = event_result_key

        current_owner_top = sorted(by_owner.items(), key=lambda item: (-item[1], item[0]))[0][0] if by_owner else ''
        latest_actor_top = sorted(by_actor.items(), key=lambda item: (-item[1], item[0]))[0][0] if by_actor else ''
        latest_event_type_top = (
            sorted(by_latest_event_type.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_latest_event_type
            else ''
        )
        workflow_lane_top = (
            sorted(by_workflow_lane.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_workflow_lane
            else ''
        )
        queue_priority_top = (
            sorted(by_queue_priority.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_queue_priority
            else ''
        )
        deadline_level_top = (
            sorted(by_deadline_level.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_deadline_level
            else ''
        )
        batch_operation_hint_top = (
            sorted(by_batch_operation_hint.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_batch_operation_hint
            else ''
        )
        escalation_tier_top = (
            sorted(by_escalation_tier.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_escalation_tier
            else ''
        )
        auto_next_action_top = (
            sorted(by_auto_next_action.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_auto_next_action
            else ''
        )
        auto_next_action_code_top = (
            sorted(by_auto_next_action_code.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_auto_next_action_code
            else ''
        )
        escalation_reason_top = (
            sorted(by_escalation_reason.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_escalation_reason
            else ''
        )
        escalation_reason_code_top = (
            sorted(by_escalation_reason_code.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_escalation_reason_code
            else ''
        )
        phase2_focus_top = (
            sorted(by_phase2_focus.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if by_phase2_focus
            else ''
        )
        batch_suggestions = cls._build_batch_suggestions(review_candidate_clusters)
        return {
            'review_storage_mode': review_storage_mode,
            'cluster_count': len(review_candidate_clusters),
            'by_status': by_status,
            'by_result': by_result,
            'by_owner': by_owner,
            'by_actor': by_actor,
            'by_latest_event_type': by_latest_event_type,
            'by_workflow_lane': by_workflow_lane,
            'by_queue_priority': by_queue_priority,
            'by_deadline_level': by_deadline_level,
            'by_batch_operation_hint': by_batch_operation_hint,
            'by_escalation_tier': by_escalation_tier,
            'by_auto_next_action_code': by_auto_next_action_code,
            'by_auto_next_action': by_auto_next_action,
            'by_escalation_reason_code': by_escalation_reason_code,
            'by_escalation_reason': by_escalation_reason,
            'by_priority': by_priority,
            'by_pattern': by_pattern,
            'by_phase2_focus': by_phase2_focus,
            'history_event_count': sum(
                int(item.get('review_history_count', 0) or 0) for item in review_candidate_clusters
            ),
            'latest_review_at': latest_review_at,
            'latest_review_owner': latest_review_owner,
            'latest_review_actor': latest_review_actor,
            'latest_review_event_type': latest_review_event_type,
            'latest_review_result': latest_review_result,
            'latest_review_result_label': cls._review_result_label(latest_review_result),
            'current_owner_top': current_owner_top,
            'current_owner_top_count': by_owner.get(current_owner_top, 0) if current_owner_top else 0,
            'latest_actor_top': latest_actor_top,
            'latest_actor_top_count': by_actor.get(latest_actor_top, 0) if latest_actor_top else 0,
            'latest_event_type_top': latest_event_type_top,
            'latest_event_type_top_count': (
                by_latest_event_type.get(latest_event_type_top, 0) if latest_event_type_top else 0
            ),
            'workflow_lane_top': workflow_lane_top,
            'workflow_lane_top_count': by_workflow_lane.get(workflow_lane_top, 0) if workflow_lane_top else 0,
            'queue_priority_top': queue_priority_top,
            'queue_priority_top_count': by_queue_priority.get(queue_priority_top, 0) if queue_priority_top else 0,
            'deadline_level_top': deadline_level_top,
            'deadline_level_top_count': by_deadline_level.get(deadline_level_top, 0) if deadline_level_top else 0,
            'batch_operation_hint_top': batch_operation_hint_top,
            'batch_operation_hint_top_count': (
                by_batch_operation_hint.get(batch_operation_hint_top, 0)
                if batch_operation_hint_top
                else 0
            ),
            'escalation_tier_top': escalation_tier_top,
            'escalation_tier_top_count': (
                by_escalation_tier.get(escalation_tier_top, 0) if escalation_tier_top else 0
            ),
            'auto_next_action_code_top': auto_next_action_code_top,
            'auto_next_action_code_top_count': (
                by_auto_next_action_code.get(auto_next_action_code_top, 0)
                if auto_next_action_code_top
                else 0
            ),
            'auto_next_action_top': auto_next_action_top,
            'auto_next_action_top_count': (
                by_auto_next_action.get(auto_next_action_top, 0) if auto_next_action_top else 0
            ),
            'escalation_reason_code_top': escalation_reason_code_top,
            'escalation_reason_code_top_count': (
                by_escalation_reason_code.get(escalation_reason_code_top, 0)
                if escalation_reason_code_top
                else 0
            ),
            'escalation_reason_top': escalation_reason_top,
            'escalation_reason_top_count': (
                by_escalation_reason.get(escalation_reason_top, 0) if escalation_reason_top else 0
            ),
            'phase2_focus_top': phase2_focus_top,
            'phase2_focus_top_count': by_phase2_focus.get(phase2_focus_top, 0) if phase2_focus_top else 0,
            'pending_assignment_count': pending_assignment_count,
            'pending_escalation_count': pending_escalation_count,
            'resolved_count': resolved_count,
            'needs_review_count': needs_review_count,
            'action_required_count': action_required_count,
            'close_ready_count': close_ready_count,
            'batch_suggestions': batch_suggestions,
        }

    @staticmethod
    def _derive_workflow_lane(cluster: dict[str, object]) -> str:
        cluster_status = str(cluster.get('cluster_status') or '').strip()
        review_result = str(cluster.get('review_result') or '').strip()
        latest_event = cluster.get('latest_review_event')
        latest_event_type = (
            str(latest_event.get('event_type') or '').strip()
            if isinstance(latest_event, dict)
            else ''
        )
        if review_result == 'needs-escalation' or cluster_status == 'escalated':
            return 'escalation_queue'
        if latest_event_type == 'assignment_update' and cluster_status != 'resolved':
            return 'assignment_queue'
        if cluster_status == 'needs_review':
            return 'human_review_queue'
        if cluster_status == 'resolved' or review_result == 'confirmed-benign':
            return 'resolved_queue'
        return 'monitor_queue'

    @staticmethod
    def _derive_queue_priority(cluster: dict[str, object]) -> str:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        review_priority = str(cluster.get('review_priority') or '').strip()
        if workflow_lane == 'resolved_queue':
            return 'done'
        if workflow_lane == 'escalation_queue':
            return 'urgent'
        if workflow_lane == 'assignment_queue':
            return 'high'
        if ExportService._has_phase2_risk(cluster) and review_priority in {'P1', 'P2'}:
            return 'high'
        if review_priority == 'P1':
            return 'high'
        if workflow_lane == 'human_review_queue' or review_priority == 'P2':
            return 'medium'
        return 'low'

    @staticmethod
    def _derive_auto_next_action_code(cluster: dict[str, object]) -> str:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        if workflow_lane == 'escalation_queue':
            return 'escalate_to_senior_review'
        if workflow_lane == 'assignment_queue':
            return 'notify_owner_to_take_over'
        if ExportService._has_phase2_risk(cluster) and str(cluster.get('review_priority') or '').strip() in {'P1', 'P2'}:
            return 'prioritize_phase2_human_review'
        if workflow_lane == 'human_review_queue':
            return 'schedule_human_review'
        if workflow_lane == 'resolved_queue':
            return 'archive_and_monitor'
        return 'observe_and_wait'

    @staticmethod
    def _derive_action_required(cluster: dict[str, object]) -> bool:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        return workflow_lane in {'escalation_queue', 'assignment_queue', 'human_review_queue'}

    @staticmethod
    def _derive_suggested_deadline_level(cluster: dict[str, object]) -> str:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        queue_priority = str(cluster.get('queue_priority') or '').strip()
        if workflow_lane == 'escalation_queue' or queue_priority == 'urgent':
            return 'urgent'
        if workflow_lane == 'assignment_queue' or queue_priority == 'high':
            return 'soon'
        if workflow_lane == 'human_review_queue' or queue_priority == 'medium':
            return 'normal'
        if workflow_lane == 'resolved_queue':
            return 'none'
        return 'backlog'

    @staticmethod
    def _derive_close_ready_gate(cluster: dict[str, object]) -> bool:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        cluster_status = str(cluster.get('cluster_status') or '').strip()
        review_result = str(cluster.get('review_result') or '').strip()
        review_history_count = int(cluster.get('review_history_count', 0) or 0)
        latest_review_event = cluster.get('latest_review_event')
        return (
            workflow_lane == 'resolved_queue'
            and cluster_status == 'resolved'
            and review_result == 'confirmed-benign'
            and review_history_count >= 1
            and isinstance(latest_review_event, dict)
            and bool(latest_review_event)
        )

    @staticmethod
    def _derive_close_ready_reason(cluster: dict[str, object]) -> str:
        if ExportService._derive_close_ready_gate(cluster):
            return '已满足关闭归档条件：状态 resolved、结论 confirmed-benign、存在复核历史。'
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        if workflow_lane != 'resolved_queue':
            return ''
        missing_parts: list[str] = []
        if str(cluster.get('cluster_status') or '').strip() != 'resolved':
            missing_parts.append('尚未进入 resolved 状态')
        if str(cluster.get('review_result') or '').strip() != 'confirmed-benign':
            missing_parts.append('尚未确认无问题')
        if int(cluster.get('review_history_count', 0) or 0) < 1:
            missing_parts.append('缺少复核历史')
        if not isinstance(cluster.get('latest_review_event'), dict) or not cluster.get('latest_review_event'):
            missing_parts.append('缺少最近复核事件')
        if not missing_parts:
            return ''
        return '暂不建议一键关闭：' + '；'.join(missing_parts) + '。'

    @staticmethod
    def _derive_close_stability_score(cluster: dict[str, object]) -> float:
        score = 0.0
        if bool(cluster.get('close_ready_gate')):
            score += 40.0
        if str(cluster.get('cluster_status') or '').strip() == 'resolved':
            score += 10.0
        if str(cluster.get('review_result') or '').strip() == 'confirmed-benign':
            score += 10.0
        score += min(float(int(cluster.get('review_history_count', 0) or 0)), 5.0) * 5.0
        score += min(float(int(cluster.get('chapter_count', 0) or 0)), 5.0) * 2.0
        score += min(float(cluster.get('max_confidence', 0.0) or 0.0) * 10.0, 10.0)
        return score

    @staticmethod
    def _derive_close_ready_rank_reason(cluster: dict[str, object]) -> str:
        return (
            f"close_ready={bool(cluster.get('close_ready_gate'))} | "
            f"history_count={int(cluster.get('review_history_count', 0) or 0)} | "
            f"chapter_count={int(cluster.get('chapter_count', 0) or 0)} | "
            f"confidence={float(cluster.get('max_confidence', 0.0) or 0.0):.2f} | "
            f"close_stability_score={ExportService._derive_close_stability_score(cluster):.2f}"
        )

    @staticmethod
    def _derive_close_batch_rank_score(cluster: dict[str, object]) -> float:
        if str(cluster.get('workflow_lane') or '').strip() != 'resolved_queue':
            return 0.0
        stability = ExportService._derive_close_stability_score(cluster)
        gate_bonus = 20.0 if bool(cluster.get('close_ready_gate')) else 0.0
        result_bonus = 10.0 if str(cluster.get('review_result') or '').strip() == 'confirmed-benign' else 0.0
        history_bonus = min(float(int(cluster.get('review_history_count', 0) or 0)), 5.0) * 3.0
        return stability + gate_bonus + result_bonus + history_bonus

    @staticmethod
    def _derive_close_batch_rank_reason(cluster: dict[str, object]) -> str:
        if str(cluster.get('workflow_lane') or '').strip() != 'resolved_queue':
            return ''
        return (
            f"close_ready={bool(cluster.get('close_ready_gate'))} | "
            f"result={cluster.get('review_result')} | "
            f"history_count={int(cluster.get('review_history_count', 0) or 0)} | "
            f"close_batch_rank_score={ExportService._derive_close_batch_rank_score(cluster):.2f}"
        )

    @staticmethod
    def _derive_human_review_batch_rank_score(cluster: dict[str, object]) -> float:
        if str(cluster.get('workflow_lane') or '').strip() != 'human_review_queue':
            return 0.0
        pattern_bonus = {
            '持续型问题': 15.0,
            '集中爆发型问题': 10.0,
            '单点问题': 5.0,
        }.get(str(cluster.get('pattern_label') or '').strip(), 0.0)
        confidence_bonus = min(float(cluster.get('max_confidence', 0.0) or 0.0) * 20.0, 20.0)
        chapter_count_bonus = min(float(int(cluster.get('chapter_count', 0) or 0)), 8.0) * 2.0
        span_bonus = min(float(len(cast(list[object], cluster.get('chapters', [])))), 6.0)
        priority_bonus = {
            'P1': 20.0,
            'P2': 10.0,
            'P3': 0.0,
        }.get(str(cluster.get('review_priority') or '').strip(), 0.0)
        return 40.0 + pattern_bonus + confidence_bonus + chapter_count_bonus + span_bonus + priority_bonus

    @staticmethod
    def _derive_human_review_batch_rank_reason(cluster: dict[str, object]) -> str:
        if str(cluster.get('workflow_lane') or '').strip() != 'human_review_queue':
            return ''
        return (
            f"priority={cluster.get('review_priority')} | "
            f"pattern={cluster.get('pattern_label')} | "
            f"chapter_count={int(cluster.get('chapter_count', 0) or 0)} | "
            f"confidence={float(cluster.get('max_confidence', 0.0) or 0.0):.2f} | "
            f"human_review_batch_rank_score={ExportService._derive_human_review_batch_rank_score(cluster):.2f}"
        )

    @staticmethod
    def _derive_escalation_urgency_score(cluster: dict[str, object]) -> float:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        if workflow_lane != 'escalation_queue':
            return 0.0
        score = 50.0
        score += {
            'P1': 30.0,
            'P2': 20.0,
            'P3': 10.0,
        }.get(str(cluster.get('review_priority') or '').strip(), 0.0)
        score += min(float(cluster.get('max_confidence', 0.0) or 0.0) * 20.0, 20.0)
        score += min(float(int(cluster.get('chapter_count', 0) or 0)), 10.0) * 2.0
        score += 5.0 if str(cluster.get('review_result') or '').strip() == 'needs-escalation' else 0.0
        score += {
            '持续型问题': 12.0,
            '集中爆发型问题': 6.0,
            '单点问题': 2.0,
        }.get(str(cluster.get('pattern_label') or '').strip(), 0.0)
        return score

    @staticmethod
    def _derive_escalation_tier(cluster: dict[str, object]) -> str:
        score = ExportService._derive_escalation_urgency_score(cluster)
        if score >= 100.0:
            return 'critical'
        if score >= 85.0:
            return 'high'
        if score > 0.0:
            return 'medium'
        return ''

    @staticmethod
    def _derive_escalation_rank_reason(cluster: dict[str, object]) -> str:
        if str(cluster.get('workflow_lane') or '').strip() != 'escalation_queue':
            return ''
        return (
            f"priority={cluster.get('review_priority')} | "
            f"confidence={float(cluster.get('max_confidence', 0.0) or 0.0):.2f} | "
            f"chapter_count={int(cluster.get('chapter_count', 0) or 0)} | "
            f"pattern={cluster.get('pattern_label')} | "
            f"escalation_urgency_score={ExportService._derive_escalation_urgency_score(cluster):.2f}"
        )

    @staticmethod
    def _derive_escalation_batch_rank_score(cluster: dict[str, object]) -> float:
        if str(cluster.get('workflow_lane') or '').strip() != 'escalation_queue':
            return 0.0
        tier_bonus = {
            'critical': 30.0,
            'high': 20.0,
            'medium': 10.0,
        }.get(str(cluster.get('escalation_tier') or '').strip(), 0.0)
        pattern_bonus = {
            '持续型问题': 8.0,
            '集中爆发型问题': 4.0,
            '单点问题': 1.0,
        }.get(str(cluster.get('pattern_label') or '').strip(), 0.0)
        chapter_bonus = min(float(int(cluster.get('chapter_count', 0) or 0)), 6.0)
        return (
            ExportService._derive_escalation_urgency_score(cluster)
            + tier_bonus
            + pattern_bonus
            + chapter_bonus
        )

    @staticmethod
    def _derive_escalation_batch_rank_reason(cluster: dict[str, object]) -> str:
        if str(cluster.get('workflow_lane') or '').strip() != 'escalation_queue':
            return ''
        return (
            f"tier={cluster.get('escalation_tier')} | "
            f"urgency={ExportService._derive_escalation_urgency_score(cluster):.2f} | "
            f"pattern={cluster.get('pattern_label')} | "
            f"chapter_count={int(cluster.get('chapter_count', 0) or 0)} | "
            f"escalation_batch_rank_score={ExportService._derive_escalation_batch_rank_score(cluster):.2f}"
        )

    @staticmethod
    def _derive_batch_operation_hint(cluster: dict[str, object]) -> str:
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        if workflow_lane == 'escalation_queue':
            return 'batch_escalate_candidates'
        if workflow_lane == 'assignment_queue':
            return 'batch_owner_handoff_followup'
        if workflow_lane == 'human_review_queue':
            return 'batch_human_review_queue'
        if workflow_lane == 'resolved_queue':
            if bool(cluster.get('close_ready_gate')):
                return 'batch_close_ready_candidates'
            return 'batch_archive_candidates'
        return 'batch_monitoring_watchlist'

    @classmethod
    def _build_batch_suggestions(
        cls,
        review_candidate_clusters: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        def pattern_rank(item: dict[str, object]) -> int:
            return {
                '持续型问题': 2,
                '集中爆发型问题': 1,
                '单点问题': 0,
            }.get(str(item.get('pattern_label') or '').strip(), -1)

        def human_review_span_bucket(item: dict[str, object]) -> str:
            label = str(item.get('pattern_label') or '').strip()
            if label == '持续型问题':
                return 'long_run'
            if label == '集中爆发型问题':
                return 'burst'
            return 'single'

        def chapter_span_width(item: dict[str, object]) -> int:
            chapters = cast(list[int], item.get('chapters', []))
            if chapters:
                return max(chapters) - min(chapters)
            first = int(item.get('first_chapter', 0) or 0)
            last = int(item.get('last_chapter', first) or first)
            return max(last - first, 0)

        def batch_rank_score(item: dict[str, object]) -> float:
            queue_weight = {
                'urgent': 500.0,
                'high': 400.0,
                'medium': 300.0,
                'low': 200.0,
                'done': 100.0,
            }.get(str(item.get('queue_priority') or ''), 0.0)
            review_weight = {
                'P1': 30.0,
                'P2': 20.0,
                'P3': 10.0,
            }.get(str(item.get('review_priority') or ''), 0.0)
            chapter_weight = min(float(int(item.get('chapter_count', 0) or 0)), 10.0) * 2.0
            confidence_weight = float(item.get('max_confidence', 0.0) or 0.0) * 10.0
            span_weight = min(float(chapter_span_width(item)), 10.0)
            phase2_bonus = 25.0 if ExportService._has_phase2_risk(item) else 0.0
            return queue_weight + review_weight + chapter_weight + confidence_weight + span_weight + phase2_bonus

        def cluster_order_key(item: dict[str, object]) -> tuple[int, int, int, float, int, str]:
            chapter_count = int(item.get('chapter_count', 0) or 0)
            max_confidence = float(item.get('max_confidence', 0.0) or 0.0)
            first_chapter = int(item.get('first_chapter', 10**9) or 10**9)
            return (
                {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3, 'done': 4}.get(
                    str(item.get('queue_priority') or ''), 5
                ),
                -ExportService._derive_escalation_batch_rank_score(item),
                -ExportService._derive_human_review_batch_rank_score(item),
                -ExportService._derive_escalation_urgency_score(item),
                -ExportService._derive_close_batch_rank_score(item),
                {'P1': 0, 'P2': 1, 'P3': 2}.get(str(item.get('review_priority') or ''), 3),
                -pattern_rank(item),
                -ExportService._derive_close_stability_score(item),
                -chapter_count,
                -max_confidence,
                -chapter_span_width(item),
                first_chapter,
                str(item.get('cluster_title') or ''),
            )

        def order_reason(item: dict[str, object]) -> str:
            return (
                f"queue={item.get('queue_priority')} | priority={item.get('review_priority')} | "
                f"pattern={item.get('pattern_label')} | chapter_count={item.get('chapter_count')} | "
                f"confidence={item.get('max_confidence')} | span_width={chapter_span_width(item)} | "
                f"batch_rank_score={batch_rank_score(item):.2f}"
            )

        action_bucket_map = {
            'batch_escalate_candidates': 'escalate',
            'batch_owner_handoff_followup': 'followup',
            'batch_human_review_queue': 'review',
            'batch_close_ready_candidates': 'close',
            'batch_archive_candidates': 'archive',
            'batch_monitoring_watchlist': 'monitor',
        }
        batch_priority_map = {
            'batch_escalate_candidates': 'urgent',
            'batch_owner_handoff_followup': 'high',
            'batch_human_review_queue': 'medium',
            'batch_close_ready_candidates': 'low',
            'batch_archive_candidates': 'low',
            'batch_monitoring_watchlist': 'low',
        }

        def subgroup_key(cluster: dict[str, object]) -> tuple[str, str, str]:
            hint = str(cluster.get('batch_operation_hint') or '').strip()
            owner = str(cluster.get('review_owner') or '').strip() or 'unassigned'
            checker_names = cast(list[object], cluster.get('checker_names', []))
            primary_checker = str(checker_names[0] if checker_names else 'unknown').strip() or 'unknown'
            if hint in {'batch_owner_handoff_followup', 'batch_archive_candidates', 'batch_close_ready_candidates'}:
                return hint, 'by_owner', owner
            if hint in {'batch_human_review_queue', 'batch_escalate_candidates'}:
                return hint, 'by_checker_span', f'{primary_checker}:{human_review_span_bucket(cluster)}'
            return hint, 'by_checker', primary_checker

        def suggestion_rank_score(suggestion: dict[str, object]) -> float:
            bucket_score = {
                'escalate': 500.0,
                'followup': 400.0,
                'review': 300.0,
                'close': 200.0,
                'archive': 100.0,
                'monitor': 50.0,
            }.get(str(suggestion.get('action_bucket') or ''), 0.0)
            priority_score = {
                'urgent': 50.0,
                'high': 40.0,
                'medium': 30.0,
                'low': 20.0,
            }.get(str(suggestion.get('batch_priority') or ''), 0.0)
            cluster_score = min(float(int(suggestion.get('cluster_count', 0) or 0)), 10.0) * 5.0
            action_required_bonus = 10.0 if bool(suggestion.get('action_required')) else 0.0
            return bucket_score + priority_score + cluster_score + action_required_bonus

        def suggestion_rank_reason(suggestion: dict[str, object]) -> str:
            return (
                f"action_bucket={suggestion.get('action_bucket')} | "
                f"batch_priority={suggestion.get('batch_priority')} | "
                f"cluster_count={int(suggestion.get('cluster_count', 0) or 0)} | "
                f"action_required={bool(suggestion.get('action_required'))} | "
                f"suggestion_rank_score={suggestion_rank_score(suggestion):.2f}"
            )

        groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
        for cluster in review_candidate_clusters:
            hint = str(cluster.get('batch_operation_hint') or '').strip()
            if not hint:
                continue
            groups.setdefault(subgroup_key(cluster), []).append(cluster)

        suggestions: list[dict[str, object]] = []
        title_map = {
            'batch_escalate_candidates': '可批量升级处理',
            'batch_owner_handoff_followup': '可批量催办交接',
            'batch_human_review_queue': '可批量人工复核',
            'batch_close_ready_candidates': '可批量关闭归档',
            'batch_archive_candidates': '可批量归档关闭',
            'batch_monitoring_watchlist': '可批量观察跟踪',
        }
        for (hint, group_strategy, group_value), items in groups.items():
            if not items:
                continue
            items_sorted = sorted(
                items,
                key=cluster_order_key,
            )
            sample = items_sorted[0]
            suggested_owner = cls._dedupe_preview(
                [item.get('review_owner') for item in items_sorted if item.get('review_owner')],
                1,
            )
            suggestions.append(
                {
                    'hint_code': hint,
                    'hint_title': title_map.get(hint, hint),
                    'action_bucket': action_bucket_map.get(hint, 'monitor'),
                    'batch_priority': batch_priority_map.get(hint, 'low'),
                    'group_strategy': group_strategy,
                    'group_key': group_value,
                    'span_bucket': human_review_span_bucket(sample),
                    'cluster_count': len(items),
                    'cluster_keys': [str(item.get('cluster_key') or '') for item in items_sorted[:5]],
                    'suggested_cluster_order': [
                        str(item.get('cluster_key') or '') for item in items_sorted[:5]
                    ],
                    'suggested_cluster_order_titles': [
                        str(item.get('cluster_title') or '') for item in items_sorted[:5]
                    ],
                    'suggested_cluster_order_details': [
                        {
                            'cluster_key': str(item.get('cluster_key') or ''),
                            'cluster_title': str(item.get('cluster_title') or ''),
                            'queue_priority': str(item.get('queue_priority') or ''),
                            'review_priority': str(item.get('review_priority') or ''),
                            'chapter_count': int(item.get('chapter_count', 0) or 0),
                            'confidence': float(item.get('max_confidence', 0.0) or 0.0),
                            'human_review_batch_rank_score': ExportService._derive_human_review_batch_rank_score(item),
                            'human_review_batch_rank_reason': ExportService._derive_human_review_batch_rank_reason(item),
                            'escalation_tier': ExportService._derive_escalation_tier(item),
                            'escalation_urgency_score': ExportService._derive_escalation_urgency_score(item),
                            'escalation_rank_reason': ExportService._derive_escalation_rank_reason(item),
                            'escalation_batch_rank_score': ExportService._derive_escalation_batch_rank_score(item),
                            'escalation_batch_rank_reason': ExportService._derive_escalation_batch_rank_reason(item),
                            'close_stability_score': ExportService._derive_close_stability_score(item),
                            'close_ready_rank_reason': ExportService._derive_close_ready_rank_reason(item),
                            'close_batch_rank_score': ExportService._derive_close_batch_rank_score(item),
                            'close_batch_rank_reason': ExportService._derive_close_batch_rank_reason(item),
                            'chapter_span_width': chapter_span_width(item),
                            'batch_rank_score': batch_rank_score(item),
                            'order_reason': order_reason(item),
                        }
                        for item in items_sorted[:5]
                    ],
                    'ordering_strategy': 'queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter',
                    'suggested_first_cluster_reason': order_reason(sample),
                    'cluster_titles': [str(item.get('cluster_title') or '') for item in items_sorted[:3]],
                    'owners': cls._dedupe_preview(
                        [item.get('review_owner') for item in items_sorted if item.get('review_owner')],
                        3,
                    ),
                    'suggested_owner': suggested_owner[0] if suggested_owner else '',
                    'primary_checker': str(
                        cast(list[object], sample.get('checker_names', []))[0]
                        if cast(list[object], sample.get('checker_names', []))
                        else ''
                    ),
                    'pattern_label_top': str(sample.get('pattern_label') or ''),
                    'risk_types': cls._dedupe_preview(
                        [risk for item in items_sorted for risk in cast(list[object], item.get('risk_types', []))],
                        4,
                    ),
                    'phase2_focus_top': ExportService._phase2_risk_focus_bucket(
                        cast(list[str], sample.get('risk_types', []))
                    ),
                    'chapter_spans': cls._dedupe_preview(
                        [item.get('chapter_span') for item in items_sorted if item.get('chapter_span')],
                        3,
                    ),
                    'queue_priority_top': str(sample.get('queue_priority') or ''),
                    'deadline_level_top': str(sample.get('suggested_deadline_level') or ''),
                    'escalation_tier_top': str(sample.get('escalation_tier') or ''),
                    'action_required': any(bool(item.get('action_required')) for item in items_sorted),
                    'resolved_candidate_count': sum(
                        1 for item in items_sorted if str(item.get('cluster_status') or '') == 'resolved'
                    ),
                    'escalation_candidate_count': sum(
                        1
                        for item in items_sorted
                        if str(item.get('review_result') or '') == 'needs-escalation'
                    ),
                    'recommended_batch_action': str(sample.get('auto_next_action') or ''),
                }
            )
        for suggestion in suggestions:
            suggestion['suggestion_rank_score'] = suggestion_rank_score(suggestion)
            suggestion['suggestion_rank_reason'] = suggestion_rank_reason(suggestion)
        suggestions.sort(
            key=lambda item: (
                -float(item.get('suggestion_rank_score', 0.0) or 0.0),
                {'batch_escalate_candidates': 0, 'batch_owner_handoff_followup': 1, 'batch_human_review_queue': 2, 'batch_close_ready_candidates': 3, 'batch_archive_candidates': 4, 'batch_monitoring_watchlist': 5}.get(
                    str(item.get('hint_code') or ''), 5
                ),
            )
        )
        return suggestions

    @staticmethod
    def _derive_auto_next_action(cluster: dict[str, object]) -> str:
        action_code = str(cluster.get('auto_next_action_code') or '').strip()
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        review_owner = str(cluster.get('review_owner') or '').strip()
        cluster_title = str(cluster.get('cluster_title') or cluster.get('cluster_key') or '该问题簇').strip()
        phase2_focus = ExportService._phase2_risk_focus_bucket(
            cast(list[str], cluster.get('risk_types', []))
        )
        if action_code == 'escalate_to_senior_review' or workflow_lane == 'escalation_queue':
            return f'尽快把 {cluster_title} 转入更高等级复核，并补充升级依据。'
        if action_code == 'notify_owner_to_take_over' or workflow_lane == 'assignment_queue':
            owner_text = review_owner or '当前负责人'
            return f'通知 {owner_text} 接手 {cluster_title}，并尽快给出复核结论。'
        if action_code == 'prioritize_phase2_human_review':
            focus_label = {
                'plot-phase2': '剧情/因果链',
                'timeline-phase2': '时间线/恢复窗口',
                'power-phase2': '战力/代价限制',
            }.get(phase2_focus, 'phase-2 风险')
            return f'优先安排人工复核 {cluster_title}，重点核对{focus_label}相关证据链是否闭合。'
        if action_code == 'schedule_human_review' or workflow_lane == 'human_review_queue':
            return f'优先安排人工复核 {cluster_title}，确认是否需要升级或关闭。'
        if action_code == 'archive_and_monitor' or workflow_lane == 'resolved_queue':
            return f'保留 {cluster_title} 的审计记录，并继续关注后续章节是否复发。'
        return f'继续观察 {cluster_title}，等待更多证据后再决定是否升级。'

    @staticmethod
    def _derive_escalation_reason_code(cluster: dict[str, object]) -> str:
        review_result = str(cluster.get('review_result') or '').strip()
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        if review_result == 'needs-escalation':
            return 'explicit_escalation_requested'
        if workflow_lane == 'assignment_queue':
            return 'awaiting_owner_followup'
        if ExportService._has_phase2_risk(cluster) and str(cluster.get('review_priority') or '').strip() in {'P1', 'P2'}:
            return 'phase2_risk_requires_human_confirmation'
        if workflow_lane == 'human_review_queue':
            return 'awaiting_human_confirmation'
        return ''

    @staticmethod
    def _derive_escalation_reason(cluster: dict[str, object]) -> str:
        reason_code = str(cluster.get('escalation_reason_code') or '').strip()
        review_result = str(cluster.get('review_result') or '').strip()
        workflow_lane = str(cluster.get('workflow_lane') or '').strip()
        review_notes = str(cluster.get('review_notes') or '').strip()
        if reason_code == 'explicit_escalation_requested' or review_result == 'needs-escalation':
            return review_notes or '当前问题簇已被标记为需要升级处理。'
        if reason_code == 'awaiting_owner_followup' or workflow_lane == 'assignment_queue':
            return '当前问题簇已完成交接，但尚未形成最终闭环结论。'
        if reason_code == 'phase2_risk_requires_human_confirmation':
            return '当前问题簇属于 phase-2 结构化风险候选，需优先补足人工确认后再决定是否升级或关闭。'
        if reason_code == 'awaiting_human_confirmation' or workflow_lane == 'human_review_queue':
            return '当前问题簇仍缺少人工确认，暂不适合直接关闭。'
        return ''

    @classmethod
    def _chapter_continuity_preview(
        cls,
        chapter_index: int,
        chapter_output_summary: dict[str, object],
        state_summary: dict[str, object],
        reasoning_graph: dict[str, object],
    ) -> tuple[list[str], list[str]]:
        chapter_signals: list[str] = []
        branch_signals: list[str] = []

        for key, label in [
            ('state_transition_notes', '推进'),
            ('evidence_backed_resolutions', '解决'),
            ('unresolved_threads', '未解'),
        ]:
            rows = cast(list[object], chapter_output_summary.get(key, []))
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if int(row.get('chapter_index', 0) or 0) != chapter_index:
                    continue
                note = str(row.get('note') or '').strip()
                if note:
                    chapter_signals.append(f'{label}: {note}')

        branch_signals.extend(
            f'活跃冲突: {item}'
            for item in cast(list[object], reasoning_graph.get('active_conflicts', []))[:2]
            if str(item).strip()
        )
        branch_signals.extend(
            f'未回收伏笔: {item}'
            for item in cast(list[object], reasoning_graph.get('open_foreshadowing', []))[:2]
            if str(item).strip()
        )
        branch_signals.extend(
            f'近期时间线: {item}'
            for item in cast(list[object], reasoning_graph.get('recent_timeline', []))[-2:]
            if str(item).strip()
        )
        branch_signals.extend(
            f'规则约束: {item}'
            for item in cast(list[object], state_summary.get('constraining_world_rules', []))[:2]
            if str(item).strip()
        )

        return cls._dedupe_preview(chapter_signals, 3), cls._dedupe_preview(branch_signals, 4)

    @classmethod
    def _cluster_review_candidates(
        cls,
        review_candidates_summary: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        phase2_title_map = {
            ('plot_logic_consistency', 'thread_state_conflict'): '剧情线程状态冲突簇',
            ('plot_logic_consistency', 'motivation_to_action_gap'): '动机到行动断桥簇',
            ('timeline_consistency', 'sequence_conflict_candidate'): '时间顺序冲突候选簇',
            ('timeline_consistency', 'recovery_window_insufficient'): '恢复窗口不足候选簇',
            ('power_scaling_consistency', 'upset_without_setup'): '越阶铺垫不足候选簇',
            ('power_scaling_consistency', 'cost_constraint_missing'): '代价约束缺口候选簇',
        }

        def cluster_title(checkers: list[str], risk_types: list[str]) -> str:
            checker = checkers[0] if checkers else 'unknown'
            risk_type = risk_types[0] if risk_types else 'review_candidate'
            mapped_title = phase2_title_map.get((checker, risk_type))
            if mapped_title:
                return mapped_title
            if checker == 'character_ooc':
                return '人物连续性复核簇' if risk_type == 'human_review_candidate' else f'人物风险簇：{risk_type}'
            if checker == 'relationship_consistency':
                return '关系连续性复核簇' if 'candidate' in risk_type else f'关系风险簇：{risk_type}'
            if checker == 'foreshadow_payoff_consistency':
                return '伏笔兑现复核簇' if 'candidate' in risk_type else f'伏笔兑现风险簇：{risk_type}'
            if checker == 'setting_scope_consistency':
                return '设定作用域复核簇' if 'candidate' in risk_type else f'设定作用域风险簇：{risk_type}'
            if checker == 'thread_closure_consistency':
                return '线程收束复核簇' if 'candidate' in risk_type else f'线程收束风险簇：{risk_type}'
            if checker == 'plot_logic_consistency':
                return '剧情因果复核簇' if 'candidate' in risk_type else f'剧情逻辑风险簇：{risk_type}'
            if checker == 'timeline_consistency':
                return '时间线复核簇' if 'candidate' in risk_type else f'时间线风险簇：{risk_type}'
            if checker == 'power_scaling_consistency':
                return '战力能力复核簇' if 'candidate' in risk_type else f'战力能力风险簇：{risk_type}'
            if checker == 'world_rule_consistency':
                return '规则一致性复核簇' if 'candidate' in risk_type else f'规则风险簇：{risk_type}'
            return f'风险问题簇：{risk_type}'

        def suggested_review_action(checkers: list[str], risk_types: list[str]) -> str:
            checker = checkers[0] if checkers else 'unknown'
            risk_type = risk_types[0] if risk_types else 'review_candidate'
            if checker == 'character_ooc':
                return '优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。'
            if checker == 'relationship_consistency':
                if risk_type == 'relationship_shift_without_bridge':
                    return '优先核对人物关系从亲近到疏远、从敌对到结盟等变化之间，是否缺少必要桥段与前文支撑。'
                if risk_type == 'trust_state_conflict':
                    return '优先核对信任/敌意关系是否同时出现“已缓和”与“仍对立”信号，确认只是阶段性变化还是关系状态冲突。'
                if risk_type == 'hostility_resolution_too_fast':
                    return '优先核对敌对关系缓和、和解或结盟是否推进过快，确认中间冲突化解是否已有正文桥接。'
                return '优先核对人物关系、信任状态与敌我口径是否有前文支撑，避免把省略桥段误判为关系跳变。'
            if checker == 'foreshadow_payoff_consistency':
                if risk_type == 'payoff_without_setup':
                    return '优先核对当前重要结果或揭示前，是否已有足够铺垫、暗示或伏笔埋设。'
                if risk_type == 'resolved_thread_reopened_without_reason':
                    return '优先核对已兑现/已解决线索为何重新回到未解状态，确认只是阶段性回收还是线程口径冲突。'
                if risk_type == 'important_thread_long_unmentioned':
                    return '优先核对关键伏笔或线程是否长期悬置且缺乏后续承接，确认是否只是有意延后。'
                return '优先核对伏笔埋设、回收与未解线程之间的链路是否完整，避免把延后回收误判为问题。'
            if checker == 'setting_scope_consistency':
                if risk_type == 'constraint_scope_expansion':
                    return '优先核对规则、权限或能力的适用范围是否被异常放大，确认是否只是例外通道或临时开放。'
                if risk_type == 'resource_limit_missing':
                    return '优先核对资源、次数、消耗或额度限制是否被正文明确交代，避免无解释扩张。'
                if risk_type == 'authority_boundary_conflict':
                    return '优先核对权限、组织、禁地或资格边界是否被异常突破，确认是否已有特批或身份变化铺垫。'
                return '优先核对设定范围、资源限制与权限边界是否保持前后一致，避免把例外机制误判为主规则扩张。'
            if checker == 'thread_closure_consistency':
                if risk_type == 'thread_dropped_after_escalation':
                    return '优先核对已升级冲突是否突然失去后续承接，确认只是暂时按下不表还是线程断头。'
                if risk_type == 'closure_without_resolution_basis':
                    return '优先核对“已解决/已收束”类表述是否真有正文依据，避免把阶段性缓和误判为真正收束。'
                if risk_type == 'ending_stability_candidate':
                    return '优先核对本章小结尾或阶段收束是否过快回落，确认是否缺少必要的冲突处理与回收依据。'
                return '优先核对冲突线程、升级节点与收束表述之间是否存在断桥或支撑不足。'
            if checker == 'plot_logic_consistency':
                if risk_type == 'thread_state_conflict':
                    return '优先核对“已解决/已解除”与未解线程是否被同时保留，确认只是阶段性缓解还是线程状态冲突。'
                if risk_type == 'motivation_to_action_gap':
                    return '优先核对角色动机、决定与实际行动之间是否存在缺失的因果桥或前置铺垫。'
                if 'resolution' in risk_type:
                    return '优先核对“已解决/已兑现”类表述是否真的有正文证据链闭合。'
                return '优先核对关键行动、结果与中间因果链是否缺少必要过渡或支撑。'
            if checker == 'timeline_consistency':
                if risk_type == 'sequence_conflict_candidate':
                    return '优先核对当夜/次日等短窗口时间锚点是否互相打架，确认是否只是叙事压缩。'
                if risk_type == 'recovery_window_insufficient':
                    return '优先核对恢复、赶路、回城与再战之间的时长窗口是否足够，确认是否缺少中间恢复过程。'
                return '优先核对事件先后顺序、恢复时长与同日多地切换是否存在时序冲突。'
            if checker == 'power_scaling_consistency':
                if risk_type == 'upset_without_setup':
                    return '优先核对越阶压制或突然反杀前是否已有铺垫、克制关系或一次性增益解释。'
                if risk_type == 'cost_constraint_missing':
                    return '优先核对强力表现后的代价、冷却、限制或后遗症是否被正文明确交代。'
                return '优先核对能力跃迁、越阶压制和新招式掌握是否有明确铺垫或限制条件。'
            if checker == 'world_rule_consistency':
                return '优先核对既有世界规则、约束条件和例外触发是否前后一致。'
            return '优先回看相关章节与证据预览，确认该候选是否仅为弱信号噪音。'

        def review_priority(chapter_count: int, max_confidence: float, checkers: list[str]) -> str:
            risk_types = current_risk_types
            if any(
                risk_type in {
                    'thread_state_conflict',
                    'recovery_window_insufficient',
                    'upset_without_setup',
                    'cost_constraint_missing',
                }
                for risk_type in risk_types
            ) and chapter_count >= 1:
                return 'P2'
            if max_confidence >= 0.75 or chapter_count >= 5:
                return 'P1'
            if max_confidence >= 0.5 or chapter_count >= 3:
                return 'P2'
            if (
                'character_ooc' in checkers
                or 'relationship_consistency' in checkers
                or 'foreshadow_payoff_consistency' in checkers
                or 'setting_scope_consistency' in checkers
                or 'thread_closure_consistency' in checkers
            ) and chapter_count >= 2:
                return 'P2'
            return 'P3'

        def cluster_pattern(chapters: list[int]) -> str:
            if len(chapters) <= 1:
                return '单点问题'
            span = max(chapters) - min(chapters)
            if span <= 3:
                return '集中爆发型问题'
            return '持续型问题'

        clusters: dict[str, dict[str, object]] = {}
        for item in review_candidates_summary:
            checker_names = cls._dedupe_preview(cast(list[object], item.get('checker_names', [])), 6)
            risk_types = cls._dedupe_preview(cast(list[object], item.get('risk_types', [])), 6)
            current_risk_types = risk_types
            cluster_key = "|".join(checker_names + ["::"] + risk_types)
            cluster = clusters.setdefault(
                cluster_key,
                {
                    'cluster_key': cluster_key,
                    'checker_names': checker_names,
                    'risk_types': risk_types,
                    'cluster_title': cluster_title(checker_names, risk_types),
                    'suggested_review_action': suggested_review_action(checker_names, risk_types),
                    'review_priority': 'P3',
                    'cluster_status': 'open',
                    'chapter_count': 0,
                    'chapters': [],
                    'first_chapter': None,
                    'last_chapter': None,
                    'max_confidence': 0.0,
                    'titles': [],
                    'sample_summary': '',
                },
            )
            preferred_risk_type = next(
                iter(
                    sorted(
                        risk_types,
                        key=lambda risk_type: (
                            -cls._risk_specificity_rank(risk_type),
                            risk_type,
                        ),
                    )
                ),
                '',
            )
            if preferred_risk_type:
                cluster['cluster_title'] = cluster_title(checker_names, [preferred_risk_type])
                cluster['suggested_review_action'] = suggested_review_action(checker_names, [preferred_risk_type])
            chapter_index = int(item.get('chapter_index', 0))
            cluster['chapter_count'] = int(cluster.get('chapter_count', 0)) + 1
            cluster['chapters'] = sorted(set(cast(list[int], cluster.get('chapters', [])) + [chapter_index]))
            cluster['first_chapter'] = (
                chapter_index
                if cluster.get('first_chapter') is None
                else min(int(cluster.get('first_chapter', chapter_index)), chapter_index)
            )
            cluster['last_chapter'] = (
                chapter_index
                if cluster.get('last_chapter') is None
                else max(int(cluster.get('last_chapter', chapter_index)), chapter_index)
            )
            first_chapter = int(cluster.get('first_chapter', chapter_index) or chapter_index)
            last_chapter = int(cluster.get('last_chapter', chapter_index) or chapter_index)
            chapters = cast(list[int], cluster.get('chapters', []))
            cluster['chapter_span'] = (
                str(first_chapter)
                if first_chapter == last_chapter
                else f'{first_chapter}-{last_chapter}'
            )
            cluster['pattern_label'] = cluster_pattern(chapters)
            cluster['max_confidence'] = max(
                float(cluster.get('max_confidence', 0.0)),
                float(item.get('confidence') or 0.0),
            )
            cluster['review_priority'] = review_priority(
                int(cluster.get('chapter_count', 0)),
                float(cluster.get('max_confidence', 0.0)),
                checker_names,
            )
            cluster['cluster_status'] = cls._derive_cluster_status(
                chapter_count=int(cluster.get('chapter_count', 0)),
                max_confidence=float(cluster.get('max_confidence', 0.0)),
                review_priority_value=cast(str, cluster.get('review_priority', 'P3')),
            )
            cluster['titles'] = cls._dedupe_preview(
                cast(list[object], cluster.get('titles', [])) + [item.get('title')],
                4,
            )
            if item.get('summary'):
                current_summary = str(cluster.get('sample_summary') or '')
                next_summary = str(item.get('summary') or '')
                current_specificity = max(
                    (cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], cluster.get('risk_types', []))),
                    default=-1,
                )
                next_specificity = max(
                    (cls._risk_specificity_rank(risk_type) for risk_type in risk_types),
                    default=-1,
                )
                if (
                    not current_summary
                    or next_specificity > current_specificity
                    or (next_specificity == current_specificity and len(next_summary) > len(current_summary))
                ):
                    cluster['sample_summary'] = next_summary
        clustered = list(clusters.values())
        has_specific_cluster = any(
            max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1) > 0
            for item in clustered
        )
        if has_specific_cluster:
            filtered = [
                item for item in clustered
                if max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1) > 0
            ]
            clustered = filtered or clustered
        clustered.sort(
            key=lambda item: (
                {'needs_review': 0, 'reopened': 1, 'escalated': 2, 'reviewed': 3, 'open': 4, 'resolved': 5}.get(cast(str, item.get('cluster_status', 'open')), 6),
                {'P1': 0, 'P2': 1, 'P3': 2}.get(cast(str, item.get('review_priority', 'P3')), 3),
                -cls._cluster_pattern_rank(cast(str | None, item.get('pattern_label'))),
                -max((cls._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1),
                -int(item.get('chapter_count', 0)),
                -float(item.get('max_confidence', 0.0)),
                int(item.get('first_chapter', 0) or 0),
            )
        )
        return clustered[:20]

    @staticmethod
    def _phase2_risk_focus_bucket(risk_types: list[str]) -> str:
        values = set(risk_types)
        if values & {'thread_state_conflict', 'motivation_to_action_gap'}:
            return 'plot-phase2'
        if values & {'sequence_conflict_candidate', 'recovery_window_insufficient'}:
            return 'timeline-phase2'
        if values & {'upset_without_setup', 'cost_constraint_missing'}:
            return 'power-phase2'
        return ''

    @staticmethod
    def _has_phase2_risk(cluster: dict[str, object]) -> bool:
        return bool(
            ExportService._phase2_risk_focus_bucket(cast(list[str], cluster.get('risk_types', [])))
        )

    @staticmethod
    def _build_audit_conclusion(
        *,
        completed_chapters: int,
        manifest_chapter_count: int,
        failed_summary: list[dict[str, object]],
        high_risk_chapters: list[int],
        review_candidate_count: int,
    ) -> dict[str, str]:
        completion_ratio = (
            (completed_chapters / manifest_chapter_count)
            if manifest_chapter_count > 0
            else 0.0
        )
        if failed_summary:
            content_judgement = (
                "当前分支已形成阶段性审查结果，但审查覆盖仍停留在已完成章节，"
                "尚不能覆盖后续未完成章节。"
            )
            risk_judgement = (
                "当前已完成章节未见明确高风险，但存在需人工复核的候选章节。"
                if review_candidate_count
                else "当前已完成章节未见明确高风险。"
            )
            blocking_judgement = "当前存在执行阻塞，阻塞主因是失败章节尚未恢复。"
            recommended_action = "先处理失败章节恢复执行，再结合风险候选章节做人工复核。"
        elif high_risk_chapters:
            content_judgement = (
                "当前分支已形成可用审查结果，且当前覆盖范围足以支撑阶段性内容判断。"
                if completion_ratio >= 0.8
                else "当前分支已形成可用的阶段性审查结果。"
            )
            risk_judgement = "当前分支存在高风险章节，后续使用结论前应优先人工复核。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "优先复核高风险章节，再决定是否继续使用下游结论。"
        elif review_candidate_count >= 5:
            content_judgement = (
                "当前分支已形成可用的阶段性审查结果，但候选风险分布较密集。"
            )
            risk_judgement = "当前未发现明确高风险，但人工复核候选较多，需谨慎使用整体稳定结论。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "按章节优先级批量复核候选章节，再决定是否给出整体稳定判断。"
        elif review_candidate_count > 0:
            content_judgement = (
                "当前分支已形成可用审查结果。"
                if completion_ratio >= 0.3
                else "当前分支已形成早期阶段审查结果。"
            )
            risk_judgement = "当前未发现明确高风险，但存在低/中风险人工复核候选。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "优先复核候选章节，再结合上下文决定是否继续推进。"
        else:
            content_judgement = (
                "当前分支已形成可用审查结果，章节连续性判断整体稳定。"
                if completion_ratio >= 0.3
                else "当前分支已形成早期阶段审查结果，目前未见明显风险候选。"
            )
            risk_judgement = "当前未发现明确风险候选，章节连续性结果整体稳定。"
            blocking_judgement = "当前无执行阻塞。"
            recommended_action = "可继续使用当前审查结果，并在新增章节后持续复查。"
        return {
            'content_judgement': content_judgement,
            'risk_judgement': risk_judgement,
            'blocking_judgement': blocking_judgement,
            'recommended_action': recommended_action,
        }

    @staticmethod
    def _recommended_questions_for_chapter(
        artifact: dict[str, object],
        retrieval: dict[str, object],
    ) -> list[str]:
        """Build guided follow-up questions for one chapter QA context."""

        title = str(artifact.get('normalized_title', '')).strip()
        chapter_summary = str(artifact.get('chapter_summary', '')).strip()
        key_events_raw = cast(list[object], artifact.get('key_events', []))
        unresolved_raw = cast(list[object], artifact.get('unresolved_threads', []))
        transitions_raw = cast(list[object], artifact.get('state_transition_notes', []))
        query_hints_raw = cast(list[object], retrieval.get('query_hints', []))
        key_events = [
            str(item).strip()
            for item in key_events_raw
            if isinstance(item, str) and str(item).strip()
        ]
        unresolved = [
            str(item).strip()
            for item in unresolved_raw
            if isinstance(item, str) and str(item).strip()
        ]
        transitions = [
            str(item).strip()
            for item in transitions_raw
            if isinstance(item, str) and str(item).strip()
        ]
        query_hints = [
            str(item).strip()
            for item in query_hints_raw
            if isinstance(item, str) and str(item).strip()
        ]
        questions: list[str] = []
        if title:
            questions.append(
                f'第{artifact.get("chapter_index", "?")}章《{title}》的核心推进是什么？'
            )
        if chapter_summary:
            questions.append('这一章里最关键的剧情兑现点是什么？')
        for item in key_events[:2]:
            questions.append(f'事件“{item}”对后续章节会产生什么影响？')
        for item in unresolved[:2]:
            questions.append(f'未解线程“{item}”后续最可能如何推进？')
        for item in transitions[:2]:
            questions.append(f'状态推进“{item}”是如何通过文本建立出来的？')
        questions.extend(query_hints[:3])
        return list(dict.fromkeys(item for item in questions if item))

    @staticmethod
    def _recommended_questions_for_branch(
        bundle: dict[str, object],
    ) -> list[str]:
        """Build guided follow-up questions for a branch QA context."""

        state_summary = cast(dict[str, object], bundle.get('state_summary', {}))
        chapter_output_summary = cast(dict[str, object], bundle.get('chapter_output_summary', {}))
        questions: list[str] = []
        for item in cast(list[object], state_summary.get('escalated_conflicts', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'冲突“{label}”是如何逐章升级的？')
        for item in cast(list[object], state_summary.get('paid_off_foreshadowing', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'伏笔“{label}”是在哪些章节逐步兑现的？')
        for item in cast(list[object], state_summary.get('constraining_world_rules', []))[:3]:
            label = str(item).strip()
            if label:
                questions.append(f'规则“{label}”如何持续影响这条故事线？')
        unresolved = cast(list[object], chapter_output_summary.get('unresolved_threads', []))
        for item in unresolved[:3]:
            if isinstance(item, dict):
                note = str(item.get('note', '')).strip()
                chapter_index = item.get('chapter_index')
                if note:
                    questions.append(f'第{chapter_index}章留下的未解线程“{note}”后续怎么承接？')
        return list(dict.fromkeys(item for item in questions if item))

    @staticmethod
    def _thematic_contexts_for_branch(bundle: dict[str, object]) -> dict[str, object]:
        """Build thematic QA entry points for downstream tools."""

        state_summary = cast(dict[str, object], bundle.get('state_summary', {}))
        chapter_output_summary = cast(dict[str, object], bundle.get('chapter_output_summary', {}))
        reasoning_graph = cast(dict[str, object], bundle.get('reasoning_graph', {}))
        central_nodes = cast(list[object], reasoning_graph.get('central_nodes', []))
        retrieval_documents = cast(list[object], bundle.get('retrieval_documents', []))

        character_focus = []
        for item in central_nodes:
            if isinstance(item, dict) and item.get('node_type') == 'entity':
                label = str(item.get('label', '')).strip()
                if label:
                    character_focus.append(label)

        def notes_from_summary(key: str, limit: int = 6) -> list[str]:
            items = cast(list[object], state_summary.get(key, []))
            return [str(item).strip() for item in items[:limit] if str(item).strip()]

        def rows_from_chapter_output(key: str, limit: int = 6) -> list[dict[str, object]]:
            rows = cast(list[object], chapter_output_summary.get(key, []))
            result: list[dict[str, object]] = []
            for row in rows[:limit]:
                if isinstance(row, dict):
                    result.append(
                        {
                            'chapter_index': row.get('chapter_index'),
                            'note': row.get('note'),
                        }
                    )
            return result

        doc_summaries = []
        for item in retrieval_documents[:6]:
            if isinstance(item, dict):
                doc_summaries.append(
                    {
                        'chapter_index': item.get('chapter_index'),
                        'title': item.get('title'),
                        'summary_text': item.get('summary_text'),
                    }
                )

        def score_text(text: str, keywords: list[str]) -> int:
            normalized = text.strip()
            if not normalized:
                return 0
            return sum(
                1
                for keyword in keywords
                if keyword and keyword in normalized
            )

        def related_chapters_from_threads(
            key: str,
            keywords: list[str],
            limit: int = 6,
        ) -> list[int]:
            rows = rows_from_chapter_output(key, limit)
            scored: list[tuple[int, int]] = []
            for row in rows:
                chapter_index = row.get('chapter_index')
                note = str(row.get('note', '')).strip()
                if isinstance(chapter_index, int):
                    score = score_text(note, keywords)
                    scored.append((chapter_index, score))
            scored.sort(key=lambda item: (-item[1], item[0]))
            return [chapter for chapter, _ in scored[:limit]]

        def evidence_summaries_for_chapters(
            chapters: list[int],
            keywords: list[str],
            limit: int = 4,
        ) -> list[str]:
            lines: list[tuple[str, int]] = []
            for item in doc_summaries:
                chapter_index = item.get('chapter_index')
                if chapter_index in chapters:
                    title = item.get('title')
                    summary_text = item.get('summary_text')
                    line = f"第{chapter_index}章《{title}》：{summary_text}"
                    lines.append((line, score_text(line, keywords)))
            lines.sort(key=lambda item: -item[1])
            return [line for line, _ in lines[:limit]]

        def question_sequence(questions: list[str]) -> list[dict[str, object]]:
            return [
                {'step': index, 'question': question}
                for index, question in enumerate(questions[:4], start=1)
            ]

        def thematic_reasoning_paths(keywords: list[str], limit: int = 6) -> list[str]:
            paths = cast(list[object], reasoning_graph.get('reasoning_paths', []))
            matched: list[str] = []
            for item in paths:
                text = str(item).strip()
                if text and any(keyword in text for keyword in keywords if keyword):
                    matched.append(text)
            return matched[:limit]

        def thematic_state_signals(keywords: list[str], limit: int = 6) -> list[str]:
            signals: list[str] = []
            for bucket, prefix in [
                ('new_conflicts', '活跃冲突'),
                ('escalated_conflicts', '升级冲突'),
                ('paid_off_foreshadowing', '已兑现伏笔'),
                ('new_foreshadowing', '待回收伏笔'),
                ('constraining_world_rules', '规则约束'),
                ('evolved_relations', '关系变化'),
            ]:
                for item in notes_from_summary(bucket, limit):
                    if any(keyword in item for keyword in keywords if keyword):
                        signals.append(f'{prefix}: {item}')
            return signals[:limit]

        def thematic_supporting_facts(keywords: list[str], limit: int = 8) -> list[str]:
            facts = cast(list[object], bundle.get('graph_nodes', []))
            rows: list[str] = []
            for item in facts:
                if not isinstance(item, dict):
                    continue
                label = str(item.get('label', '')).strip()
                node_type = str(item.get('node_type', '')).strip()
                if label and any(keyword in label for keyword in keywords if keyword):
                    rows.append(f'{node_type}:{label}')
            return rows[:limit]

        def thematic_node_refs(keywords: list[str], limit: int = 8) -> list[dict[str, object]]:
            nodes = cast(list[object], bundle.get('graph_nodes', []))
            refs: list[dict[str, object]] = []
            for item in nodes:
                if not isinstance(item, dict):
                    continue
                label = str(item.get('label', '')).strip()
                if label and any(keyword in label for keyword in keywords if keyword):
                    refs.append(
                        {
                            'node_type': item.get('node_type'),
                            'label': label,
                            'chapter_first_seen': item.get('chapter_first_seen'),
                            'chapter_last_seen': item.get('chapter_last_seen'),
                        }
                    )
            return refs[:limit]

        def thematic_edge_refs(keywords: list[str], limit: int = 8) -> list[dict[str, object]]:
            edges = cast(list[object], reasoning_graph.get('edges', []))
            refs: list[dict[str, object]] = []
            for item in edges:
                if not isinstance(item, dict):
                    continue
                source = str(item.get('source', '')).strip()
                target = str(item.get('target', '')).strip()
                if any(
                    keyword in source or keyword in target
                    for keyword in keywords
                    if keyword
                ):
                    refs.append(
                        {
                            'edge_type': item.get('edge_type'),
                            'source': source,
                            'target': target,
                            'chapter_first_seen': item.get('chapter_first_seen'),
                            'chapter_last_seen': item.get('chapter_last_seen'),
                        }
                    )
            return refs[:limit]

        def timeline_points(
            chapters: list[int],
            facts: list[str],
            limit: int = 8,
        ) -> list[dict[str, object]]:
            points: list[dict[str, object]] = []
            for chapter, fact in zip(chapters[:limit], facts[:limit], strict=False):
                points.append({'chapter_index': chapter, 'summary': fact})
            return points

        character_questions = [
            f'角色“{label}”在当前分支的成长线如何推进？'
            for label in character_focus[:4]
        ]
        conflict_questions = [
            f'冲突“{label}”是如何升级并影响人物选择的？'
            for label in notes_from_summary('escalated_conflicts', 4)
        ]
        foreshadow_questions = [
            f'伏笔“{label}”的铺垫与兑现节奏是怎样的？'
            for label in notes_from_summary('paid_off_foreshadowing', 4)
        ]
        rule_questions = [
            f'规则“{label}”如何塑造故事推进与人物处境？'
            for label in notes_from_summary('constraining_world_rules', 4)
        ]

        conflict_keywords = notes_from_summary('escalated_conflicts', 4)
        foreshadow_keywords = (
            notes_from_summary('new_foreshadowing', 4)
            + notes_from_summary('paid_off_foreshadowing', 4)
        )[:4]
        rule_keywords = notes_from_summary('constraining_world_rules', 4)
        conflict_chapters = related_chapters_from_threads(
            'unresolved_threads',
            conflict_keywords,
        )
        foreshadow_chapters = related_chapters_from_threads(
            'state_transition_notes',
            foreshadow_keywords,
        )
        rule_chapters = related_chapters_from_threads(
            'evidence_backed_resolutions',
            rule_keywords,
        )
        character_matches: list[tuple[int, int]] = []
        for item in doc_summaries:
            chapter_index = item.get('chapter_index')
            if not isinstance(chapter_index, int):
                continue
            summary_text = str(item.get('summary_text', ''))
            score = score_text(summary_text, character_focus[:2])
            if score > 0:
                character_matches.append((chapter_index, score))
        character_matches.sort(key=lambda item: (-item[1], item[0]))
        character_chapters = [chapter for chapter, _ in character_matches[:6]]

        return {
            'character_arc': {
                'focus_entities': character_focus[:8],
                'recommended_questions': character_questions,
                'question_sequence': question_sequence(character_questions),
                'related_chapters': character_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    character_chapters,
                    character_focus[:4],
                ),
                'reasoning_paths': thematic_reasoning_paths(character_focus[:4]),
                'state_signals': thematic_state_signals(character_focus[:4]),
                'supporting_facts': thematic_supporting_facts(character_focus[:4]),
                'node_refs': thematic_node_refs(character_focus[:4]),
                'edge_refs': thematic_edge_refs(character_focus[:4]),
                'timeline_points': timeline_points(
                    character_chapters,
                    evidence_summaries_for_chapters(character_chapters, character_focus[:4]),
                ),
                'document_summaries': doc_summaries,
            },
            'conflict_arc': {
                'active_conflicts': notes_from_summary('new_conflicts'),
                'escalated_conflicts': notes_from_summary('escalated_conflicts'),
                'recommended_questions': conflict_questions,
                'question_sequence': question_sequence(conflict_questions),
                'related_chapters': conflict_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    conflict_chapters,
                    conflict_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'state_signals': thematic_state_signals(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'supporting_facts': thematic_supporting_facts(
                    notes_from_summary('escalated_conflicts', 4)
                ),
                'node_refs': thematic_node_refs(notes_from_summary('escalated_conflicts', 4)),
                'edge_refs': thematic_edge_refs(notes_from_summary('escalated_conflicts', 4)),
                'timeline_points': timeline_points(
                    conflict_chapters,
                    evidence_summaries_for_chapters(conflict_chapters, conflict_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('unresolved_threads'),
            },
            'foreshadow_arc': {
                'open_or_paid_off': (
                    notes_from_summary('new_foreshadowing')
                    + notes_from_summary('paid_off_foreshadowing')
                )[:8],
                'recommended_questions': foreshadow_questions,
                'question_sequence': question_sequence(foreshadow_questions),
                'related_chapters': foreshadow_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    foreshadow_chapters,
                    foreshadow_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('paid_off_foreshadowing', 4)
                ),
                'state_signals': thematic_state_signals(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'supporting_facts': thematic_supporting_facts(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'node_refs': thematic_node_refs(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'edge_refs': thematic_edge_refs(
                    (
                        notes_from_summary('new_foreshadowing', 4)
                        + notes_from_summary('paid_off_foreshadowing', 4)
                    )[:4]
                ),
                'timeline_points': timeline_points(
                    foreshadow_chapters,
                    evidence_summaries_for_chapters(foreshadow_chapters, foreshadow_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('state_transition_notes'),
            },
            'world_rule_arc': {
                'rules': (
                    notes_from_summary('observed_world_rules')
                    + notes_from_summary('constraining_world_rules')
                )[:8],
                'recommended_questions': rule_questions,
                'question_sequence': question_sequence(rule_questions),
                'related_chapters': rule_chapters,
                'evidence_summaries': evidence_summaries_for_chapters(
                    rule_chapters,
                    rule_keywords,
                ),
                'reasoning_paths': thematic_reasoning_paths(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'state_signals': thematic_state_signals(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'supporting_facts': thematic_supporting_facts(
                    notes_from_summary('constraining_world_rules', 4)
                ),
                'node_refs': thematic_node_refs(notes_from_summary('constraining_world_rules', 4)),
                'edge_refs': thematic_edge_refs(notes_from_summary('constraining_world_rules', 4)),
                'timeline_points': timeline_points(
                    rule_chapters,
                    evidence_summaries_for_chapters(rule_chapters, rule_keywords),
                ),
                'chapter_threads': rows_from_chapter_output('evidence_backed_resolutions'),
            },
        }

    @staticmethod
    def _aggregate_chapter_output_summaries(
        artifacts: Sequence[ChapterArtifact],
    ) -> dict[str, object]:
        """Aggregate chapter-level transition/resolution/thread notes for branch outputs."""

        def collect(key: str) -> list[dict[str, object]]:
            rows: list[dict[str, object]] = []
            for artifact in artifacts:
                payload = artifact.payload_json
                raw_items = payload.get(key, [])
                if not isinstance(raw_items, list):
                    continue
                for item in raw_items:
                    text = str(item).strip()
                    if text:
                        rows.append(
                            {
                                'chapter_index': artifact.chapter_index,
                                'note': text,
                            }
                        )
            return rows

        return {
            'state_transition_notes': collect('state_transition_notes'),
            'evidence_backed_resolutions': collect('evidence_backed_resolutions'),
            'unresolved_threads': collect('unresolved_threads'),
        }

    def export_branch_bundle(self, run_id: str, branch_id: str) -> dict[str, object]:
        """Return a JSON-serializable bundle for one branch."""

        status = self.status_service.get_run_status(run_id, branch_id)
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        windows = self.session.scalars(
            select(WindowArtifact)
            .where(WindowArtifact.branch_id == branch_id)
            .order_by(WindowArtifact.window_start_chapter)
        ).all()
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .order_by(GraphEdge.edge_type)
        ).all()
        reasoning_graph = self.graph_service.reasoning_snapshot(branch_id)
        chapter_rows = [
            {key: getattr(row, key) for key in row.__dataclass_fields__}
            for row in self.chapter_index_service.list_rows(branch_id)
        ]
        chapter_row_by_index = {
            int(row.get('chapter_index', 0)): row for row in chapter_rows
        }
        try:
            risk_cards = self.session.scalars(
                select(ChapterRiskCardRecord)
                .where(ChapterRiskCardRecord.branch_id == branch_id)
                .where(ChapterRiskCardRecord.visibility == 'active')
                .order_by(ChapterRiskCardRecord.chapter_index)
            ).all()
            checker_results = self.session.scalars(
                select(GateCheckerResultRecord)
                .where(GateCheckerResultRecord.branch_id == branch_id)
                .where(GateCheckerResultRecord.visibility == 'active')
                .order_by(GateCheckerResultRecord.chapter_index, GateCheckerResultRecord.checker_name)
            ).all()
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            risk_cards = []
            checker_results = []
        state_summary = self.graph_service.state_summary_from_snapshot(reasoning_graph)
        chapter_output_summary = self._aggregate_chapter_output_summaries(artifacts)
        risk_counts_by_domain: dict[str, int] = {}
        risk_counts_by_severity: dict[str, int] = {}
        high_risk_chapters: list[int] = []
        review_candidates_summary_by_chapter: dict[int, dict[str, object]] = {}
        for record in risk_cards:
            payload = cast(dict[str, object], record.payload_json)
            chapter_index = int(payload.get('chapter_index', 0))
            if str(payload.get('overall_risk_level', '')) == 'high':
                high_risk_chapters.append(chapter_index)
            for key, value in cast(dict[str, object], payload.get('risk_counts_by_domain', {})).items():
                risk_counts_by_domain[key] = risk_counts_by_domain.get(key, 0) + int(value)
            for key, value in cast(dict[str, object], payload.get('risk_counts_by_severity', {})).items():
                risk_counts_by_severity[key] = risk_counts_by_severity.get(key, 0) + int(value)
            top_risks = cast(list[dict[str, object]], payload.get('top_risks', []))
            top_risks = self._suppress_generic_review_candidates(top_risks)
            if top_risks:
                merged = review_candidates_summary_by_chapter.setdefault(
                    chapter_index,
                    {
                        'chapter_index': chapter_index,
                        'title': chapter_row_by_index.get(chapter_index, {}).get('title'),
                        'overall_risk_level': payload.get('overall_risk_level'),
                        'risk_count': 0,
                        'risk_types': [],
                        'checker_names': [],
                        'confidence': 0.0,
                        'summary': '',
                        'supporting_evidence_preview': [],
                        'counter_evidence_preview': [],
                        'needs_human_review': False,
                    },
                )
                merged['risk_count'] = max(int(merged.get('risk_count', 0)), len(top_risks))
                merged['overall_risk_level'] = (
                    payload.get('overall_risk_level')
                    if self._severity_rank(cast(str | None, payload.get('overall_risk_level')))
                    >= self._severity_rank(cast(str | None, merged.get('overall_risk_level')))
                    else merged.get('overall_risk_level')
                )
                merged['confidence'] = max(
                    float(merged.get('confidence', 0.0)),
                    max(float(risk.get('confidence') or 0.0) for risk in top_risks),
                )
                merged['needs_human_review'] = bool(merged.get('needs_human_review')) or any(
                    bool(risk.get('needs_human_review', True)) for risk in top_risks
                )
                merged['risk_types'] = self._dedupe_preview(
                    cast(list[object], merged.get('risk_types', []))
                    + [risk.get('risk_type') for risk in top_risks],
                    4,
                )
                merged['checker_names'] = self._dedupe_preview(
                    cast(list[object], merged.get('checker_names', []))
                    + [risk.get('checker_name') for risk in top_risks],
                    4,
                )
                top_risk = max(
                    top_risks,
                    key=lambda risk: (
                        self._risk_specificity_rank(cast(str | None, risk.get('risk_type'))),
                        self._severity_rank(cast(str | None, risk.get('severity'))),
                        float(risk.get('confidence') or 0.0),
                    ),
                )
                if not merged.get('summary') or len(str(top_risk.get('summary') or '')) > len(str(merged.get('summary') or '')):
                    merged['summary'] = top_risk.get('summary')
                merged['supporting_evidence_preview'] = self._dedupe_preview(
                    cast(list[object], merged.get('supporting_evidence_preview', []))
                    + [e for risk in top_risks for e in cast(list[object], risk.get('supporting_evidence', []))],
                    3,
                )
                merged['counter_evidence_preview'] = self._dedupe_preview(
                    cast(list[object], merged.get('counter_evidence_preview', []))
                    + [e for risk in top_risks for e in cast(list[object], risk.get('counter_evidence', []))],
                    2,
                )
                continuity_preview, branch_preview = self._chapter_continuity_preview(
                    chapter_index,
                    chapter_output_summary,
                    state_summary,
                    reasoning_graph,
                )
                merged['continuity_evidence_preview'] = continuity_preview
                merged['branch_signal_preview'] = branch_preview
        review_candidates_summary = list(review_candidates_summary_by_chapter.values())
        review_candidates_summary.sort(
            key=lambda item: (
                -self._severity_rank(cast(str | None, item.get('overall_risk_level'))),
                -max((self._risk_specificity_rank(risk_type) for risk_type in cast(list[str], item.get('risk_types', []))), default=-1),
                -int(item.get('risk_count', 0)),
                0 if bool(item.get('needs_human_review')) else 1,
                int(item.get('chapter_index', 0)),
            )
        )
        failed_summary = [
            {
                'chapter_index': item.chapter_index,
                'attempts': item.attempts,
                'error': item.last_error,
                'failure_class': item.failure_class,
                'failure_code': item.failure_code,
            }
            for item in self.run_service.list_failed_jobs(branch_id, limit=1000)
        ]
        audit_conclusion = self._build_audit_conclusion(
            completed_chapters=int(getattr(status, 'completed_chapters', 0)),
            manifest_chapter_count=int(getattr(status, 'manifest_chapter_count', 0)),
            failed_summary=failed_summary,
            high_risk_chapters=high_risk_chapters,
            review_candidate_count=len(review_candidates_summary),
        )
        review_candidate_clusters = self._cluster_review_candidates(review_candidates_summary)
        review_storage_mode = "db"
        try:
            persisted_cluster_states = self.cluster_review_service.read_branch(branch_id)
            history_by_cluster = {
                str(cluster.get('cluster_key') or ''): self.cluster_review_service.read_history(branch_id, str(cluster.get('cluster_key') or ''))
                for cluster in review_candidate_clusters
            }
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            persisted_cluster_states = read_cluster_review_state(branch_id)
            history_by_cluster = {}
            review_storage_mode = "file-fallback"
        for cluster in review_candidate_clusters:
            cluster_key = str(cluster.get('cluster_key') or '')
            override = persisted_cluster_states.get(str(cluster.get('cluster_key') or ''))
            if not override:
                override = {}
            if override.get('cluster_status'):
                cluster['cluster_status'] = override['cluster_status']
            if override.get('review_notes'):
                cluster['review_notes'] = override['review_notes']
            if override.get('review_owner'):
                cluster['review_owner'] = override['review_owner']
            if override.get('resolved_at'):
                cluster['resolved_at'] = override['resolved_at']
            if override.get('review_result'):
                cluster['review_result'] = override['review_result']
                cluster['review_result_label'] = self._review_result_label(override['review_result'])
            history = history_by_cluster.get(cluster_key, [])
            if history:
                cluster['review_history_count'] = len(history)
                cluster['review_history'] = history
                cluster['latest_review_event'] = history[-1]
            cluster['workflow_lane'] = self._derive_workflow_lane(cluster)
            cluster['queue_priority'] = self._derive_queue_priority(cluster)
            cluster['action_required'] = self._derive_action_required(cluster)
            cluster['suggested_deadline_level'] = self._derive_suggested_deadline_level(cluster)
            cluster['auto_next_action_code'] = self._derive_auto_next_action_code(cluster)
            cluster['auto_next_action'] = self._derive_auto_next_action(cluster)
            cluster['escalation_reason_code'] = self._derive_escalation_reason_code(cluster)
            escalation_reason = self._derive_escalation_reason(cluster)
            if escalation_reason:
                cluster['escalation_reason'] = escalation_reason
            cluster['close_ready_gate'] = self._derive_close_ready_gate(cluster)
            close_ready_reason = self._derive_close_ready_reason(cluster)
            if close_ready_reason:
                cluster['close_ready_reason'] = close_ready_reason
            cluster['close_stability_score'] = self._derive_close_stability_score(cluster)
            cluster['close_ready_rank_reason'] = self._derive_close_ready_rank_reason(cluster)
            cluster['close_batch_rank_score'] = self._derive_close_batch_rank_score(cluster)
            close_batch_rank_reason = self._derive_close_batch_rank_reason(cluster)
            if close_batch_rank_reason:
                cluster['close_batch_rank_reason'] = close_batch_rank_reason
            cluster['human_review_batch_rank_score'] = self._derive_human_review_batch_rank_score(cluster)
            human_review_batch_rank_reason = self._derive_human_review_batch_rank_reason(cluster)
            if human_review_batch_rank_reason:
                cluster['human_review_batch_rank_reason'] = human_review_batch_rank_reason
            cluster['escalation_urgency_score'] = self._derive_escalation_urgency_score(cluster)
            cluster['escalation_tier'] = self._derive_escalation_tier(cluster)
            escalation_rank_reason = self._derive_escalation_rank_reason(cluster)
            if escalation_rank_reason:
                cluster['escalation_rank_reason'] = escalation_rank_reason
            cluster['escalation_batch_rank_score'] = self._derive_escalation_batch_rank_score(cluster)
            escalation_batch_rank_reason = self._derive_escalation_batch_rank_reason(cluster)
            if escalation_batch_rank_reason:
                cluster['escalation_batch_rank_reason'] = escalation_batch_rank_reason
            cluster['batch_operation_hint'] = self._derive_batch_operation_hint(cluster)
        resolved_cluster_count = sum(
            1 for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') == 'resolved'
        )
        needs_review_cluster_count = sum(
            1 for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') == 'needs_review'
        )
        review_result_counts: dict[str, int] = {}
        review_owner_counts: dict[str, int] = {}
        review_actor_counts: dict[str, int] = {}
        latest_event_type_counts: dict[str, int] = {}
        pending_assignment_clusters: list[dict[str, object]] = []
        latest_review_event_overall: dict[str, object] | None = None
        for cluster in review_candidate_clusters:
            result = str(cluster.get('review_result') or '').strip()
            if result:
                review_result_counts[result] = review_result_counts.get(result, 0) + 1
            owner = str(cluster.get('review_owner') or '').strip()
            if owner:
                review_owner_counts[owner] = review_owner_counts.get(owner, 0) + 1
            latest_event = cluster.get('latest_review_event')
            if isinstance(latest_event, dict) and str(latest_event.get('review_actor') or '').strip():
                actor = str(latest_event.get('review_actor') or '').strip()
                review_actor_counts[actor] = review_actor_counts.get(actor, 0) + 1
            if isinstance(latest_event, dict) and str(latest_event.get('event_type') or '').strip():
                event_type = str(latest_event.get('event_type') or '').strip()
                latest_event_type_counts[event_type] = latest_event_type_counts.get(event_type, 0) + 1
                if (
                    event_type == 'assignment_update'
                    and str(cluster.get('cluster_status') or '') != 'resolved'
                ):
                    pending_assignment_clusters.append(cluster)
            if isinstance(latest_event, dict) and latest_event:
                if latest_review_event_overall is None:
                    latest_review_event_overall = latest_event
                elif str(latest_event.get('review_owner') or '') and not str(latest_review_event_overall.get('review_owner') or ''):
                    latest_review_event_overall = latest_event
        effective_unresolved_cluster_count = sum(
            1
            for cluster in review_candidate_clusters
            if str(cluster.get('cluster_status') or '') != 'resolved'
            and str(cluster.get('review_result') or '') != 'confirmed-benign'
        )
        if resolved_cluster_count or needs_review_cluster_count:
            note_parts: list[str] = []
            if resolved_cluster_count:
                note_parts.append(f'已人工处理问题簇 {resolved_cluster_count} 个')
            if needs_review_cluster_count:
                note_parts.append(f'仍待人工复核问题簇 {needs_review_cluster_count} 个')
            audit_conclusion['review_progress_note'] = '；'.join(note_parts) + '。'
        if needs_review_cluster_count:
            audit_conclusion['needs_review_note'] = (
                f'当前仍有 {needs_review_cluster_count} 个问题簇处于 needs_review，建议优先安排人工复核。'
            )
        if resolved_cluster_count:
            audit_conclusion['resolved_cluster_note'] = (
                f'当前已有 {resolved_cluster_count} 个问题簇被标记为 resolved。'
            )
        if review_result_counts:
            result_note_parts: list[str] = []
            labels = {
                'confirmed-issue': '已确认有问题',
                'confirmed-benign': '已确认无问题',
                'needs-escalation': '需升级处理',
                'deferred': '暂缓判断',
            }
            for key in ['confirmed-issue', 'confirmed-benign', 'needs-escalation', 'deferred']:
                count = review_result_counts.get(key, 0)
                if count:
                    result_note_parts.append(f"{labels[key]} {count} 个")
            if result_note_parts:
                audit_conclusion['review_result_note'] = '；'.join(result_note_parts) + '。'
        pending_escalation_count = review_result_counts.get('needs-escalation', 0)
        if pending_escalation_count:
            audit_conclusion['pending_escalation_note'] = (
                f'当前有 {pending_escalation_count} 个问题簇等待升级处理，建议尽快转入高等级复核。'
            )
        audit_conclusion['review_storage_note'] = (
            '当前 review 数据来自数据库主路径。'
            if review_storage_mode == 'db'
            else '当前 review 数据来自兼容 fallback 路径。'
        )
        if review_owner_counts:
            owner, count = sorted(review_owner_counts.items(), key=lambda item: (-item[1], item[0]))[0]
            audit_conclusion['review_owner_note'] = f'当前已记录复核人中，{owner} 处理了 {count} 个问题簇。'
            audit_conclusion['current_owner_note'] = f'当前问题簇负责人分布中，{owner} 负责 {count} 个问题簇。'
        if review_actor_counts:
            actor, count = sorted(review_actor_counts.items(), key=lambda item: (-item[1], item[0]))[0]
            audit_conclusion['review_actor_note'] = f'最近审查动作记录中，{actor} 执行了 {count} 次变更。'
        if latest_event_type_counts:
            latest_event_type, count = sorted(
                latest_event_type_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[0]
            audit_conclusion['latest_event_type_note'] = (
                f'最近一批问题簇的最新动作类型中，{latest_event_type} 出现了 {count} 次。'
            )
        if pending_assignment_clusters:
            top_cluster = pending_assignment_clusters[0]
            audit_conclusion['pending_assignment_note'] = (
                f"存在 {len(pending_assignment_clusters)} 个已交接但未闭环的问题簇；"
                f"优先关注 {top_cluster.get('cluster_title') or top_cluster.get('cluster_key')}"
                f"（owner={top_cluster.get('review_owner') or 'unknown'}）。"
            )
        if latest_review_event_overall:
            audit_conclusion['latest_review_note'] = (
                f"最近一次复核记录：状态={latest_review_event_overall.get('cluster_status')}，"
                f"结果={latest_review_event_overall.get('review_result')}，"
                f"处理人={latest_review_event_overall.get('review_owner') or 'unknown'}，"
                f"操作人={latest_review_event_overall.get('review_actor') or latest_review_event_overall.get('review_owner') or 'unknown'}。"
            )
        if (
            not failed_summary
            and not high_risk_chapters
            and review_candidate_clusters
            and effective_unresolved_cluster_count == 0
        ):
            audit_conclusion['risk_judgement'] = '当前候选问题簇已完成人工复核，未见需继续升级的明确风险。'
            audit_conclusion['recommended_action'] = '可保留复核记录并继续后续章节审查。'
        review_summary = self._build_review_summary(
            review_candidate_clusters=review_candidate_clusters,
            review_storage_mode=review_storage_mode,
        )
        return {
            'status': {
                key: getattr(status, key) for key in status.__dataclass_fields__
            },
            'chapter_index': chapter_rows,
            'windows': [window.payload_json for window in windows],
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'chapter_first_seen': node.chapter_first_seen,
                    'chapter_last_seen': node.chapter_last_seen,
                    'occurrence_count': node.occurrence_count,
                    'metadata': node.metadata_json,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source_node_id': edge.source_node_id,
                    'target_node_id': edge.target_node_id,
                    'weight': edge.weight,
                    'chapter_first_seen': edge.chapter_first_seen,
                    'chapter_last_seen': edge.chapter_last_seen,
                    'metadata': edge.metadata_json,
                }
                for edge in edges
            ],
            'reasoning_graph': reasoning_graph,
            'state_summary': state_summary,
            'chapter_output_summary': chapter_output_summary,
            'failed_summary': failed_summary,
            'audit_conclusion': audit_conclusion,
            'review_storage_mode': review_storage_mode,
            'review_summary': review_summary,
            'risk_summary': {
                'risk_card_count': len(risk_cards),
                'checker_result_count': len(checker_results),
                'review_candidate_count': len(review_candidates_summary),
                'high_risk_chapters': high_risk_chapters,
                'risk_counts_by_domain': risk_counts_by_domain,
                'risk_counts_by_severity': risk_counts_by_severity,
                'review_candidates_summary': review_candidates_summary[:20],
                'review_candidate_clusters': review_candidate_clusters,
            },
        }

    def export_chapter_bundle(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return a chapter-level bundle with artifact, facts, retrieval, and graph slices."""

        artifact = self.session.scalar(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.chapter_index == chapter_index)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.created_at.desc())
        )
        if artifact is None:
            raise ValueError('chapter artifact not found')

        facts = self.session.scalars(
            select(FactRecord)
            .where(FactRecord.branch_id == branch_id)
            .where(FactRecord.chapter_index == chapter_index)
            .order_by(FactRecord.fact_type, FactRecord.label)
        ).all()
        retrieval = self.session.scalar(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == branch_id)
            .where(RetrievalDocument.chapter_index == chapter_index)
        )
        nodes = self.session.scalars(
            select(GraphNode)
            .where(GraphNode.branch_id == branch_id)
            .where(GraphNode.chapter_first_seen <= chapter_index)
            .where(GraphNode.chapter_last_seen >= chapter_index)
            .order_by(GraphNode.node_type, GraphNode.label)
        ).all()
        node_by_id = {node.id: node for node in nodes}
        edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.chapter_first_seen <= chapter_index)
            .where(GraphEdge.chapter_last_seen >= chapter_index)
            .order_by(GraphEdge.edge_type)
        ).all()

        reasoning_graph = self.graph_service.reasoning_snapshot(
            branch_id,
            upto_chapter=chapter_index,
        )
        state_summary = self.graph_service.state_summary_from_snapshot(
            reasoning_graph,
            chapter_index=chapter_index,
        )
        try:
            risk_card = self.session.scalar(
                select(ChapterRiskCardRecord)
                .where(ChapterRiskCardRecord.branch_id == branch_id)
                .where(ChapterRiskCardRecord.chapter_index == chapter_index)
                .where(ChapterRiskCardRecord.visibility == 'active')
                .order_by(ChapterRiskCardRecord.created_at.desc())
            )
        except (OperationalError, ProgrammingError) as exc:
            if not self._is_missing_relation_error(exc):
                raise
            self.session.rollback()
            risk_card = None
        artifact_payload = {
            **artifact.payload_json,
            'state_summary': state_summary,
        }

        return {
            'chapter_index': chapter_index,
            'artifact': artifact_payload,
            'facts': [
                {
                    'fact_type': fact.fact_type,
                    'label': fact.label,
                    'confidence': fact.confidence,
                    'evidence_list': fact.evidence_list,
                }
                for fact in facts
            ],
            'retrieval': {
                'title': retrieval.title if retrieval else None,
                'summary_text': retrieval.summary_text if retrieval else None,
                'keyword_list': retrieval.keyword_list if retrieval else [],
                'query_hints': retrieval.query_hints if retrieval else [],
            },
            'graph_nodes': [
                {
                    'node_type': node.node_type,
                    'label': node.label,
                    'occurrence_count': node.occurrence_count,
                    'metadata': node.metadata_json,
                }
                for node in nodes
            ],
            'graph_edges': [
                {
                    'edge_type': edge.edge_type,
                    'source': (
                        node_by_id[edge.source_node_id].label
                        if edge.source_node_id in node_by_id
                        else edge.source_node_id
                    ),
                    'target': (
                        node_by_id[edge.target_node_id].label
                        if edge.target_node_id in node_by_id
                        else edge.target_node_id
                    ),
                    'weight': edge.weight,
                    'metadata': edge.metadata_json,
                }
                for edge in edges
            ],
            'reasoning_graph': reasoning_graph,
            'state_summary': state_summary,
            'risk_card': risk_card.payload_json if risk_card is not None else None,
            'foreshadowing_threads': self._export_foreshadowing(branch_id, chapter_index),
            'causal_chains': self._export_causal_chains(branch_id, chapter_index),
        }

    def _export_foreshadowing(self, branch_id: str, chapter_index: int) -> list[dict[str, object]]:
        threads = self.foreshadowing_service.get_open_threads(
            branch_id, before_chapter=chapter_index + 1, limit=20,
        )
        return [
            {
                'label': t.label,
                'status': t.status,
                'chapter_planted': t.chapter_planted,
                'chapter_last_seen': t.chapter_last_seen,
                'age': chapter_index - t.chapter_planted,
                'reinforcement_count': t.reinforcement_count,
                'evidence': t.evidence[:3],
            }
            for t in threads
        ]

    def _export_causal_chains(self, branch_id: str, chapter_index: int) -> list[dict[str, object]]:
        causal_edges = self.session.scalars(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(GraphEdge.edge_type.in_(list(CAUSAL_EDGE_TYPES)))
            .where(GraphEdge.chapter_first_seen <= chapter_index)
            .order_by(GraphEdge.weight.desc(), GraphEdge.chapter_first_seen.desc())
            .limit(15)
        ).all()
        chains: list[dict[str, object]] = []
        for edge in causal_edges:
            source = self.session.scalar(
                select(GraphNode).where(GraphNode.id == edge.source_node_id)
            )
            target = self.session.scalar(
                select(GraphNode).where(GraphNode.id == edge.target_node_id)
            )
            if source and target:
                chains.append({
                    'source': source.label,
                    'target': target.label,
                    'edge_type': edge.edge_type,
                    'chapter': edge.chapter_first_seen,
                    'weight': edge.weight,
                    'confidence': (edge.metadata_json or {}).get('confidence', 0.5),
                })
        return chains

    def export_causal_mermaid(self, branch_id: str, chapter_index: int) -> str:
        """Generate a Mermaid flowchart from causal chains up to a given chapter."""
        chains = self._export_causal_chains(branch_id, chapter_index)
        if not chains:
            return ''
        lines = ['graph LR']
        node_ids: dict[str, str] = {}
        counter = [0]

        def _node_id(label: str) -> str:
            if label not in node_ids:
                counter[0] += 1
                node_ids[label] = f'N{counter[0]}'
            return node_ids[label]

        edge_labels = {
            'causes': '导致',
            'enables': '使得',
            'prevents': '阻止',
            'triggers': '触发',
            'blocks': '阻断',
        }
        for chain in chains:
            src = _node_id(str(chain['source']))
            tgt = _node_id(str(chain['target']))
            edge_type = str(chain.get('edge_type', 'causes'))
            label = edge_labels.get(edge_type, edge_type)
            ch = chain.get('chapter', '?')
            lines.append(f'    {src}["{chain["source"]}"] -->|{label} ch{ch}| {tgt}["{chain["target"]}"]')
        return '\n'.join(lines)

    def export_foreshadowing_timeline_mermaid(self, branch_id: str, chapter_index: int) -> str:
        """Generate a Mermaid gantt chart for foreshadowing thread lifecycles."""
        threads = self._export_foreshadowing(branch_id, chapter_index)
        if not threads:
            return ''
        lines = [
            'gantt',
            '    title 伏笔生命周期',
            '    dateFormat X',
            '    axisFormat Ch%s',
        ]
        for t in threads:
            status_tag = 'active' if t['status'] in ('planted', 'reinforced') else 'done'
            start = t['chapter_planted']
            end = t['chapter_last_seen']
            duration = max(1, end - start + 1)
            lines.append(
                f'    {t["label"]} :{status_tag}, {start}, {duration}'
            )
        return '\n'.join(lines)

    def export_chapter_qa_context(self, branch_id: str, chapter_index: int) -> dict[str, object]:
        """Return a question-answering context package for one chapter."""

        bundle = self.export_chapter_bundle(branch_id, chapter_index)
        artifact = cast(dict[str, object], bundle['artifact'])
        retrieval = cast(dict[str, object], bundle['retrieval'])
        payload = {
            'chapter_index': chapter_index,
            'title': artifact.get('normalized_title'),
            'chapter_summary': artifact.get('chapter_summary'),
            'key_events': artifact.get('key_events', []),
            'state_transition_notes': artifact.get('state_transition_notes', []),
            'evidence_backed_resolutions': artifact.get('evidence_backed_resolutions', []),
            'unresolved_threads': artifact.get('unresolved_threads', []),
            'facts': bundle['facts'],
            'retrieval': retrieval,
            'query_hints': retrieval.get('query_hints', []),
            'recommended_questions': self._recommended_questions_for_chapter(
                artifact,
                retrieval,
            ),
            'reasoning_graph': bundle['reasoning_graph'],
            'state_summary': bundle['state_summary'],
        }
        return ChapterQAContextOutput.model_validate(payload).model_dump(mode='json')

    def export_branch_qa_context(self, run_id: str, branch_id: str) -> dict[str, object]:
        """Return a branch-level QA context package for downstream tools."""

        bundle = self.export_branch_bundle(run_id, branch_id)
        docs = self.session.scalars(
            select(RetrievalDocument)
            .where(RetrievalDocument.branch_id == branch_id)
            .order_by(RetrievalDocument.chapter_index)
        ).all()
        payload = {
            'status': bundle['status'],
            'chapter_index': bundle['chapter_index'],
            'windows': bundle['windows'],
            'state_summary': bundle['state_summary'],
            'chapter_output_summary': bundle['chapter_output_summary'],
            'reasoning_graph': bundle['reasoning_graph'],
            'retrieval_documents': [
                {
                    'chapter_index': doc.chapter_index,
                    'title': doc.title,
                    'summary_text': doc.summary_text,
                    'keyword_list': doc.keyword_list,
                    'query_hints': doc.query_hints,
                }
                for doc in docs
            ],
        }
        payload['recommended_questions'] = self._recommended_questions_for_branch(payload)
        payload['thematic_contexts'] = self._thematic_contexts_for_branch(payload)
        return BranchQAContextOutput.model_validate(payload).model_dump(mode='json')
