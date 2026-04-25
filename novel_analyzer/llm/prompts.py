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
6. 输出 JSON，结构如下：
{{
  "answer": "...",
  "used_chapters": [1, 2],
  "evidence": ["..."],
  "confidence": 0.0,
  "insufficient_context": false
}}
7. 如果问题无法由当前上下文完整回答：
   - answer 仍给出保守但有信息量的部分回答
   - insufficient_context = true
   - confidence 低于 0.5
8. 不要只说“无法判断”，除非上下文几乎完全没有相关信息。
""".strip()
