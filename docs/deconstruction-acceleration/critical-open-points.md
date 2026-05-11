# 拆书加速优化：仍需重点盯防的关键点

## 1. 已经被这轮方案显式覆盖的关键点

### 1.1 canonical / enrichment 边界
已明确：
- Quick 是 canonical commit
- Deep 是 additive enrichment
- 不允许 deep 替换 canonical durable 语义

### 1.2 writer deferred 的诚实表示
已明确：
- 可以 deferred
- 不能伪造 placeholder notes
- guard 仍要跑

### 1.3 stale background writes
已明确：
- start check
- pre-write check
- stale/ignored only

### 1.4 默认 reader 污染风险
已明确：
- enrichment 不能作为 active default artifact 被读到
- 需要统一修 summary/window/status/readiness/export 读路径

---

## 1.5 canonical-readable 是否已经被当成一等合同
已明确方向，但实现时最容易被弱化成"存储约定"而不是"读契约"。

必须持续确认：
- active artifact 不等于 canonical-readable
- 只有显式满足默认读条件的 canonical artifact 才能驱动 downstream
- enrichment sidecar 不能因为"也落库了"就天然进入默认读路径

---

## 2. 当前仍值得继续追问的关键点

## 2.0 inherited deferred completeness 是否要自动迁移
这是 fork 之后最容易被忽略的关键点。

当前仍需在实现时最终拍板：
- inherited chapter 的 deferred completeness 是自动补排，还是显式 repair/backfill 才补；
- dashboard 要不要显示 `inherited_pending`；
- child branch 的 deep completeness SLA 是否与 source branch 脱钩。

### 当前判断
- 这不是阻止首轮启动的 blocker；
- 但它是 branch safety 的一级后续观察点，不能在实现时临场拍脑袋。

---

## 2.1 fixed-window summary 的语义是否足够稳定
本轮假设：
- fixed-window 仍只基于 canonical-ready artifact

但后续可能会遇到问题：
- 如果 writer/handoff enrichment 对“窗口交付可读性”很重要，那么只用 canonical 生成 window，窗口摘要可能会偏“能用但不够丰富”。

这不是阻塞问题，但可能会影响：
- 人工交付体验
- 后续 handoff 文档质量

### 当前判断
- **不是本轮阻塞项**
- 适合在 quick/deep 稳定后单独评估是否给 window 增加 deep-aware 展示层，而不是改 canonical 生成逻辑

---

## 2.2 Loom / risk 哪些部分可以更晚再异步化
本轮只把 Loom / risk 当成既有 non-blocking follow-on 继续保留，但没有细拆：
- 哪些 risk signals 其实对 next-step orchestration 有即时价值
- 哪些 Loom 产物只是观察层，不需要与 canonical commit 同步紧耦合

### 当前判断
- **需要后续细化，但不是首轮 blocker**
- 建议等 benchmark 有数据后，再判断 Loom/risk 的哪部分值得更重并发优化

---

## 2.3 benchmark 是否会出现“主线快了，但 deep backlog 越积越多”
这是最现实的二阶问题。

如果：
- Quick commit 变快了
- 但 deep writer/style/handoff backlog 无法追平

系统会出现：
- 主线吞吐高
- 交付 completeness 长期滞后

### 当前判断
- 这是 **必须监控但不阻止首轮落地** 的点
- benchmark 里必须额外看：
  - deferred completion rate
  - backlog age
  - stale ratio
  - average catch-up latency

---

## 2.3.1 canonical progress 与 deep completeness 双口径是否会让看板混乱
如果 operator surface、status、assistant 都只展示一个"完成度"，就很容易把 canonical progress 与 deep completeness 混在一起。

### 当前判断
- 首轮必须接受双口径：
  - canonical progress
  - deep completeness
- 如果后续多处 surface 都需要解释 partial completeness，应该尽快抽独立 readiness projection，而不是继续让每个消费者各自解析 payload + events。

---

## 2.4 readiness 元数据是否最终需要独立 persistence surface
本轮为了低风险，先放到：
- `payload_json["_deconstruction_profile"]`
- job events

这很适合首轮落地，但长期可能会遇到：
- reader 逻辑越来越复杂
- status / dashboard / export 多处重复解析 payload
- benchmark 查询不够高效

### 当前判断
- **首轮先不扩表是对的**
- 但如果第二轮继续加状态机复杂度，可能需要独立 surface

---

## 2.5 “同一 branch 主线章节并行”未来是否永远不做
本轮明确不做，是对的。

但需要意识到：
- 如果未来真的要冲击非常激进的整书吞吐指标
- 最终几乎一定会碰到“主线是否可分层并发”的问题

这会牵动：
- context assembly
- checkpoint 语义
- branch inheritance
- consistency model

### 当前判断
- **本轮不做完全正确**
- 但它是未来真正大吞吐优化绕不过去的议题
- 一旦要做，必须新开架构专题，不应在本方案里顺手扩张

---

## 3. 本轮最容易漏掉但必须加到开发 checklist 的点

1. **所有默认 reader 都要逐个点名检查**，不能只看 graph rebuild。
2. **writer deferred 不是 writer skipped**，guard contract 必须稳定。
3. **benchmark 要拆 commit latency 与 enrichment latency**，不能只看总 wall time。
4. **status/readiness/export 的计数口径必须重新确认**，不然看板会虚高。
5. **deep job stale 判定要做双重检查**，不能只在任务启动时查一次。

---

## 4. 当前结论

如果问“当前还有没有没考虑到的关键点”，答案是：

### 已被本轮主方案纳入、不能再漏的关键点
- canonical / enrichment 边界
- writer deferred 的 guard 合同
- context-critical materialization blocking
- enrichment isolation
- stale / idempotency / supersede write guard
- status/export/readiness 口径校准

### 仍值得后续继续观察、但不阻塞首轮文档与开发启动的点
- window/handoff rich summary 是否需要 deep-aware 展示层
- Loom/risk 的更细粒度异步边界
- deep backlog 长期追平能力
- readiness 元数据是否未来需要独立 surface
- 更激进的主线并发是否值得单开新专题

因此当前判断是：
- **没有遗漏掉会阻止本轮启动的一级关键点**；
- 但有若干二级关键点，应该在实现和 benchmark 过程中持续观察，而不是现在就扩大范围。
