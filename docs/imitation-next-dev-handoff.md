# Imitation Next Dev Handoff / 仿写下一步开发对接

## 当前已完成

### 主链
- imitation harness
- constraint pack
- reader-sim / rhythm / style / dialogue / research lanes
- steering pack
- writer-facing CLI
- batch innovation experiment

### 创新层
- worldview / trope / audience 文档库格式
- 本地样例库
- 本地 steering 装配器
- 最小 retrieval hit reasons
- innovation/risk delta summary

---

## 当前最重要的文档入口

- `docs/architecture/chapter-imitation-harness-architecture.md`
- `docs/writer-imitation-workflow.md`
- `docs/imitation-innovation-and-steering.md`
- `docs/trope-worldview-rag-library-format.md`
- `docs/batch-innovation-experiment-workflow.md`
- `docs/imitation-control-plane-glossary.md`

## 最新推进补充（2026-05-09）

- `writer-imitate-session-state.json` 已升级到 `writer-imitate-session-state.v3`
- 新增 6 个聚合注册表：
  - `session_control_loop`
  - `session_queue_registry`
  - `session_execution_registry`
  - `session_governance_registry`
  - `session_digest_registry`
  - `session_live_ops_board`
- 新增 3 个更偏执行面的 action-loop 入口：
  - `session_action_backlog`
  - `session_transition_queue`
  - `session_checkpoint_mutations`
- `writer-imitate-index` 现已同时产出：
  - `writer-imitate-action-queue.json`
  - `writer-imitate-action-queue.md`
  - `writer-imitate-execution-state.json`
  - `writer-imitate-execution-state.md`
  - `writer-imitate-execution-replay.json`
  - `writer-imitate-execution-replay.md`
- 新增显式命令面：
  - `writer-imitate-apply-replay`
  - `writer-imitate-resume-replay`
- `writer-imitate-index.md` 已新增 `Operator-Facing Stable Contract` 小节，开始把 operator 第一层字段从全量 session 面中单独收口
- 这一步的目的不是继续堆 taxonomy，而是把已有 session 字段压缩成更像真实商业 Agent 控制层可消费的编排注册表
- 下一步优先方向应转向：
  1. action execution
  2. checkpoint persistence / mutation
  3. queue 状态回写与恢复
  4. external metric / feedback backflow

---

## 下一步最推荐开发顺序

### P1
1. 扩 trope/worldview/audience 样例库
2. 增强本地检索规则（tag / label / query）
3. 把命中文档摘要直接落进 experiment 输出

### P2
4. 做 baseline vs steering 对照报告
5. 做 innovation delta / risk delta 可视化摘要
6. 补 reader-sim 对创新接受度评估

### P3
7. 升级成真正轻量 RAG surface
8. 给 writer-facing output 增加更明确的“本轮创新说明”

---

## 当前建议暂停点

当前建议先停在这里，等待：
- 真实读者反馈
- 人工评审反馈
- 实验批次结果

再决定：
- 哪些 trope/worldview 真的值得扩库
- 哪些创新导向在商业上更有效

---

## 一句话

> 当前仿写链已经从“保守贴原章”升级成“可控 steering + 可实验 + 可解释”的状态，下一阶段重点不是再堆功能，而是把这套创新控制面做得更稳、更准、更可复盘。
