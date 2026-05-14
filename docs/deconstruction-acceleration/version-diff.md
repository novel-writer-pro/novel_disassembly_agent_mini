# 拆书旧版 vs 新版加速版：差异说明

> 本文档专门回答一个问题：
> **当前这条“拆书加速优化版本”，和之前的拆书版本相比，到底有什么不同？**
>
> 重点不是代码实现细节，而是：
> - 使用差异
> - 能力差异
> - 运行差异
> - 恢复差异
> - 适用场景差异

---

## 1. 一句话区别

### 旧版拆书
更像是：
- 一条单线 staged 拆书主链
- 重点是“先把章节拆出来并产出结构化结果”
- 默认读路径、回退/恢复、风险聚合都能工作，但对“加速主线”和“companion 不污染默认读路径”的约束没有现在这么明确

### 新版加速拆书
更像是：
- 在旧版主链之上，补上**canonical / companion 边界**、**reader isolation**、**blocking materialization 回滚保护**、**运行时基线 benchmark**
- 目标不是完全重写拆书，而是让拆书链路更适合往 **Quick / Deep 双档** 和更长程稳定运行演进

---

## 2. 使用差异

## 2.1 CLI 命令层面
### 旧版
用户主要还是：
- `ingest`
- `start-run`
- `analyze-next`
- `analyze-range`
- `show-run-status`
- `show-chapter`
- `show-context`
- `show-window`
- `search-branch`
- `ask-branch`

### 新版
**命令本身并没有被大改**，但推荐使用方式变了：

#### 新版更推荐
- **显式传 `--database-url`**
- 小步推进（特别是长篇真实跑时）
- 运行中主动看：
  - `show-run-status`
  - `show-context`
  - `show-window`
  - `search-branch`
  - `ask-branch`

#### 新版不建议再默认假设
- 只要 artifact 是 active，就一定会进入默认读路径
- `retry-chapter` 可以对任何章节直接重跑

---

## 2.2 运行方式差异
### 旧版倾向
- 更偏“先能跑起来”
- 对 companion / manual / shadow 类产物进入默认读路径的边界没有当前这么显式

### 新版倾向
- 更偏“先把边界做对，再谈更快”
- 尤其强调：
  - default-readable artifact
  - canonical-only 读口径
  - non-downstream companion 不污染默认行为

---

## 3. 能力差异

## 3.1 默认读路径能力
### 旧版
重点是：
- 章节能拆
- context 能组
- QA / search 能跑

但如果后续增加 companion / manual / shadow 产物，默认 reader 容易混淆“哪一个才是当前真相”。

### 新版
新增/强化了：
- **canonical-readable / downstream-driving 合同**
- 默认 reader 只读 canonical/default-readable artifact
- active 但 `participates_in_downstream=false` 的 companion 不会自动替代 canonical

这直接影响：
- `previous_summary`
- `chapter index`
- `show-run-status`
- `fixed window summary`
- 默认 QA / search / context 消费面

---

## 3.2 物化安全性差异
### 旧版
如果 materialization 在 artifact persist 后失败，可能留下不干净的活跃状态，后续恢复和排障成本更高。

### 新版
新增/强化了：
- **blocking materialization failure rollback**
- 也就是：
  - retrieval / fact / graph / window 仍然 blocking
  - 如果失败，会恢复 previous active artifact
  - 不让半成品 active state 留在主链里

这是这轮非常重要的稳定性增强。

---

## 3.3 元数据能力差异
### 旧版
更偏“有 chapter artifact 就算完成一章”。

### 新版
新增了 `_deconstruction_profile` 这类 shadow metadata 能力，用来为后续 Quick / Deep 双档铺路，例如：
- `profile`
- `quick_ready`
- `writer_lens_status`
- `loom_status`
- `risk_status`
- `canonical_artifact_id`
- `content_hash`
- `idempotency_key`

注意：
- **它是附加 metadata，不是替换旧字段**
- `ChapterAnalysisOutput` 既有 key 不改名

---

## 3.4 稳定性观测能力差异
### 旧版
有基础运行状态，但不够系统地表达：
- canonical progress
- companion 隔离
- benchmark 基线
- 真实长跑中的稳定性问题画像

### 新版
新增/强化了：
- canonical 默认读路径 benchmark baseline
- usage log / development log
- 当前版本用户手册
- 已知问题与恢复建议

所以新版更像一个：
- **可运行**
- **可验证**
- **可说明当前边界**
的版本

---

## 4. 恢复差异

## 4.1 retry 语义差异
### 旧版
`retry-chapter` 更偏“失败就拉起来重跑”。

### 新版
新增保护：
- **如果某章已经有 active canonical artifact，则拒绝 retry**

原因：
- 避免 chapter job 状态和 artifact 进度错位
- 避免“章节明明已经完成，却又被重新拉起来跑”的脏状态

---

## 4.2 stall 行为差异
### 旧版
默认 `chapter_job_stall_timeout_seconds = 180`，对真实外部模型较长阶段调用来说偏紧。

### 新版
当前已经调整为：
- `chapter_job_stall_timeout_seconds = 600`

这不是根治，但能明显降低：
- 长阶段调用被过早误判 stalled

---

## 5. QA / Search / Context 使用差异

### 旧版
这些接口能用，但更多是假定：
- 章节主链结果就是当前唯一真相

### 新版
这些接口不仅继续可用，而且更明确地建立在 canonical 读口径上：
- `ask-branch`
- `search-branch`
- `show-context`
- `show-window`
- `show-chapter`

这意味着：
- 结果更稳定
- 后续引入 companion / deep enrichment 时，不容易把默认消费面搞脏

---

## 6. 适用场景差异

## 6.1 什么时候更适合用旧版思路看待系统
如果你只是：
- 想快速手工拆几章
- 不关心 companion / shadow / metadata 边界
- 不关心长跑稳定性

那你看到的仍然会像“旧版拆书主链”。

## 6.2 什么时候必须用新版思路看待系统
如果你要：
- 跑真实长篇
- 做 QA / search / context / window 消费
- 后续准备引入 Quick / Deep 双档
- 关心不影响仿写默认行为
- 关心长跑稳定性与恢复语义

那你必须按“新版加速拆书”的思路来理解它。

---

## 7. 当前最现实的使用建议

### 如果你只是想安全跑真实拆书
按新版方式：
1. 独立新库
2. 显式 `--database-url`
3. 真实 provider 配置显式传入
4. 小步推进并持续看：
   - `show-run-status`
   - `show-context`
   - `show-window`
   - `search-branch`
   - `ask-branch`

### 如果你想评估新版是否值得继续演进
重点看：
- 长跑能推进到多少章
- 是否还会在 staged 中间阶段 stall
- fallback / retry 能否托底
- QA / search / context / window 是否持续可用

---

## 8. 当前版本的最终差异结论

### 旧版的核心价值
- 先把拆书主链做出来
- 先能拆、能查、能问

### 新版的核心价值
- 在不破坏原能力的前提下，把：
  - canonical / companion 边界
  - default-readable 合同
  - blocking materialization 安全性
  - retry 边界
  - stall timeout
  - benchmark / 使用文档 / 恢复手册
都往“真实可运行、可长期演进”的方向推了一步

所以最准确的一句话是：

> **旧版解决“能拆”；新版开始解决“拆得更稳、更可恢复、更适合后续加速演进”。**

## 8. 当前新版的现实收益与现实上限
### 已确认收益
- 比旧版更稳：真实 DeepSeek 长跑下，已通过 stall timeout / retry guard / canonical 读口径保护，把“容易中途错位或恢复污染”的风险压低。
- 比旧版更可用：status / context / window / search / QA 这一整条消费链当前已能在真实卫图样例上闭环工作。

### 当前上限
- 新版当前不是“极限吞吐版”。
- 卫图前 5 章真实吞吐约为 31 分钟，说明现阶段的主要收益在稳定性、可验证性、QA 可用性，而不是数量级加速。
