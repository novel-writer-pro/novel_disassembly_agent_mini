# 章节仿写能力：方法、步骤与实验闭环

## 1. 定位

这里的“仿写”不应理解为无约束模仿文风直接代写，而应理解为：

1. 先抽取原章的结构与推进方式
2. 再在既有世界观/人物状态/剧情进度下生成结构草案
3. 再对草案做风险检查
4. 最后才考虑扩写为正文

因此推荐流程是：

> **原章拆解 → 仿写计划 → 结构草案 → 风险检查 → 对比优化 → 扩写**

补充：

后续正式生产架构不建议只依赖“单次生成 + 审查回退”，而建议升级为：

> **约束输入层 + skills 生产链 + harness agent 控制层 + risk audit 门控层**

对应的详细架构文档见：

- `docs/architecture/chapter-imitation-harness-architecture.md`
- `docs/chapter-imitation-capability-matrix.md`

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

---

## 8. 整本仿写 orchestration 入口（当前骨架）

建议使用：

```bash
novel-analyzer plan-whole-book-imitation <branch_id> \
  "测试项目" \
  "示例小说" \
  "新世界版示例小说" \
  "2:延续资源铺垫" \
  "3:延续主角获得功法后的行动线" \
  --world-map "郑国=星际联邦" \
  --character-map "卫图=魏拓"
```

当前输出会明确给出：

- `mapping_pack`
- `source_chapter_range`
- `chapter_goals`
- `continuity_focus`
- `orchestration_notes`

这使得“整本仿写”的上层规划已经有了清晰输入输出。

---

## 9. 整本 dry-run 执行队列入口（当前骨架）

建议使用：

```bash
novel-analyzer run-whole-book-imitation <branch_id> \
  "测试项目" \
  "示例小说" \
  "新世界版示例小说" \
  "2:延续资源铺垫" \
  "3:延续主角获得功法后的行动线" \
  --world-map "郑国=星际联邦" \
  --character-map "卫图=魏拓"
```

当前输出会明确给出：

- `queue`
  - `order`
  - `source_chapter_index`
  - `target_goal`
  - `prerequisites`
  - `carry_over_inputs`
  - `expected_outputs`
  - `risk_focus`
- `carry_over_notes`
- `run_notes`

因此现在已经能把整本仿写从“概念计划”推进到“章节执行队列骨架”。

---

## 10. 整本 sandbox execute（当前最终推荐入口）

建议使用：

```bash
novel-analyzer run-whole-book-imitation <branch_id> \
  "测试项目" \
  "示例小说" \
  "新世界版示例小说" \
  "2:延续资源铺垫" \
  "3:延续主角获得功法后的行动线" \
  --world-map "郑国=星际联邦" \
  --character-map "卫图=魏拓" \
  --execute \
  --max-rounds 1 \
  --use-llm
```

当前输出会明确给出：

- `execution_mode = "sandbox_execute"`
- `queue`
- `executed_steps`
  - `overall_score`
  - `overall_risk_level`
  - `draft_excerpt`
  - `carry_over_state`
- `final_carry_over_state`

这意味着系统现在已经不仅能：

> 规划整本仿写怎么跑

还可以：

> 在 sandbox 中逐章执行 imitation iteration，并显式把上一章生成出的摘要 / 关系状态 / 未解线程 / 规则约束传给下一章

当前边界仍然明确：

- 仍不会把生成正文写入 live branch artifact
- 当前 carry-over 仍然是 sandbox report state，不是正式生产内容发布
- 更适合作为“整本仿写实验链 / 评估链 / agentOS 编排链”的稳定中间层

---

## 11. 推荐输入 / 输出结构

如果未来要把它复用到“全文仿写 / 换皮改写 / agentOS 工作流”，建议把输入拆成四层：

### 输入层

1. source anchor
   - source chapter index / range
   - source chapter title / excerpt / skeleton
2. target transformation
   - target goal
   - world mapping
   - character mapping
   - faction / power mapping
3. continuity memory
   - previous generated summary
   - previous relationship state
   - previous unresolved threads
   - previous rule state
4. gate constraints
   - risk focus
   - forbidden transformations
   - rule overrides

### 输出层

1. `plan`
2. `draft`
3. `comparison / review / gate / risk`
4. `carry_over_state`

这样后续不管接：

- openFang / openClaw 这类 agentOS
- 批处理 orchestrator
- 后续全文仿写 runner

都可以复用同一套可解释、可检查、可门控的 contract。

---

## 12. 当前已实现的 harness / preflight 入口

本轮已补入第一版受控仿写入口：

```bash
novel-analyzer show-imitation-skill-contracts
novel-analyzer preflight-imitation <branch_id> <source_chapter_index> "<target_goal>"
novel-analyzer harness-imitation <branch_id> <source_chapter_index> "<target_goal>" --max-rounds 2
```

当前含义：

- `show-imitation-skill-contracts`
  - 输出本地 `skills_dir` 下仿写 harness 依赖的 skill contract
- `preflight-imitation`
  - 在正式 gate/risk 前执行 deterministic preflight
- `harness-imitation`
  - 运行第一版 harness controller
  - 输出 `skill_contracts / rounds / final_preflight / final_verdict / stop_reason`
  - 当前 round 内已开始暴露 `skill_prompt_previews`，用于观察 harness 实际消费的本地 prompt assets
  - 当前 round 也开始暴露 `skill_outputs`，用于证明 harness 已开始消费结构化本地 skill 输出，而不只是 prompt 预览
  - 当前 preflight / action routing 已开始消费这些 `skill_outputs`，例如 constraint repair / continuity memory repair
  - 当前还新增了人物动机 / 关系变化 / 世界规则 / 章尾 hook 方向的 repair routing
  - 当前也开始纳入 `chapter-intake / chapter-fact-extractor` 的结构化 outputs，用于关系证据 / 规则证据方向的 repair routing
  - 当前还新增了 typed `severity / priority`，并开始让 gate/risk meta 信号进入 preflight
  - 当前 `severity / priority` 还开始影响 action 排序与 stop policy 聚合决策
  - 当前 report 还新增 `action_queue / policy_summary`，用于直接观察 controller 的聚合决策面
  - 当前 ordered `action_queue` 也开始写回 revise 输入痕迹，whole-book sandbox report 也开始聚合 chapter harness 的 policy summary
  - 当前 whole-book policy summary 也开始补充最小/最大分数、最大 action 数等聚合统计
  - 当前 round 还新增 `revise_payload`，用于观察 ordered actions 如何结构化进入 revise 输入
  - 当前 whole-book report 也开始显式暴露 chapter-level `revise_payload`、`chapter_ranking`、`severity_histogram`
  - 当前 whole-book 层也开始尝试消费上一章 `revise_payload` 影响后续章节目标，并补充 `book_priority_ranking / risk_bucket_histogram`
  - 当前 whole-book 层进一步新增 `strategy_input / dashboard_summary`，用于结构化表达跨章节策略反馈与总览面板
  - 当前 `strategy_input` 已开始进入 chapter structured constraint 层，dashboard 也新增 `issue_family_histogram / cluster_buckets`
  - 当前还进一步把 rhythm / reader 两类弱能力接入 harness structured outputs，并新增 `issue_family_ranking`
  - 当前 dialogue / research 两类弱能力也已经开始进入 harness preflight / routing，并在 dashboard taxonomy 中占位
  - 当前 strategy_input 还开始携带 `prioritized_families`，并进一步注入 chapter constraint/self-check 层
  - 当前 prioritized family 还会进一步影响 rhythm / reader / dialogue / research 四类弱能力输出的重点修复方向
  - 当前 whole-book dashboard 还新增 `weak_lane_priority_ranking`，用于观察弱能力族群在整书中的优先级分布
  - 当前 whole-book dashboard 还新增 `weak_lane_histogram`，用于观察四类弱能力的整体分布
  - 当前 whole-book dashboard 还新增 `weak_lane_top_actions`，用于观察弱能力在整书里最靠前的修复动作
  - 当前 whole-book dashboard 还新增 `top_priority_summary / top_risk_summary`，用于把弱能力信号直接并入整书级优先级与风险汇总
  - 当前 whole-book dashboard 还新增 `weak_lane_dominance / chapter_flags`，用于观察弱能力主导面与逐章旗标
  - 当前 top-priority / top-risk summary 还继续补入 `top_priority_families / high_risk_families`
  - 当前 top-priority / top-risk summary 也开始直接暴露 `weak_lane_action_count / weak_lane_families`
  - 当前 weak lane 的 preflight priority 也开始进一步影响 action 排序，并新增 `top_weak_lane_chapters`

这意味着系统已经从：

> 只有 imitation service

推进到了：

> imitation service + harness controller + preflight + local skill contracts
