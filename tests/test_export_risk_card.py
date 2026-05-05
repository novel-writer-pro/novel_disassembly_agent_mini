from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_schema
from novel_analyzer.runtime.cluster_review_state import (
    read_cluster_review_history,
    write_cluster_review_state,
)
from novel_analyzer.services.cluster_review_service import ClusterReviewService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_schema(engine)
    return Session(engine)


def test_export_chapter_bundle_includes_risk_card(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "unsupported_inferences": [],
                "ambiguous_points": [],
                "needs_human_review": True,
                "quality_gate_notes": [],
                "hook_score": 4.0,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_chapter_bundle(branch.id, 1)
        assert bundle["risk_card"] is not None
        assert bundle["risk_card"]["top_risks"][0]["checker_name"] == "character_ooc"

        branch_bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        assert branch_bundle["review_storage_mode"] in {"db", "file-fallback"}
        assert branch_bundle["review_summary"]["cluster_count"] == 1
        assert branch_bundle["review_summary"]["by_priority"]["P2"] == 1
        assert branch_bundle["review_summary"]["by_workflow_lane"]["human_review_queue"] == 1
        assert branch_bundle["review_summary"]["by_queue_priority"]["medium"] == 1
        assert branch_bundle["review_summary"]["by_deadline_level"]["normal"] == 1
        assert branch_bundle["review_summary"]["by_batch_operation_hint"]["batch_human_review_queue"] == 1
        assert branch_bundle["review_summary"]["by_escalation_tier"] == {}
        assert branch_bundle["review_summary"]["by_auto_next_action"]
        assert branch_bundle["review_summary"]["by_auto_next_action_code"]["schedule_human_review"] == 1
        assert branch_bundle["review_summary"]["workflow_lane_top"] == "human_review_queue"
        assert branch_bundle["review_summary"]["queue_priority_top"] == "medium"
        assert branch_bundle["review_summary"]["deadline_level_top"] == "normal"
        assert branch_bundle["review_summary"]["batch_operation_hint_top"] == "batch_human_review_queue"
        assert branch_bundle["review_summary"]["auto_next_action_code_top"] == "schedule_human_review"
        assert branch_bundle["review_summary"]["auto_next_action_top"]
        assert branch_bundle["review_summary"]["action_required_count"] == 1
        assert branch_bundle["review_summary"]["by_phase2_focus"] == {}
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["hint_code"] == "batch_human_review_queue"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["action_bucket"] == "review"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["batch_priority"] == "medium"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["suggestion_rank_score"] > 0
        assert "suggestion_rank_score" in branch_bundle["review_summary"]["batch_suggestions"][0]["suggestion_rank_reason"]
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["group_strategy"] == "by_checker_span"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["span_bucket"] == "single"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["primary_checker"] == "character_ooc"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["pattern_label_top"] == "单点问题"
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["suggested_cluster_order"]
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["suggested_cluster_order_titles"]
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["suggested_cluster_order_details"]
        assert (
            branch_bundle["review_summary"]["batch_suggestions"][0]["ordering_strategy"]
            == "queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter"
        )
        assert (
            branch_bundle["review_summary"]["batch_suggestions"][0]["suggested_cluster_order_details"][0]["human_review_batch_rank_score"]
            > 0
        )
        assert branch_bundle["review_summary"]["batch_suggestions"][0]["suggested_first_cluster_reason"]
        assert branch_bundle["review_summary"]["needs_review_count"] == 1
        assert branch_bundle["review_summary"]["resolved_count"] == 0
        assert branch_bundle["review_summary"]["pending_escalation_count"] == 0
        assert branch_bundle["risk_summary"]["risk_card_count"] == 1
        assert branch_bundle["risk_summary"]["checker_result_count"] == 9
        assert branch_bundle["risk_summary"]["review_candidate_count"] == 1
        assert branch_bundle["audit_conclusion"]
        assert branch_bundle["audit_conclusion"]["content_judgement"]
        assert branch_bundle["audit_conclusion"]["risk_judgement"]
        assert branch_bundle["audit_conclusion"]["blocking_judgement"]
        assert branch_bundle["audit_conclusion"]["recommended_action"]
        assert branch_bundle["risk_summary"]["review_candidates_summary"]
        assert branch_bundle["risk_summary"]["review_candidate_clusters"]
        candidate = branch_bundle["risk_summary"]["review_candidates_summary"][0]
        assert "checker_names" in candidate
        assert "risk_types" in candidate
        assert "continuity_evidence_preview" in candidate
        assert "branch_signal_preview" in candidate
        cluster = branch_bundle["risk_summary"]["review_candidate_clusters"][0]
        assert "cluster_title" in cluster
        assert "suggested_review_action" in cluster
        assert cluster["workflow_lane"] == "human_review_queue"
        assert cluster["queue_priority"] == "medium"
        assert cluster["action_required"] is True
        assert cluster["suggested_deadline_level"] == "normal"
        assert cluster["close_ready_gate"] is False
        assert "close_stability_score" in cluster["close_ready_rank_reason"]
        assert cluster["close_batch_rank_score"] == 0
        assert cluster["human_review_batch_rank_score"] > 0
        assert "human_review_batch_rank_score" in cluster["human_review_batch_rank_reason"]
        assert cluster["escalation_urgency_score"] == 0
        assert cluster["batch_operation_hint"] == "batch_human_review_queue"
        assert cluster["auto_next_action_code"] == "schedule_human_review"
        assert cluster["auto_next_action"]
        assert cluster["review_priority"] in {"P1", "P2", "P3"}
        assert cluster["cluster_status"] in {
            "open",
            "needs_review",
            "reviewed",
            "escalated",
            "reopened",
            "resolved",
        }
        assert cluster["pattern_label"] in {"单点问题", "集中爆发型问题", "持续型问题"}
        assert "chapters" in cluster
        assert "chapter_span" in cluster
        assert "chapter_count" in cluster
        assert branch_bundle["failed_summary"] == []


def test_branch_snapshot_rows_include_risk_level_and_count(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "quality_gate_notes": [],
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        row = ExportService(session).chapter_index_service.list_rows(branch.id)[0]
        assert row.risk_level in {"medium", "high", "low"}
        assert row.risk_count >= 1


def test_review_candidate_prefers_more_specific_cross_checker_signal(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "跨 checker 候选排序测试",
                "chapter_summary": "本章存在人物与规则双重可疑点。",
                "key_entities": ["卫图"],
                "key_events": ["卫图突然突破限制"],
                "continuity_notes": ["主线推进。"],
                "ambiguous_points": ["人物态度变化存在歧义。"],
                "needs_human_review": True,
                "world_rule_issues": [
                    {
                        "risk_type": "rule_consistency",
                        "severity": "medium",
                        "summary": "本章对规则限制的突破缺少明确解释。",
                        "supporting_evidence": ["命格限制突然被绕过"],
                        "counter_evidence": ["也可能是特殊条件触发"],
                    }
                ],
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        branch_bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        candidate = branch_bundle["risk_summary"]["review_candidates_summary"][0]
        assert "world_rule_consistency" in candidate["checker_names"]
        assert candidate["summary"] == "本章对规则限制的突破缺少明确解释。"
        assert "rule_consistency" in candidate["risk_types"]
        cluster = branch_bundle["risk_summary"]["review_candidate_clusters"][0]
        assert "规则" in cluster["cluster_title"]
        assert "human_review_candidate" not in candidate["risk_types"]
        assert "rule_consistency" in cluster["risk_types"]
        assert cluster["sample_summary"] == "本章对规则限制的突破缺少明确解释。"


def test_build_audit_conclusion_uses_failed_and_candidate_signals() -> None:
    conclusion = ExportService._build_audit_conclusion(
        completed_chapters=103,
        manifest_chapter_count=775,
        failed_summary=[{"chapter_index": 104}],
        high_risk_chapters=[],
        review_candidate_count=4,
    )
    assert "阶段性审查结果" in conclusion["content_judgement"]
    assert "执行阻塞" in conclusion["blocking_judgement"]
    assert "失败章节" in conclusion["recommended_action"]


def test_build_audit_conclusion_uses_dense_candidate_threshold() -> None:
    conclusion = ExportService._build_audit_conclusion(
        completed_chapters=120,
        manifest_chapter_count=150,
        failed_summary=[],
        high_risk_chapters=[],
        review_candidate_count=6,
    )
    assert "候选风险分布较密集" in conclusion["content_judgement"]
    assert "人工复核候选较多" in conclusion["risk_judgement"]


def test_derive_cluster_status_prefers_needs_review_for_dense_or_high_confidence_clusters() -> None:
    assert (
        ExportService._derive_cluster_status(
            chapter_count=5, max_confidence=0.2, review_priority_value="P3"
        )
        == "needs_review"
    )
    assert (
        ExportService._derive_cluster_status(
            chapter_count=1, max_confidence=0.7, review_priority_value="P3"
        )
        == "needs_review"
    )
    assert (
        ExportService._derive_cluster_status(
            chapter_count=1, max_confidence=0.2, review_priority_value="P1"
        )
        == "needs_review"
    )
    assert (
        ExportService._derive_cluster_status(
            chapter_count=1, max_confidence=0.2, review_priority_value="P3"
        )
        == "open"
    )


def test_cluster_review_candidates_prefers_sustained_and_more_specific_items_first() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 10,
                "checker_names": ["character_ooc"],
                "risk_types": ["human_review_candidate"],
                "confidence": 0.35,
                "summary": "泛化候选",
                "title": "第10章",
            },
            {
                "chapter_index": 14,
                "checker_names": ["character_ooc"],
                "risk_types": ["relationship_shift_candidate"],
                "confidence": 0.35,
                "summary": "关系漂移",
                "title": "第14章",
            },
            {
                "chapter_index": 30,
                "checker_names": ["world_rule_consistency"],
                "risk_types": ["rule_support_gap"],
                "confidence": 0.6,
                "summary": "规则支撑缺口",
                "title": "第30章",
            },
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] in {
        "人物风险簇：relationship_shift_candidate",
        "规则风险簇：rule_support_gap",
    }


def test_phase2_specific_risk_types_get_stable_cluster_titles_and_actions() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 12,
                "checker_names": ["timeline_consistency"],
                "risk_types": ["recovery_window_insufficient"],
                "confidence": 0.32,
                "summary": "恢复窗口不足",
                "title": "第12章",
                "needs_human_review": True,
            },
            {
                "chapter_index": 18,
                "checker_names": ["power_scaling_consistency"],
                "risk_types": ["cost_constraint_missing"],
                "confidence": 0.31,
                "summary": "代价限制缺口",
                "title": "第18章",
                "needs_human_review": True,
            },
        ]
    )
    assert len(clusters) == 2
    titles = {cluster["cluster_title"] for cluster in clusters}
    assert "恢复窗口不足候选簇" in titles
    assert "代价约束缺口候选簇" in titles
    for cluster in clusters:
        assert cluster["review_priority"] == "P2"
        assert cluster["suggested_review_action"]


def test_phase2_plot_risk_type_gets_specialized_cluster_title() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 22,
                "checker_names": ["plot_logic_consistency"],
                "risk_types": ["thread_state_conflict"],
                "confidence": 0.34,
                "summary": "线程状态冲突",
                "title": "第22章",
                "needs_human_review": True,
            }
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] == "剧情线程状态冲突簇"
    assert "已解决" in clusters[0]["suggested_review_action"] or "未解线程" in clusters[0]["suggested_review_action"]


def test_relationship_risk_type_gets_stable_cluster_title_and_action() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 33,
                "checker_names": ["relationship_consistency"],
                "risk_types": ["relationship_shift_without_bridge"],
                "confidence": 0.34,
                "summary": "关系变化桥接不足",
                "title": "第33章",
                "needs_human_review": True,
            }
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] == "关系风险簇：relationship_shift_without_bridge"
    assert "关系" in clusters[0]["suggested_review_action"]


def test_foreshadow_risk_type_gets_stable_cluster_title_and_action() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 41,
                "checker_names": ["foreshadow_payoff_consistency"],
                "risk_types": ["payoff_without_setup"],
                "confidence": 0.33,
                "summary": "兑现缺少铺垫",
                "title": "第41章",
                "needs_human_review": True,
            }
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] == "伏笔兑现风险簇：payoff_without_setup"
    assert "铺垫" in clusters[0]["suggested_review_action"] or "伏笔" in clusters[0]["suggested_review_action"]


def test_setting_scope_risk_type_gets_stable_cluster_title_and_action() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 52,
                "checker_names": ["setting_scope_consistency"],
                "risk_types": ["constraint_scope_expansion"],
                "confidence": 0.33,
                "summary": "作用域异常放大",
                "title": "第52章",
                "needs_human_review": True,
            }
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] == "设定作用域风险簇：constraint_scope_expansion"
    assert "范围" in clusters[0]["suggested_review_action"] or "权限" in clusters[0]["suggested_review_action"]


def test_thread_closure_risk_type_gets_stable_cluster_title_and_action() -> None:
    clusters = ExportService._cluster_review_candidates(
        [
            {
                "chapter_index": 61,
                "checker_names": ["thread_closure_consistency"],
                "risk_types": ["thread_dropped_after_escalation"],
                "confidence": 0.33,
                "summary": "升级冲突后失去承接",
                "title": "第61章",
                "needs_human_review": True,
            }
        ]
    )
    assert clusters
    assert clusters[0]["cluster_title"] == "线程收束风险簇：thread_dropped_after_escalation"
    assert "冲突" in clusters[0]["suggested_review_action"] or "线程" in clusters[0]["suggested_review_action"]


def test_phase2_summary_tracks_phase2_focus_bucket(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "恢复窗口测试",
                "chapter_summary": "本章恢复时长存在可疑压缩。",
                "key_entities": ["卫图"],
                "key_events": ["卫图三日后回城又当夜再战"],
                "continuity_notes": ["主线推进。"],
                "timeline_signals": ["三日后回城", "当夜再次出手"],
                "unsupported_inferences": ["“当夜已完成全部恢复”缺少直接证据支撑"],
                "needs_human_review": True,
                "quality_gate_notes": [],
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        branch_bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        assert branch_bundle["review_summary"]["by_phase2_focus"]["timeline-phase2"] == 1
        assert branch_bundle["review_summary"]["phase2_focus_top"] == "timeline-phase2"
        assert branch_bundle["review_summary"]["phase2_focus_top_count"] == 1
        cluster = branch_bundle["risk_summary"]["review_candidate_clusters"][0]
        assert cluster["queue_priority"] == "high"
        assert cluster["auto_next_action_code"] == "prioritize_phase2_human_review"
        assert "时间线/恢复窗口" in cluster["auto_next_action"]
        assert cluster["escalation_reason_code"] == "phase2_risk_requires_human_confirmation"
        assert "phase-2" in cluster["escalation_reason"]
        suggestion = branch_bundle["review_summary"]["batch_suggestions"][0]
        assert suggestion["phase2_focus_top"] == "timeline-phase2"


def test_export_branch_bundle_applies_manual_cluster_status_override(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster = bundle["risk_summary"]["review_candidate_clusters"][0]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster["cluster_key"],
            cluster_status="resolved",
            review_notes="已人工复核",
            review_result="confirmed-benign",
        )
        overridden = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster2 = overridden["risk_summary"]["review_candidate_clusters"][0]
        assert cluster2["cluster_status"] == "resolved"
        assert cluster2["review_notes"] == "已人工复核"


def test_export_branch_bundle_applies_manual_cluster_metadata_override(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "命格初现",
                "chapter_summary": "卫图在本章做出异常决定。",
                "key_entities": ["卫图"],
                "key_events": ["卫图做出异常决定"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster = bundle["risk_summary"]["review_candidate_clusters"][0]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster["cluster_key"],
            cluster_status="resolved",
            review_notes="已复核并确认无问题",
            review_owner="editor-a",
            review_actor="review-bot",
            resolved_at="2026-04-29T02:00:00Z",
            review_result="confirmed-benign",
        )
        overridden = ExportService(session).export_branch_bundle(run.id, branch.id)
        cluster2 = overridden["risk_summary"]["review_candidate_clusters"][0]
        assert cluster2["review_owner"] == "editor-a"
        assert cluster2["resolved_at"] == "2026-04-29T02:00:00Z"
        assert cluster2["review_result"] == "confirmed-benign"
        assert cluster2["review_result_label"] == "确认无问题"
        assert cluster2["review_history_count"] >= 1
        assert isinstance(cluster2["review_history"], list)
        assert cluster2["latest_review_event"]["review_owner"] == "editor-a"
        assert cluster2["latest_review_event"]["review_actor"] == "review-bot"
        assert cluster2["latest_review_event"]["created_at"]
        assert cluster2["workflow_lane"] == "resolved_queue"
        assert cluster2["queue_priority"] == "done"
        assert cluster2["action_required"] is False
        assert cluster2["suggested_deadline_level"] == "none"
        assert cluster2["close_ready_gate"] is True
        assert "已满足关闭归档条件" in cluster2["close_ready_reason"]
        assert cluster2["close_stability_score"] > 0
        assert cluster2["close_batch_rank_score"] > 0
        assert "close_batch_rank_score" in cluster2["close_batch_rank_reason"]
        assert cluster2["batch_operation_hint"] == "batch_close_ready_candidates"
        assert cluster2["auto_next_action_code"] == "archive_and_monitor"
        assert "保留" in cluster2["auto_next_action"]
        assert "review_progress_note" in overridden["audit_conclusion"]
        assert "resolved_cluster_note" in overridden["audit_conclusion"]
        assert "review_result_note" in overridden["audit_conclusion"]
        assert "review_storage_note" in overridden["audit_conclusion"]
        assert "review_owner_note" in overridden["audit_conclusion"]
        assert "current_owner_note" in overridden["audit_conclusion"]
        assert "review_actor_note" in overridden["audit_conclusion"]
        assert "latest_event_type_note" in overridden["audit_conclusion"]
        assert "latest_review_note" in overridden["audit_conclusion"]
        assert overridden["review_summary"]["latest_review_actor"] == "review-bot"
        assert overridden["review_summary"]["latest_event_type_top"] == "assignment_update"
        assert overridden["review_summary"]["workflow_lane_top"] == "resolved_queue"
        assert overridden["review_summary"]["queue_priority_top"] == "done"
        assert overridden["review_summary"]["deadline_level_top"] == "none"
        assert overridden["review_summary"]["batch_operation_hint_top"] == "batch_close_ready_candidates"
        assert overridden["review_summary"]["auto_next_action_code_top"] == "archive_and_monitor"
        assert overridden["review_summary"]["auto_next_action_top"]
        assert overridden["review_summary"]["batch_suggestions"][0]["hint_code"] == "batch_close_ready_candidates"
        assert overridden["review_summary"]["batch_suggestions"][0]["action_bucket"] == "close"
        assert overridden["review_summary"]["batch_suggestions"][0]["batch_priority"] == "low"
        assert overridden["review_summary"]["batch_suggestions"][0]["suggestion_rank_score"] > 0
        assert overridden["review_summary"]["batch_suggestions"][0]["group_strategy"] == "by_owner"
        assert overridden["review_summary"]["batch_suggestions"][0]["group_key"] == "editor-a"
        assert overridden["review_summary"]["batch_suggestions"][0]["ordering_strategy"]
        assert overridden["review_summary"]["batch_suggestions"][0]["resolved_candidate_count"] == 1
        assert (
            overridden["review_summary"]["batch_suggestions"][0]["suggested_cluster_order_details"][0]["close_stability_score"]
            > 0
        )
        assert (
            overridden["review_summary"]["batch_suggestions"][0]["suggested_cluster_order_details"][0]["close_batch_rank_score"]
            > 0
        )
        assert overridden["review_summary"]["close_ready_count"] == 1
        assert overridden["review_summary"]["resolved_count"] == 1
        assert overridden["review_summary"]["needs_review_count"] == 0
        assert "未见需继续升级的明确风险" in overridden["audit_conclusion"]["risk_judgement"]


def test_write_cluster_review_state_rejects_unknown_review_result(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            "branch-x",
            "cluster-y",
            "resolved",
            review_result="custom-free-text",
        )


def test_write_cluster_review_state_requires_review_result_when_resolved(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            "branch-x",
            "cluster-y",
            "resolved",
            review_result="",
        )


def test_write_cluster_review_state_requires_notes_for_needs_escalation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            "branch-x",
            "cluster-y",
            "needs_review",
            review_result="needs-escalation",
            review_notes="",
        )


def test_write_cluster_review_state_requires_matching_status_for_needs_escalation(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        write_cluster_review_state(
            "branch-x",
            "cluster-y",
            "resolved",
            review_result="needs-escalation",
            review_notes="需要升级",
        )


def test_file_fallback_review_state_records_history_chain(tmp_path: Path) -> None:
    settings = Settings(runtime_cache_dir=str(tmp_path / 'cache'))
    write_cluster_review_state(
        'branch-x',
        'cluster-y',
        'needs_review',
        review_result='deferred',
        review_notes='first pass',
        review_owner='editor-a',
        review_actor='editor-a',
        settings=settings,
    )
    write_cluster_review_state(
        'branch-x',
        'cluster-y',
        'reviewed',
        review_result='confirmed-benign',
        review_notes='second pass',
        review_owner='editor-b',
        review_actor='review-bot',
        settings=settings,
    )

    history = read_cluster_review_history('branch-x', 'cluster-y', settings)

    assert len(history) == 2
    assert history[0]['previous_cluster_status'] == ''
    assert history[1]['previous_cluster_status'] == 'needs_review'
    assert history[1]['previous_review_result'] == 'deferred'
    assert history[1]['previous_review_notes'] == 'first pass'
    assert history[1]['previous_review_owner'] == 'editor-a'
    assert history[1]['previous_review_actor'] == 'editor-a'
    assert history[1]['review_owner'] == 'editor-b'
    assert history[1]['review_actor'] == 'review-bot'
    assert history[1]['created_at'].endswith('Z')


def test_cluster_review_service_persists_review_record_in_database(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = ClusterReviewService(session)
        service.write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|human_review_candidate",
            cluster_status="reviewed",
            review_result="confirmed-benign",
            review_notes="已读",
            review_owner="editor-a",
            review_actor="editor-a",
            resolved_at="2026-04-29T02:00:00Z",
        )
        payload = service.read_branch(branch.id)
        assert payload["character_ooc|::|human_review_candidate"]["cluster_status"] == "reviewed"
        assert payload["character_ooc|::|human_review_candidate"]["review_owner"] == "editor-a"
        service.write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|human_review_candidate",
            cluster_status="reopened",
            review_result="deferred",
            review_notes="需要二次确认",
            review_owner="editor-b",
            review_actor="review-bot",
        )
        history = service.read_history(branch.id, "character_ooc|::|human_review_candidate")
        assert len(history) == 2
        assert history[0]["event_id"]
        assert history[0]["previous_cluster_status"] == ""
        assert history[0]["cluster_status"] == "reviewed"
        assert history[1]["previous_cluster_status"] == "reviewed"
        assert history[1]["previous_review_result"] == "confirmed-benign"
        assert history[1]["previous_review_notes"] == "已读"
        assert history[1]["previous_review_owner"] == "editor-a"
        assert history[1]["previous_review_actor"] == "editor-a"
        assert history[1]["previous_resolved_at"] == "2026-04-29T02:00:00Z"
        assert history[1]["cluster_status"] == "reopened"
        assert history[1]["review_actor"] == "review-bot"
        assert history[0]["event_type"] == "assignment_update"
        assert history[1]["event_type"] == "assignment_update"


def test_cluster_review_service_reads_legacy_db_schema_without_review_actor_columns() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE cluster_review_records (
                    branch_id TEXT,
                    cluster_key TEXT,
                    cluster_status TEXT,
                    review_result TEXT,
                    review_notes TEXT,
                    review_owner TEXT,
                    resolved_at_text TEXT,
                    visibility TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE cluster_review_event_records (
                    branch_id TEXT,
                    cluster_key TEXT,
                    cluster_status TEXT,
                    review_result TEXT,
                    review_notes TEXT,
                    review_owner TEXT,
                    resolved_at_text TEXT,
                    event_type TEXT,
                    created_at TEXT,
                    previous_review_notes TEXT,
                    previous_review_owner TEXT,
                    previous_resolved_at_text TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO cluster_review_records
                (branch_id, cluster_key, cluster_status, review_result, review_notes, review_owner, resolved_at_text, visibility)
                VALUES
                ('branch-x', 'cluster-y', 'needs_review', 'deferred', 'legacy row', 'editor-a', '', 'active')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO cluster_review_event_records
                (branch_id, cluster_key, cluster_status, review_result, review_notes, review_owner, resolved_at_text, event_type, created_at, previous_review_notes, previous_review_owner, previous_resolved_at_text)
                VALUES
                ('branch-x', 'cluster-y', 'needs_review', 'deferred', 'legacy row', 'editor-a', '', 'note_update', '2026-05-04T10:00:00Z', '', '', '')
                """
            )
        )

    with Session(engine) as session:
        service = ClusterReviewService(session)
        state = service.read_branch("branch-x")
        history = service.read_history("branch-x", "cluster-y")

    assert state["cluster-y"]["review_owner"] == "editor-a"
    assert state["cluster-y"]["review_actor"] == "editor-a"
    assert history[0]["review_owner"] == "editor-a"
    assert history[0]["review_actor"] == "editor-a"
    assert history[0]["previous_review_actor"] == ""


def test_cluster_review_history_event_type_distinguishes_owner_only_updates(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        service = ClusterReviewService(session)
        service.write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|human_review_candidate",
            cluster_status="needs_review",
            review_result="deferred",
            review_notes="待处理",
            review_owner="editor-a",
            review_actor="editor-a",
        )
        service.write(
            branch_id=branch.id,
            cluster_key="character_ooc|::|human_review_candidate",
            cluster_status="needs_review",
            review_result="deferred",
            review_notes="待处理",
            review_owner="editor-b",
            review_actor="review-bot",
        )
        history = service.read_history(branch.id, "character_ooc|::|human_review_candidate")
        assert history[1]["event_type"] == "assignment_update"
        assert "review_owner" in history[1]["changed_fields"]
        assert "review_actor" in history[1]["changed_fields"]
        assert history[1]["previous_values"]["review_owner"] == "editor-a"
        assert history[1]["current_values"]["review_owner"] == "editor-b"
        assert history[1]["current_values"]["review_actor"] == "review-bot"


def test_audit_conclusion_marks_pending_assignment_clusters(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "交接测试",
                "chapter_summary": "问题簇被交接给新的负责人。",
                "key_entities": ["卫图"],
                "key_events": ["交接处理"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        cluster_key = ExportService(session).export_branch_bundle(run.id, branch.id)["risk_summary"][
            "review_candidate_clusters"
        ][0]["cluster_key"]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster_key,
            cluster_status="needs_review",
            review_result="deferred",
            review_notes="转交给 editor-b",
            review_owner="editor-a",
            review_actor="editor-a",
        )
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster_key,
            cluster_status="needs_review",
            review_result="deferred",
            review_notes="已完成交接",
            review_owner="editor-b",
            review_actor="review-bot",
        )
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        conclusion = bundle["audit_conclusion"]
        summary = bundle["review_summary"]
        assert "needs_review_note" in conclusion
        assert "current_owner_note" in conclusion
        assert "latest_event_type_note" in conclusion
        assert "pending_assignment_note" in conclusion
        assert "assignment_update" in conclusion["latest_event_type_note"]
        assert "editor-b" in conclusion["pending_assignment_note"]
        assert summary["pending_assignment_count"] == 1
        assert summary["needs_review_count"] == 1
        assert summary["resolved_count"] == 0
        assert summary["workflow_lane_top"] == "assignment_queue"
        assert summary["queue_priority_top"] == "high"
        assert summary["deadline_level_top"] == "soon"
        assert summary["batch_operation_hint_top"] == "batch_owner_handoff_followup"
        assert summary["auto_next_action_code_top"] == "notify_owner_to_take_over"
        assert summary["escalation_reason_code_top"] == "awaiting_owner_followup"
        assert summary["auto_next_action_top"]
        assert summary["escalation_reason_top"]
        assert summary["batch_suggestions"][0]["hint_code"] == "batch_owner_handoff_followup"
        assert summary["batch_suggestions"][0]["action_bucket"] == "followup"
        assert summary["batch_suggestions"][0]["batch_priority"] == "high"
        assert summary["batch_suggestions"][0]["suggestion_rank_score"] > 0
        assert summary["batch_suggestions"][0]["group_strategy"] == "by_owner"
        assert summary["batch_suggestions"][0]["group_key"] == "editor-b"
        assert summary["batch_suggestions"][0]["span_bucket"] == "single"
        assert "queue=high" in summary["batch_suggestions"][0]["suggested_first_cluster_reason"]
        assert "batch_rank_score" in summary["batch_suggestions"][0]["suggested_first_cluster_reason"]
        assert summary["batch_suggestions"][0]["suggested_cluster_order_details"][0]["queue_priority"] == "high"
        assert summary["batch_suggestions"][0]["suggested_cluster_order_details"][0]["escalation_urgency_score"] == 0
        assert summary["batch_suggestions"][0]["suggested_owner"] == "editor-b"
        assert summary["current_owner_top"] == "editor-b"
        cluster = bundle["risk_summary"]["review_candidate_clusters"][0]
        assert cluster["queue_priority"] == "high"
        assert cluster["workflow_lane"] == "assignment_queue"
        assert cluster["action_required"] is True
        assert cluster["suggested_deadline_level"] == "soon"
        assert cluster["batch_operation_hint"] == "batch_owner_handoff_followup"
        assert cluster["auto_next_action_code"] == "notify_owner_to_take_over"
        assert cluster["escalation_reason_code"] == "awaiting_owner_followup"
        assert "接手" in cluster["auto_next_action"]
        assert "交接" in cluster["escalation_reason"]


def test_review_summary_counts_pending_escalation_clusters(tmp_path: Path) -> None:
    novel_path = tmp_path / "novel.txt"
    novel_path.write_text("第1章 一\n正文\n", encoding="utf-8")
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), "样例")
        run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                "chapter_index": 1,
                "normalized_title": "升级测试",
                "chapter_summary": "问题簇需要升级处理。",
                "key_entities": ["卫图"],
                "key_events": ["升级处理"],
                "continuity_notes": ["主线推进。"],
                "ooc_candidates": [
                    {
                        "character_name": "卫图",
                        "risk_type": "motivation_shift",
                        "severity": "medium",
                        "summary": "卫图目标改变过快。",
                        "supporting_evidence": ["前文目标A"],
                        "counter_evidence": ["也许有新情报"],
                    }
                ],
                "needs_human_review": True,
                "dimensions": [],
            },
        )
        RiskAuditService(session).generate_for_chapter(branch.id, 1)
        cluster_key = ExportService(session).export_branch_bundle(run.id, branch.id)["risk_summary"][
            "review_candidate_clusters"
        ][0]["cluster_key"]
        ClusterReviewService(session).write(
            branch_id=branch.id,
            cluster_key=cluster_key,
            cluster_status="escalated",
            review_result="needs-escalation",
            review_notes="需要更高等级复核",
            review_owner="editor-a",
            review_actor="review-bot",
        )
        summary = ExportService(session).export_branch_bundle(run.id, branch.id)["review_summary"]
        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        conclusion = bundle["audit_conclusion"]
        cluster = bundle["risk_summary"]["review_candidate_clusters"][0]
        assert summary["pending_escalation_count"] == 1
        assert summary["workflow_lane_top"] == "escalation_queue"
        assert summary["queue_priority_top"] == "urgent"
        assert summary["deadline_level_top"] == "urgent"
        assert summary["batch_operation_hint_top"] == "batch_escalate_candidates"
        assert summary["escalation_tier_top"] in {"medium", "high", "critical"}
        assert summary["auto_next_action_code_top"] == "escalate_to_senior_review"
        assert summary["escalation_reason_code_top"] == "explicit_escalation_requested"
        assert summary["auto_next_action_top"]
        assert summary["escalation_reason_top"]
        assert summary["batch_suggestions"][0]["hint_code"] == "batch_escalate_candidates"
        assert summary["batch_suggestions"][0]["action_bucket"] == "escalate"
        assert summary["batch_suggestions"][0]["batch_priority"] == "urgent"
        assert summary["batch_suggestions"][0]["suggestion_rank_score"] > 0
        assert summary["batch_suggestions"][0]["group_strategy"] == "by_checker_span"
        assert summary["batch_suggestions"][0]["group_key"] == "character_ooc:single"
        assert summary["batch_suggestions"][0]["primary_checker"] == "character_ooc"
        assert summary["batch_suggestions"][0]["span_bucket"] == "single"
        assert "queue=urgent" in summary["batch_suggestions"][0]["suggested_first_cluster_reason"]
        assert "batch_rank_score" in summary["batch_suggestions"][0]["suggested_first_cluster_reason"]
        assert summary["batch_suggestions"][0]["suggested_cluster_order_details"][0]["queue_priority"] == "urgent"
        assert summary["batch_suggestions"][0]["suggested_cluster_order_details"][0]["escalation_urgency_score"] > 0
        assert summary["batch_suggestions"][0]["suggested_cluster_order_details"][0]["escalation_batch_rank_score"] > 0
        assert summary["batch_suggestions"][0]["escalation_candidate_count"] == 1
        assert summary["resolved_count"] == 0
        assert "pending_escalation_note" in conclusion
        assert cluster["queue_priority"] == "urgent"
        assert cluster["workflow_lane"] == "escalation_queue"
        assert cluster["action_required"] is True
        assert cluster["suggested_deadline_level"] == "urgent"
        assert cluster["escalation_urgency_score"] > 0
        assert cluster["escalation_tier"] in {"medium", "high", "critical"}
        assert "escalation_urgency_score" in cluster["escalation_rank_reason"]
        assert cluster["escalation_batch_rank_score"] > 0
        assert "escalation_batch_rank_score" in cluster["escalation_batch_rank_reason"]
        assert cluster["batch_operation_hint"] == "batch_escalate_candidates"
        assert cluster["auto_next_action_code"] == "escalate_to_senior_review"
        assert cluster["escalation_reason_code"] == "explicit_escalation_requested"
        assert "升级" in cluster["auto_next_action"]
        assert "更高等级复核" in cluster["escalation_reason"]
