"""Author-facing knowledge pack assembly."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact, FactRecord
from novel_analyzer.services.context_service import ContextService


class AuthorKnowledgeService:
    """Build a structured branch knowledge pack from existing knowledge layers."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.context = ContextService(session)

    @staticmethod
    def _story_bible_pack(
        *,
        chapter_cards: list[dict[str, Any]],
        entity_profiles: list[dict[str, Any]],
        relationship_index: list[dict[str, Any]],
        rule_index: list[dict[str, Any]],
        thread_index: list[dict[str, Any]],
        summary_layer: dict[str, Any],
    ) -> dict[str, object]:
        protagonist_candidates = [item.get("label", "") for item in entity_profiles[:3] if item.get("label")]
        backbone = []
        for card in chapter_cards[:8]:
            backbone.append(
                {
                    "chapter_index": card.get("chapter_index"),
                    "title": card.get("title", ""),
                    "summary": card.get("summary", ""),
                    "key_events": list(card.get("key_events", []))[:3],
                }
            )
        actives = [item.get("label", "") for item in relationship_index[:5] if item.get("label")]
        rules = [item.get("label", "") for item in rule_index[:5] if item.get("label")]
        threads = [item.get("label", "") for item in thread_index[:6] if item.get("label")]
        premise = ""
        if summary_layer.get("chapter_focus"):
            premise = f"围绕{summary_layer['chapter_focus'][0]}所展开的长线叙事，当前聚焦于人物成长、资源获取与身份突破。"

        chapter_text = "\n".join(str(card.get("summary", "")) for card in chapter_cards)
        relationship_text = "\n".join(actives)
        thread_text = "\n".join(threads)
        character_cards = []
        for item in entity_profiles[:6]:
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            role_tags = ["entity"]
            if protagonist_candidates and label == protagonist_candidates[0]:
                role_tags.append("protagonist")
            if label in relationship_text:
                role_tags.append("relationship-core")
            if label in thread_text:
                role_tags.append("thread-linked")
            motivations = []
            if label in chapter_text:
                if any(key in chapter_text for key in ["赎身", "脱籍", "武举", "身份"]):
                    motivations.append("追求身份突破与长期上升")
                if any(key in chapter_text for key in ["资源", "养生功", "功法", "修炼"]):
                    motivations.append("获取资源与能力积累")
                if any(key in chapter_text for key in ["婚事", "家", "夫妇", "亲属"]):
                    motivations.append("维持家庭与关系稳定")
            if not motivations:
                motivations.append("在当前叙事里承担持续推进作用")
            tensions = []
            if any(key in chapter_text for key in ["阶级", "家奴", "身契"]):
                tensions.append("受身份/阶层约束")
            if label in relationship_text:
                tensions.append("关键关系将影响后续选择空间")
            if not tensions:
                tensions.append("仍需更多章节证据来确认长期冲突")
            character_cards.append(
                {
                    "label": label,
                    "role_tags": role_tags,
                    "first_chapter_index": item.get("first_chapter_index"),
                    "last_chapter_index": item.get("last_chapter_index"),
                    "motivation_candidates": motivations[:3],
                    "tension_points": tensions[:3],
                    "continuity_focus": f"关注{label}在后续章节中的目标、关系与代价是否持续一致。",
                }
            )

        primary_goal = "推进主角的身份突破与资源积累"
        if any(key in chapter_text for key in ["武举", "脱籍", "赎身"]):
            primary_goal = "完成赎身/脱籍并争取进入更高身份路径"
        support_goals = []
        if any(key in chapter_text for key in ["婚事", "夫妇", "杏"]):
            support_goals.append("保持家庭与婚后协作稳定")
        if any(key in chapter_text for key in ["养生功", "功法", "修炼"]):
            support_goals.append("持续通过修炼累积可转化能力")
        if any(key in relationship_text for key in ["二姑", "卫荭", "李宅"]):
            support_goals.append("经营关键关系以换取资源与信息入口")
        obstacles = []
        if any(key in chapter_text for key in ["家奴", "身契", "阶级"]):
            obstacles.append("身份与身契限制")
        if any(key in chapter_text for key in ["银子", "钱", "收成"]):
            obstacles.append("银钱与资源不足")
        if any(key in thread_text for key in ["冲突", "风险"]):
            obstacles.append("未解线程与潜在风险压力")
        if not obstacles:
            obstacles.append("长线冲突仍需更多章节显式化")
        motivation_tree = {
            "contract_version": "motivation-tree.v1",
            "primary_goal": primary_goal,
            "support_goals": support_goals[:4],
            "obstacles": obstacles[:4],
            "decision_pressure": [
                "每次重要选择都要同时考虑身份、资源、关系三重约束。",
                "不能只追求短期爽点，要检查是否破坏长期成长弧。",
            ],
        }
        growth_arc = {
            "contract_version": "growth-arc.v1",
            "current_stage": "从底层生存转向主动争取身份与能力提升",
            "completed_beats": [
                "获得关键关系入口",
                "开始修炼/资源积累",
                "形成婚后协作与现实筹划",
            ],
            "next_beats": [
                "把资源积累转成身份跃迁机会",
                "验证主角是否能承受更高代价与风险",
                "让家庭、修炼、身份目标形成更强冲突与选择",
            ],
            "regression_risks": [
                "无铺垫的战力或身份跃迁",
                "关系变化缺少中间证据",
                "只推进事件，不推进人物选择逻辑",
            ],
        }
        volume_outline = {
            "contract_version": "volume-outline.v1",
            "volume_goal": primary_goal,
            "opening_status": backbone[0]["summary"] if backbone else premise,
            "mid_volume_turns": [
                "把关键关系入口转成持续资源通路",
                "让主角在资源/身份/家庭之间做更难选择",
            ],
            "late_volume_payoffs": [
                "让赎身/脱籍主线迎来一次实质性推进",
                "让前期修炼与关系经营开始兑现为新位置或新风险",
            ],
            "gating_threads": threads[:4],
            "required_payoffs": support_goals[:3] or ["家庭线与身份线必须发生交叉兑现"],
        }
        arc_outline = {
            "contract_version": "arc-outline.v1",
            "arc_name": "身份突破与能力积累弧",
            "setup": [
                "确认主角受限的初始位置与现实代价",
                "建立修炼、关系、家庭三条支撑线",
            ],
            "progression": growth_arc["completed_beats"] + growth_arc["next_beats"][:2],
            "turning_points": [
                "关键关系带来机会，但同时抬高代价",
                "资源或身份压力迫使主角提前行动",
            ],
            "payoff_targets": [
                "主角获得可验证的新位置或新资格",
                "关系线不只是陪衬，而要影响主线选择",
            ],
            "anti_patterns": growth_arc["regression_risks"],
        }
        return {
            "contract_version": "story-bible-pack.v1",
            "premise": premise,
            "protagonist_candidates": protagonist_candidates,
            "world_rules_digest": rules,
            "relationship_backbone": actives,
            "active_threads": threads,
            "chapter_backbone": backbone,
            "character_cards": character_cards,
            "motivation_tree": motivation_tree,
            "growth_arc": growth_arc,
            "volume_outline": volume_outline,
            "arc_outline": arc_outline,
            "arc_questions": [
                "主角当前最核心的长期目标是否稳定？",
                "哪些关系会决定下一阶段资源或身份突破？",
                "哪些未解线程必须进入卷纲级管理，而不能只留在章节记忆里？",
            ],
            "next_author_actions": [
                "把 active_threads 按主线 / 支线 / 伏笔分层整理。",
                "把 protagonist_candidates 扩成角色卡、动机与代价表。",
                "把 world_rules_digest 转成可直接约束续写/仿写的规则表。",
            ],
        }

    def build_branch_knowledge_pack(
        self,
        branch_id: str,
        *,
        from_chapter_index: int | None = None,
        upto_chapter_index: int | None = None,
        focus_label: str = "",
        limit_per_section: int = 20,
    ) -> dict[str, object]:
        artifact_stmt = select(ChapterArtifact).where(
            ChapterArtifact.branch_id == branch_id,
            ChapterArtifact.artifact_type == "chapter_analysis",
            ChapterArtifact.visibility == "active",
        )
        if from_chapter_index is not None:
            artifact_stmt = artifact_stmt.where(ChapterArtifact.chapter_index >= from_chapter_index)
        if upto_chapter_index is not None:
            artifact_stmt = artifact_stmt.where(ChapterArtifact.chapter_index <= upto_chapter_index)
        artifacts = self.session.scalars(artifact_stmt.order_by(ChapterArtifact.chapter_index.asc())).all()
        facts_stmt = select(FactRecord).where(FactRecord.branch_id == branch_id)
        if from_chapter_index is not None:
            facts_stmt = facts_stmt.where(FactRecord.chapter_index >= from_chapter_index)
        if upto_chapter_index is not None:
            facts_stmt = facts_stmt.where(FactRecord.chapter_index <= upto_chapter_index)
        normalized_focus = focus_label.strip()
        if normalized_focus:
            facts_stmt = facts_stmt.where(FactRecord.label.like(f"%{normalized_focus}%"))
        facts = self.session.scalars(
            facts_stmt.order_by(FactRecord.chapter_index.asc(), FactRecord.fact_type.asc(), FactRecord.label.asc())
        ).all()

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        aggregated_labels: dict[str, dict[str, Any]] = {}
        for row in facts:
            item = aggregated_labels.setdefault(
                row.label,
                {
                    "label": row.label,
                    "fact_types": [],
                    "first_chapter_index": row.chapter_index,
                    "last_chapter_index": row.chapter_index,
                    "occurrence_count": 0,
                    "top_confidence": row.confidence,
                },
            )
            item["first_chapter_index"] = min(int(item["first_chapter_index"]), row.chapter_index)
            item["last_chapter_index"] = max(int(item["last_chapter_index"]), row.chapter_index)
            item["occurrence_count"] = int(item["occurrence_count"]) + 1
            item["top_confidence"] = max(float(item["top_confidence"]), row.confidence)
            if row.fact_type not in item["fact_types"]:
                item["fact_types"].append(row.fact_type)
            grouped[row.fact_type].append(
                {
                    "label": row.label,
                    "chapter_index": row.chapter_index,
                    "confidence": row.confidence,
                    "evidence_list": row.evidence_list,
                }
            )

        latest_chapter = artifacts[-1].chapter_index if artifacts else 0
        state_summary = self.context.state_summary_json(branch_id, latest_chapter + 1) if latest_chapter else {}
        graph_context = self.context.graph_context_json(branch_id, latest_chapter + 1) if latest_chapter else {}

        chapter_cards = [
            {
                "chapter_index": artifact.chapter_index,
                "title": str(artifact.payload_json.get("normalized_title", "")),
                "summary": str(artifact.payload_json.get("chapter_summary", "")),
                "key_entities": list(artifact.payload_json.get("key_entities", []))[:5],
                "key_events": list(artifact.payload_json.get("key_events", []))[:5],
                "continuity_notes": list(artifact.payload_json.get("continuity_notes", []))[:3],
            }
            for artifact in artifacts[:limit_per_section]
        ]
        knowledge_index = sorted(
            aggregated_labels.values(),
            key=lambda item: (
                -int(item["occurrence_count"]),
                -float(item["top_confidence"]),
                str(item["label"]),
            ),
        )[:limit_per_section]
        relationship_watch = list(state_summary.get("evolved_relations", []))[:limit_per_section]
        rule_watch = list(state_summary.get("constraining_world_rules", []))[:limit_per_section]
        unresolved_threads = list(state_summary.get("new_conflicts", []))[:limit_per_section]
        entity_profiles = [
            {
                **item,
                "primary_fact_type": (
                    "entity" if "entity" in item["fact_types"] else item["fact_types"][0]
                ),
            }
            for item in knowledge_index
            if "entity" in item["fact_types"]
        ][:limit_per_section]
        relationship_index = [
            {"label": str(item), "source": "state_summary.evolved_relations"}
            for item in relationship_watch
        ][:limit_per_section]
        rule_index = [
            {"label": str(item), "source": "state_summary.constraining_world_rules"}
            for item in rule_watch
        ][:limit_per_section]
        thread_index = [
            {"label": str(item), "source": "state_summary.new_conflicts"}
            for item in unresolved_threads
        ][:limit_per_section]
        summary_layer = {
            "top_entities": [item["label"] for item in entity_profiles[:5]],
            "top_rules": [item["label"] for item in rule_index[:5]],
            "top_relationships": [item["label"] for item in relationship_index[:5]],
            "top_threads": [item["label"] for item in thread_index[:5]],
            "chapter_focus": [item["title"] for item in chapter_cards[:3]],
        }
        story_bible_pack = self._story_bible_pack(
            chapter_cards=chapter_cards,
            entity_profiles=entity_profiles,
            relationship_index=relationship_index,
            rule_index=rule_index,
            thread_index=thread_index,
            summary_layer=summary_layer,
        )

        return {
            "contract_version": "author-knowledge.v1",
            "branch_id": branch_id,
            "focus_label": normalized_focus,
            "chapter_span": {
                "min": artifacts[0].chapter_index if artifacts else None,
                "max": latest_chapter or None,
                "count": len(artifacts),
            },
            "chapter_cards": chapter_cards,
            "entities": grouped.get("entity", [])[:limit_per_section],
            "events": grouped.get("event", [])[:limit_per_section],
            "continuity": grouped.get("continuity", [])[:limit_per_section],
            "knowledge_index": knowledge_index,
            "entity_profiles": entity_profiles,
            "relationship_index": relationship_index,
            "rule_index": rule_index,
            "thread_index": thread_index,
            "summary_layer": summary_layer,
            "story_bible_pack": story_bible_pack,
            "relationship_watch": relationship_watch,
            "rule_watch": rule_watch,
            "unresolved_threads": unresolved_threads,
            "state_summary": state_summary,
            "graph_overview": graph_context.get("overview", {}),
            "central_nodes": graph_context.get("central_nodes", [])[:10],
            "recent_timeline": graph_context.get("recent_timeline", [])[:10],
            "recommended_questions": [
                "主角当前最重要的推进线是什么？",
                "当前有哪些关键关系与未解线程？",
                "规则/世界观约束最近有哪些变化？",
            ],
        }
