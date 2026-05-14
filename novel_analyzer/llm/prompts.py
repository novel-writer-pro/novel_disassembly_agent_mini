"""Prompt builders for chapter analysis and retrieval-backed Q&A."""

from __future__ import annotations

from novel_analyzer.domain.analysis_dimensions import AnalysisDimension


def build_chapter_analysis_prompt(
    *,
    chapter_index: int,
    normalized_title: str,
    chapter_content: str,
) -> str:
    """Build the live chapter-analysis prompt."""

    dimensions = ", ".join(dimension.value for dimension in AnalysisDimension)
    return f"""
你是一个专业的小说拆书分析师。
请对下面章节输出严格 JSON，且只输出 JSON，
不要 Markdown 代码块，不要解释文字。

章节序号：{chapter_index}
章节标题：{normalized_title}

必须覆盖这些维度：{dimensions}

输出 JSON 结构要求：
{{
  "chapter_index": {chapter_index},
  "normalized_title": "{normalized_title}",
  "dimensions": [
    {{
      "dimension": "chapter_summary",
      "summary": "...",
      "evidence": ["..."],
      "confidence": 0.0
    }}
  ],
  "chapter_summary": "...",
  "key_entities": ["..."],
  "key_events": ["..."],
  "continuity_notes": ["..."]
}}

要求：
1. chapter_summary 必须简洁准确。
2. key_events 要提炼关键事件。
3. continuity_notes 要说明与前文衔接、伏笔、状态变化。
4. dimensions 中尽量覆盖所有维度；不足时也至少覆盖本章最相关维度。
5. 不要编造未在本章文本直接出现的事实；如果是推断，请降低 confidence。

本章正文：
{chapter_content}
""".strip()


def build_branch_qa_prompt(*, question: str, retrieval_context: str) -> str:
    """Build a retrieval-grounded Q&A prompt for one branch."""

    return f"""
你是小说拆书 agent 的问答模块。
你的任务是根据给定的检索上下文，回答用户关于小说细节的问题。

问题：
{question}

检索上下文：
{retrieval_context}

回答要求：
1. 只能根据检索上下文回答，不要编造。
2. 尽量先给出“当前能确定的最直接答案”，再补充证据。
3. 如果证据不足，请明确说“当前证据不足”，并指出缺少什么。
4. 尽量引用章节号，例如“第1章”。
5. 如果窗口总结或图谱上下文支持你的回答，也要纳入 explanation。
6. 如果图谱里存在明确的 reasoning path、活跃冲突、未回收伏笔或世界规则，尽量把这些信号转成保守表述。
6. 输出 JSON，结构如下：
{{
  "answer": "...",
  "used_chapters": [1, 2],
  "evidence": ["..."],
  "reasoning_paths": ["A -[advances_to]-> B"],
  "graph_signals": ["活跃冲突: ...", "未回收伏笔: ..."],
  "confidence": 0.0,
  "insufficient_context": false
}}
7. evidence 必须优先放章节证据，reasoning_paths 放图谱路径，graph_signals 放冲突/伏笔/规则等图信号。
8. 如果问题无法由当前上下文完整回答：
   - answer 仍给出保守但有信息量的部分回答
   - insufficient_context = true
   - confidence 低于 0.5
9. 不要只说“无法判断”，除非上下文几乎完全没有相关信息。
""".strip()


def build_chapter_imitation_prompt(
    *,
    source_chapter_index: int,
    source_title: str,
    source_excerpt: str,
    target_goal: str,
    style_axes: list[str],
    scene_beats: list[str],
    hard_constraints: list[str],
    soft_constraints: list[str],
    previous_summary: str = "",
    active_characters: list[str] | None = None,
    unresolved_threads: list[str] | None = None,
    mapping_pack: dict[str, object] | None = None,
) -> str:

    style_text = "\n".join(f"- {item}" for item in style_axes) or "- 保持原章结构功能"
    beat_text = "\n".join(f"- {item}" for item in scene_beats) or "- 维持原章推进"
    hard_text = "\n".join(f"- {item}" for item in hard_constraints) or "- 不得违背现有世界规则"
    soft_text = "\n".join(f"- {item}" for item in soft_constraints) or "- 保持人物与关系推进连续"

    memory_block = ""
    if previous_summary or active_characters or unresolved_threads:
        parts: list[str] = []
        if previous_summary:
            parts.append(f"前情摘要：\n{previous_summary[:600]}")
        if active_characters:
            parts.append(f"当前活跃角色：{', '.join(active_characters[:8])}")
        if unresolved_threads:
            parts.append(f"待回收线索：\n" + "\n".join(f"- {t}" for t in unresolved_threads[:5]))
        memory_block = "\n\n记忆上下文：\n" + "\n".join(parts)

    mapping_block = ""
    if mapping_pack:
        mp_parts: list[str] = []
        cm = mapping_pack.get("character_mapping") or {}
        wm = mapping_pack.get("world_mapping") or {}
        fm = mapping_pack.get("faction_mapping") or {}
        pm = mapping_pack.get("power_mapping") or {}
        rules = mapping_pack.get("rule_overrides") or []
        forbids = mapping_pack.get("forbidden_transformations") or []
        if isinstance(cm, dict) and cm:
            mp_parts.append("人物名替换（必须执行）：" + "；".join(f"{k}→{v}" for k, v in cm.items()))
        if isinstance(wm, dict) and wm:
            mp_parts.append("世界设定替换（必须执行）：" + "；".join(f"{k}→{v}" for k, v in wm.items()))
        if isinstance(fm, dict) and fm:
            mp_parts.append("势力替换（必须执行）：" + "；".join(f"{k}→{v}" for k, v in fm.items()))
        if isinstance(pm, dict) and pm:
            mp_parts.append("力量体系替换（必须执行）：" + "；".join(f"{k}→{v}" for k, v in pm.items()))
        if isinstance(rules, list) and rules:
            mp_parts.append("规则覆盖：" + "；".join(str(r) for r in rules[:5]))
        if isinstance(forbids, list) and forbids:
            mp_parts.append("禁止转化：" + "；".join(str(f) for f in forbids[:5]))
        if mp_parts:
            mapping_block = "\n\n设定替换映射（draft_text 中所有出现都必须按映射后名称写）：\n" + "\n".join(f"- {p}" for p in mp_parts)

    return f"""
你是一个"章节仿写规划执行器"。

任务：
在保留原章结构功能、冲突推进与人物选择逻辑的前提下，
基于给定目标生成一个**结构化仿写草案**。

注意：
1. 不要直接抄原文句子。
2. 不要擅自突破世界规则。
3. 不要让人物行为脱离既有逻辑。
4. 输出只允许 JSON，不要 Markdown。
5. 若给出了"设定替换映射"，draft_text 中必须使用映射后的名称，不得保留原名。

源章节：
- chapter_index: {source_chapter_index}
- title: {source_title}

源章节摘录：
{source_excerpt}

本次目标：
{target_goal}
{memory_block}{mapping_block}

风格轴：
{style_text}

场景节拍：
{beat_text}

硬约束：
{hard_text}

软约束：
{soft_text}

输出 JSON：
{{
  "draft_title": "{source_title}",
  "draft_text": "...",
  "method_notes": ["..."],
  "comparison_notes": ["..."],
  "risk_gate_notes": ["..."]
}}

要求：
- draft_text 先写成“短章草案”，重在结构正确，不追求篇幅。
- comparison_notes 必须说明与原章骨架的对应关系。
- risk_gate_notes 必须明确指出应该重点过哪些风险检查。
""".strip()
