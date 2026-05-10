# 拆书加速优化开发文档

## 1. 开发目标

本轮开发目标不是一次性做完“高速拆完全书”的所有能力，而是做出一条可安全演进的主线：

1. Quick commit 可以稳定推进全书拆书进度。
2. Deep enrichment 可以异步补全，不污染 canonical。
3. 默认 reader / context / status / export 不会误读 enrichment。
4. benchmark 能告诉我们速度到底提升了多少、瓶颈还在哪。

---

## 2. 建议开发顺序

## Phase 1 — 先钉死 contract 与 reader isolation
优先做：
1. canonical quick contract
2. canonical-readable / downstream-driving 合同
3. `_deconstruction_profile` 元数据
4. reader isolation rule（summary / window / status / assistant / export / derivative stores）
5. 测试覆盖 `previous_summary` / window / status / readiness

理由：
- 如果不先解决读路径污染，后面加任何 enrichment 都可能把系统搞脏。
- 在 reader isolation 没完成前，任何 enrichment companion 都不能变成 active default-readable artifact，也不能触发 chapter-index keyed rematerialization。

## Phase 2 — 把 writer_learning_lens 挪出主线
优先做：
1. quick 模式不再阻塞 writer lens
2. guard 接收空合法 writer payload
3. deep background writer enrichment
4. writer deferred 状态可观测

理由：
- 这是当前最明确、风险最小的主链减负点。

## Phase 3 — 做 stale / idempotency / supersede 防护
优先做：
1. deep job start check
2. pre-write check
3. stale/ignored event
4. fork/supersede pending deep 验证

理由：
- 异步一旦上线，最容易先出 branch 语义错误。

## Phase 4 — 做 benchmark / telemetry
优先做：
1. per-stage timing
2. canonical vs enrichment 分开统计
3. queue depth / stale count / retry count
4. 10 章 / 100 章 benchmark 报告

理由：
- 没有 telemetry，后续优化就会变成拍脑袋。

---

## 3. 关键代码触点

### 核心主线
- `novel_analyzer/services/analysis_service.py`
  - quick/deep 主流程切分
  - writer stage 后置
  - guard 输入契约
  - materialization blocking boundary

### 异步执行 / 调度
- `novel_analyzer/application/pipeline_async.py`
  - 保持主线 chapter commit 顺序
  - 增加 enrichment follow-on 调度
  - 真实消费 `concurrency` 到 post-commit lane

### durable 与分支语义
- `novel_analyzer/services/run_service.py`
  - canonical artifact persist
  - fork / supersede / active branch
  - stale / idempotency write guards 所依赖的真相面

### 默认 reader / 污染路径
- `novel_analyzer/services/context_service.py`
- `novel_analyzer/services/fact_service.py`
- `novel_analyzer/services/graph_service.py`
- `novel_analyzer/services/status_service.py`
- `novel_analyzer/services/novel_assistant_service.py`

这些文件需要统一校准：“默认读的到底是不是 canonical-ready artifact”。

### 文档 / 对外合同
- `docs/interface-manifest.md`
- `docs/api-current-surface.md`
- `docs/whole-book-imitation-integration-quickstart.md`
- `docs/imitation-next-dev-handoff.md`

---

## 4. 推荐实现约束

### 4.1 不要改 canonical payload 的既有键名
这条是兼容性底线。

能新增：
- `_deconstruction_profile`
- event / telemetry / sidecar state

不要做：
- 把 `unsupported_inferences` 改成别的名字
- 把 `ambiguous_points` / `needs_human_review` 改 contract
- 让 TS / API 消费方必须同步改大量字段

### 4.2 不要把 enrichment 直接保存成 active default artifact
这是当前最容易误伤默认 reader 的点。

只要 enrichment 出现在：
- `visibility='active'`
- 且默认 reader 不做过滤

就有很大概率污染：
- 上一章 summary
- fixed window
- completed count
- readiness

### 4.3 不要让 writer deferred 变成 guard skipped
writer 可以延后，但 facts/evidence/analysis/guard 不能一起塌掉。

### 4.4 不要把 context-critical materialization 误异步化
如果把 retrieval/fact/graph/window 都后置：
- 下一章 context 很可能就会拿不到同步事实面
- 主线 correctness 会退化成“靠运气”

---

## 4.5 Fork / inherited deferred completeness 的实现约束

实现时不要只处理 stale old-branch writes，还要处理 inherited canonical 的 deferred completeness 所有权：
- child 继承 `keep_through` 内 canonical artifact 时，一并继承 `_deconstruction_profile`；
- 若 inherited chapter 仍是 deferred/pending，必须明确它是 `inherited_pending`，而不是无主状态；
- source branch 的 deep jobs 不得继续写 child；
- child 若要补齐 inherited deep completeness，必须重新调度 child-owned enrichment job。

这是 branch safety 的一部分，不是额外锦上添花。

## 4.6 Readiness / telemetry 的权威口径

开发时必须明确：
- active canonical artifact count = canonical progress，不等于 deep-complete
- job validated/completed = 主线提交状态，不等于 enrichment 全完成
- deep completeness 需要单独读 `_deconstruction_profile` + job events

如果一个 dashboard / status / assistant surface 只显示一个"完成"数字，那默认它只表示 canonical progress，不能偷带 deep-complete 含义。

## 5. 推荐测试矩阵

## 5.1 Unit
- `_deconstruction_profile` schema shape
- quick 模式空 writer payload
- idempotency key 生成
- stale check 判定

## 5.2 Integration
- quick commit 后 `next_chapter_index()` 推进
- writer deferred 但 guard 仍成功运行
- fork while deep pending -> stale ignored
- default readers 只读 canonical-ready
- window summary 不读 enrichment companion

## 5.3 Benchmark
- 10 章 baseline vs quick
- 100 章 aspiration
- `concurrency=1` vs `>1` 只对 enrichment lane 做对比

---

## 6. 开发时最容易踩的坑

### 坑 1：以为 `concurrency` 直接开大就能并行章节
不行。当前主线 context consumption 还是顺序语义。

### 坑 2：为了“看起来完整”而补假 writer notes
这会让 deferred 和 complete 混淆，后续排障更难。

### 坑 3：只修 graph rebuild 过滤，不修 summary/window/status 读路径
这会留下最隐蔽的污染路径。

### 坑 4：只在 job 启动时做 stale check，不在写入前再查一次
fork/supersede 正好发生在 job 执行期间时，就会漏掉脏写。

### 坑 5：只测 wall time，不测 commit vs enrichment 分层时间
你会看不到到底是主链快了，还是只是把耗时藏到后台了。

---

## 7. 推荐 rollout 方式

### 第一步：shadow metadata + canonical-readable contract
先落 `_deconstruction_profile`、canonical-readable / downstream-driving 合同，以及不改变默认可读行为的 shadow metadata。

### 第二步：reader isolation / derivative-store isolation 全量收口
在任何真实 deep writeback 或 writer deferred 生效之前，先统一修：
- summary 读路径
- fixed window 读路径
- status / readiness 计数口径
- assistant / export 默认读路径
- chapter-index keyed derivative store 的 canonical-only 驱动约束

**硬门槛：在这一步完成前，enrichment companion 不得变成 active default-readable artifact，也不得触发 chapter-index keyed rematerialization。**

### 第三步：writer deferred 真正生效
在 reader / derivative-store isolation 已完成后，再把 writer 挪到 deep lane，同时保留同步 materialization 与空合法 writer payload guard 合同。

### 第四步：stale / fork / inherited pending 收口
把 branch supersede、inherited pending、deep stale/ignored 行为做完整回归验证。

### 第五步：benchmark / regression 常态化
有了稳定隔离与 branch safety 后，再持续测：
- canonical commit latency
- enrichment throughput
- backlog age / stale ratio
- 10 章与 100 章 benchmark

之后再讨论是否需要下一轮更激进优化。

---

## 8. 什么时候说明方案还不够

如果出现以下任一情况，说明当前方案还需要再开一轮设计：
- 想并行多个 chapter commit
- 想把 retrieval/fact/graph/window 也一起异步化
- 想把 enrichment 直接当 active chapter artifact 使用
- 想引入新的队列/调度依赖
- 想把 Quick 再进一步压缩到 facts/evidence/guard 之外

这些都已经越过了本轮“增量优化”的边界。
