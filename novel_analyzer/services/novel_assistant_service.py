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

    @staticmethod
    def _reader_feedback_pack(
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
        if not pain_point_hypotheses:
            pain_point_hypotheses.append("当前主风险更偏执行质量，而非明显的读者体验断点。")
        return {
            "contract_version": "reader-feedback-pack.v1",
            "pain_point_hypotheses": pain_point_hypotheses,
            "feedback_collection_prompts": [
                "哪一章开始觉得节奏变慢？原因是什么？",
                "你最想继续追的角色/线程是什么？",
                "哪些设定、关系或战力变化让你觉得突兀？",
            ],
            "revision_from_feedback": [
                "把反馈映射回 thread / character / rule，再决定是补铺垫还是删枝杈。",
                "优先处理会影响续读率的章尾钩子、主角目标感、信息负担问题。",
            ],
            "priority_entities": top_entities[:4],
            "priority_threads": top_threads[:4],
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
            knowledge_pack=knowledge_pack,
            review_summary=review_summary,
            continuation_pack=continuation_pack,
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
                "original_planning",
                "creation_control",
                "editor_revision",
                "reader_feedback_loop",
                "retrieval_benchmark",
                "chapter_draft_preparation",
                "direct_draft_skeleton",
                "direct_revision_loop",
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
            "continuation_pack": continuation_pack,
            "imitation_pack": imitation_pack,
            "original_planning_pack": original_planning_pack,
            "creation_control_pack": creation_control_pack,
            "editor_revision_pack": editor_revision_pack,
            "reader_feedback_pack": reader_feedback_pack,
            "chapter_draft_preparation_pack": chapter_draft_preparation_pack,
            "direct_draft_skeleton_pack": direct_draft_skeleton_pack,
            "direct_revision_loop_pack": direct_revision_loop_pack,
            "audit_conclusion": branch_bundle.get("audit_conclusion", {}),
            "review_summary": review_summary,
            "risk_summary": risk_summary,
            "author_knowledge": knowledge_pack,
            "retrieval_diagnostics": retrieval_diagnostics,
            "qa_answer": qa_answer,
        }
