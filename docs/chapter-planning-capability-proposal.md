# 下一章规划 / 章节仿写能力方案（预研版）

## 1. 目标定义

这里的目标不是直接放开“正文代写”，而是先做一套 **下一章规划能力**：

- 给定世界观
- 给定剧情进度
- 给定人物状态
- 给定未解线程 / 伏笔
- 给定用户本次写作意图

输出：

- 下一章该写什么
- 应该怎么推进
- 哪些线必须推进
- 哪些线不能乱碰
- 哪些写法有风险

因此第一阶段建议定义为：

> **Next Chapter Planner / 下一章规划器**

而不是：

> **Full Chapter Ghostwriter / 正文代写器**

---

## 2. 为什么先做“规划”而不是“正文”

原因有四个：

1. **规划比正文更稳定**
2. **规划更容易评估**
3. **规划更适合辅助作家，而不是替代作家**
4. **规划更容易接入当前门控体系做反向审查**

建议顺序：

1. 章节规划卡
2. 场景提纲
3. 风险约束卡
4. 可选草案
5. 最后才考虑正文仿写

---

## 3. 和当前系统如何衔接

当前拆书/门控系统已经能给出很多“续写规划”所需底座：

- `chapter_artifacts`
- `fact_records`
- `graph_nodes / graph_edges`
- `chapter_risk_cards`
- `gate_checker_results`
- `risk_semantic_signals`
- `risk_signal_links`
- `risk_signal_clusters`

因此章节规划能力不应另起炉灶，而应建立在现有结构化层之上。

---

## 4. 建议的四层结构

## Layer A：写作上下文汇总层

目标：从既有拆书结构中抽取“可供续写使用的当前状态快照”。

建议输出：

- `world_rule_pack`
- `character_state_pack`
- `relationship_state_pack`
- `active_conflict_pack`
- `unresolved_thread_pack`
- `recent_arc_pack`
- `pace_snapshot`
- `forbidden_moves`

## Layer B：下一章规划层

目标：不写正文，先写“下一章应该做什么”。

建议结构：

```json
{
  "chapter_goal": "...",
  "main_conflict": "...",
  "secondary_conflicts": ["..."],
  "required_progressions": ["..."],
  "scene_plan": [
    {"scene": 1, "purpose": "...", "must_include": ["..."]},
    {"scene": 2, "purpose": "...", "must_include": ["..."]}
  ],
  "character_movements": ["..."],
  "relationship_movements": ["..."],
  "foreshadow_to_touch": ["..."],
  "rule_constraints": ["..."],
  "ending_hook": "...",
  "risk_notes": ["..."]
}
```

## Layer C：仿写执行层

只有当用户明确需要时，才从 plan 继续生成：

- scene outline
- beat sheet
- prose draft

建议分两步：

1. 提纲稿
2. 草案稿

不要一上来直接整章长文输出。

## Layer D：反向门控层

生成后立刻过你当前的风险审查体系：

- character_ooc
- world_rule_consistency
- relationship_consistency
- plot_logic_consistency
- timeline_consistency
- power_scaling_consistency

形成闭环：

> 规划 / 草案生成 → 风险门控复审 → 返回作家修正建议

---

## 5. 最低可用输入

第一阶段建议要求这些输入：

### 必要输入

1. 当前章节位置
2. 最近 3~5 章摘要
3. 主角色当前状态
4. 关键关系状态
5. 当前世界规则约束
6. 未闭合线程 / 伏笔
7. 本章意图

### 本章意图示例

- 推主线
- 推关系
- 推世界观
- 铺垫下一次冲突
- 回收局部伏笔
- 缓冲/过渡
- 造高潮

### 可选输入

8. 风格约束
9. 禁区约束
10. 节奏强度约束

---

## 6. 第一版最值得交付的输出

## 输出 1：章节规划卡

- 本章目标
- 主冲突
- 次冲突
- 预期推进线
- 结尾钩子

## 输出 2：场景拆解卡

- 场景 1 做什么
- 场景 2 做什么
- 场景 3 做什么
- 每个场景的信息增量

## 输出 3：风险写法提示

- 哪些写法容易 OOC
- 哪些写法容易破坏规则
- 哪些写法会导致关系变化过猛
- 哪些写法会让节奏失衡

## 输出 4：可选仿写草案

只在用户主动需要时给：

- scene draft
- short prose draft

---

## 7. 与当前风险审查系统的关系

建议形成双向闭环：

### 拆书 / 审查 → 规划

当前系统提供：

- 当前世界里什么是真的
- 哪些线没有收
- 哪些关系敏感
- 哪些设定不能乱动

### 规划 / 草案 → 审查

规划完成后再过门控：

- 有无 OOC
- 有无规则冲突
- 有无时间线断裂
- 有无逻辑跳变

---

## 8. 第一阶段不建议做什么

以下内容不建议在第一版就做：

1. 直接整章自动代写
2. 不加约束地做“模仿文风”
3. 让模型自由发明新设定
4. 让模型绕过当前门控体系

这些会导致：

- 漂移大
- 不可控
- 很难评估
- 很难维护

---

## 9. 建议的下一步研发顺序

### Phase 1

- `next_chapter_context_builder`
- `next_chapter_planner`
- `chapter_plan_risk_checker`

### Phase 2

- `scene_outline_generator`
- `draft_constraint_generator`
- `draft_review_loop`

### Phase 3

- `style-aware prose draft`
- `planner + gate + revise loop`

---

## 10. 一句话结论

> 章节仿写能力的正确起点，不是“直接代写正文”，而是 **基于拆书状态与风险门控底座，先做下一章规划器 + 风险约束器**，再逐步放开到场景草案和正文草案。

---

## 11. 当前已落地的最小代码骨架

本轮已补入最小服务骨架：

- `novel_analyzer/services/next_chapter_planner_service.py`
- `ChapterPlanningIntent`
- `ChapterPlanningContext`
- `ChapterPlanningCard`
- `ChapterPlanningScene`

当前能力边界：

1. 能从 branch 当前状态提炼：
   - recent chapter summaries
   - active characters
   - unresolved threads
   - active conflicts
   - world rules
   - recent risk signal hints
2. 能生成最小的：
   - chapter goal
   - main conflict
   - scene plan
   - ending hook
   - risk notes
3. 当前仍是：
   - deterministic skeleton
   - non-LLM first-pass planner
   - 方便后续接 LLM / prompt planner / gate loop

这意味着：

> 下一步不必从 0 开始，而可以直接在这个 skeleton 上继续接入 branch package / risk card / LLM planner。

---

## 12. Whole-book orchestration 当前骨架

本轮已补入：

- `StoryMappingPack`
- `WholeBookImitationPlan`
- `WholeBookImitationService`
- `plan-whole-book-imitation`

这意味着系统已经开始支持：

1. 原作名 → 目标作品名
2. 世界映射
3. 人物映射
4. 势力映射
5. 能力/资源映射
6. 按章节目标排布整本仿写队列

当前仍是 orchestration skeleton，而不是完整整本生成器。
