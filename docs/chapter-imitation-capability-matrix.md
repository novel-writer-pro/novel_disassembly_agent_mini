# 仿写 / 续写全能力矩阵 v1

> 目标：把“仿写/续写到底要具备哪些能力、当前做到哪、下一步先做什么”整理成统一矩阵，方便后续持续建设。

---

## 1. 总览结论

当前系统已经较强覆盖：

- 风控审查
- 章节规划
- 知识提炼
- harness 控制
- whole-book policy surface

当前系统仍待强化：

- 文风修辞
- 节奏分析
- 对话设计
- 资料研究
- 读者模拟评审

---

## 2. 全能力矩阵

| 能力类 | 子能力 | 当前覆盖度 | 当前状态 | 后续优先级 |
|---|---|---:|---|---:|
| 风控审查 | 人物 OOC / 规则 / 关系 / 逻辑 | 高 | 已有 risk audit + preflight + harness routing | P0 |
| 知识提炼 | facts / state / graph / unresolved threads | 高 | 已稳定进入 skill outputs | P0 |
| 章节规划 | chapter plan / scene beats / hook | 高 | 已有 next chapter planner + imitation plan | P0 |
| whole-book 编排 | carry-over / strategy_input / dashboard | 中高 | 已进入 sandbox orchestration | P1 |
| 节奏分析 | 起伏 / 高潮 / 节奏偏差 | 中低 | 有 scene/hook 基础，但无独立 analyzer | P1 |
| 对话设计 | 角色说话风格 / 台词效率 / 冲突对话 | 低 | 仅有 dialogue candidate 级基础 | P1 |
| 文风修辞 | prose polish / style calibration | 低 | 只有 style axes 和轻量 polish | P1 |
| 多线叙事 | 多线优先级 / 支线平衡 / 线索切换 | 中低 | 有 unresolved threads，但缺调度器 | P1 |
| 逐章场景优化 | 场景推进与结构修复 | 中高 | harness/action queue 已可控制 | P0 |
| 故事架构 | chapter-level / book-level structure | 中高 | 章级较强，书级正在增强 | P1 |
| 资料研究 | 世界观 / 历史 / 题材 / 读者体系 | 低 | 目前主要是书内知识，不是真 research lane | P1 |
| 模拟读者评审 | 小白读者 / 老书虫 / 爽点读者 / 编辑视角 | 低 | 目前只有 system review，不是 reader simulation | P1 |

---

## 3. 当前已较强利用的能力

## 3.1 风控审查

当前最成熟：

- risk audit
- preflight
- gate / risk / score
- severity / priority
- action_queue
- policy_summary
- strategy_input
- dashboard_summary

也就是：

> 已不是“写完再看”，而是“写前约束 + 写中控制 + 写后门控”。

---

## 3.2 知识提炼

当前已有：

- chapter-intake
- chapter-fact-extractor
- evidence-binder
- chapter-analysis-generator
- graph / state / retrieval
- local structured skill outputs

这意味着：

> 知识不是缺失，而是后续要进一步放大其控制价值。

---

## 3.3 章节规划 / 场景优化

当前已有：

- next chapter planner
- chapter imitation plan
- scene beats
- harness revise
- action queue
- revise payload

所以这块已经从“规划提议”进入“受控优化”。

---

## 4. 当前还没充分利用的能力

## 4.1 文风修辞

当前只有：

- style axes
- 简单 polish

缺：

- style calibrator
- prose quality scorer
- sentence tension optimizer
- 修辞级 rewrite lane

---

## 4.2 节奏分析

当前有：

- scene beats
- hook_score
- ending hook precheck

但缺：

- 节奏类型模型
- 爽点密度模型
- 高潮点检测
- 节奏修复器

---

## 4.3 对话设计

当前几乎没有独立能力，只能抽一些 dialogue candidates。

后续需要：

- 角色说话风格控制
- 对话信息效率检查
- 冲突对话设计
- 对话驱动 scene repair

---

## 4.4 资料研究

当前更多是书内提炼，不是外部 research。

后续需要：

- research pack
- setting dossier
- audience expectation pack
- 历史/题材/世界观资料支撑

---

## 4.5 模拟读者评审

当前更像：

- gate
- risk
- review
- harness self-check

缺：

- 小白读者视角
- 老书虫视角
- 爽文读者视角
- 严苛编辑视角

---

## 5. 推荐的最终总架构

## A. 约束与知识层

- facts
- state summary
- graph / unresolved threads
- world rules
- relationship state
- research pack
- audience expectation pack

## B. 生成与规划层

- chapter planner
- scene optimizer
- multi-line planner
- dialogue designer
- style polisher

## C. 控制与评估层

- harness
- preflight
- risk audit
- reader simulation
- dashboard summary

---

## 6. 下一批最值得做的能力

### 第一批（最值钱）
1. 节奏分析器
2. 对话设计器
3. reader simulation reviewer
4. research pack

### 第二批（提升质量上限）
5. style polisher
6. multi-line planner
7. book architecture optimizer

### 第三批（高级增强）
8. audience-specific reader panels
9. world/history external research integration
10. long-book adaptive orchestration

---

## 7. 与当前 harness 架构的映射

| 新能力 | 最适合接入层 |
|---|---|
| 节奏分析器 | preflight + policy summary |
| 对话设计器 | draft-writer / draft-reviser / scene optimizer |
| 读者模拟评审 | reader-sim review lane + dashboard |
| research pack | constraint layer |
| style polisher | draft-reviser / style-calibrator |
| multi-line planner | whole-book orchestration |

---

## 8. 一句话结论

当前系统不是“没考虑这些能力”，而是：

> **已经把风控、规划、知识提炼、控制编排做成主链；文风、修辞、节奏、研究、读者模拟这几类能力还没有被充分拉起来。**

因此后续最合理的路线不是推倒重来，而是：

> **沿当前 harness / skill / policy 架构，按能力矩阵逐批补强。**
