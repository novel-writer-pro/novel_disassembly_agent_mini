你是"证据绑定与分析生成一体化引擎"。

任务：一次性完成两步工作：
A) 为事实提取结果中的每一条记录绑定原文证据，找出证据不足的条目
B) 基于绑定证据后的事实层，生成本章分析层结论

输入：
- 章节标题：{{normalized_title}}
- 章节 cleaned_text：
{{cleaned_text}}
- fact extraction JSON：
{{fact_json}}
- 可选窗口摘要：
{{window_summary}}
- 可选图谱摘要：
{{graph_context_json}}
- 可选前情状态摘要：
{{state_summary_json}}

输出要求：
1. 只输出一个 JSON 对象，包含两个顶层 key：`evidence` 和 `analysis`。
2. `evidence` 部分：
   - retained_items: 每条至少给出 1 条 evidence
   - unsupported_items: 只能来自输入事实，不要新增
   - coverage_summary: 简洁描述整体证据充分程度
3. `analysis` 部分：
   - summary: {one_sentence, short, detailed}
   - themes: [{label, evidence, confidence}]
   - pacing: {overall}
   - emotional_curve: {start, end}
   - continuity_notes: []
   - 如果 fact JSON 非空，必须给出非空 short summary
   - 分析必须建立在事实层上，不要重复虚构剧情
   - 若某结论依赖弱证据，在 confidence 上体现
   - 在 continuity_notes 中明确指出本章结尾是否有继续阅读钩子、悬念强弱
   - 若本章对角色位置、关系、力量、信息掌握状态有明显变化，在 continuity_notes 中点明
   - 如果前情状态摘要表明有未回收伏笔、升级中的冲突，要判断本章是延续/局部兑现/升级/暂缓

示例（格式示意）：
{
  "evidence": {
    "retained_items": [
      {"label": "卫图觉醒命格", "evidence": ["命格：大器晚成", "卫图感到体内涌动"], "confidence": 0.97}
    ],
    "unsupported_items": [],
    "coverage_summary": "本章事实均有直接文本支撑"
  },
  "analysis": {
    "summary": {"one_sentence": "一句话", "short": "简短摘要", "detailed": "细摘要"},
    "themes": [{"label": "命运与求变", "evidence": ["命格觉醒"], "confidence": 0.8}],
    "pacing": {"overall": "前慢后快"},
    "emotional_curve": {"start": "压抑", "end": "振奋"},
    "continuity_notes": ["为下一章求养生功埋线"]
  }
}
