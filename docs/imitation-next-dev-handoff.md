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
- `docs/architecture/imitation-commercial-agent-control-plane-architecture-20260509.md`
- `docs/architecture/imitation-commercial-agent-ops-closed-loop-20260509.md`
- `docs/architecture/imitation-control-plane-implementation-status-map-20260509.md`
- `docs/architecture/imitation-control-plane-field-artifact-console-map-20260509.md`
- `docs/architecture/imitation-legacy-retirement-roadmap-20260509.md`
- `docs/architecture/imitation-live-mutation-bridge-roadmap-20260509.md`

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
- `writer-imitate-operator-surface.json/.md` 已新增，作为独立默认入口承载 `session_operator_contract`
- 该默认入口现已开始额外承载 `session_primary_verdicts` / `session_primary_digests`，作为 P1 字段家族收敛的低风险切口
- 这些 primary verdict/digest 收口层也已开始向 action/execution/replay/apply/resume 产物同步扩散
- 现已新增 `session_primary_contract_hints`，把 primary 层与 legacy compatibility layer 的关系机读显式化
- 现已进一步新增 `session_legacy_contract_layer`，把 legacy verdict/digest 家族正式对象化
- 现已额外产出 `writer-imitate-legacy-contract-surface.json/.md`，把 compatibility layer 从 hints 提升成独立入口产物
- 主控制链产物现也开始统一暴露 `legacy_operator_entrypoint`，使 legacy surface 成为显式可发现的次级入口
- index 与 session-state 也已开始显式暴露 `session_control_surface_entrypoints`，把双入口治理提升到总入口层
- 顶层入口层现已新增 `display_policy=primary-first-legacy-secondary`，把显示优先级也机读固化下来
- 顶层入口层现也开始显式暴露 `legacy_retirement_preview`，让 retirement 试探预演面从 root 层可发现
- 顶层入口层现也开始显式暴露 `live_control_state`，让 live mutation bridge state 从 root 层可发现
- `operator-surface` 与 `legacy-contract-surface` 现也开始显式承载 `session_legacy_retirement_readiness`
- 现已进一步新增 `session_legacy_retirement_plan`，把 pilot candidates / second wave / retirement order 结构化下来
- 现已进一步新增 `session_legacy_retirement_pilot_wave`，把 first-wave 试探切片单独对象化
- 现已额外产出 `writer-imitate-legacy-retirement-preview.json/.md`，为第一次最小 retirement patch 提供独立预演面
- 现已新增 `writer-imitate-live-control-state.json/.md`，作为 apply preview 向未来 live mutation 过渡的独立状态面
- markdown 第一层也开始显式提示 compatibility layer，进一步把 primary 层提升成默认展示入口
- 现在 `Primary Verdicts / Primary Digests` 的显示顺序也已前置到 operator contract 之前，展示优先级开始真正偏向 primary 层
- `writer-imitate-index.md` 的完整字段面中，legacy verdict/digest 家族也已开始被单独归类到 compatibility layer 小节
- 其他 markdown 产物也开始显式标注 `primary_operator_entrypoint: writer-imitate-operator-surface.md`，降低控制链入口歧义
- 对应 JSON 产物也开始统一暴露 `primary_operator_entrypoint=writer-imitate-operator-surface.json`
- `writer-imitate-action-queue` / `writer-imitate-execution-state` 也开始复用 `session_operator_contract` 作为统一第一层合同
- `writer-imitate-execution-replay / apply / resume` 也开始复用 `session_operator_contract`，第一层 operator 合同已逐步覆盖整条控制链
- `Operator-Facing Stable Contract` 的 markdown 渲染已抽成统一 helper，后续第一层摘要演进时不必再多处手改
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
