"""Composite novel-assistant capability pack assembly."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterArtifact, FactRecord, RunBranch
from novel_analyzer.runtime.provider_health import read_provider_health
from novel_analyzer.services.author_knowledge_service import AuthorKnowledgeService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.domain.schemas import ChapterPlanningIntent
from novel_analyzer.services.chapter_imitation_service import ChapterImitationService
from novel_analyzer.services.next_chapter_planner_service import NextChapterPlannerService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.retrieval_service import RetrievalService
from novel_analyzer.services.reader_feedback_service import ReaderFeedbackService
from novel_analyzer.services.run_service import RunService


class NovelAssistantService:
    """Build a unified assistant capability pack for one branch."""

    DEFAULT_BENCHMARK_QUERIES = [
        "卫图 命格",
        "二姑 资源",
        "婚事 养生功",
    ]

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.run_service = RunService(session, self.settings)
        self.export_service = ExportService(session)
        self.retrieval_service = RetrievalService(session, self.settings)
        self.qa_service = BranchQAService(session, self.settings)
        self.author_knowledge = AuthorKnowledgeService(session)
        self.next_chapter_planner = NextChapterPlannerService(session)
        self.chapter_imitation = ChapterImitationService(session, self.settings)
        self.reader_feedback_service = ReaderFeedbackService(session)

    def _sample_evidence_summary(self) -> dict[str, object]:
        sample_paths = [
            "docs/examples/sample-branch-search-diagnostics-20260505.sample.json",
            "docs/examples/sample-branch-author-knowledge-20260505.sample.json",
            "docs/examples/sample-branch-novel-assistant-20260505.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260504.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json",
        ]
        available = [path for path in sample_paths if Path(path).exists()]
        return {
            "available_samples": available,
            "sample_count": len(available),
        }

    def _whole_book_readiness_summary(self, branch_id: str) -> dict[str, object]:
        chapter_analysis_count = self.session.scalar(
            select(func.count())
            .select_from(ChapterArtifact)
            .where(
                ChapterArtifact.branch_id == branch_id,
                ChapterArtifact.artifact_type == "chapter_analysis",
            )
        ) or 0
        fact_count = self.session.scalar(
            select(func.count()).select_from(FactRecord).where(FactRecord.branch_id == branch_id)
        ) or 0
        provider_health = read_provider_health(self.settings)
        return {
            "whole_book_contract_version": "whole-book-imitation.v1",
            "whole_book_stable_contract_version": "whole-book-imitation-pre-v1",
            "provider_name": self.settings.llm_provider_name,
            "base_url": self.settings.resolved_llm_base_url,
            "model_name": self.settings.llm_model_name,
            "provider_last_status": provider_health.last_status,
            "chapter_analysis_count": int(chapter_analysis_count),
            "fact_record_count": int(fact_count),
            "ready_for_whole_book": bool(chapter_analysis_count >= 2 and fact_count > 0),
        }

    @staticmethod
    def _whole_book_consistency_backflow_pack() -> dict[str, object]:
        sample_paths = [
            "docs/examples/whole-book-imitation-run.sandbox-live-20260505.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json",
            "docs/examples/whole-book-imitation-run.provider-success-20260504.sample.json",
        ]
        for sample_path in sample_paths:
            path = Path(sample_path)
            if not path.exists():
                continue
            import json
            payload = json.loads(path.read_text(encoding='utf-8'))
            dashboard = payload.get("dashboard_summary", {}) if isinstance(payload, dict) else {}
            diagnostics = dashboard.get("long_book_consistency_diagnostics", {}) if isinstance(dashboard, dict) else {}
            handoff = dashboard.get("book_handoff_summary", {}) if isinstance(dashboard, dict) else {}
            next_focus = list(handoff.get("next_stage_focus", []))[:4] if isinstance(handoff, dict) else []
            top_repairs = list(handoff.get("top_repair_recommendations", []))[:4] if isinstance(handoff, dict) else []
            requires_consistency_pass = bool(diagnostics.get("requires_consistency_pass"))
            candidate_backflow_actions = [
                "将 top_repair_recommendations 回灌到 candidate/revision/rewrite 主链。",
                "若 requires_consistency_pass=true，则禁止直接进入 release。",
            ]
            release_impact = "whole_book_consistency_blocks_release" if requires_consistency_pass else "whole_book_consistency_clear"
            return {
                "contract_version": "whole-book-consistency-backflow-pack.v1",
                "sample_path": sample_path,
                "diagnostic_version": diagnostics.get("diagnostic_version") or diagnostics.get("contract") or "",
                "requires_consistency_pass": requires_consistency_pass,
                "next_stage_focus": next_focus,
                "top_repair_recommendations": top_repairs,
                "candidate_backflow_actions": candidate_backflow_actions,
                "release_impact": release_impact,
            }
        return {
            "contract_version": "whole-book-consistency-backflow-pack.v1",
            "degraded": True,
            "reason": "whole_book_consistency_sample_unavailable",
            "requires_consistency_pass": False,
            "next_stage_focus": [],
            "top_repair_recommendations": [],
            "candidate_backflow_actions": [],
            "release_impact": "unknown",
        }

    def _retrieval_benchmark_summary(
        self,
        branch_id: str,
        *,
        limit: int,
        queries: list[str] | None = None,
    ) -> dict[str, object]:
        benchmark_queries = [item.strip() for item in (queries or self.DEFAULT_BENCHMARK_QUERIES) if item.strip()]
        if not benchmark_queries:
            benchmark_queries = list(self.DEFAULT_BENCHMARK_QUERIES)
        cases: list[dict[str, object]] = []
        route_totals: dict[str, int] = {}
        raw_latency_total = 0.0
        rerank_latency_total = 0.0
        rerank_applied_count = 0
        for item in benchmark_queries:
            try:
                payload = self.retrieval_service.search_branch_with_diagnostics(branch_id, item, limit)
            except RuntimeError:
                return {
                    "contract_version": "retrieval-benchmark-summary.v1",
                    "degraded": True,
                    "reason": "retrieval_benchmark_unavailable_for_current_runtime",
                    "benchmark_queries": benchmark_queries,
                }
            route_counts = payload.route_counts or {}
            for route, count in route_counts.items():
                route_totals[str(route)] = route_totals.get(str(route), 0) + int(count)
            raw_latency_total += float(payload.raw_latency_ms or 0.0)
            rerank_latency_total += float(payload.rerank_latency_ms or 0.0)
            rerank_applied_count += 1 if payload.rerank_applied else 0
            raw_top = payload.raw_hits[:limit]
            reranked_top = payload.reranked_hits[:limit]
            raw_top_chapters = [hit.chapter_index for hit in raw_top]
            reranked_top_chapters = [hit.chapter_index for hit in reranked_top]
            overlap = len(set(raw_top_chapters) & set(reranked_top_chapters))
            cases.append(
                {
                    "query": payload.query,
                    "fusion_applied": payload.fusion_applied,
                    "rerank_applied": payload.rerank_applied,
                    "route_counts": route_counts,
                    "raw_latency_ms": payload.raw_latency_ms,
                    "rerank_latency_ms": payload.rerank_latency_ms,
                    "raw_top_chapters": raw_top_chapters,
                    "reranked_top_chapters": reranked_top_chapters,
                    "rerank_changed_order": raw_top_chapters != reranked_top_chapters,
                    "top_overlap": overlap,
                }
            )
        query_count = len(cases) or 1
        return {
            "contract_version": "retrieval-benchmark-summary.v1",
            "degraded": False,
            "benchmark_queries": benchmark_queries,
            "query_count": len(cases),
            "route_totals": route_totals,
            "avg_raw_latency_ms": round(raw_latency_total / query_count, 2),
            "avg_rerank_latency_ms": round(rerank_latency_total / query_count, 2),
            "rerank_coverage_ratio": round(rerank_applied_count / query_count, 3),
            "cases": cases,
        }

    @staticmethod
    def _original_planning_pack(
        *,
        knowledge_pack: dict[str, object],
        continuation_pack: dict[str, object] | None,
    ) -> dict[str, object]:
        summary_layer = knowledge_pack.get("summary_layer", {}) if isinstance(knowledge_pack, dict) else {}
        top_entities = list(summary_layer.get("top_entities", [])) if isinstance(summary_layer, dict) else []
        top_rules = list(summary_layer.get("top_rules", [])) if isinstance(summary_layer, dict) else []
        top_threads = list(summary_layer.get("top_threads", [])) if isinstance(summary_layer, dict) else []
        chapter_span = knowledge_pack.get("chapter_span", {}) if isinstance(knowledge_pack, dict) else {}
        planning_gaps = []
        if len(top_entities) < 3:
            planning_gaps.append("主要人物密度不足，建议先补角色卡与动机链。")
        if not top_rules:
            planning_gaps.append("世界规则摘要不足，长书创作前应补规则/代价说明。")
        if not top_threads:
            planning_gaps.append("未解线程显式化不足，建议先补卷纲级伏笔表。")
        return {
            "contract_version": "original-planning-pack.v1",
            "planning_scope": {
                "chapter_count": int(chapter_span.get("count", 0) or 0),
                "top_entities": top_entities[:5],
                "top_rules": top_rules[:5],
                "top_threads": top_threads[:5],
            },
            "world_and_rule_focus": top_rules[:3],
            "character_arc_candidates": top_entities[:4],
            "thread_backlog": top_threads[:5],
            "planning_gaps": planning_gaps,
            "next_planning_actions": [
                "先固化世界规则、人物目标、长线线程三张底表。",
                "把未解线程映射到卷纲/章纲，避免续写时只靠局部记忆。",
                "将 continuation pack 作为单章执行面，而不是替代长期规划。",
            ],
            "continuation_goal_hint": (continuation_pack or {}).get("chapter_goal", ""),
        }

    @staticmethod
    def _creation_control_pack(
        *,
        continuation_pack: dict[str, object] | None,
        imitation_pack: dict[str, object] | None,
    ) -> dict[str, object]:
        continuation_pack = continuation_pack or {}
        imitation_pack = imitation_pack or {}
        scene_plan = continuation_pack.get("scene_plan", [])
        scene_controls = []
        if isinstance(scene_plan, list):
            for item in scene_plan[:3]:
                if isinstance(item, dict):
                    scene_controls.append(
                        {
                            "scene_index": item.get("scene_index"),
                            "purpose": item.get("purpose"),
                            "must_include": item.get("must_include", []),
                            "risk_notes": item.get("risk_notes", []),
                        }
                    )
        return {
            "contract_version": "creation-control-pack.v1",
            "chapter_goal": continuation_pack.get("chapter_goal", ""),
            "scene_controls": scene_controls,
            "ending_hook": continuation_pack.get("ending_hook", ""),
            "risk_notes": continuation_pack.get("risk_notes", []),
            "style_axes": imitation_pack.get("style_axes", []),
            "scene_beats": imitation_pack.get("scene_beats", []),
            "control_checklist": [
                "每章必须有明确目标、阻力、回应、章尾钩子。",
                "风格控制优先看 style_axes，剧情控制优先看 scene_controls。",
                "如 risk_notes 中出现规则/关系风险，生成前必须先修正。",
            ],
        }

    @staticmethod
    def _editor_revision_pack(
        *,
        review_summary: dict[str, object],
        risk_summary: dict[str, object],
        continuation_pack: dict[str, object] | None,
        imitation_pack: dict[str, object] | None,
    ) -> dict[str, object]:
        needs_review_count = int(review_summary.get("needs_review_count", 0) or 0)
        risk_card_count = int(risk_summary.get("risk_card_count", 0) or 0)
        revision_priorities = []
        if needs_review_count > 0:
            revision_priorities.append(f"先处理 {needs_review_count} 个 needs_review 问题簇，再推进正文定稿。")
        if risk_card_count > 0:
            revision_priorities.append(f"当前有 {risk_card_count} 张 risk card，改稿时优先消化高风险卡片。")
        if continuation_pack:
            revision_priorities.append("检查 scene_plan 是否每场都承担推进功能，避免空转段落。")
        if imitation_pack:
            revision_priorities.append("检查 style_axes 与实际文本是否一致，避免只学句式不学结构。")
        if not revision_priorities:
            revision_priorities.append("当前缺少显式风险/复核阻塞，可转入语言润色与节奏微调。")
        return {
            "contract_version": "editor-revision-pack.v1",
            "revision_priorities": revision_priorities,
            "revision_lanes": [
                {
                    "lane": "logic_and_risk",
                    "goal": "先修逻辑、规则、关系连续性。",
                },
                {
                    "lane": "structure_and_pacing",
                    "goal": "再修场景功能、章尾钩子、节奏切分。",
                },
                {
                    "lane": "style_and_dialogue",
                    "goal": "最后修文风、对白、细节密度。",
                },
            ],
            "done_definition": [
                "review / risk 不再阻塞生成。",
                "scene plan 与正文推进一致。",
                "仿写约束和人物/规则状态无明显冲突。",
            ],
        }

    def _reader_feedback_pack(
        self,
        branch_id: str,
        *,
        knowledge_pack: dict[str, object],
        review_summary: dict[str, object],
        continuation_pack: dict[str, object] | None,
    ) -> dict[str, object]:
        summary_layer = knowledge_pack.get("summary_layer", {}) if isinstance(knowledge_pack, dict) else {}
        top_threads = list(summary_layer.get("top_threads", [])) if isinstance(summary_layer, dict) else []
        top_entities = list(summary_layer.get("top_entities", [])) if isinstance(summary_layer, dict) else []
        pain_point_hypotheses = []
        if int(review_summary.get("needs_review_count", 0) or 0) > 0:
            pain_point_hypotheses.append("读者可能感到部分逻辑/衔接点仍不够顺。")
        if len(top_threads) > 4:
            pain_point_hypotheses.append("未解线程较多，可能带来信息负担或追读疲劳。")
        if continuation_pack and not continuation_pack.get("ending_hook"):
            pain_point_hypotheses.append("章尾钩子较弱，可能影响追读转化。")
        feedback_summary = self.reader_feedback_service.summarize_branch_feedback(branch_id)
        if feedback_summary.get("pain_point_hypotheses"):
            for item in feedback_summary.get("pain_point_hypotheses", []):
                if item not in pain_point_hypotheses:
                    pain_point_hypotheses.append(item)
        if not pain_point_hypotheses:
            pain_point_hypotheses.append("当前主风险更偏执行质量，而非明显的读者体验断点。")
        revision_from_feedback = [
            "把反馈映射回 thread / character / rule，再决定是补铺垫还是删枝杈。",
            "优先处理会影响续读率的章尾钩子、主角目标感、信息负担问题。",
        ]
        for item in feedback_summary.get("revision_recommendations", []):
            if item not in revision_from_feedback:
                revision_from_feedback.append(item)
        return {
            "contract_version": "reader-feedback-pack.v1",
            "feedback_summary": feedback_summary,
            "pain_point_hypotheses": pain_point_hypotheses,
            "feedback_collection_prompts": [
                "哪一章开始觉得节奏变慢？原因是什么？",
                "你最想继续追的角色/线程是什么？",
                "哪些设定、关系或战力变化让你觉得突兀？",
            ],
            "revision_from_feedback": revision_from_feedback,
            "priority_entities": top_entities[:4],
            "priority_threads": top_threads[:4],
        }


    @staticmethod
    def _feedback_revision_bridge_pack(
        *,
        reader_feedback_pack: dict[str, object],
        editor_revision_pack: dict[str, object],
    ) -> dict[str, object]:
        feedback_summary = dict(reader_feedback_pack.get("feedback_summary", {}))
        revision_lanes = list(editor_revision_pack.get("revision_lanes", []))
        revision_from_feedback = list(reader_feedback_pack.get("revision_from_feedback", []))
        signal_counts = dict(feedback_summary.get("signal_counts", {}))
        bridge_actions = []
        if signal_counts.get("pacing_slow"):
            bridge_actions.append("优先走 structure_and_pacing lane，压缩拖沓段落。")
        if signal_counts.get("logic_confusion"):
            bridge_actions.append("优先走 logic_and_risk lane，补足因果与过渡证据。")
        if signal_counts.get("character_ooc"):
            bridge_actions.append("优先走 logic_and_risk lane，回看角色动机与行为一致性。")
        if signal_counts.get("reader_hook_strong"):
            bridge_actions.append("保留并强化 hook，不要在修稿中削弱章尾期待。")
        if not bridge_actions:
            bridge_actions.extend(revision_from_feedback[:2])
        return {
            "contract_version": "feedback-revision-bridge-pack.v1",
            "bridge_actions": bridge_actions,
            "revision_lanes": revision_lanes,
            "signal_counts": signal_counts,
            "top_feedback_signals": list(feedback_summary.get("signals", []))[:4],
        }

    @staticmethod
    def _chapter_draft_preparation_pack(
        *,
        knowledge_pack: dict[str, object],
        continuation_pack: dict[str, object] | None,
        imitation_pack: dict[str, object] | None,
        risk_summary: dict[str, object],
        review_summary: dict[str, object],
    ) -> dict[str, object]:
        story_bible = knowledge_pack.get("story_bible_pack", {}) if isinstance(knowledge_pack, dict) else {}
        continuation_pack = continuation_pack or {}
        imitation_pack = imitation_pack or {}
        future_outline = list(story_bible.get("future_chapter_outline", [])) if isinstance(story_bible, dict) else []
        first_outline = future_outline[0] if future_outline and isinstance(future_outline[0], dict) else {}
        draft_checklist = [
            "先按 chapter_goal / core_conflict 写出场景草骨架，再补对白与细节。",
            "优先兑现 payoff_target 与 turning_point，不要只推进表面事件。",
            "写完后对照 risk_notes / style_axes / rule_constraints 做一次自检。",
        ]
        blocking_risks = []
        needs_review_count = int(review_summary.get("needs_review_count", 0) or 0)
        risk_card_count = int(risk_summary.get("risk_card_count", 0) or 0)
        if needs_review_count > 0:
            blocking_risks.append(f"存在 {needs_review_count} 个 needs_review 问题簇，草稿前应优先确认。")
        if risk_card_count > 0:
            blocking_risks.append(f"存在 {risk_card_count} 张 risk card，起草时要规避高风险路径。")
        return {
            "contract_version": "chapter-draft-preparation-pack.v1",
            "draft_goal": continuation_pack.get("chapter_goal", ""),
            "draft_conflict": first_outline.get("core_conflict") or continuation_pack.get("main_conflict", ""),
            "draft_payoff": first_outline.get("payoff_target", ""),
            "draft_turning_point": first_outline.get("turning_point", ""),
            "scene_outline": continuation_pack.get("scene_plan", []),
            "style_axes": imitation_pack.get("style_axes", []),
            "scene_beats": imitation_pack.get("scene_beats", []),
            "future_chapter_outline": future_outline[:3],
            "character_focus": list(story_bible.get("character_cards", []))[:3],
            "rule_focus": list(story_bible.get("world_rules_digest", []))[:4],
            "draft_checklist": draft_checklist,
            "blocking_risks": blocking_risks,
        }

    @staticmethod
    def _direct_draft_skeleton_pack(
        *,
        chapter_draft_preparation_pack: dict[str, object],
    ) -> dict[str, object]:
        scene_outline = list(chapter_draft_preparation_pack.get("scene_outline", []))
        scene_blocks = []
        draft_lines = []
        for item in scene_outline[:3]:
            if not isinstance(item, dict):
                continue
            scene_index = item.get("scene_index")
            purpose = str(item.get("purpose", "")).strip()
            must_include = [str(x).strip() for x in item.get("must_include", []) if str(x).strip()][:3]
            risk_notes = [str(x).strip() for x in item.get("risk_notes", []) if str(x).strip()][:2]
            scene_blocks.append(
                {
                    "scene_index": scene_index,
                    "purpose": purpose,
                    "must_include": must_include,
                    "risk_notes": risk_notes,
                }
            )
            draft_lines.append(f"### 场景{scene_index}: {purpose}")
            if must_include:
                draft_lines.append("- 必须包含：" + "；".join(must_include))
            if risk_notes:
                draft_lines.append("- 注意：" + "；".join(risk_notes))
            draft_lines.append("- 草写提示：先写行动推进，再补情绪与对白。")
        draft_goal = str(chapter_draft_preparation_pack.get("draft_goal", "")).strip()
        draft_conflict = str(chapter_draft_preparation_pack.get("draft_conflict", "")).strip()
        draft_payoff = str(chapter_draft_preparation_pack.get("draft_payoff", "")).strip()
        draft_turning = str(chapter_draft_preparation_pack.get("draft_turning_point", "")).strip()
        draft_title = draft_goal or "下一章草稿骨架"
        draft_text = "\n".join([
            f"目标：{draft_goal}" if draft_goal else "",
            f"核心冲突：{draft_conflict}" if draft_conflict else "",
            f"兑现点：{draft_payoff}" if draft_payoff else "",
            f"转折点：{draft_turning}" if draft_turning else "",
            *draft_lines,
        ]).strip()
        return {
            "contract_version": "direct-draft-skeleton-pack.v1",
            "draft_title": draft_title,
            "draft_text": draft_text,
            "scene_blocks": scene_blocks,
            "checklist": list(chapter_draft_preparation_pack.get("draft_checklist", []))[:3],
            "blocking_risks": list(chapter_draft_preparation_pack.get("blocking_risks", []))[:3],
        }


    @staticmethod
    def _direct_revision_loop_pack(
        *,
        direct_draft_skeleton_pack: dict[str, object],
        editor_revision_pack: dict[str, object],
    ) -> dict[str, object]:
        scene_blocks = list(direct_draft_skeleton_pack.get("scene_blocks", []))
        revision_lanes = list(editor_revision_pack.get("revision_lanes", []))
        revised_blocks = []
        for item in scene_blocks[:3]:
            if not isinstance(item, dict):
                continue
            revised_blocks.append(
                {
                    "scene_index": item.get("scene_index"),
                    "revision_goal": "先修逻辑/风险，再修节奏/对白",
                    "must_keep": item.get("must_include", [])[:3],
                    "revision_notes": item.get("risk_notes", [])[:2],
                }
            )
        revision_text = "\n".join([
            f"# 修稿目标：{direct_draft_skeleton_pack.get('draft_title', '')}",
            "- 先处理逻辑与风险，再处理风格与节奏。",
            "- 每场都检查 must_keep / revision_notes / chapter continuity。",
            f"- 草骨架摘要：{str(direct_draft_skeleton_pack.get('draft_text', ''))[:240]}",
        ]).strip()
        return {
            "contract_version": "direct-revision-loop-pack.v1",
            "revision_text": revision_text,
            "revision_lanes": revision_lanes,
            "revised_blocks": revised_blocks,
            "revision_checklist": [
                "先修逻辑、规则、关系连续性。",
                "再修场景功能、节奏与章尾钩子。",
                "最后修文风、对白与细节密度。",
            ],
            "blocking_risks": list(direct_draft_skeleton_pack.get("blocking_risks", []))[:3],
        }


    @staticmethod
    def _automatic_rewrite_guidance_pack(
        *,
        direct_revision_loop_pack: dict[str, object],
        reader_feedback_pack: dict[str, object],
        feedback_revision_bridge_pack: dict[str, object],
    ) -> dict[str, object]:
        revised_blocks = list(direct_revision_loop_pack.get("revised_blocks", []))
        feedback_hypotheses = list(reader_feedback_pack.get("pain_point_hypotheses", []))
        rewrite_steps = []
        for item in revised_blocks[:3]:
            if not isinstance(item, dict):
                continue
            rewrite_steps.append(
                {
                    "scene_index": item.get("scene_index"),
                    "rewrite_goal": item.get("revision_goal", ""),
                    "must_keep": item.get("must_keep", [])[:3],
                    "rewrite_actions": [
                        "先保持 must_keep 不丢失，再重写冲突展开。",
                        "优先把 revision_notes 对应的问题改成可见的行动/对白/转折。",
                    ],
                }
            )
        bridge_actions = list(feedback_revision_bridge_pack.get("bridge_actions", []))
        guidance_text = "\n".join([
            "# 自动改写指导",
            "- 先锁定 must_keep，再处理逻辑/节奏/对白问题。",
            "- 每次改写只处理一个场景块，避免整体重写导致连续性漂移。",
            f"- 读者风险假设：{'；'.join(feedback_hypotheses[:2])}" if feedback_hypotheses else "",
        ]).strip()
        return {
            "contract_version": "automatic-rewrite-guidance-pack.v1",
            "guidance_text": guidance_text,
            "rewrite_steps": rewrite_steps,
            "reader_feedback_hypotheses": feedback_hypotheses[:3],
            "rewrite_checklist": [
                "先修逻辑，再修节奏，再修文风。",
                "每轮改写后回看 must_keep 是否仍在。",
                "避免为追求流畅度而丢失 payoff / turning point。",
            ],
            "feedback_bridge_actions": bridge_actions[:3],
        }


    @staticmethod
    def _automatic_prose_rewrite_pack(
        *,
        direct_draft_skeleton_pack: dict[str, object],
        automatic_rewrite_guidance_pack: dict[str, object],
        reader_feedback_pack: dict[str, object],
    ) -> dict[str, object]:
        scene_blocks = list(direct_draft_skeleton_pack.get("scene_blocks", []))
        rewrite_steps = list(automatic_rewrite_guidance_pack.get("rewrite_steps", []))
        feedback_signals = list(reader_feedback_pack.get("feedback_summary", {}).get("signals", []))
        rewritten_blocks = []
        prose_lines = []
        for index, item in enumerate(scene_blocks[:3], start=1):
            if not isinstance(item, dict):
                continue
            step = rewrite_steps[index - 1] if index - 1 < len(rewrite_steps) and isinstance(rewrite_steps[index - 1], dict) else {}
            must_keep = item.get("must_include", [])[:2]
            rewritten_blocks.append(
                {
                    "scene_index": item.get("scene_index"),
                    "rewrite_goal": step.get("rewrite_goal", "优化当前场景"),
                    "must_keep": must_keep,
                    "rewrite_prompt": "；".join([str(x) for x in must_keep if str(x).strip()]) or "保持主线推进与连续性",
                }
            )
            prose_lines.append(f"### 改写场景{item.get('scene_index')}")
            prose_lines.append(f"- 改写目标：{step.get('rewrite_goal', '优化当前场景')}")
            if must_keep:
                prose_lines.append("- 必须保留：" + "；".join(str(x) for x in must_keep))
            prose_lines.append("- 改写提示：把问题改成更明确的行动、对白、冲突承接。")
            if feedback_signals:
                prose_lines.append("- 读者反馈优先：" + "；".join(feedback_signals[:2]))
        prose_text = "\n".join(prose_lines).strip()
        return {
            "contract_version": "automatic-prose-rewrite-pack.v1",
            "rewrite_title": direct_draft_skeleton_pack.get("draft_title", ""),
            "rewrite_text": prose_text,
            "rewritten_blocks": rewritten_blocks,
            "rewrite_checklist": list(automatic_rewrite_guidance_pack.get("rewrite_checklist", []))[:3],
            "feedback_signals": feedback_signals[:4],
        }


    @staticmethod
    def _final_draft_candidate_pack(
        *,
        automatic_prose_rewrite_pack: dict[str, object],
        risk_summary: dict[str, object],
        review_summary: dict[str, object],
        reader_feedback_pack: dict[str, object],
    ) -> dict[str, object]:
        rewritten_blocks = list(automatic_prose_rewrite_pack.get("rewritten_blocks", []))
        candidate_lines = [
            f"# 候选稿：{automatic_prose_rewrite_pack.get('rewrite_title', '')}",
            str(automatic_prose_rewrite_pack.get("rewrite_text", "")).strip(),
        ]
        feedback_summary = dict(reader_feedback_pack.get("feedback_summary", {}))
        negative_signal_count = sum(
            int(feedback_summary.get("signal_counts", {}).get(key, 0) or 0)
            for key in ["pacing_slow", "logic_confusion", "character_ooc"]
        )
        review_gate = {
            "needs_review_count": int(review_summary.get("needs_review_count", 0) or 0),
            "risk_card_count": int(risk_summary.get("risk_card_count", 0) or 0),
            "negative_feedback_signal_count": negative_signal_count,
            "ready_for_candidate_review": not (
                int(review_summary.get("needs_review_count", 0) or 0) > 0
                or int(risk_summary.get("risk_card_count", 0) or 0) > 12
                or negative_signal_count > 2
            ),
        }
        return {
            "contract_version": "final-draft-candidate-pack.v1",
            "candidate_title": automatic_prose_rewrite_pack.get("rewrite_title", ""),
            "candidate_text": "\n\n".join([item for item in candidate_lines if item]),
            "candidate_blocks": rewritten_blocks[:3],
            "review_gate": review_gate,
            "candidate_checklist": [
                "候选稿必须保留 must_keep 与 payoff / turning point。",
                "候选稿输出后先过 review_gate，再进入人工/模型复核。",
                "如果 risk_card_count 较高，不要直接进入最终定稿。",
            ],
            "reader_feedback_signals": list(feedback_summary.get("signals", []))[:4],
        }


    @staticmethod
    def _publish_ready_release_pack(
        *,
        final_draft_candidate_pack: dict[str, object],
        whole_book_readiness_summary: dict[str, object],
        whole_book_consistency_backflow_pack: dict[str, object],
    ) -> dict[str, object]:
        review_gate = dict(final_draft_candidate_pack.get("review_gate", {}))
        ready_for_candidate_review = bool(review_gate.get("ready_for_candidate_review"))
        whole_book_ready = bool(whole_book_readiness_summary.get("ready_for_whole_book"))
        requires_consistency_pass = bool(whole_book_consistency_backflow_pack.get("requires_consistency_pass"))
        release_gate = {
            "candidate_review_ready": ready_for_candidate_review,
            "whole_book_ready": whole_book_ready,
            "whole_book_consistency_ready": not requires_consistency_pass,
            "ready_for_release": bool(ready_for_candidate_review and whole_book_ready and not requires_consistency_pass),
        }
        release_summary = "候选稿仍需复核后再发布。"
        if release_gate["ready_for_release"]:
            release_summary = "候选稿已满足当前发布前置条件，可进入 release review。"
        return {
            "contract_version": "publish-ready-release-pack.v1",
            "release_gate": release_gate,
            "release_summary": release_summary,
            "release_checklist": [
                "先确认 candidate_review_ready。",
                "再确认 whole_book_ready 与主链样例完整。",
                "发布前保留 review_gate / risk evidence 作为回溯依据。",
            ],
            "candidate_title": final_draft_candidate_pack.get("candidate_title", ""),
        }


    @staticmethod
    def _sample_based_release_criteria_bundle(
        *,
        publish_ready_release_pack: dict[str, object],
        sample_evidence_summary: dict[str, object],
        retrieval_benchmark_summary: dict[str, object],
        reader_feedback_pack: dict[str, object],
    ) -> dict[str, object]:
        release_gate = dict(publish_ready_release_pack.get("release_gate", {}))
        sample_count = int(sample_evidence_summary.get("sample_count", 0) or 0)
        query_count = int(retrieval_benchmark_summary.get("query_count", 0) or 0)
        feedback_summary = dict(reader_feedback_pack.get("feedback_summary", {}))
        negative_signal_count = sum(
            int(feedback_summary.get("signal_counts", {}).get(key, 0) or 0)
            for key in ["pacing_slow", "logic_confusion", "character_ooc"]
        )
        criteria = {
            "sample_count_ready": sample_count >= 3,
            "retrieval_benchmark_ready": query_count >= 3,
            "reader_feedback_ready": negative_signal_count <= 2,
            "release_gate_ready": bool(release_gate.get("ready_for_release")),
        }
        criteria["ready_for_bundle_review"] = all(criteria.values())
        return {
            "contract_version": "sample-based-release-criteria-bundle.v1",
            "criteria": criteria,
            "sample_count": sample_count,
            "retrieval_query_count": query_count,
            "bundle_summary": "样例、retrieval benchmark、release gate 已汇总，可用于 release criteria review。",
        }


    @staticmethod
    def _release_decision_freeze_artifact_pack(
        *,
        sample_based_release_criteria_bundle: dict[str, object],
        publish_ready_release_pack: dict[str, object],
    ) -> dict[str, object]:
        criteria = dict(sample_based_release_criteria_bundle.get("criteria", {}))
        release_gate = dict(publish_ready_release_pack.get("release_gate", {}))
        go_for_release = bool(criteria.get("ready_for_bundle_review") and release_gate.get("ready_for_release"))
        decision = "go" if go_for_release else "no_go"
        freeze_reason = "release_gate_or_sample_criteria_not_ready"
        if go_for_release:
            freeze_reason = "ready_for_release_review"
        freeze_artifact = {
            "decision": decision,
            "freeze_reason": freeze_reason,
            "criteria_snapshot": criteria,
            "release_gate_snapshot": release_gate,
        }
        return {
            "contract_version": "release-decision-freeze-artifact-pack.v1",
            "decision": decision,
            "freeze_artifact": freeze_artifact,
            "decision_summary": "满足条件后进入 release freeze review。" if go_for_release else "当前仍处于 no-go / freeze 保守状态。",
            "next_actions": [
                "若 no_go，则优先关闭 review_gate 与 release criteria 缺口。",
                "若 go，则保留 freeze_artifact 并进入 release review。",
            ],
        }


    @staticmethod
    def _handoff_approval_record_pack(
        *,
        release_decision_freeze_artifact_pack: dict[str, object],
        publish_ready_release_pack: dict[str, object],
    ) -> dict[str, object]:
        decision = str(release_decision_freeze_artifact_pack.get("decision", "no_go"))
        freeze_artifact = dict(release_decision_freeze_artifact_pack.get("freeze_artifact", {}))
        release_summary = str(publish_ready_release_pack.get("release_summary", "")).strip()
        handoff_record = {
            "decision": decision,
            "freeze_reason": freeze_artifact.get("freeze_reason", ""),
            "release_summary": release_summary,
        }
        approval_status = "pending"
        if decision == "go":
            approval_status = "ready_for_approval"
        return {
            "contract_version": "handoff-approval-record-pack.v1",
            "approval_status": approval_status,
            "handoff_record": handoff_record,
            "approval_checklist": [
                "确认 freeze_artifact 与 release_gate 快照可回溯。",
                "确认候选稿、release criteria、risk evidence 已一并交接。",
                "进入 approval 前记录最终 decision 与责任人。",
            ],
        }


    @staticmethod
    def _operator_release_brief_pack(
        *,
        handoff_approval_record_pack: dict[str, object],
        sample_based_release_criteria_bundle: dict[str, object],
    ) -> dict[str, object]:
        handoff_record = dict(handoff_approval_record_pack.get("handoff_record", {}))
        criteria = dict(sample_based_release_criteria_bundle.get("criteria", {}))
        brief_lines = [
            f"decision={handoff_record.get('decision', '')}",
            f"freeze_reason={handoff_record.get('freeze_reason', '')}",
            f"sample_count_ready={criteria.get('sample_count_ready')}",
            f"retrieval_benchmark_ready={criteria.get('retrieval_benchmark_ready')}",
            f"release_gate_ready={criteria.get('release_gate_ready')}",
        ]
        return {
            "contract_version": "operator-release-brief-pack.v1",
            "brief_summary": " | ".join([item for item in brief_lines if item]),
            "operator_status": handoff_approval_record_pack.get("approval_status", "pending"),
            "brief_checklist": [
                "先看 decision / freeze_reason。",
                "再看 sample/retrieval/release criteria 是否齐备。",
                "最后确认是否进入人工 approval 或继续回修。",
            ],
        }


    @staticmethod
    def _release_ops_runbook_pack(
        *,
        operator_release_brief_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
    ) -> dict[str, object]:
        decision = str(release_decision_freeze_artifact_pack.get("decision", "no_go"))
        freeze_artifact = dict(release_decision_freeze_artifact_pack.get("freeze_artifact", {}))
        runbook_steps = [
            "检查 operator brief 与 freeze_artifact 是否一致。",
            "确认 release gate / sample criteria / risk evidence 的最新快照。",
            "若 decision=no_go，则生成阻断清单并停止发布动作。",
            "若 decision=go，则进入人工 approval 与 release review。",
        ]
        if decision == 'go':
            runbook_steps.append('完成审批后执行最终发布与留档。')
        blockers = []
        if decision != 'go':
            blockers.append(str(freeze_artifact.get('freeze_reason', 'release_not_ready')))
        return {
            "contract_version": "release-ops-runbook-pack.v1",
            "runbook_status": "blocked" if decision != 'go' else 'ready',
            "runbook_steps": runbook_steps,
            "blockers": blockers,
            "rollback_note": "若发布后发现风险回归，回退到候选稿并重新进入 freeze review。",
            "brief_summary": operator_release_brief_pack.get("brief_summary", ""),
        }


    @staticmethod
    def _incident_rollback_pack(
        *,
        release_ops_runbook_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
    ) -> dict[str, object]:
        freeze_artifact = dict(release_decision_freeze_artifact_pack.get("freeze_artifact", {}))
        blockers = list(release_ops_runbook_pack.get("blockers", []))
        rollback_trigger = blockers[0] if blockers else str(freeze_artifact.get("freeze_reason", "post_release_regression"))
        rollback_steps = [
            "停止当前发布/扩散动作。",
            "回退到上一版候选稿或安全版本。",
            "重新收集 risk / review / release gate 快照。",
            "完成问题修复后重新进入 freeze review。",
        ]
        return {
            "contract_version": "incident-rollback-pack.v1",
            "rollback_trigger": rollback_trigger,
            "rollback_target": "previous_candidate_or_safe_release",
            "rollback_steps": rollback_steps,
            "rollback_summary": "若触发 release 风险或 freeze 阻断，按既定回退链处理。",
        }


    @staticmethod
    def _postmortem_recovery_record_pack(
        *,
        incident_rollback_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
    ) -> dict[str, object]:
        freeze_artifact = dict(release_decision_freeze_artifact_pack.get("freeze_artifact", {}))
        rollback_trigger = str(incident_rollback_pack.get("rollback_trigger", "")).strip()
        recovery_record = {
            "rollback_trigger": rollback_trigger,
            "rollback_target": incident_rollback_pack.get("rollback_target", ""),
            "freeze_reason": freeze_artifact.get("freeze_reason", ""),
        }
        return {
            "contract_version": "postmortem-recovery-record-pack.v1",
            "recovery_record": recovery_record,
            "postmortem_summary": "已记录 rollback trigger / target / freeze reason，可用于事故复盘与恢复追踪。",
            "recovery_checklist": [
                "记录 rollback trigger 与 freeze_reason。",
                "记录恢复后的风险/评审快照。",
                "确认问题关闭后再重新进入 freeze/release review。",
            ],
        }


    @staticmethod
    def _recovery_closure_artifact_pack(
        *,
        postmortem_recovery_record_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
    ) -> dict[str, object]:
        recovery_record = dict(postmortem_recovery_record_pack.get("recovery_record", {}))
        decision = str(release_decision_freeze_artifact_pack.get("decision", "no_go"))
        closure_status = "recovery_pending" if decision != "go" else "recovery_closed"
        closure_summary = "恢复动作仍需持续跟踪。"
        if closure_status == "recovery_closed":
            closure_summary = "恢复闭环已满足当前条件，可结束本轮 incident recovery。"
        return {
            "contract_version": "recovery-closure-artifact-pack.v1",
            "closure_status": closure_status,
            "closure_summary": closure_summary,
            "closure_record": recovery_record,
            "closure_checklist": [
                "确认 rollback trigger / target / freeze reason 已归档。",
                "确认恢复后快照已重新记录。",
                "确认是否需要重新进入 release/freeze review。",
            ],
        }


    @staticmethod
    def _final_governance_summary_pack(
        *,
        publish_ready_release_pack: dict[str, object],
        sample_based_release_criteria_bundle: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
        handoff_approval_record_pack: dict[str, object],
        release_ops_runbook_pack: dict[str, object],
        recovery_closure_artifact_pack: dict[str, object],
    ) -> dict[str, object]:
        release_gate = dict(publish_ready_release_pack.get("release_gate", {}))
        criteria = dict(sample_based_release_criteria_bundle.get("criteria", {}))
        decision = str(release_decision_freeze_artifact_pack.get("decision", "no_go"))
        approval_status = str(handoff_approval_record_pack.get("approval_status", "pending"))
        runbook_status = str(release_ops_runbook_pack.get("runbook_status", "blocked"))
        closure_status = str(recovery_closure_artifact_pack.get("closure_status", "recovery_pending"))
        summary = [
            f"release_ready={release_gate.get('ready_for_release')}",
            f"criteria_ready={criteria.get('ready_for_bundle_review')}",
            f"decision={decision}",
            f"approval_status={approval_status}",
            f"runbook_status={runbook_status}",
            f"closure_status={closure_status}",
        ]
        return {
            "contract_version": "final-governance-summary-pack.v1",
            "governance_summary": " | ".join(summary),
            "governance_status": "ready" if decision == "go" and approval_status == "ready_for_approval" else "guarded",
            "governance_checklist": [
                "先看 release_ready 与 criteria_ready。",
                "再看 decision / approval_status / runbook_status。",
                "最后确认 closure_status 与 recovery 记录是否完备。",
            ],
        }


    @staticmethod
    def _governance_report_brief_pack(
        *,
        governance_dashboard_pack: dict[str, object],
        final_governance_summary_pack: dict[str, object],
        whole_book_consistency_backflow_pack: dict[str, object],
    ) -> dict[str, object]:
        summary_card = str(governance_dashboard_pack.get("summary_card", "")).strip()
        dashboard_status = str(governance_dashboard_pack.get("dashboard_status", "guarded"))
        operator_brief = str(governance_dashboard_pack.get("operator_brief", "")).strip()
        markdown = "\n".join([
            "# Governance Report Brief",
            "",
            f"- dashboard_status: {dashboard_status}",
            f"- governance_status: {final_governance_summary_pack.get('governance_status', 'guarded')}",
            f"- summary_card: {summary_card}",
            f"- operator_brief: {operator_brief}",
            f"- whole_book_release_impact: {whole_book_consistency_backflow_pack.get('release_impact', '')}",
        ]).strip() + "\n"
        return {
            "contract_version": "governance-report-brief-pack.v1",
            "dashboard_status": dashboard_status,
            "brief_text": markdown,
            "summary_card": summary_card,
        }


    @staticmethod
    def _release_review_note_pack(
        *,
        governance_report_brief_pack: dict[str, object],
        publish_ready_release_pack: dict[str, object],
        sample_based_release_criteria_bundle: dict[str, object],
        whole_book_consistency_backflow_pack: dict[str, object],
    ) -> dict[str, object]:
        release_gate = dict(publish_ready_release_pack.get("release_gate", {}))
        criteria = dict(sample_based_release_criteria_bundle.get("criteria", {}))
        note_lines = [
            "# Release Review Note",
            "",
            f"- candidate_review_ready: {release_gate.get('candidate_review_ready')}",
            f"- whole_book_ready: {release_gate.get('whole_book_ready')}",
            f"- ready_for_release: {release_gate.get('ready_for_release')}",
            f"- criteria_ready: {criteria.get('ready_for_bundle_review')}",
            f"- governance_brief: {governance_report_brief_pack.get('summary_card', '')}",
            f"- whole_book_consistency_release_impact: {whole_book_consistency_backflow_pack.get('release_impact', '')}",
        ]
        note_text = "\n".join(note_lines).strip() + "\n"
        return {
            "contract_version": "release-review-note-pack.v1",
            "note_text": note_text,
            "review_status": "ready" if release_gate.get("ready_for_release") else "blocked",
            "note_summary": governance_report_brief_pack.get("summary_card", ""),
        }


    @staticmethod
    def _approval_decision_memo_pack(
        *,
        release_review_note_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
        whole_book_consistency_backflow_pack: dict[str, object],
    ) -> dict[str, object]:
        decision = str(release_decision_freeze_artifact_pack.get("decision", "no_go"))
        freeze_artifact = dict(release_decision_freeze_artifact_pack.get("freeze_artifact", {}))
        verdict = "APPROVE" if decision == "go" else "REJECT"
        memo_lines = [
            "# Approval Decision Memo",
            "",
            f"- verdict: {verdict}",
            f"- decision: {decision}",
            f"- freeze_reason: {freeze_artifact.get('freeze_reason', '')}",
            f"- review_note: {release_review_note_pack.get('note_summary', '')}",
            f"- whole_book_release_impact: {whole_book_consistency_backflow_pack.get('release_impact', '')}",
        ]
        memo_text = "\n".join(memo_lines).strip() + "\n"
        return {
            "contract_version": "approval-decision-memo-pack.v1",
            "decision_verdict": verdict,
            "memo_text": memo_text,
            "memo_status": "approved" if verdict == "APPROVE" else "rejected",
        }


    @staticmethod
    def _external_report_bundle_pack(
        *,
        governance_dashboard_pack: dict[str, object],
        governance_report_brief_pack: dict[str, object],
        release_review_note_pack: dict[str, object],
        approval_decision_memo_pack: dict[str, object],
        release_ops_runbook_pack: dict[str, object],
        incident_rollback_pack: dict[str, object],
        final_governance_summary_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "external-report-bundle-pack.v1",
            "dashboard": governance_dashboard_pack,
            "brief": governance_report_brief_pack,
            "review_note": release_review_note_pack,
            "approval_memo": approval_decision_memo_pack,
            "runbook": release_ops_runbook_pack,
            "rollback": incident_rollback_pack,
            "governance_summary": final_governance_summary_pack,
        }


    @staticmethod
    def _external_report_markdown_pack(
        *,
        external_report_bundle_pack: dict[str, object],
    ) -> dict[str, object]:
        dashboard = dict(external_report_bundle_pack.get("dashboard", {}))
        brief = dict(external_report_bundle_pack.get("brief", {}))
        review_note = dict(external_report_bundle_pack.get("review_note", {}))
        approval_memo = dict(external_report_bundle_pack.get("approval_memo", {}))
        runbook = dict(external_report_bundle_pack.get("runbook", {}))
        rollback = dict(external_report_bundle_pack.get("rollback", {}))
        governance_summary = dict(external_report_bundle_pack.get("governance_summary", {}))
        markdown = "\n".join([
            "# External Report Bundle",
            "",
            "## Dashboard",
            str(dashboard.get("summary_card", "")),
            "",
            "## Governance Brief",
            str(brief.get("brief_text", "")).strip(),
            "",
            "## Release Review Note",
            str(review_note.get("note_text", "")).strip(),
            "",
            "## Approval Memo",
            str(approval_memo.get("memo_text", "")).strip(),
            "",
            "## Runbook",
            "\n".join(f"- {item}" for item in runbook.get("runbook_steps", [])),
            "",
            "## Rollback",
            "\n".join(f"- {item}" for item in rollback.get("rollback_steps", [])),
            "",
            "## Governance Summary",
            str(governance_summary.get("governance_summary", "")),
        ]).strip() + "\n"
        return {
            "contract_version": "external-report-markdown-pack.v1",
            "markdown_text": markdown,
            "dashboard_status": dashboard.get("dashboard_status", "guarded"),
        }


    @staticmethod
    def _final_release_archive_pack(
        *,
        final_draft_candidate_pack: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
        handoff_approval_record_pack: dict[str, object],
        external_report_bundle_pack: dict[str, object],
        archive_retention_metadata_pack: dict[str, object],
        archive_index_metadata_pack: dict[str, object],
        archive_integrity_check_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "final-release-archive-pack.v1",
            "candidate": final_draft_candidate_pack,
            "freeze_artifact": release_decision_freeze_artifact_pack,
            "handoff_record": handoff_approval_record_pack,
            "external_report_bundle": external_report_bundle_pack,
            "archive_retention_metadata_pack": archive_retention_metadata_pack,
            "archive_index_metadata_pack": archive_index_metadata_pack,
            "archive_integrity_check_pack": archive_integrity_check_pack,
            "archive_summary": "已汇总候选稿、freeze 决策、handoff 记录与外部治理包，可直接归档。",
        }


    @staticmethod
    def _archive_manifest_pack(
        *,
        final_release_archive_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "archive-manifest-pack.v1",
            "manifest_items": [
                "candidate",
                "freeze_artifact",
                "handoff_record",
                "external_report_bundle",
            ],
            "archive_summary": final_release_archive_pack.get("archive_summary", ""),
            "archive_contract": final_release_archive_pack.get("contract_version", ""),
        }


    @staticmethod
    def _archive_integrity_check_pack(
        *,
        final_release_archive_pack: dict[str, object],
    ) -> dict[str, object]:
        required_keys = ["candidate", "freeze_artifact", "handoff_record", "external_report_bundle"]
        present_keys = [key for key in required_keys if key in final_release_archive_pack]
        missing_keys = [key for key in required_keys if key not in final_release_archive_pack]
        return {
            "contract_version": "archive-integrity-check-pack.v1",
            "present_keys": present_keys,
            "missing_keys": missing_keys,
            "integrity_ok": not missing_keys,
        }


    @staticmethod
    def _archive_retention_metadata_pack(
        *,
        archive_manifest_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "archive-retention-metadata-pack.v1",
            "retention_policy": "keep_release_archive_until_next_major_revision",
            "archive_status": "active",
            "manifest_contract": archive_manifest_pack.get("contract_version", ""),
            "manifest_item_count": len(list(archive_manifest_pack.get("manifest_items", []))),
        }


    @staticmethod
    def _archive_index_metadata_pack(
        *,
        archive_manifest_pack: dict[str, object],
        archive_retention_metadata_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "archive-index-metadata-pack.v1",
            "archive_key": "sample-branch-final-release-archive-20260505",
            "manifest_contract": archive_manifest_pack.get("contract_version", ""),
            "retention_policy": archive_retention_metadata_pack.get("retention_policy", ""),
            "archive_status": archive_retention_metadata_pack.get("archive_status", "active"),
            "indexed_sections": list(archive_manifest_pack.get("manifest_items", [])),
        }


    @staticmethod
    def _governance_dashboard_pack(
        *,
        final_governance_summary_pack: dict[str, object],
        publish_ready_release_pack: dict[str, object],
        sample_based_release_criteria_bundle: dict[str, object],
        release_decision_freeze_artifact_pack: dict[str, object],
        operator_release_brief_pack: dict[str, object],
        whole_book_consistency_backflow_pack: dict[str, object],
    ) -> dict[str, object]:
        return {
            "contract_version": "governance-dashboard-pack.v1",
            "dashboard_status": final_governance_summary_pack.get("governance_status", "guarded"),
            "summary_card": final_governance_summary_pack.get("governance_summary", ""),
            "release_gate": publish_ready_release_pack.get("release_gate", {}),
            "criteria": sample_based_release_criteria_bundle.get("criteria", {}),
            "decision": release_decision_freeze_artifact_pack.get("decision", "no_go"),
            "operator_status": operator_release_brief_pack.get("operator_status", "pending"),
            "operator_brief": operator_release_brief_pack.get("brief_summary", ""),
            "whole_book_consistency": {
                "requires_consistency_pass": whole_book_consistency_backflow_pack.get("requires_consistency_pass"),
                "release_impact": whole_book_consistency_backflow_pack.get("release_impact", ""),
                "next_stage_focus": whole_book_consistency_backflow_pack.get("next_stage_focus", []),
            },
        }


    @staticmethod
    def _preparation_guidance(
        *,
        top_entities: list[str],
        review_needs_count: int,
        risk_card_count: int,
    ) -> dict[str, list[str]]:
        next_chapter = [
            "先确认主角当前目标、关系推进与未解线程，再进行续写规划。",
            "如果存在待复核问题簇，优先阅读 review summary 后再定续写方向。",
        ]
        imitation = [
            "先使用 author knowledge 确认人物/规则/线程现状，再进入仿写。",
            "whole-book 前先确认 retrieval diagnostics 是否能稳定召回关键章节。",
        ]
        risk_gate = [
            "进入生成前先看 risk summary 与 review summary，避免带病生成。",
        ]
        if top_entities:
            next_chapter.append(f"当前最重要的人物/实体：{'、'.join(top_entities[:3])}")
            imitation.append(f"仿写时优先保留这些实体线：{'、'.join(top_entities[:3])}")
        if review_needs_count > 0:
            risk_gate.append(f"当前仍有 {review_needs_count} 个 needs_review 问题簇，建议先复核。")
        if risk_card_count <= 0:
            risk_gate.append("当前 branch 尚无稳定 risk card，生成前应先确认审查链是否完整。")
        return {
            "next_chapter_preparation": next_chapter,
            "imitation_preparation": imitation,
            "risk_gate_preflight": risk_gate,
        }

    def build_branch_assistant_pack(
        self,
        branch_id: str,
        *,
        query: str = "",
        question: str = "",
        from_chapter_index: int | None = None,
        upto_chapter_index: int | None = None,
        focus_label: str = "",
        limit: int = 5,
        benchmark_queries: list[str] | None = None,
    ) -> dict[str, object]:
        branch = self.session.scalar(select(RunBranch).where(RunBranch.id == branch_id))
        if branch is None:
            raise ValueError(f"Unknown branch_id: {branch_id}")

        branch_snapshot = self.run_service.branch_snapshot(branch_id)
        branch_bundle = self.export_service.export_branch_bundle(branch.run_id, branch_id)
        knowledge_pack = self.author_knowledge.build_branch_knowledge_pack(
            branch_id,
            from_chapter_index=from_chapter_index,
            upto_chapter_index=upto_chapter_index,
            focus_label=focus_label,
        )
        retrieval_diagnostics: dict[str, object] | None = None
        if query.strip():
            try:
                diagnostics = self.retrieval_service.search_branch_with_diagnostics(
                    branch_id, query, limit
                )
            except RuntimeError:
                retrieval_diagnostics = {
                    "query": query,
                    "degraded": True,
                    "reason": "retrieval_diagnostics_unavailable_for_current_runtime",
                }
            else:
                retrieval_diagnostics = {
                    "query": diagnostics.query,
                    "fusion_applied": diagnostics.fusion_applied,
                    "rerank_applied": diagnostics.rerank_applied,
                    "route_counts": diagnostics.route_counts or {},
                    "raw_latency_ms": diagnostics.raw_latency_ms,
                    "rerank_latency_ms": diagnostics.rerank_latency_ms,
                    "raw_hits": [
                        {
                            "chapter_index": hit.chapter_index,
                            "title": hit.title,
                            "score": hit.score,
                        }
                        for hit in diagnostics.raw_hits[:limit]
                    ],
                    "reranked_hits": [
                        {
                            "chapter_index": hit.chapter_index,
                            "title": hit.title,
                            "score": hit.score,
                        }
                        for hit in diagnostics.reranked_hits[:limit]
                    ],
                }
        qa_answer: dict[str, object] | None = None
        if question.strip():
            answer = self.qa_service.answer_question(branch_id, question, limit)
            qa_answer = answer.model_dump()

        chapter_count = int(branch_snapshot.get("completed_chapters", 0) or 0)
        if chapter_count <= 0:
            chapter_count = int(knowledge_pack.get("chapter_span", {}).get("count", 0) or 0)
        review_summary = branch_bundle.get("review_summary", {})
        risk_summary = branch_bundle.get("risk_summary", {})
        top_entities = knowledge_pack.get("summary_layer", {}).get("top_entities", [])
        readiness_summary = self._whole_book_readiness_summary(branch_id)
        sample_evidence_summary = self._sample_evidence_summary()
        preparation_guidance = self._preparation_guidance(
            top_entities=top_entities,
            review_needs_count=int(review_summary.get("needs_review_count", 0) or 0),
            risk_card_count=int(risk_summary.get("risk_card_count", 0) or 0),
        )
        retrieval_benchmark_summary = self._retrieval_benchmark_summary(
            branch_id,
            limit=limit,
            queries=benchmark_queries,
        )
        whole_book_consistency_backflow_pack = self._whole_book_consistency_backflow_pack()
        continuation_pack = None
        imitation_pack = None
        if chapter_count > 0:
            latest_chapter = int(knowledge_pack.get("chapter_span", {}).get("max", 0) or 0)
            if latest_chapter > 0:
                intent = ChapterPlanningIntent(
                    primary_goal="延续当前主线并优先处理高价值未解线程",
                    emphasis=["连续性", "关系推进", "规则一致性"],
                    forbidden_moves=["不要无铺垫升级战力", "不要引入未准备的大设定"],
                    preferred_tone="克制务实",
                    pace="steady",
                )
                continuation_pack = self.next_chapter_planner.build_plan(branch_id, intent=intent).model_dump()
                imitation_pack = self.chapter_imitation.build_imitation_plan(
                    branch_id,
                    source_chapter_index=latest_chapter,
                    target_goal="延续当前主线并保持人物/规则连续性",
                ).model_dump()
        original_planning_pack = self._original_planning_pack(
            knowledge_pack=knowledge_pack,
            continuation_pack=continuation_pack,
        )
        creation_control_pack = self._creation_control_pack(
            continuation_pack=continuation_pack,
            imitation_pack=imitation_pack,
        )
        editor_revision_pack = self._editor_revision_pack(
            review_summary=review_summary,
            risk_summary=risk_summary,
            continuation_pack=continuation_pack,
            imitation_pack=imitation_pack,
        )
        reader_feedback_pack = self._reader_feedback_pack(
            branch_id,
            knowledge_pack=knowledge_pack,
            review_summary=review_summary,
            continuation_pack=continuation_pack,
        )
        feedback_revision_bridge_pack = self._feedback_revision_bridge_pack(
            reader_feedback_pack=reader_feedback_pack,
            editor_revision_pack=editor_revision_pack,
        )
        chapter_draft_preparation_pack = self._chapter_draft_preparation_pack(
            knowledge_pack=knowledge_pack,
            continuation_pack=continuation_pack,
            imitation_pack=imitation_pack,
            risk_summary=risk_summary,
            review_summary=review_summary,
        )
        direct_draft_skeleton_pack = self._direct_draft_skeleton_pack(
            chapter_draft_preparation_pack=chapter_draft_preparation_pack,
        )
        direct_revision_loop_pack = self._direct_revision_loop_pack(
            direct_draft_skeleton_pack=direct_draft_skeleton_pack,
            editor_revision_pack=editor_revision_pack,
        )
        automatic_rewrite_guidance_pack = self._automatic_rewrite_guidance_pack(
            direct_revision_loop_pack=direct_revision_loop_pack,
            reader_feedback_pack=reader_feedback_pack,
            feedback_revision_bridge_pack=feedback_revision_bridge_pack,
        )
        automatic_prose_rewrite_pack = self._automatic_prose_rewrite_pack(
            direct_draft_skeleton_pack=direct_draft_skeleton_pack,
            automatic_rewrite_guidance_pack=automatic_rewrite_guidance_pack,
            reader_feedback_pack=reader_feedback_pack,
        )
        final_draft_candidate_pack = self._final_draft_candidate_pack(
            automatic_prose_rewrite_pack=automatic_prose_rewrite_pack,
            risk_summary=risk_summary,
            review_summary=review_summary,
            reader_feedback_pack=reader_feedback_pack,
        )
        publish_ready_release_pack = self._publish_ready_release_pack(
            final_draft_candidate_pack=final_draft_candidate_pack,
            whole_book_readiness_summary=readiness_summary,
            whole_book_consistency_backflow_pack=whole_book_consistency_backflow_pack,
        )
        sample_based_release_criteria_bundle = self._sample_based_release_criteria_bundle(
            publish_ready_release_pack=publish_ready_release_pack,
            sample_evidence_summary=sample_evidence_summary,
            retrieval_benchmark_summary=retrieval_benchmark_summary,
            reader_feedback_pack=reader_feedback_pack,
        )
        release_decision_freeze_artifact_pack = self._release_decision_freeze_artifact_pack(
            sample_based_release_criteria_bundle=sample_based_release_criteria_bundle,
            publish_ready_release_pack=publish_ready_release_pack,
        )
        handoff_approval_record_pack = self._handoff_approval_record_pack(
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
            publish_ready_release_pack=publish_ready_release_pack,
        )
        operator_release_brief_pack = self._operator_release_brief_pack(
            handoff_approval_record_pack=handoff_approval_record_pack,
            sample_based_release_criteria_bundle=sample_based_release_criteria_bundle,
        )
        release_ops_runbook_pack = self._release_ops_runbook_pack(
            operator_release_brief_pack=operator_release_brief_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
        )
        incident_rollback_pack = self._incident_rollback_pack(
            release_ops_runbook_pack=release_ops_runbook_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
        )
        postmortem_recovery_record_pack = self._postmortem_recovery_record_pack(
            incident_rollback_pack=incident_rollback_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
        )
        recovery_closure_artifact_pack = self._recovery_closure_artifact_pack(
            postmortem_recovery_record_pack=postmortem_recovery_record_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
        )
        final_governance_summary_pack = self._final_governance_summary_pack(
            publish_ready_release_pack=publish_ready_release_pack,
            sample_based_release_criteria_bundle=sample_based_release_criteria_bundle,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
            handoff_approval_record_pack=handoff_approval_record_pack,
            release_ops_runbook_pack=release_ops_runbook_pack,
            recovery_closure_artifact_pack=recovery_closure_artifact_pack,
        )
        governance_dashboard_pack = self._governance_dashboard_pack(
            final_governance_summary_pack=final_governance_summary_pack,
            publish_ready_release_pack=publish_ready_release_pack,
            sample_based_release_criteria_bundle=sample_based_release_criteria_bundle,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
            operator_release_brief_pack=operator_release_brief_pack,
            whole_book_consistency_backflow_pack=whole_book_consistency_backflow_pack,
        )
        governance_report_brief_pack = self._governance_report_brief_pack(
            governance_dashboard_pack=governance_dashboard_pack,
            final_governance_summary_pack=final_governance_summary_pack,
            whole_book_consistency_backflow_pack=whole_book_consistency_backflow_pack,
        )
        release_review_note_pack = self._release_review_note_pack(
            governance_report_brief_pack=governance_report_brief_pack,
            publish_ready_release_pack=publish_ready_release_pack,
            sample_based_release_criteria_bundle=sample_based_release_criteria_bundle,
            whole_book_consistency_backflow_pack=whole_book_consistency_backflow_pack,
        )
        approval_decision_memo_pack = self._approval_decision_memo_pack(
            release_review_note_pack=release_review_note_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
            whole_book_consistency_backflow_pack=whole_book_consistency_backflow_pack,
        )
        external_report_bundle_pack = self._external_report_bundle_pack(
            governance_dashboard_pack=governance_dashboard_pack,
            governance_report_brief_pack=governance_report_brief_pack,
            release_review_note_pack=release_review_note_pack,
            approval_decision_memo_pack=approval_decision_memo_pack,
            release_ops_runbook_pack=release_ops_runbook_pack,
            incident_rollback_pack=incident_rollback_pack,
            final_governance_summary_pack=final_governance_summary_pack,
        )
        external_report_markdown_pack = self._external_report_markdown_pack(
            external_report_bundle_pack=external_report_bundle_pack,
        )
        archive_manifest_pack = self._archive_manifest_pack(
            final_release_archive_pack={
                "contract_version": "final-release-archive-pack.v1",
                "archive_summary": "已汇总候选稿、freeze 决策、handoff 记录与外部治理包，可直接归档。",
            },
        )
        archive_retention_metadata_pack = self._archive_retention_metadata_pack(
            archive_manifest_pack=archive_manifest_pack,
        )
        archive_index_metadata_pack = self._archive_index_metadata_pack(
            archive_manifest_pack=archive_manifest_pack,
            archive_retention_metadata_pack=archive_retention_metadata_pack,
        )
        archive_integrity_check_pack = self._archive_integrity_check_pack(
            final_release_archive_pack={
                "candidate": {},
                "freeze_artifact": {},
                "handoff_record": {},
                "external_report_bundle": {},
            },
        )
        final_release_archive_pack = self._final_release_archive_pack(
            final_draft_candidate_pack=final_draft_candidate_pack,
            release_decision_freeze_artifact_pack=release_decision_freeze_artifact_pack,
            handoff_approval_record_pack=handoff_approval_record_pack,
            external_report_bundle_pack=external_report_bundle_pack,
            archive_retention_metadata_pack=archive_retention_metadata_pack,
            archive_index_metadata_pack=archive_index_metadata_pack,
            archive_integrity_check_pack=archive_integrity_check_pack,
        )
        return {
            "contract_version": "novel-assistant.v1",
            "branch_id": branch_id,
            "run_id": branch.run_id,
            "branch_snapshot": branch_snapshot,
            "assistant_summary": {
                "chapter_count": chapter_count,
                "review_cluster_count": int(review_summary.get("cluster_count", 0) or 0),
                "review_needs_count": int(review_summary.get("needs_review_count", 0) or 0),
                "risk_card_count": int(risk_summary.get("risk_card_count", 0) or 0),
                "top_entities": top_entities[:5],
                "assistant_mode": "commercial-novel-assistant",
            },
            "supported_actions": [
                "split_novel",
                "retrieve_evidence",
                "answer_question",
                "author_knowledge",
                "risk_gate_review",
                "continue_writing_preparation",
                "imitation_preparation",
                "whole_book_preparation",
                "whole_book_consistency_backflow",
                "original_planning",
                "creation_control",
                "editor_revision",
                "reader_feedback_loop",
                "feedback_revision_bridge",
                "retrieval_benchmark",
                "chapter_draft_preparation",
                "direct_draft_skeleton",
                "direct_revision_loop",
                "automatic_rewrite_guidance",
                "automatic_prose_rewrite",
                "final_draft_candidate",
                "publish_ready_release",
                "sample_based_release_criteria",
                "release_decision_freeze_artifact",
                "handoff_approval_record",
                "operator_release_brief",
                "release_ops_runbook",
                "incident_rollback",
                "postmortem_recovery_record",
                "recovery_closure_artifact",
                "final_governance_summary",
                "governance_dashboard",
                "governance_report_brief",
                "release_review_note",
                "approval_decision_memo",
                "external_report_bundle",
                "external_report_markdown",
                "final_release_archive",
                "archive_manifest",
                "archive_retention_metadata",
                "archive_index_metadata",
                "archive_integrity_check",
            ],
            "recommended_next_actions": [
                "先用 author knowledge 确认人物/规则/线程现状，再进入续写/仿写。",
                "需要问答或检索时，优先使用 retrieval diagnostics 与 benchmark summary 确认召回质量。",
                "进入 whole-book 之前先看 review_summary 与 risk_summary，避免带病生成。",
                "生成完成后按 editor revision 与 reader feedback pack 进入修文闭环。",
            ],
            "whole_book_readiness_summary": readiness_summary,
            "sample_evidence_summary": sample_evidence_summary,
            "preparation_guidance": preparation_guidance,
            "retrieval_benchmark_summary": retrieval_benchmark_summary,
            "whole_book_consistency_backflow_pack": whole_book_consistency_backflow_pack,
            "continuation_pack": continuation_pack,
            "imitation_pack": imitation_pack,
            "original_planning_pack": original_planning_pack,
            "creation_control_pack": creation_control_pack,
            "editor_revision_pack": editor_revision_pack,
            "reader_feedback_pack": reader_feedback_pack,
            "feedback_revision_bridge_pack": feedback_revision_bridge_pack,
            "chapter_draft_preparation_pack": chapter_draft_preparation_pack,
            "direct_draft_skeleton_pack": direct_draft_skeleton_pack,
            "direct_revision_loop_pack": direct_revision_loop_pack,
            "automatic_rewrite_guidance_pack": automatic_rewrite_guidance_pack,
            "automatic_prose_rewrite_pack": automatic_prose_rewrite_pack,
            "final_draft_candidate_pack": final_draft_candidate_pack,
            "publish_ready_release_pack": publish_ready_release_pack,
            "sample_based_release_criteria_bundle": sample_based_release_criteria_bundle,
            "release_decision_freeze_artifact_pack": release_decision_freeze_artifact_pack,
            "handoff_approval_record_pack": handoff_approval_record_pack,
            "operator_release_brief_pack": operator_release_brief_pack,
            "release_ops_runbook_pack": release_ops_runbook_pack,
            "incident_rollback_pack": incident_rollback_pack,
            "postmortem_recovery_record_pack": postmortem_recovery_record_pack,
            "recovery_closure_artifact_pack": recovery_closure_artifact_pack,
            "final_governance_summary_pack": final_governance_summary_pack,
            "governance_dashboard_pack": governance_dashboard_pack,
            "governance_report_brief_pack": governance_report_brief_pack,
            "release_review_note_pack": release_review_note_pack,
            "approval_decision_memo_pack": approval_decision_memo_pack,
            "external_report_bundle_pack": external_report_bundle_pack,
            "external_report_markdown_pack": external_report_markdown_pack,
            "final_release_archive_pack": final_release_archive_pack,
            "archive_manifest_pack": archive_manifest_pack,
            "archive_retention_metadata_pack": archive_retention_metadata_pack,
            "archive_index_metadata_pack": archive_index_metadata_pack,
            "archive_integrity_check_pack": archive_integrity_check_pack,
            "audit_conclusion": branch_bundle.get("audit_conclusion", {}),
            "review_summary": review_summary,
            "risk_summary": risk_summary,
            "author_knowledge": knowledge_pack,
            "retrieval_diagnostics": retrieval_diagnostics,
            "qa_answer": qa_answer,
        }
