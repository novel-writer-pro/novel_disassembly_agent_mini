# 风险审查体系：下一批 Checker 技术设计

## 1. 目的

这份文档专门回答一个问题：

> 在当前统一风险审查体系已经有 `character / world_rule / plot / timeline / power` 五条主线后，下一批 checker 应该怎么扩，但仍然保持“小而精、风险提示优先”的边界？

它不是 UI 方案，也不是 reader-facing 能力文档，而是：

- 面向后端/系统设计者
- 面向后续 checker 实施者
- 面向 review workflow 维护者

---

## 2. 扩展边界

下一批 checker 继续沿用当前统一体系，不单独开新系统。

必须继续满足：

1. **默认只做风险提示**
2. **不自动改文**
3. **不做全书最终裁决**
4. **不做纯风格好坏判断**
5. **结论必须能回到证据**

因此下一批 checker 的目标不是“更会点评”，而是：

> 把更多“可复核的设定/连续性风险”纳入同一套 `risk card -> cluster -> review workflow` 交付链。

---

## 3. 统一接入方式

下一批 checker 仍然走现有统一 contract：

- 输入：
  - chapter artifact
  - branch / cross-chapter context
  - 结构化 signals
- 输出：
  - `GateRiskItem`
  - `CheckerResult`
  - `ChapterRiskCard`
  - `review_candidate_clusters`

也就是说：

- **checker 独立判断**
- **聚合层统一消费**
- **review workflow 统一承接**

不建议为新 checker 另起一套独立报告、独立状态机或独立 UI 协议。

---

## 4. 下一批最值得做的 4 类 checker

## A. `relationship_consistency`

### 主要回答

- 人物关系口径是否突然跳变
- 敌我/亲疏/信任关系是否缺乏前文支撑
- 关系缓和或恶化是否存在过快跃迁

### 建议风险类型

- `relationship_shift_without_bridge`
- `trust_state_conflict`
- `hostility_resolution_too_fast`
- `relationship_review_candidate`

### 需要的核心信号

- `stable_relations`
- `evolved_relations`
- 人物共现事件
- 带关系语义的状态变更 note
- 关键冲突与和解事件

### 适合的输出语义

- 重点给出“前态 -> 当前态 -> 缺失桥段”
- 必须附带涉及人物和相关章节

### 不建议做

- 不根据一句暧昧台词就下强关系结论
- 不做 CP / 情感倾向主观评价

---

## B. `foreshadow_payoff_consistency`

### 主要回答

- 前文埋设的线索是否被异常遗忘
- 当前章突然兑现的重要结果是否缺少前置铺垫
- 已被明确解决的线索是否又被当作未解问题重复出现

### 建议风险类型

- `payoff_without_setup`
- `resolved_thread_reopened_without_reason`
- `important_thread_long_unmentioned`
- `foreshadow_review_candidate`

### 需要的核心信号

- `new_foreshadowing`
- `paid_off_foreshadowing`
- `unresolved_threads`
- `evidence_backed_resolutions`
- branch 级 thread 生命周期

### 适合的输出语义

- 重点给出“线索首次出现章 / 最近出现章 / 当前兑现或重开章”
- 反证必须明确：是否可能只是作者有意延后

### 不建议做

- 不把“尚未回收”自动判成问题
- 不做“读者是否满意伏笔回收”的主观评分

---

## C. `setting_scope_consistency`

### 主要回答

- 设定的作用域是否突然失控
- 某类资源/限制/权限是否无解释扩张
- 地图、组织、系统、道具的边界是否被随意突破

### 建议风险类型

- `constraint_scope_expansion`
- `resource_limit_missing`
- `authority_boundary_conflict`
- `setting_scope_review_candidate`

### 需要的核心信号

- `observed_world_rules`
- `constraining_world_rules`
- 资源/权限/范围类 state notes
- 组织、地点、系统、道具的约束事实

### 与 `world_rule_consistency` 的区别

- `world_rule_consistency` 更偏“规则是否被打脸”
- `setting_scope_consistency` 更偏“规则虽然没被直接打脸，但适用范围被悄悄放大/缩小”

### 不建议做

- 不把所有地图新增、组织新增都视为风险
- 只在“既有边界已被明确描述”时给出候选

---

## D. `thread_closure_consistency`

### 主要回答

- 当前章节推进后，关键冲突线是否出现异常断头
- 某条主线程是否被新事件强行覆盖但没有交代
- 结尾或阶段性收束是否存在明显收束不稳迹象

### 建议风险类型

- `thread_dropped_after_escalation`
- `closure_without_resolution_basis`
- `ending_stability_candidate`
- `thread_closure_review_candidate`

### 需要的核心信号

- `new_conflicts`
- `escalated_conflicts`
- `unresolved_threads`
- `evidence_backed_resolutions`
- plot phase-2 的 thread state signals

### 适合的输出语义

- 这类 checker 只能输出“收束稳定性风险候选”
- 适合服务“结尾崩坏风险预警”，但不直接输出“这本书结尾崩了”

### 不建议做

- 不做全书口碑式评价
- 不做“高潮够不够爽”的主观判断

---

## 5. 推荐实现顺序

在当前阶段，推荐顺序不是按“听起来酷”，而是按“最容易复用现有 signals”：

1. `relationship_consistency`
2. `foreshadow_payoff_consistency`
3. `setting_scope_consistency`
4. `thread_closure_consistency`

原因：

- `relationship` 最容易复用当前 `state_summary` 与人物事件
- `foreshadow/payoff` 最容易复用当前 thread / resolution 资产
- `setting_scope` 需要更强规则边界提取
- `thread_closure` 最后做，因为它最容易滑向“主观评价”

---

## 6. 与现有五大 checker 的关系

这些新 checker 不应取代现有 checker，而是补位：

- `character_ooc`
  - 关注人物是否 OOC
- `world_rule_consistency`
  - 关注规则是否被打脸
- `plot_logic_consistency`
  - 关注因果链是否断裂
- `timeline_consistency`
  - 关注时间顺序/恢复窗口
- `power_scaling_consistency`
  - 关注能力跃迁/代价约束

下一批 checker 则主要补足：

- **关系**
- **伏笔兑现**
- **设定作用域**
- **线程收束稳定性**

---

## 7. 对聚合层的要求

下一批 checker 接入后，聚合层建议继续保持统一，而不是按 checker 特化 UI：

### 风险卡层

- `risk_domain`
- `risk_type`
- `severity`
- `confidence`
- `supporting_evidence`
- `counter_evidence`

### 问题簇层

- cluster title
- suggested review action
- review priority
- queue priority
- phase focus（如有）

### 审查结论层

- 仍输出“建议复核什么”
- 不输出“作品最终质量定级”

---

## 8. 何时算“可以立项实现”

一个下一批 checker 建议同时满足以下条件再开始编码：

1. 已能列出 3–5 个明确风险类型
2. 已明确至少 3 类可复用 signals
3. 已明确至少 2 条反误报规则
4. 已明确它进入 cluster 后的 review 动作

如果这些条件还不清晰，就先停留在路线图层，不急着实现。

---

## 9. 一句话总结

> 下一批 checker 仍然应该是“多个独立检查器 + 聚合层”的统一体系；最值得优先落地的是关系、伏笔兑现、设定作用域、线程收束稳定性四类，而且都必须坚持 evidence-first、advisory-only 的系统边界。
