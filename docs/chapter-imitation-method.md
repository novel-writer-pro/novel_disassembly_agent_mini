# 章节仿写能力：方法、步骤与实验闭环

## 1. 定位

这里的“仿写”不应理解为无约束模仿文风直接代写，而应理解为：

1. 先抽取原章的结构与推进方式
2. 再在既有世界观/人物状态/剧情进度下生成结构草案
3. 再对草案做风险检查
4. 最后才考虑扩写为正文

因此推荐流程是：

> **原章拆解 → 仿写计划 → 结构草案 → 风险检查 → 对比优化 → 扩写**

---

## 2. 推荐步骤

### Step 1：抽取原章骨架

至少抽取：

- 本章目标
- 主冲突
- 关键转折
- 结尾钩子
- 人物动作逻辑
- 信息释放顺序

### Step 2：抽取风格轴

不要直接说“模仿文风”，要拆成：

- 叙事视角
- 节奏速度
- 冲突密度
- 信息密度
- 句式张力
- 情绪克制度

### Step 3：建立硬约束

至少要约束：

- 世界规则
- 当前角色状态
- 关系状态
- 未解线程
- 不可越界动作

### Step 4：生成结构草案

优先生成：

- chapter goal
- scene beats
- required progression
- ending hook

而不是直接整章 prose。

### Step 5：风险门控

生成后立即执行：

- `character_ooc`
- `plot_logic_consistency`
- `world_rule_consistency`
- `relationship_consistency`

### Step 6：对比原章

比较：

- 原章推进骨架
- 草案推进骨架
- 风险差异
- 节奏差异

---

## 3. 当前已落地骨架

本轮已补入：

- `ChapterImitationPlan`
- `ChapterImitationDraft`
- `ChapterImitationService`

当前服务能力：

1. 从 branch 状态构建 imitation plan
2. 生成结构化 skeleton draft
3. 给出 comparison notes / risk gate notes

当前边界：

- 还不是自动优质正文生成器
- 先是 planning / skeleton 层
- 为后续第 3 章实验与门控闭环提供脚手架

---

## 4. 第3章实验建议

建议以《第3章 养生功法》做实验：

### 原章核心骨架

1. 求助
2. 受轻视
3. 得到有限资源
4. 自我消化羞辱
5. 转入主动修炼
6. 用金手指确认长期成长路径

### 仿写时必须保持的东西

- 主角不是情绪化爆发，而是克制推进
- 资源获取不是直接白给，而是带有身份落差
- 章尾必须把“长期成长”钉住
- 不可突然引入越级战力或突兀和解

### 仿写时应重点检查的风险

- `character_ooc.character_resolution_support_gap`
- `plot_logic_consistency.resolution_support_gap`
- `relationship_shift_candidate`

---

## 5. 一句话结论

> 真正稳定的章节仿写能力，不是“让模型直接写”，而是 **让模型先学会在约束下规划、在门控下修正、在对比中逼近原章骨架**。

---

## 6. 当前 live 实验入口

建议直接使用：

```bash
novel-analyzer iterate-imitation <branch_id> <source_chapter_index> "<target_goal>" --use-llm --max-rounds 2
```

当前它会输出：

- `rounds[]`
  - `draft`
  - `comparison`
  - `review`
  - `gate`
  - `risk`
  - `score`
- `final_draft`
- `stop_reason`

对应的首个正式实验报告：

- `docs/chapter-imitation-ch3-live-report-20260502.md`

### 当前 stop 条件

第一版 runner 当前会综合：

- 结构对齐
- 质量门控
- sandbox 风险级别
- `overall_score`

来决定是否停止继续迭代。

---

## 7. 多章连续一致性入口（当前骨架）

建议使用：

```bash
novel-analyzer multi-chapter-imitation-consistency <branch_id> \
  "2:延续资源铺垫" \
  "3:延续主角获得功法后的行动线，并保持克制成长节奏" \
  --max-rounds 1
```

当前输出：

- `steps[]`
  - 每章 final draft 摘要
  - 每章 overall_score
  - 每章 overall_risk_level
- `continuity_notes`
- `risk_notes`
- `overall_verdict`

这意味着系统已经开始从“单章仿写器”向“多章连续仿写协调器”过渡。
