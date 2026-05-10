# 拆书加速优化架构说明

## 1. 目标

本轮不是重写拆书系统，而是在现有章节递进式拆书主线上，引入 **Quick / Deep 双档**，同时保住以下不变量：

1. **章节仍是唯一 durable commit 单元**。
2. **Quick 提交后必须能继续推进下一章**。
3. **Deep 只能做 additive enrichment，不能污染 canonical chapter commit**。
4. **回滚 / 分支 / retry / supersede 语义不被破坏**。
5. **速度收益优先来自 orchestration / scheduling，而不是牺牲 facts / evidence / guard 主链**。

---

## 2. 当前瓶颈基线

### 2.1 每章阻塞链过长
当前 `AnalysisService` 的单章主链包含：

- `chapter_intake`
- `fact_extractor`
- `evidence_binder`
- `analysis_generator`
- `writer_learning_lens`
- `anti_fabrication_guard`
- `quality_gate`
- artifact persist
- retrieval / fact / graph / window materialization
- Loom / risk follow-on

其中 `writer_learning_lens` 也在 commit 前阻塞。代码见：
- `novel_analyzer/services/analysis_service.py`

### 2.2 名义有并发参数，实际仍逐章串行
`pipeline_async` 保存了 `concurrency`，但 `_runner_loop()` 仍是：
- 算 `next_chapter`
- 一次只处理一个 chapter
- 完成后再取下一个

因此当前没有真正消费“并发额度”来提升整书吞吐。代码见：
- `novel_analyzer/application/pipeline_async.py`

### 2.3 durable 语义依赖 active canonical artifact
以下行为都以 active chapter artifact 为真相来源：
- `next_chapter_index()`
- checkpoint 提交
- branch fork / supersede / inherited artifacts

代码见：
- `novel_analyzer/services/run_service.py`

这意味着任何“快速档”设计，如果改变了 canonical artifact 的含义，就会直接伤到主线推进与分支语义。

---

## 3. 目标架构：Quick / Deep 双档

## 3.1 Quick = core-committed
Quick 的目标不是 preview，而是：
- 生成一个**可信、可提交、可回滚、可继续推进下一章**的 canonical chapter artifact。

Quick 必须阻塞完成：
- `chapter_intake`
- `fact_extractor`
- `evidence_binder`
- `analysis_generator`
- `anti_fabrication_guard`
- `quality_gate`
- artifact persist
- retrieval / fact / graph / fixed-window materialization

Quick 默认允许延后：
- `writer_learning_lens`
- writer/style/handoff 类 enrichment
- 已经天然 non-blocking 的 Loom / risk 增强观察层

### 为什么 writer 可以延后
`writer_learning_lens` 的价值更偏“写法洞察 / 风格迁移 / handoff 可读性增强”，而不是下一章上下文正确性的必要条件。

### 为什么 facts / evidence / guard 不能延后
因为它们决定：
- canonical artifact 是否可信
- retrieval/fact/graph/window 是否能同步物化
- 下一章 context 是否正确

---

## 3.2 Deep = enrichment-complete
Deep 负责补全：
- `writer_learning_lens`
- writer/style/handoff notes
- 更丰富的交付摘要
- 可选更重的非主链观测增强

Deep **不是第二条主线 commit**，而是对 Quick 的加法增强。

Deep 的写回必须满足：
- 不改 canonical artifact 的基本 durable 语义
- 不污染 next-chapter context
- 不在 branch supersede 后继续写旧数据

---

## 4. Canonical Contract

首轮保持 `ChapterAnalysisOutput` 现有字段名完全不变，避免 API / TS / consumer 破坏。

canonical payload 仍使用既有内容字段：
- `dimensions`
- `chapter_summary`
- `key_entities`
- `key_events`
- `continuity_notes`
- `state_transition_notes`
- `evidence_backed_resolutions`
- `unresolved_threads`
- `writer_learning_notes`
- `unsupported_inferences`
- `ambiguous_points`
- `needs_human_review`
- `quality_gate_notes`
- `hook_score`

### Quick 模式下的 writer 字段
Quick 模式允许：
- `writer_learning_notes = []`

但必须同时在元数据里标明：
- `writer_lens_status = deferred`

重点是：
- **不伪造 placeholder craft notes**
- 不用“看起来完整”的假内容掩盖 deferred 事实

---

## 4.1 Canonical-Readable / Downstream-Driving Contract

本专题新增一个必须显式成立的读契约：

- **canonical-readable**：允许被默认 reader 当成"这一章的当前真相"读取
- **downstream-driving**：允许驱动 retrieval / fact / graph / window / status / export 等衍生层

在当前代码里，`visibility='active'` 远远不够表达这层语义，因为很多 reader 只看 active artifact，就会把它当 canonical。

因此首轮必须把这件事写死：
- Quick canonical artifact = 默认 canonical-readable + downstream-driving
- Deep enrichment companion = 默认 **不是** canonical-readable，也 **不是** downstream-driving

如果后续某部分 enrichment 想进入默认读路径，必须通过 guarded promotion，不能靠“也是 active artifact”自动获得资格。

---

## 5. Readiness / Profile 元数据

首期新增一层附加元数据：
- `payload_json["_deconstruction_profile"]`
- 同步 job events

建议最少字段：
- `profile`: `quick | deep`
- `quick_ready`: `true | false`
- `writer_lens_status`: `deferred | pending | complete | failed_nonblocking`
- `loom_status`: `pending | complete | failed_nonblocking`
- `risk_status`: `pending | complete | failed_nonblocking`
- `canonical_artifact_id`
- `content_hash`
- `idempotency_key`
- `timing`（至少保留 commit 阶段与 enrichment 阶段）

这层元数据是 orchestration truth，不替代 canonical content。

---

## 6. Guard 与 Deferred Writer 的协作约束

当前 `anti_fabrication_guard` 在 writer stage 之后运行，并会接收 `writer_json`。

Quick 模式若延后 writer，必须明确：
- `guard` 仍运行；
- `guard` 接收一个**合法但为空的** `WriterLearningLensOutput()`；
- guard 不能因为 writer deferred 而失效；
- deep backfill 后再补 writer enrichment，不回头改变 canonical facts/evidence judgment。

这保证：
- 事实防幻觉链不被拆断；
- writer deferred 不会演化成“guard 也被跳过”。

---

## 7. Context-Critical Materialization 仍保持 Blocking

以下能力仍是下一章上下文的基础，因此 **不能异步化**：
- retrieval materialization
- fact materialization
- graph materialization
- fixed-window summary materialization

原因：
- `ContextService.previous_summary()` 直接读上一章 active artifact summary
- `fact_context_json()` / graph context / window summary 都依赖已物化内容

因此本轮“加速”的真实来源不是这些步骤后置，而是：
1. 把 writer/style/handoff enrichment 挪出 commit 主链
2. 保持 context-critical materialization blocking
3. 对 post-commit enrichment 做并发调度与独立 telemetry

---

## 8. Enrichment Isolation Rule

这是当前方案最关键的安全边界。

### 规则
**enrichment companion 首期不得作为 active `ChapterArtifact` 出现在默认 reader 路径里。**

否则会污染：
- `previous_summary()`
- fixed-window summary
- status completed counts
- assistant readiness
- export/index/status surfaces

### 首期允许的落点
- canonical payload 的 `_deconstruction_profile` guarded metadata merge
- job events
- 非 active sidecar persistence
- 或默认 reader 不会直接读取到的 companion surface

### 如果复用 artifact 家族表
则所有默认 reader 必须显式过滤：
- `visibility='active'`
- `participates_in_downstream=True`
- `artifact_type='chapter_analysis'`

否则 enrichment companion 即使不是 graph downstream，也可能被 summary/window/status 错读。

---

## 8.1 Fork / Inherited Deferred Completeness 语义

本轮除了定义 stale old-branch writes，还需要明确：**fork 之后 inherited canonical artifact 的 deferred completeness 怎么办**。

规则建议如下：
1. `keep_through` 以内继承到 child 的 canonical artifact，连同 `_deconstruction_profile` 一起继承。
2. 若某章在 source branch 上是 `writer_lens_status=deferred|pending`，child branch 继承后默认标记为 `inherited_pending`（或等价 machine-readable 状态）。
3. source branch 上仍在跑的 deep job 只允许写 source branch；一旦 `active_branch_id` 已切到 child，则 source branch deep job 一律 stale/ignored。
4. child branch 若仍需要补齐 inherited chapter 的 deep completeness，应在 child 上重新调度新的 enrichment job，而不是复用 source branch 的旧 job writeback。
5. 是否自动为 child 重排 inherited pending enrichment，首轮可保持显式策略：
   - 默认不自动补排；
   - 由后续 repair/backfill 命令或调度器显式拉起。

这样可以避免“旧 branch 任务写新 branch 数据”与“继承了 canonical，但没有定义 deferred completeness 所有权”的双重歧义。

---

## 9. Deep Writeback / Stale Guard / Idempotency

Deep/background job 的写回不能只靠“branch 还存在”判断，必须同时检查：

### start-check
任务启动前检查：
- `RunBranch.status == active`
- `AnalysisRun.active_branch_id == branch_id`
- canonical artifact 存在且还是目标 artifact

### pre-write-check
真正写入前再次检查：
- canonical artifact `visibility == active`
- canonical artifact id 未变化
- `content_hash` 仍匹配
- `idempotency_key` 仍匹配

### idempotency key 建议
`branch_id + chapter_index + canonical_artifact_id + profile + chapter_content_hash + enrichment_kind`

### 失败处理
任一检查失败：
- 标记 `stale/ignored`
- 只写 event / metric
- 不写 canonical content
- 不更新 default readable state

---

## 10. 并发模型

本轮明确拒绝“同一 branch 主线章节并行 commit”。

### 为什么不做主线章节并行
因为当前主线依赖：
- 上一章 summary
- 已物化 fact/graph/window context
- active artifact 驱动 next chapter

在没有重写上下文消费与 branch semantics 之前，直接并行 chapter commit 会制造伪加速与真实污染风险。

### 本轮允许的并发范围
- writer/style/handoff enrichment
- Loom / risk / metrics 等 post-commit follow-on
- benchmark / telemetry 统计

因此本轮更准确地说是：
- **主线仍顺序**
- **非主线 enrichment 并发化**

---

## 10.1 Derivative Store 隔离

需要额外强调：enrichment 的风险不只在默认 reader，还在 **chapter-index keyed 衍生表重写**。

当前 repo 中：
- fact materialization 会按 `(branch_id, chapter_index)` 删后重建
- retrieval materialization 会更新该章 document
- graph rebuild 会按 branch 聚合 active downstream artifacts

因此首轮实现必须满足：
- enrichment 不能触发 canonical 的 retrieval/fact/window/materialization 重跑；
- enrichment 若要持久化，只能写 sidecar / metadata / non-default-readable surface；
- 只有 canonical-ready payload 才能驱动 chapter-index keyed derivative stores。

否则即使 enrichment 没有直接污染 summary reader，也可能静默覆盖 retrieval/fact truth。

---

## 10.2 Operator Readiness Truth

首轮必须避免 split-brain readiness。建议定义：
- **authoritative canonical progress**：仍以 canonical artifact + chapter job validated/completed 为主
- **authoritative enrichment progress**：以 `_deconstruction_profile` + job events 为主
- dashboard / status / assistant 若展示"拆书完成度"，必须分开显示：
  - canonical progress
  - deep enrichment completeness

不要把 `validated` 或 active artifact count 直接当成"整章 fully deep-complete"。

如果后续有超过 2 个独立 surface 都需要判断 partial completeness，而不得不重复解析 payload + events，则应触发下一轮设计：抽独立 readiness projection / persistence surface。

---

## 11. Benchmark 模型

### 必须分开测两类时间
1. **canonical commit latency**
   - 这一部分决定主线推进速度
2. **enrichment throughput / backlog latency**
   - 这一部分决定 deep completeness 追平速度

### benchmark 至少包含
- 10 章 baseline vs quick
- 100 章 aspiration benchmark
- per-stage latency
- queue depth
- stale skip count
- retry count
- writer deferred completion rate
- Loom/risk non-blocking completion rate

### 关于“100 章 5 分钟”
这只能是：
- benchmark aspiration
- 不应成为 release blocking gate

否则团队会为了追一个极端数字而破坏 durable correctness。

---

## 12. 推荐架构分层结论

### 第一层：canonical mainline
负责：
- 可提交
- 可回滚
- 可向后推进
- 可供下一章消费

### 第二层：enrichment follow-on
负责：
- writer/style/handoff 可读性增强
- Loom / risk / delivery 增强观察
- benchmark / telemetry / handoff richness

### 第三层：guarded promotion
只允许在满足 stale/idempotency/active checks 后，把部分 enrichment 元数据安全晋升回 canonical metadata；
不允许无检查地回写主内容。

---

## 13. 结论

本轮最重要的不是“多快”，而是把以下边界写死：
- 什么算 canonical quick commit
- 什么只能做 deep enrichment
- enrichment 怎样不污染默认读路径
- stale job 如何永远写不脏数据

如果这四条边界守住了，后续再做更激进的吞吐优化才有意义。
