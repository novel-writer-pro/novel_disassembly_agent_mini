## Unreleased

- imitation: `writer-imitate-session-state.json` 已升级到 `writer-imitate-session-state.v3`，在 v2 聚合注册表基础上继续新增 `session_action_backlog`、`session_transition_queue`、`session_checkpoint_mutations`，把“下一步做什么、怎么迁移、要回写什么状态”显式化。

- imitation: `writer-imitate-index.md` 现在同步输出 action backlog / transition / checkpoint 摘要，`docs/writer-imitation-workflow.md` 的 mermaid 架构图与字段解释也已升级到 v3，使控制面从 taxonomy 汇总继续靠近真实商业 Agent 的 action-loop 编排层。

- imitation: writer innovation experiment outputs now include `steering_retrieval_meta.selected_doc_summaries`, so selected trope/worldview/audience docs carry compact summaries alongside hit reasons.
- imitation: local steering retrieval now understands `tags` and scores tag / label / query overlap separately, making trope/worldview/audience doc selection more stable and explainable.

- imitation: expanded the local trope/worldview/audience sample corpus with return-home payoff, mercantile resource play, frontier spirit-market, ancestral-contract, revenge rhythm, and faction-intrigue variants so the new retrieval rules have a broader P1 seed library.

- imitation: writer innovation experiment now emits a baseline-vs-steering comparison report, so each batch can directly compare baseline and steering verdict/title drift without a second manual pass.

- imitation: experiment outputs now include `delta_visual_summary`, making innovation/risk pressure easier to scan in markdown and JSON without a separate dashboard.

- imitation: experiment outputs now include `reader_sim_acceptance_summary`, so innovation batches can compare baseline/steering engagement and concern drift with existing harness evidence.

- imitation: experiment outputs now include `writer_innovation_explanation`, turning steering, hit docs, delta summaries, and reader acceptance signals into a concise writer-facing explanation block.

- imitation: writer-imitate-index now summarizes innovation experiment artifacts, making output workdirs easier to scan across multiple experiment batches.

- imitation: writer-imitate-index now includes an Experiment Ledger view so multiple innovation batches can be reviewed chronologically from one output index.

- imitation: experiment outputs now include `experiment_decision_note`, turning comparison, delta, and reader-acceptance signals into an actionable commercial recommendation instead of a demo-style artifact.

- imitation: experiment_decision_note now carries rollout-lane fields (`pilot_scope`, `promotion_gate`, `rollback_trigger`, `evidence_required`) so the artifact can drive commercial operations instead of acting like a demo summary.

- imitation: experiment_decision_note now includes go-live gate fields (`ship_blockers`, `required_human_review`, `confidence_level`, `business_risk_label`, `go_live_checklist`) so the artifact can act more like an execution contract than a report.

- imitation: experiment_decision_note now includes post-launch operations fields (`success_kpi_targets`, `failure_kpi_triggers`, `observation_window`, `owner_roles`, `handoff_packet`) so the artifact can govern post-launch operation instead of stopping at go-live review.

- imitation: writer-imitate-index now emits a session-level control plane (`promotion_verdict`, `risk_register`, `handoff_summary`) so multiple experiment artifacts can be operated as one commercial lane instead of isolated reports.

- imitation: writer-imitate-index now includes operator-panel session fields (`session_ship_decision`, `session_blockers`, `session_required_review`, `session_owner_handoff`, `session_priority_queue`) so multiple experiments can be queued and handed off as one commercial lane.

- imitation: writer-imitate-index now includes orchestration-facing session fields (`session_lane_status`, `session_escalation_path`, `session_release_readiness`, `session_recovery_plan`, `session_command_brief`) so the output workspace behaves more like a commercial agent control surface.

- imitation: writer-imitate-index now includes runtime-facing session fields (`session_execution_mode`, `session_action_window`, `session_ready_queue`, `session_blocked_queue`, `session_recovery_owner`) so the control surface gets closer to a commercial agent orchestration layer.

- imitation: writer-imitate-index now includes runtime-contract session fields (`session_runtime_contract`, `session_state_snapshot`, `session_transition_rules`, `session_auto_actions`, `session_manual_overrides`) so the control layer behaves more like an agent runtime contract than a static operator summary.

- imitation: writer-imitate-index now includes runtime-governance session fields (`session_guard_conditions`, `session_entry_criteria`, `session_exit_criteria`, `session_auto_escalations`, `session_override_audit`) so the control layer gets closer to an executable governance contract.

- imitation: writer-imitate-index now includes session state-machine and reconciliation fields (`session_state_machine`, `session_allowed_transitions`, `session_trigger_matrix`, `session_reconciliation_steps`, `session_operator_commands`) so the control plane gets closer to a commercial agent execution surface.

- imitation: writer-imitate-index now includes enterprise control fields (`session_policy_pack`, `session_slo_contract`, `session_failure_domains`, `session_intervention_matrix`, `session_audit_digest`) so the control plane moves closer to a commercial agent operations layer.

- imitation: writer-imitate-index now includes governor-facing session fields (`session_governor_mode`, `session_decision_bus`, `session_watchdog_rules`, `session_contingency_routes`, `session_operating_envelope`) so the control plane gets closer to a commercial agent runtime governor.

- imitation: writer-imitate-index now includes control-objective session fields (`session_control_objectives`, `session_enforcement_rules`, `session_decision_priorities`, `session_supervision_hooks`, `session_telemetry_digest`) so the control plane gets closer to a commercial agent operating system.

- imitation: writer-imitate-index now includes contract-plane session fields (`session_policy_versions`, `session_safety_budget`, `session_latency_budget`, `session_review_quorum`, `session_contract_digest`) so the control surface gets closer to an enterprise commercial agent contract plane.

- imitation: writer-imitate-index now includes compliance-plane session fields (`session_compliance_pack`, `session_failure_budget`, `session_override_budget`, `session_reliability_digest`, `session_governance_checksum`) so the control plane gets closer to an enterprise commercial agent governance OS.

- imitation: writer-imitate-index now includes governance-OS session fields (`session_authority_map`, `session_escalation_budget`, `session_remediation_contract`, `session_consensus_rules`, `session_integrity_digest`) so the control plane gets closer to a commercial agent governance operating system.

- imitation: writer-imitate-index now includes execution-kernel session fields (`session_control_kernel`, `session_safety_circuit_breakers`, `session_override_channels`, `session_repair_loops`, `session_operating_checksum`) so the control plane gets closer to a commercial agent runtime kernel.

- imitation: writer-imitate-index now includes core-constraint session fields (`session_control_memory`, `session_constraint_register`, `session_safety_invariants`, `session_repair_budget`, `session_runtime_digest`) so the control plane gets closer to a commercial agent runtime core.

- imitation: writer-imitate-index now includes control-fabric session fields (`session_control_fabric`, `session_guardrail_matrix`, `session_override_protocol`, `session_failure_isolation`, `session_runtime_manifest`) so the control plane gets closer to a commercial agent control fabric.

- imitation: writer-imitate-index now emits `writer-imitate-session-state.json`, providing a machine-readable session-level state snapshot with ready/blocked/escalation/recovery views alongside the markdown control plane.

- imitation: writer-imitate-index now includes control-bus session fields (`session_control_bus`, `session_event_channels`, `session_runtime_priorities`, `session_alert_routes`, `session_state_checkpoint`) so the control plane gets closer to a commercial runtime bus/checkpoint layer.

- imitation: writer-imitate-index now includes stateful-execution session fields (`session_execution_graph`, `session_signal_registry`, `session_action_contract`, `session_backpressure_rules`, `session_runtime_proof`) so the control plane gets closer to a stateful commercial agent execution contract.

- imitation: writer-imitate-index now includes supervisory/ledger session fields (`session_supervisory_contract`, `session_recovery_matrix`, `session_signal_budget`, `session_checkpoint_policy`, `session_operating_ledger`) so the control plane gets closer to a commercial operating ledger.

- imitation: writer-imitate-index now includes governance-fabric session fields (`session_governance_fabric`, `session_checkpoint_contract`, `session_supervision_priorities`, `session_ledger_consistency_rules`, `session_runtime_attestation`) so the control plane gets closer to a governed checkpoint OS.

- imitation: writer-imitate-index now includes runtime-mesh session fields (`session_runtime_mesh`, `session_policy_router`, `session_checkpoint_ring`, `session_audit_stream`, `session_operating_signature`) so the control plane gets closer to a commercial agent mesh/ring/stream/signature layer.

- imitation: writer-imitate-index now includes policy-kernel session fields (`session_policy_mesh`, `session_enforcement_bus`, `session_runtime_sentry`, `session_checkpoint_audit_chain`, `session_operating_posture`) so the control plane gets closer to a commercial agent policy kernel.

- imitation: writer-imitate-index now includes attestation/trust session fields (`session_attestation_chain`, `session_trust_zones`, `session_policy_attestors`, `session_recovery_posture`, `session_control_verdict`) so the control plane gets closer to a commercial agent trust/attestation layer.

- imitation: writer-imitate-index now includes protocol-stack session fields (`session_protocol_stack`, `session_trust_contract`, `session_recovery_authority`, `session_audit_checkpoint_map`, `session_runtime_certificate`) so the control plane gets closer to a commercial agent protocol/certificate layer.

- imitation: writer-imitate-index now includes topology/authorization session fields (`session_governance_topology`, `session_protocol_budget`, `session_certificate_chain`, `session_recovery_authorizations`, `session_control_attestation`) so the control plane gets closer to a commercial agent topology/certificate/authorization layer.

- imitation: writer-imitate-index now includes assurance/alignment session fields (`session_assurance_contract`, `session_policy_checksum`, `session_runtime_alignment`, `session_recovery_certainty`, `session_operator_assurance`) so the control plane gets closer to a commercial assurance/checksum layer.

- imitation: writer-imitate-index now includes meta-governance session fields (`session_meta_governor`, `session_policy_integrity`, `session_runtime_consistency`, `session_override_accountability`, `session_control_confidence`) so the control plane gets closer to a commercial control-integrity layer.

- imitation: writer-imitate-index now includes executive-governance session fields (`session_executive_contract`, `session_governance_checksum_v2`, `session_supervision_certificate`, `session_override_liability`, `session_operating_authority`) so the control plane gets closer to a commercial executive-governance layer.

- imitation: writer-imitate-index now includes authority/assurance session fields (`session_authority_certificate`, `session_policy_envelope`, `session_escalation_authority`, `session_assurance_digest`, `session_governance_verdict`) so the control plane gets closer to a commercial authority/assurance/verdict OS layer.

- imitation: writer-imitate-index now includes governance-mesh session fields (`session_governance_mesh`, `session_attestation_budget`, `session_policy_fallbacks`, `session_recovery_routing`, `session_runtime_verdict`) so the control plane gets closer to a final commercial governance mesh.

- imitation: writer-imitate-index now includes control-plane closure fields (`session_control_plane_closure`, `session_exec_fabric`, `session_authority_routes`, `session_assurance_chain`, `session_runtime_seal`) so the control plane gets closer to a closed-loop commercial execution fabric.

- imitation: writer-imitate-index now includes authority-fabric session fields (`session_authority_fabric`, `session_override_chain`, `session_control_closure_audit`, `session_runtime_witness`, `session_governance_posture`) so the control plane gets closer to a closed-loop commercial authority fabric.

- imitation: writer-imitate-index now includes final-charter session fields (`session_operating_charter`, `session_control_charter`, `session_governance_charter`, `session_runtime_authority_digest`, `session_final_control_verdict`) so the control plane gets closer to a commercial agent final control charter.

- imitation: writer-imitate-index now includes governance-closure session fields (`session_governance_closure`, `session_authority_verdict`, `session_runtime_horizon`, `session_supervision_digest`, `session_control_summary`) so the control plane gets closer to a closed-loop commercial governance summary.

- imitation: writer-imitate-index now includes operating-system session fields (`session_operating_system_contract`, `session_control_checkpoint_digest`, `session_authority_signature`, `session_recovery_escalation_mesh`, `session_final_operating_posture`) so the control plane gets closer to a commercial agent operating system layer.

- imitation: writer-imitate-index now includes final-runtime session fields (`session_command_mesh`, `session_authority_fabric_v2`, `session_closure_attestation`, `session_operating_charter_mesh`, `session_final_runtime_verdict`) so the control plane gets closer to a commercial final runtime OS layer.

- imitation: writer-imitate-index now includes executive-command session fields (`session_executive_command_mesh`, `session_authority_control_matrix`, `session_runtime_closure_proof`, `session_governance_signal_chain`, `session_operating_system_verdict`) so the control plane gets closer to a final commercial operating-system verdict layer.

- imitation: writer-imitate-index now includes control-OS session fields (`session_governance_backbone`, `session_control_lattice`, `session_authority_bus`, `session_runtime_witness_chain`, `session_os_control_digest`) so the control plane gets closer to a final commercial control OS layer.

## 2026-05-05

### 仿写实战工作流与 output 工作目录补齐
- 新增 `writer-imitate` 与 `writer-imitate-range` CLI，统一把仿写结果输出到 `output/`。
- `output/` 已加入 `.gitignore`，明确只作为仿写工作目录，不纳入版本管理。
- 新增 `docs/writer-imitation-workflow.md`，把仿写实战流程、关键字段、工作目录约束和后续增强方向写清楚。
- writer-facing `writer-imitate` / `writer-imitate-range` markdown 导出现在会移除 `Harness Action Queue` 正文污染，并对重复 `risk_gate_notes` 做去重，方便直接在 `output/` 下阅读和实战。


### 小说导入、切章与保存规范补强
- 自动切章现在支持真实中文网文常见的 `第X节` 标题，不再只识别 `第X章`。
- CLI 新增 `ingest-chapter-list`，支持按 JSON chapter list 做逐章 / 多章导入。
- `POST /api/import` 现在也支持 JSON `chapters` list 导入，便于外部系统先分章再送入主链。
- 新增 `docs/novel-ingest-chapter-standard.md`，集中说明切章标准、原文保存位置、续跑/续传原则，以及 chapter list 接口规范。


### 真实中文修仙样例首轮 manual eval
- 新增 `docs/real-xianxia-manual-eval-20260506.md`，记录首个真实中文修仙样例的 manual eval 结果与问题清单。
- 真实原文使用 `第一节/第二节/第三节` 标题时，`inspect/ingest` 显示 `chapter_count=0`，确认当前切章器对节级标题兼容不足。
- 对标题做最小归一化后，3 章主链成功完成；但第 2 章暴露 `small_model_pipeline` 的 `dialogue_candidates` schema 不兼容，依赖 `monolithic_fallback` 收口。
- 同时记录 operator-facing 导出链在该真实分支上的超时现象，作为下一轮 retrieval / governance 稳定性排查入口。
- 后续补修后已用同一份原始未归一化修仙样例复测，`inspect/ingest` 直接得到 `normalized_chapter_count=5` / `chapter_count=5`，说明 `第X节` 标题兼容已打通。
- 后续 5 节原始短复跑已完成：`completed_chapters=5`、`failed_jobs=0`；并确认 chapter 2 的 dialogue schema 问题与 chapter 3 的 normalized_title 问题都未在真实链路上复发。
- 对完成分支做 stepwise profiling 后，已确认导出慢点边界主要落在 retrieval diagnostics / benchmark 链，而不是 branch report / author knowledge 基础导出。
- 进一步对完成分支做导出链优化后，`export-retrieval-benchmark`、`export-search-branch-diagnostics`、`export-governance-dashboard` 与 `export-novel-assistant` 已恢复成功导出，说明 operator-facing 导出已从“不可用”改善为“可用但 retrieval 链仍偏重”。
- 继续做 route-level profiling 后，已确认 retrieval diagnostics 链中 `rerank`（约 6.3s）与 `vector route`（约 2.5s）是主要慢点，SQL route 并非主瓶颈。
- 继续加入 rerank candidate cap 后复测发现：当前 5 节分支的 raw_search 仅有 5 个候选，因此 rerank 仍约 6.7s；说明该改动更偏向保护大分支，而短分支的下一步优化应聚焦 rerank 本体。
- 在完成分支上补入按需触发 rerank 后，service 级 diagnostics 约 0.031s，CLI diagnostics/benchmark 分别在 5s/10s 窗口内成功，说明 retrieval operator export 已恢复到短窗口稳定可用。
- 在完成分支上引入 vector route 按需跳过后，`search_branch_with_diagnostics` service 级约 4.375s，CLI diagnostics/benchmark 也已在 20s/25s 窗口内成功，说明 retrieval operator export 进一步恢复。
- 继续加入 rerank 输入裁剪后复测，完成分支上的 rerank 时延从约 6.688s 降到约 6.021s，说明已有小幅收益，但 rerank 仍是第一慢点。
- 进一步尝试把 rerank 文本裁剪从 320 收紧到 160 后，在完成分支上未得到更好时延（约 6.745s），因此已回退，并把该负向证据记录到评估文档中。
- 进一步尝试只对 top5 候选做 rerank，在完成分支上复测约 6.998s，未优于当前较优基线，因此该改动已回退并作为负向证据保留。
- 在完成分支上补入 reader feedback 真导入与 whole-book readiness 证据：3 条评论成功导入，feedback summary 可导出；whole-book readiness contract 成功返回，但 provider health 仍提示 degraded。


### 小说助手多能力人工测试与评估手册
- 新增 `docs/novel-assistant-manual-eval-handbook-20260505.md`，把导入新小说后的人工测试流程收口成一份可直接执行的操作手册。
- 手册覆盖拆书、检索/RRF/rerank、风险检测、续写/仿写、whole-book、reader feedback、governance/archive 的人工验收路径。
- 同时补入“薄弱点溯源”方法，要求问题按源文本层 / 知识层 / 检索层 / 控制生成层 / 治理层定位，而不是只给模糊结论。
- `docs/README.md` 已同步把这份手册挂到使用者主路径，方便后续手动测试与商业化验收。
- 进一步新增 `docs/manual-eval-record-template.md`，用于把每本新小说的人工测试结果、薄弱点与商业化判断标准化沉淀。
- 新增 `runs/manual_eval/_template/` 样板目录，方便直接复制出一套评估工作区，统一 artifacts / exports / notes 收纳结构。
- 新增 `scripts/bootstrap_manual_eval_workspace.py`，可一键从模板生成新小说评估工作区，降低手工初始化成本。
















































- imitation: writer-imitate-index now includes final-runtime session fields (`session_command_mesh`, `session_authority_fabric_v2`, `session_closure_attestation`, `session_operating_charter_mesh`, `session_final_runtime_verdict`) so the control plane gets closer to a commercial final runtime OS layer.



## 2026-05-05

### AI 小说助手主链与治理导出升级
- 新增并持续扩展了 novel assistant 主链：planning / control / revision / rewrite / candidate / governance / archive。
- 关键能力包括：story bible、future chapter outline、draft preparation、direct skeleton、revision loop、automatic rewrite、final candidate、publish-ready release、sample-based release criteria、freeze artifact、handoff approval、operator brief、runbook、rollback、postmortem、closure、governance summary、external report bundle、final release archive。
- 新增真实 reader feedback ingestion 与 live PostgreSQL 验证样例。
- 新增 whole-book consistency backflow 到 candidate/release/governance surfaces。
- 每轮遇到的挑战（例如旧库缺表降级、sample-derived backflow、markdown 拼接错误）均通过测试、样例刷新和文档收口闭环。

## 2026-05-04
- Added executable eval/governance cross-lane sample bundle coverage via `CrossLaneSampleBundle`, `EvalGovernanceService.evaluate_sample_bundle()`, and `docs/examples/eval-governance-cross-lane-bundle.sample.json`.
- Documented the `eval-governance-freeze.v1` handoff gate across README, docs index, final handoff, release handoff, and the eval governance sample release contract.
- Added `sample_count_by_lane` to the freeze policy so handoffs can prove every required lane is represented by the evaluated bundle.

### Mainline architecture upgrade review docs
- Added `docs/mainline-architecture-upgrade-review-20260504.md` to document the retrieval/RRF/rerank, risk semantic, whole-book imitation/generation, and eval/governance upgrade lanes.
- Linked the review from `docs/README.md` so maintainers can find the cross-lane release criteria, freeze policy, and handoff checklist.

## 2026-05-01

### future target API 契约文档补 current surface 回链
- 在 `docs/api-contract.md` 中补充显式回链，说明当前已实现并可调用的 API surface 应查看 `docs/api-current-surface.md`
- 让读者在看到“这不是当前实现”时，能立刻知道当前实现的 source-of-truth 在哪里
- 增加自动测试，锁定 future-target 文档必须继续指回 current-surface 文档
- 验证：api-contract backlink / fence / current-surface boundary targeted strict 回归通过

### docs/README 开发者阅读顺序补 current API surface
- 在 `docs/README.md` 的“开发者（继续开发 / 维护 / 接手的人）”阅读顺序中加入 `api-current-surface.md`，并将其明确为第 3 步
- 让继续开发/接手的读者更早看到当前已实现 API surface，而不是只看到高层交接说明和内部 agent 设计
- 增加自动测试，锁定开发者阅读顺序的第 3 步必须是 current API surface
- 验证：developer flow / integrator flow / docs index targeted strict 回归通过

### docs/README 接入者阅读顺序说明与当前 API surface 对齐
- 修正 `docs/README.md` 中“接入者”小节的步骤说明，使第 2 步明确对应 `api-current-surface.md`，不再沿用旧的“先对照样例 JSON”说明
- 让阅读顺序说明与实际链接顺序保持一致，减少接入者被错误引导
- 增加自动测试，锁定第 2 步必须明确指向当前已实现 API surface
- 验证：integrator flow / docs index / current-surface targeted strict 回归通过

### 非技术入口不暴露 current API surface 的边界加保护
- 增加显式测试，要求 `docs/roles/product/README.md` 与 `docs/tracks/reader-experience/README.md` 不能引入 `api-current-surface.md` 入口
- 让 current API surface 的导航边界不只验证“该出现的地方出现”，也验证“不该出现的地方不出现”
- 验证：技术入口 + 非技术入口边界 targeted strict 回归通过

### current API surface 维护规则同步到 endpoint specs 时代
- 更新 `docs/api-current-surface.md` 的维护规则，明确 `_API_ENDPOINT_SPECS` 是 method+path 的 source-of-truth
- 将 `available_endpoint_specs` 与 `available_endpoints` 的维护责任都写入文档，避免维护规则停留在旧的 path-only 时代
- 增加自动测试，锁定 current-surface 文档必须继续提到 `_API_ENDPOINT_SPECS` / `available_endpoint_specs` / `available_endpoints`
- 验证：current-surface maintenance rule targeted strict 回归通过

### apps/api README 补 method-aware meta 契约说明
- 在 `apps/api/README.md` 中补充 `/api/meta` 的 `available_endpoint_specs` 字段说明
- 让后端接入者在 README 层就能知道：`available_endpoints` 是兼容字段，自动接入/契约校验应优先消费 `available_endpoint_specs`
- 增加自动测试，锁定 README 必须继续提到该 method-aware 元信息字段
- 验证：API README / current-surface / meta targeted strict 回归通过

### /api/meta 升级为 method+path 契约清单
- 为 `/api/meta` 新增 `available_endpoint_specs` 字段，显式返回 `{method, path}` 列表，同时保留 `available_endpoints` 作为兼容字段
- 将 endpoint spec 提升为后端模块级 source-of-truth 常量，并让 `/api/meta` 测试直接复用该常量，减少依赖源码正则反推实现的脆弱性
- 增加唯一性测试，要求 endpoint spec 中的 path 不得重复
- 验证：meta + endpoint spec + current-surface targeted strict 回归通过

### roles/tracks 总入口补 current API surface 链接
- 为 `docs/roles/README.md` 与 `docs/tracks/README.md` 补充 `api-current-surface.md` 总入口
- 让从角色总导航和能力线总导航进入的技术型读者，也能快速落到当前已实现 API surface 的 source-of-truth
- 增加自动测试，锁定 roles/tracks 总入口必须继续暴露该文档
- 验证：roles/tracks 总入口与下层技术入口 targeted strict 回归通过

### 维护者与风险审查主线入口补 current API surface 链接
- 为 `docs/roles/maintainer/README.md` 与 `docs/tracks/risk-audit/README.md` 补充 `api-current-surface.md` 入口
- 明确让维护者与风险审查主线读者可以直接落到“当前已实现 API surface”的 source-of-truth
- 同时保持 product / reader-experience 入口不过度暴露实现细节
- 增加自动测试，锁定这两个入口必须继续暴露 current API surface 文档
- 验证：maintainer / risk-audit targeted strict 回归通过

### 角色/轨道入口补 current API surface 链接
- 为 `docs/roles/integrator/README.md`、`docs/roles/backend/README.md`、`docs/tracks/review-workflow/README.md` 补充 `api-current-surface.md` 入口
- 让接入者、后端维护者与 review workflow 读者都能更快看到“当前已实现 API surface”的 source-of-truth
- 增加自动测试，锁定这三个角色/轨道入口必须继续暴露该文档
- 验证：角色/轨道入口 targeted strict 回归通过

### current API surface 文档边界说明加保护
- 为 `docs/api-current-surface.md` 增加显式测试，要求该文档必须继续指向 `docs/api-contract.md`，并保留“未来目标契约”的边界说明
- 避免后续维护中把 current-surface 文档误改成没有边界的实现清单，或丢失与目标契约的关系说明
- 验证：current-surface / docs index / apps-api README targeted strict 回归通过

### docs/README 增加 current API surface 入口保护
- 为 `docs/README.md` 增加显式测试，要求文档索引必须暴露 `api-current-surface.md` 入口
- 让 root README、docs/README、apps/api/README 三层入口都进入 current API surface 文档的自动保护范围
- 验证：三层入口 targeted strict 回归通过

### 根 README 补当前 API 实现契约入口
- 在仓库根 `README.md` 的 newcomer path 中补充 `docs/api-current-surface.md` 直链
- 让接入者能从项目顶层直接区分“当前已实现 API surface”和“未来目标契约”
- 增加自动测试，要求根 README 必须暴露当前 API 实现契约文档
- 验证：root README / current-surface targeted strict 回归通过

### docs/README 编号检查升级为全节扫描
- 修复 `docs/README.md` 第二个“推荐阅读顺序”小节的编号漂移问题
- 将原本只覆盖“接口类文档”的编号测试升级为：扫描 `docs/README.md` 所有带编号的 `###` 小节，并要求编号连续递增
- 让文档入口结构的自动保护从单点检查升级为全节检查
- 验证：全节编号测试与 API README 路由清单测试 strict 模式通过

### 根 README 标题层级修正并加保护
- 修复根 `README.md` 中一行误写成一级标题的说明文本，消除文档标题层级跳级问题
- 增加自动测试，要求根 README 的标题层级不得出现大于 1 级的跳跃
- 验证：README heading 测试与现有契约测试 strict 模式通过

### docs/api-contract Markdown 结构修复
- 修复 `docs/api-contract.md` 中未闭合的 fenced code block，避免后续标题与内容被错误吞入代码块
- 增加轻量测试，要求该文档的 Markdown 代码块 fence 数量必须成对平衡
- 验证：api-contract fence 测试与 current-surface 契约测试通过

### docs/README 接口文档编号修正并加保护
- 修正 `docs/README.md` 中“接口类文档”小节因多轮增补导致的编号漂移问题
- 增加自动测试，要求该小节的编号必须连续递增，避免后续文档入口继续失序
- 验证：接口文档编号测试与 API README 路由清单一致性测试通过

### apps/api README 路由清单增加完整一致性保护
- 修正 `apps/api/README.md` 中把 `pause|resume|cancel` 写成伪单条 endpoint 的误导表述
- 为 `apps/api/README.md` 增加完整路由集合一致性测试，直接把 README 暴露的 `METHOD /path` 列表与真实 WSGI 路由集合进行比对
- 让 README、`/api/meta` 与 `docs/api-current-surface.md` 三者都进入自动一致性保护范围
- 验证：README / current-surface / meta 三方 targeted 回归通过

### 当前 API surface 文档增加自动一致性保护
- 为 `docs/api-current-surface.md` 增加自动一致性测试，直接把当前实现路由集合与文档中的 `METHOD /path` 列表进行比对
- 让当前实现文档、`/api/meta` 与 `apps/api/README.md` 的维护规则从“靠人工自觉”升级为“有测试锁定”
- 验证：current surface / README / meta 三方 targeted 回归通过

### 新增当前 API 实现契约文档
- 新增 `docs/api-current-surface.md`，专门描述 `apps/api/app/main.py` 当前已经实现并可调用的 WSGI API surface
- `apps/api/README.md` 改为把该文档作为当前实现契约入口，同时保留 `docs/api-contract.md` 作为未来目标契约参考
- 避免未来目标契约文档被误读成当前实现清单
- 验证：README 指向与 meta/README 一致性 targeted 回归通过

### apps/api README 端点清单补齐
- 补充 `apps/api/README.md` 中缺失的 review workflow、job events、search、ask-branch 等已实现端点
- 增加 README 一致性测试，锁定关键端点在后端 README 中必须被暴露
- 避免 API 实现、`/api/meta` 元信息与后端 README 三者继续漂移
- 验证：README / meta targeted 回归通过

### API meta 端点清单与真实路由对齐
- 修正 `/api/meta` 的 `available_endpoints` 列表，使其与 WSGI 中真实实现的路由集合一致
- 补入真实存在但之前遗漏的 `/api/start` 与 `/api/recovery`
- 移除之前误列入但实际并不存在于该 WSGI 路由表中的 `/api/pipeline/pause`、`/api/pipeline/resume`、`/api/pipeline/cancel`
- 为 `/api/meta` 增加自动比对测试，防止元信息与实现再次漂移
- 验证：meta route inventory targeted 回归通过

### API meta 契约与实际能力对齐
- 修正 `/api/meta` 中关于 write-side import/upload 的过时说明，不再把已可用的 `/api/import` 描述为 future work
- 将 `/api/import` 补入 `available_endpoints` 列表，避免接口清单与真实能力不一致
- 为 `/api/meta` 增加更严格的测试断言，锁定端点暴露与说明文案的一致性
- 验证：`test_meta_endpoint_lists_available_routes` + import endpoint targeted 回归通过

### API multipart 解析去除 cgi 依赖
- 将 `apps/api/app/main.py` 中的 `cgi.FieldStorage` multipart 解析替换为基于 `email.parser.BytesParser` 的标准库实现
- 消除 Python 3.13 方向上的 `cgi` deprecation warning，同时保持 `/api/import` 现有行为不变
- 新增正向 multipart 上传测试，覆盖 `title` / `pipeline_profile` / `file` 三类字段的实际解析与落盘
- 验证：`tests/test_api_main.py` 全量通过

### 根 README 风险审查入口补齐
- 在仓库根 `README.md` 的 newcomer path 中补充 `risk-audit-completion-status.md` 直链
- 让新接手者能直接看到风险审查第一阶段的完成度、测试方法与使用说明
- 验证：关联 report / review endpoint smoke 通过

### 仓库缓存文件治理
- 将 `**/__pycache__/` 与 `*.py[cod]` 明确加入 `.gitignore`，避免 Python 字节码缓存继续污染版本库
- 将历史上已被错误纳管的 `__pycache__` / `.pyc` 文件从 Git 索引中移除
- 这一变更不影响业务代码行为，目标是降低噪音 diff、减少误提交，并提升仓库卫生与后续开发稳定性
- 验证：`git ls-files | rg '(__pycache__/|\.pyc$)' | wc -l` 结果为 `0`；同时补跑导出/报告 smoke 用例通过

# Changelog

> 约定：后续每次开发更改，都应在本文件追加一条记录，至少说明“做了什么 / 为什么 / 如何验证”。

## 2026-05-03

### 仿写/续写全能力矩阵文档补齐
- 新增 `docs/chapter-imitation-capability-matrix.md`
- 将仿写/续写能力拆成：
  - 风控审查
  - 知识提炼
  - 章节规划
  - whole-book 编排
  - 节奏分析
  - 对话设计
  - 文风修辞
  - 多线叙事
  - 资料研究
  - 模拟读者评审
- 同步标注当前覆盖度、现状、后续优先级，并接入：
  - `docs/chapter-imitation-method.md`
  - `docs/architecture/chapter-imitation-harness-architecture.md`
  - `docs/README.md`
- 目的：把“我们有没有考虑这些能力、哪些已经利用充分、哪些还没做强”收口为结构化文档，方便后续持续建设

### 对话设计器与 research pack 本地 skill 资产补齐

## 2026-05-07

### 仿写创新 steering pack 落地
- 为仿写链新增外置 steering pack 入口，可显式注入：
  - `worldview_capsule`
  - `trope_axes`
  - `innovation_directives`
  - `taboo_innovations`
  - `external_knowledge_refs`
- 代码接入点：
  - `ChapterImitationPlan` 新增对应字段
  - `ChapterImitationService.build_imitation_plan(...)`
  - `build_skeleton_draft(...)`
  - `build_llm_draft(...)`
  - `HarnessControllerService.build_skill_outputs(...)`
  - `build_skill_prompt_previews(...)`
  - `run_harness(...)`
  - CLI:
    - `writer-imitate`
    - `writer-imitate-range`
    - `writer-imitate-review`
    - `preflight-imitation`
    - `harness-imitation`
- 目的：
  - 让仿写不只贴着 source chapter 走
  - 允许显式注入新的世界观底座、题材套路轴与创新导向
  - 同时保留 taboo list 防止越界创新
- 新增文档：
  - `docs/imitation-innovation-and-steering.md`
  - `docs/writer-imitation-workflow.md` 补 steering pack 用法
- 新增回归：
  - `tests/test_chapter_imitation_service.py`
  - `tests/test_imitation_harness_service.py`
  - `tests/test_cli.py`
- 验证：
  - `./.venv/bin/pytest tests/test_chapter_imitation_service.py tests/test_imitation_harness_service.py tests/test_cli.py -q`
  - `26 passed`
  - `python3 -m py_compile ...` 通过

### steering pack 持久化与批量创新实验流程补齐
- 将 `steering_pack` 持久化到 writer-facing 输出：
  - `writer-imitate*.json`
  - `writer-imitate*.md`
  - `writer-innovation-experiment-*.json/.md`
- 新增批量实验 CLI：
  - `writer-innovation-experiment`
- 新增文档：
  - `docs/trope-worldview-rag-library-format.md`
  - `docs/batch-innovation-experiment-workflow.md`
- 价值：
  - 让世界观/套路/创新导向不只在执行时存在，而是能被落盘复盘
  - 给后续 trope/worldview RAG 文档库一个可执行的文档格式
  - 给连续章节提供一条统一底座的创新实验工作流

### 本地 steering 文档库装配器落地
- 新增：
  - `novel_analyzer/services/steering_library_service.py`
  - `rag/trope-library/xianxia-underdog-ledger.md`
  - `rag/worldview-dossiers/aura-decline-tax-state.md`
  - `rag/audience-expectation-notes/male-xianxia-commercial-hooks.md`
- 新能力：
  - 通过 `--trope-doc`
  - `--worldview-doc`
  - `--audience-doc`
  从本地 markdown 文档库装配 steering pack
- 接入点：
  - `writer-imitate`
  - `writer-imitate-range`
  - `writer-imitate-review`
  - `preflight-imitation`
  - `harness-imitation`
  - `writer-innovation-experiment`
- 价值：
  - 不必直接上复杂 RAG，也能先把 trope/worldview/audience 文档库接入仿写链
  - 后续真正做检索层时，可复用同一 steering pack contract
- 验证：
  - `./.venv/bin/pytest tests/test_steering_library_service.py tests/test_cli.py tests/test_chapter_imitation_service.py tests/test_imitation_harness_service.py -q`
  - `27 passed`

### steering 最小检索器 + 命中原因 + innovation/risk delta
- 为 `SteeringLibraryService` 新增最小 retrieval/ranking：
  - 基于 slug / label / section 内容做轻量匹配
  - 输出 `retrieval_meta.hit_reasons`
- 为 experiment / writer 输出新增：
  - `steering_retrieval_meta`
  - `experiment_meta.innovation_delta_summary`
  - `experiment_meta.risk_delta_summary`
- 价值：
  - 不再只是“装配到哪些文档”，而是知道“为什么命中这些文档”
  - 让实验结果可复盘“创新增量”和“越界风险增量”
- 验证：
  - `./.venv/bin/pytest tests/test_steering_library_service.py tests/test_cli.py tests/test_chapter_imitation_service.py tests/test_imitation_harness_service.py -q`
  - `28 passed`

### 命中文档摘要 + 样例库扩充
- 在 writer-facing markdown 输出中新增：
  - `## Steering Retrieval Meta`
  - `### Hit Reasons`
- 扩充本地样例库：
  - `rag/trope-library/clan-bureaucracy-power-climb.md`
  - `rag/worldview-dossiers/sect-credit-feudal-order.md`
  - `rag/audience-expectation-notes/cautious-growth-reader-signals.md`
- 价值：
  - 让人工复盘能直接看到“命中了哪些文档、为什么命中”
  - 让本地文档库不再只有单条样例，更接近最小可用实验库
- 验证：
  - `./.venv/bin/pytest tests/test_steering_library_service.py tests/test_cli.py tests/test_chapter_imitation_service.py tests/test_imitation_harness_service.py -q`
  - `29 passed`

### 长分支推进到 30 章并锁定 fresh evidence
- 继续推进真实中文修仙长分支 `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- fresh evidence：
  - `completed_chapters=30`
  - `failed_jobs=0`
  - `running_jobs=0`
  - `next_chapter=31`
  - `fact_count=491`
  - `graph_node_count=679`
  - `graph_edge_count=37602`
- 新增落盘证据：
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/status-after-30.txt`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/chapters-after-30.txt`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/ch21.bundle.json`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/ch22.raw.json`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/ch23.raw.json`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/ch24.raw.json`
  - `runs/manual_eval/real-xianxia-longer-branch-20260506/ch25.raw.json`
- 价值：把“真实长分支是否已推进到 30 章”从口头状态升级为可复查证据

### provider 波动下的 22~25 章 fallback 边界补证
- 对 chapter 22~25 导出 raw output，确认存在：
  - `402 Insufficient Balance`
  - `403 SUBSCRIPTION_NOT_FOUND`
- 与已落地的 `analysis_service` 本地 heuristic fallback 一起，形成新的主链判断：
  - provider 不可用时仍可保章节不断档
  - 但 chapter 22~25 的细粒度语义质量仍需后续 provider 恢复后补跑
- 价值：避免把 fallback 章误当成完整语义分析章，减少后续仿写/评估误判

### 新小说仿写 21~30 正文补写落到 output/
- 在 `output/novel-imitation-21-30/` 下新增：
  - `combined.md`
  - `eval-notes.md`
  - `README.md`
  - `ch21-周家子女.md` ~ `ch30-料峭春风.md`
- 本轮不是继续输出 skeleton，而是基于：
  - branch context
  - chapter bundle
  - raw output
  - 已完成章节连续状态
  进行人工实战补写
- 当前状态：21~30 已达到“可连续阅读、可人工审稿、可顺着写 31+”的水平
- 价值：把用户要的“根据示例小说仿写新的小说”从结构稿推进到可读正文稿

### 文档入口补充本地仿写正文评审路径
- 更新 `docs/real-xianxia-manual-eval-20260506.md`
  - 补入长分支推进到 30 章
  - 补入 provider fallback 边界
  - 补入 `output/novel-imitation-21-30/` 的正文评审入口
- 更新 `docs/README.md`
  - 在使用者阅读顺序中补充本地 `output` 仿写正文入口说明
- 价值：减少后续接手时只看到流程文档、却找不到最新正文样稿的问题

### targeted regression 继续通过
- 验证：
  - `./.venv/bin/pytest tests/test_analysis_service.py tests/test_cli.py -q`
- 结果：
  - `24 passed`
- 说明：
  - provider unavailable fallback
  - writer review markdown 增强
  - writer index CLI
  当前回归仍稳定
- 新增：
  - `skills_dir/dialogue-designer/`
  - `skills_dir/research-pack/`
- 让“对话设计”“资料研究/题材与读者预期”这两类此前覆盖较弱的能力，正式进入本地 skill 资产层
- 目标：先把能力从概念矩阵推进到真实 skill surface，后续再由 harness/controller 深度消费

### 仿写 harness / preflight / local skill contracts 第一版落地
- 新增 `novel_analyzer/services/imitation_harness_service.py`
- 新增第一版：
  - `HarnessControllerService`
  - `ChapterImitationPreflightReport`
  - `ChapterImitationHarnessReport`
  - `ChapterImitationSkillContract`
- CLI 新增：
  - `show-imitation-skill-contracts`
  - `preflight-imitation`
  - `harness-imitation`
- harness round 当前已开始暴露 `skill_prompt_previews`，用于证明它正在消费本地 skill prompt assets，而不只是暴露 contract 名称
- harness round 当前也开始暴露 `skill_outputs`，用于证明 constraint-pack / self-check 结构化结果已进入 preflight 与 action routing
- preflight / action routing 现已开始显式消费这些 `skill_outputs`，新增 constraint repair / continuity memory repair 路由
- 本轮继续补入人物动机 / 关系变化 / 世界规则 / 章尾 hook 方向的 repair routing
- 本轮进一步把 `chapter-intake / chapter-fact-extractor` 结构化 outputs 接入 preflight 与 routing，新增关系证据 / 规则证据 repair 路由
- 当前进一步补入 typed `severity / priority`，并开始让 gate/risk meta 信号进入 preflight 与 routing
- 当前 `severity / priority` 已开始影响 action 排序与 stop policy 聚合决策
- 当前 harness report 还新增 `action_queue / policy_summary`，用于输出排序后的 action 队列与聚合控制摘要
- 当前 ordered `action_queue` 已开始写回 revise 输入痕迹，whole-book sandbox report 也开始聚合 chapter harness 的 policy summary
- 当前 whole-book policy summary 继续补充 min/max score、max action count、verdicts 等聚合统计
- 当前 round 还新增 `revise_payload`，用于显式观察 ordered actions 如何进入 revise 输入
- 当前 whole-book report 也开始显式暴露 chapter-level `revise_payload`、`chapter_ranking`、`severity_histogram`
- 当前 whole-book 层开始尝试消费上一章 `revise_payload` 影响后续章节目标，并补充 `book_priority_ranking / risk_bucket_histogram`
- 当前 whole-book 层进一步新增 `strategy_input / dashboard_summary`，用于结构化表达跨章节策略反馈与总览面板
- 当前 `strategy_input` 已开始进入 chapter structured constraint 层，dashboard 也新增 `issue_family_histogram / cluster_buckets`
- 当前还继续把 rhythm / reader 两类弱能力接入 harness structured outputs，并新增 `issue_family_ranking`
- 当前 dialogue / research 两类弱能力也开始进入 harness preflight / routing，并补到 dashboard taxonomy
- 当前 strategy_input 还开始携带 `prioritized_families`，并进一步注入 chapter constraint/self-check 层
- 当前 prioritized family 也开始进一步影响 rhythm / reader / dialogue / research 四类弱能力输出的修复重点
- 当前 whole-book dashboard 还新增 `weak_lane_priority_ranking`，用于观察弱能力族群的优先级分布
- 当前 whole-book dashboard 还新增 `weak_lane_histogram`，用于观察四类弱能力的整体分布
- 当前 whole-book dashboard 还新增 `weak_lane_top_actions`，用于观察弱能力最靠前的修复动作
- 当前 whole-book dashboard 还新增 `top_priority_summary / top_risk_summary`，用于把弱能力信号并入整书级优先级与风险汇总
- 当前 whole-book dashboard 还新增 `weak_lane_dominance / chapter_flags`，用于观察弱能力主导面与逐章旗标
- 当前 top-priority / top-risk summary 还继续补入 `top_priority_families / high_risk_families`
- 当前这些 family summary 也开始回流到后续章节 `strategy_input`，不再只停留在 dashboard 展示层
- 当前这些 family 摘要还开始反向注入后续章节 `strategy_input`，参与下一章策略反馈
- 当前 top-priority / top-risk summary 也开始直接暴露 `weak_lane_action_count / weak_lane_families`
- 当前 whole-book executed step 还新增 `scheduling_priority / scheduling_reason`，用于明确章节调度优先级
- 当前 whole-book queue step 也开始显式暴露 `scheduling_priority / scheduling_reason`
- 当前 dry-run queue report 也开始输出 `queue_priority_preview / top_queue_priority_chapters / queue_cluster_buckets`
- 当前 dry-run / sandbox whole-book report 进一步新增：
  - `priority_reason_histogram / queue_next_actions`
  - `next_stage_focus / book_handoff_summary.top_repair_recommendations`
- 当前 whole-book 仿写 report 已同步固化到 `docs/interface-manifest.md` 与 `docs/examples/whole-book-imitation-run.sample.json`
- 当前新增 `export-whole-book-imitation-run`，可把 dry-run / sandbox execute 的整本仿写 report 直接落盘给系统消费
- 当前新增 `POST /api/whole-book-imitation-run`，系统侧可直接拿 whole-book dry-run / sandbox execute report
- 当前补充 `docs/whole-book-imitation-api-stability-summary.md`，明确 whole-book imitation 为 pre-v1 / system-contract-ready
- 当前 whole-book imitation report 已新增显式版本字段：
  - `contract_version=whole-book-imitation.v1`
  - `stable_contract_version=whole-book-imitation-pre-v1`
- 当前补充：
  - `docs/whole-book-imitation-api-versioning.md`
  - `docs/whole-book-imitation-api-freeze-readiness.md`
  用于说明 breaking-change 规则与正式 freeze 条件
- 当前新增 `docs/whole-book-imitation-freeze-evidence-20260503.md`，记录真实 provider-backed whole-book run 已触达上游，但被 `403 billing_error / daily usage limit exceeded` 阻断
- 当前新增 `show-whole-book-imitation-readiness`，可在重跑真实 provider 回归前一次性检查 contract/version、provider 配置、provider health 与 branch 数据准备度
- 当前已在真实 `novel_analyzer` 数据库上执行 `show-whole-book-imitation-readiness`，确认 branch `62e636f0-c901-4167-aa1c-aff3da9c83ef` 具备 11 个 chapter_analysis / 232 条 fact_records，provider 配置存在但 health 状态仍为 `degraded`
- 当前新增 `GET /api/whole-book-imitation-readiness`，system/agentOS 可直接读取 whole-book freeze readiness 信息而不依赖 CLI
- 当前新增 `docs/examples/whole-book-imitation-readiness.sample.json`，用于对接方直接参考 readiness payload
- 当前新增 `docs/examples/whole-book-imitation-run.request.sample.json`，用于对接方直接参考 whole-book run API 请求体
- 当前新增 `docs/examples/whole-book-imitation-run.error.provider-billing.sample.json`，用于对接方直接参考 provider 配额阻断时的结构化错误返回
- 当前 `docs/interface-manifest.md` 已补 whole-book run 错误合同字段说明与 `provider_billing_limited / provider_bad_gateway / provider_timeout` 语义
- 当前 `apps/api/README.md` 已直接链接 whole-book run 的 request / success / error 三类样例，方便 system 对接方快速查阅
- 当前新增 `docs/whole-book-imitation-integration-quickstart.md`，把 readiness / run / success / error 四类接入路径收口到一页
- 当前 `apps/api/README.md` 已直接链接 quickstart 与 readiness sample，进一步压缩 whole-book 对接的最短路径
- 当前 `apps/api/README.md` 已补 whole-book integration quick path，明确 readiness → run → success/error 的读取顺序
- 当前 `apps/api/README.md` 已补 readiness / run 的 curl quick examples，入口页可直接复制调用
- 当前 `apps/api/README.md` 也已直接链接 sample coverage matrix 与 provider recovery checklist，最浅入口已覆盖“怎么接 / 覆盖到哪 / 恢复后怎么收尾”
- 当前新增 request sample 可执行性回归，直接用 `whole-book-imitation-run.request.sample.json` 打 API 校验样例与实现不漂移
- 当前新增 readiness sample 可执行性回归，确保 `whole-book-imitation-readiness.sample.json` 与 live readiness endpoint 不漂移
- 当前新增 error sample 形状回归，确保 `whole-book-imitation-run.error.provider-billing.sample.json` 与 live billing-error 返回不漂移
- 当前新增 `docs/whole-book-imitation-docs-index.md`，把 contract / samples / governance / evidence / quickstart 收口成单页索引
- 当前新增 `docs/whole-book-imitation-provider-recovery-checklist.md`，明确 provider 恢复后如何重跑 readiness / execute / freeze evidence
- 当前新增 `docs/whole-book-imitation-sample-coverage-matrix.md`，明确 request / readiness / error / success 样例各自的 executable regression 覆盖状态
- 当前新增 `docs/whole-book-imitation-handoff-brief.md`，把当前完成度、唯一阻断、恢复后动作压缩成单页交接说明
- 当前 success sample 也已补 live stable-field regression，request / readiness / error / success 四类样例现在都有更明确的自动校验覆盖
- 当前 readiness 已反映 provider 运行态恢复为 `ok`，whole-book 线当前剩余事项已收敛为 stable 级别/治理口径判断
- 当前 retrieval/QA 主链已新增本地 ONNX rerank 接入，默认模型为 `onnx-community/bge-reranker-v2-m3-ONNX`，会在 `search_branch` 召回后执行 rerank，并在 provider 不可用时自动回退原始召回顺序
- 当前 weak lane 的 preflight priority 也开始进一步影响 action 排序，并新增 `top_weak_lane_chapters`
- 本地 `skills_dir` 新增：
  - `imitation-constraint-pack`
  - `draft-self-check`
- 目的：把“仿写 should use skills + harness”的规划推进为第一版真实执行框架，而不是只停留在架构文档
- 验证：
  - 新增 harness/service/CLI/skill-loader 相关测试
  - 后续本轮回归会以 strict pytest + compileall 作为签收依据

### 仿写能力收口为 skills + harness + risk-audit 最终推荐架构
- 新增 `docs/architecture/chapter-imitation-harness-architecture.md`
- 将章节仿写 / 全书仿写的推荐方向明确收口为：
  - 约束输入层
  - skills 分阶段生产链
  - harness agent 控制层
  - risk audit 最终门控层
- 把这套规划同步接入：
  - `docs/architecture/README.md`
  - `docs/chapter-imitation-method.md`
  - `docs/roles/imitation/README.md`
  - `docs/tracks/imitation/README.md`
  - `docs/README.md`
- 目的：避免后续继续走“单次大模型生成 + 审查不过反复重写”的低效路线，而是转向可分工、可复用、可定向修复的受控生成系统
- 验证：
  - `pytest tests/test_next_chapter_planner_service.py tests/test_chapter_imitation_service.py tests/test_whole_book_imitation_service.py tests/test_cli.py tests/test_api_main.py -q`
  - `python -m compileall novel_analyzer docs tests`

### whole-book imitation 增加 sandbox execute 与显式 carry-over state
- 为 whole-book imitation 增加：
  - `WholeBookCarryOverState`
  - `WholeBookImitationExecutedStep`
  - `WholeBookImitationRunReport.execution_mode / executed_steps / final_carry_over_state`
- `run-whole-book-imitation` 新增：
  - `--execute`
  - `--max-rounds`
  - `--use-llm`
  - `--model-name`
- 当前可以在 sandbox 中逐章执行 imitation iteration，并显式把“上一章生成摘要 / 关系状态 / 未解线程 / 规则约束”传给下一章
- 仍保持严格边界：不会把生成正文写入 live branch artifact
- 验证：
  - `pytest tests/test_whole_book_imitation_service.py tests/test_cli.py -q`
  - `python -m compileall novel_analyzer docs tests`

## 2026-05-02

### 仿写评分器补入迭代闭环
- 为 imitation loop 新增多轴评分：
  - `structure_score`
  - `style_alignment_score`
  - `risk_score`
  - `overall_score`
- 将 `iterate-imitation` 的 stop 条件从纯布尔判断升级为“结构 + 风险 + 评分阈值”联合判定
- 第3章 live 实验报告同步补入评分与 stop 逻辑说明

### 第3章 live 仿写实验报告补齐
- 新增 `docs/chapter-imitation-ch3-live-report-20260502.md`
- 将《第3章 养生功法》的 live 仿写实验结果收口为正式文档
- 记录：
  - 原章核心骨架
  - live 命令
  - rounds 结果
  - stop_reason
  - 当前优点 / 不足 / 下一步

### next_chapter_planner 数据结构与服务骨架落地
- 新增 `novel_analyzer/services/next_chapter_planner_service.py`
- 新增规划相关 schema：
  - `ChapterPlanningIntent`
  - `ChapterPlanningContext`
  - `ChapterPlanningCard`
  - `ChapterPlanningScene`
- 当前 skeleton 已能从 branch 现有状态生成最小的“下一章规划卡”，包括：
  - chapter goal
  - main conflict
  - scene plan
  - ending hook
  - risk notes
- 新增 `tests/test_next_chapter_planner_service.py`，锁定当前最小上下文构建与规划输出
- 文档补充：
  - `docs/chapter-planning-capability-proposal.md` 增补当前已落地骨架说明

### 章节仿写方法与实验骨架补齐
- 新增 `novel_analyzer/services/chapter_imitation_service.py`
- 新增仿写相关 schema：
  - `ChapterImitationPlan`
  - `ChapterImitationDraft`
- 新增 `tests/test_chapter_imitation_service.py`
- 新增 `docs/chapter-imitation-method.md`
- 当前实现先落：
  - 仿写方法论
  - imitation plan
  - skeleton draft
  - comparison / risk gate notes
- 暂不直接放开高自由度正文代写，优先形成“规划 → 草案 → 风险检查”闭环

### fresh 真库前10章风险结论与交接文档补齐
- 新增 `docs/risk-audit-fresh10-verification-20260502.md`
- 新增 `docs/chapter-planning-capability-proposal.md`
- 将样例小说前 10 章的 fresh PostgreSQL 真库结果写入正式文档，而不再只依赖离线报告或口头结论
- 明确记录：
  - fresh run/branch 标识
  - 1~10 章全部跑通
  - 低风险候选主要集中在 `character_ooc` 与 `plot_logic_consistency`
  - small-model schema 漂移为非阻断稳定性债
- 同步将这些文档接入 docs 索引，方便后续维护与交接

### 风险语义信号表补入正式 Alembic schema
- 新增迁移 `20260502_01_risk_signal_tables.py`
- 将 `risk_semantic_signals`、`risk_signal_links`、`risk_signal_clusters` 正式纳入 Alembic 管理
- 修复“空库 init-db 成功，但 fresh 风险审查在第1章因缺表中断”的真环境问题
- 让 ONNX/pgvector/semantic middle layer 在新库中不再依赖历史手工残留表
- 验证：后续将以真库 fresh10 rerun 作为主证据继续签收

### Alembic 多 head 冲突收口为线性迁移链
- 修复 `alembic/versions/20260430_01_cluster_review_records.py` 与 `20260430_01_cluster_review_tables.py` 共享同一 revision id 的问题
- 将 records 迁移改为 `20260430_02`，并收口为兼容性 no-op bridge，避免空库 `init-db` 时出现 multiple heads
- 保留 `20260429_01` / `20260430_01` 的实际建表/补列职责，不让历史已有库的语义被破坏
- 同步修正文档中对 cluster review 迁移编号的描述
- 验证：本地 PostgreSQL 真环境下 `scripts/check_postgres.py` / `init-db` / `db-capabilities` 可继续作为后续收尾验收路径

### 风险审查正式生产收尾文档补齐
- 新增 `docs/risk-audit-production-readiness.md`
- 将“正式稳定生产”缺少的外部条件从口头说明收口为结构化文档，明确区分：
  - PostgreSQL / pgvector 真环境
  - provider 长链稳定性
  - ONNX embedding 资源
  - 可重复运行壳层
- 补充推荐验收顺序，便于后续按 checklist 收尾
- 验证：本地读取文档、docs index 编号检查、相关入口链接回归

### 样例小说前10章风险核验报告补齐
- 新增 `.omx/reports/sample-novel-first-10-risk-check-20260502.md`
- 基于现有离线样例产物，对前 10 章风险卡与章节摘要进行一次 best-effort 复核
- 明确记录：前 10 章当前均为 `risk=low`、`risk_count=0`，未发现明确 OOC / 规则冲突 / 关系突变 / 时间线异常 / 能力突变
- 同时保留边界说明：当前会话下 PostgreSQL `127.0.0.1:5432` 连接拒绝，因此这不是 fresh DB 重跑 verdict
- 验证：离线报告与 `.omx/tmp/sample-branch-report.md` / 既有 sample-novel 结论文档交叉核对一致

## 2026-04-27

### 基础 release 文档收口
- 将当前版本明确收口为“基础可用 release”
- 补充 release 交接说明、工作台基础能力边界与推荐阅读顺序
- 明确这版优先保障可导入、可拆书、可阅读、可问答、可恢复、可导出

### 多作品适配与后端并发补强
- 工作台新增“当前作品库”切换入口，允许在同一个 UI 中切换不同 run / branch
- 为后续多本小说总览页预留基础数据接口：`GET /api/library`
- 后端 WSGI 服务改为可并发处理请求，避免一个长拆书请求把整个 API 完全阻塞
- 当前仍是“单工作台聚焦一个 branch”的交互模型，但已经不再写死只能服务单本小说

### 问答状态可视化与当前作品识别增强
- branch QA 结果新增 `answer_mode` / `degraded_reason`，显式区分正常回答与降级回答
- 当上游问答模型临时 503 时，界面会显示“降级回答”提示，而不是只剩无结果状态
- 工作台头部新增“当前作品”区域，明确显示正在查看的是哪一本小说
- 控制台新增当前作品摘要与作品快捷卡，避免多本切换时看不出自己正处于哪一本

### 小说空间与多作品管理入口
- 新增独立的 `/library` 小说空间页面，作为多本小说管理入口
- 支持按小说名 / 分支 / 状态搜索，并以卡片方式管理大量小说记录
- 小说空间中新增每本书的状态卡、后台进行中统计、待恢复统计与快捷进入按钮
- 将首页默认入口切换到小说空间，先选当前生效小说，再进入控制台 / 阅读 / 问答
- 左侧章节卡片调小，减少单条章节占用高度，便于长目录阅读
- 修复 `/api/library` 中 `_setup_status` 未导入导致的后端报错
- 新增多任务运行 / 恢复中心，并支持自动状态刷新
- 工作台会根据是否存在运行中 / 待恢复任务自动提高刷新频率

### 运行时缓存路径收口
- 将 Web 工作台运行期文件从 `.omx/...` 收口到 `.cache/novel-analyzer/...`
- 导出文件迁移到 `.cache/novel-analyzer/runtime-exports/`
- 上传小说原文迁移到 `.cache/novel-analyzer/uploads/`
- 补充旧 `.omx/uploads/` 路径的兼容读取，减少重启或历史数据切换时出现“文件不存在”
- 后端启动时会自动迁移历史 `.omx/uploads/` 与 `.omx/runtime-exports/` 内容到 `.cache/novel-analyzer/`
- 工作台按 branch 记住独立的最后阅读章节，切回同一本小说时优先恢复各自阅读位置
- 新增 `novel-analyzer runtime-storage` 与 `scripts/check_runtime_storage.py`，用于检查/迁移历史运行时文件
- 新增 `GET /api/runtime-health`，便于后续工作台或排障流程直接查看运行时文件状态

### 系统健康面板与任务中心增强
- 小说空间与运行/恢复中心接入 `runtime-health` 数据
- 新增系统健康面板，直接展示 `.cache` / `.omx` 文件数量与迁移状态
- 多任务运行/恢复中心增加筛选视图：聚焦 / 运行中 / 待恢复
- 新增 `provider-health` 状态记录与 API，用于展示 ask-stream 最近的 503 / 降级情况
- 任务中心开始联动 provider 健康状态，在 ask-stream 持续 503 时给出更明确的运行/恢复建议
- 问答页降级提示改为更产品化文案，减少直接暴露原始 503/429 错误噪音
- 顶部新增统一系统状态条，集中显示 provider/cache/自动刷新状态
- 恢复页开始根据 provider degraded 状态调整恢复动作提示与按钮强调级别
- provider degraded 时，工作台自动刷新会自动退避到较低频率，减少高频轮询噪音
- 任务中心中的恢复入口也开始根据 provider degraded 状态弱化动作强调
- 问答页降级回答减少重复提示，只保留一次清晰说明
- 系统健康面板新增聚合建议文案
- 恢复页进一步细化“什么时候该等、什么时候该恢复”的说明
- 系统健康面板、任务中心、恢复页开始复用统一建议规则，减少状态解释冲突
- 任务中心新增统一优先级排序规则，优先展示“待恢复 > 运行中 > 可继续推进 > 已完成”
- 小说空间卡片排序已与任务中心优先级规则统一，减少不同界面对同一批小说的排序不一致
- 任务中心、恢复页、系统健康面板开始复用共享的恢复动作策略规则

### 小说问答页修复与产品化增强
- 修复 `/qa` 页面实际未挂载问答组件、进入后无内容的问题
- 将小说问答页重做为真正可交互的聊天式界面，而不是只显示零散表单
- 保留“快速检索”页签，并把问答 / 检索 / 当前回答摘要拆成更清晰的三段结构
- 回答区改为卡片化渲染：引用章节、证据摘要、推理摘要、图谱信号分别分组展示
- 回答中的 `第N章` 引用继续支持直接跳转到章节阅读页

### 流式问答输出
- 新增 `POST /api/ask-branch-stream`
- 前端默认优先使用流式问答接口，按聊天场景逐步显示回答内容
- 若流式接口不可用，前端会自动回退到普通 `/api/ask-branch`，并在本地模拟逐段输出，避免界面完全卡死
- 前端问答消息中补充“推理摘要”展示，用于承接可展示的证据链 / reasoning paths，而不是直接平铺原始 JSON
- 当上游问答模型临时返回 503/不可用时，branch QA 服务现在会自动降级为“基于检索结果的保守回答”，不再直接给用户空结果

### 文档同步
- 更新 `README.md`
- 更新 `apps/web/README.md`
- 更新 `apps/api/README.md`
- 补充当前问答页的位置、流式能力与开发 / 部署说明

### 问答页二次打磨
- 将 `/qa` 页从单列问答改为“主聊天区 + 侧边提示区”的更稳定布局
- 增加顶部概览卡：已提问轮次、最近引用章节、当前模式
- 增加本轮提问记录，支持一键回填问题继续追问
- 将回答明细收拢为折叠分组：引用章节 / 证据摘要 / 推理摘要 / 图谱信号
- 检索结果支持“一键围绕这一章继续问”，让检索和问答联动更自然
- 增加清空会话与自动滚动到底部，减少长对话时的操作负担

### 本轮验证
- `cd apps/web && ./node_modules/.bin/tsc --noEmit`
- `cd apps/web && npm run build`
- `.venv/bin/python -m py_compile apps/api/app/main.py novel_analyzer/services/qa_service.py`

## 2026-04-28

### 工作台运行态规则进一步收口
- 新增 `apps/web/src/lib/operations.ts`，把 provider/cache/恢复/优先级 相关规则从纯展示格式化中拆出
- 系统状态条、小说空间、任务中心、健康面板、恢复页开始复用同一套运行态摘要与建议文案
- 进一步降低 provider degraded 时的界面噪音，把“该等待还是该恢复”统一成更稳定的产品文案

### Next.js 页面构建修复
- 为 `/library`、`/control`、`/reader`、`/qa`、`/ops` 等工作台页面补充 SSR 入口
- 修复 `npm run build` 时 `/reader`、`/qa` 等页面 prerender 阶段报 `Cannot find module for page` 的问题
- 当前工作台页面已明确作为动态产品界面按需服务，而不是强行静态导出

### 文档同步
- 更新 `apps/web/README.md`
- 更新 `docs/final-handoff.md`

### 章节跳转状态同步修复
- 修复 reader 内部章节跳转时“界面切到新章节，但 URL 仍停留旧章节”的状态分裂问题
- 修复因此引发的章节被 `router.query.chapter` 回拉到旧值、点击后跳错章/跳回旧章的问题
- 现在左侧目录、章节内引用跳转、问答引用跳转都会优先同步 reader 路由参数，再加载对应章节
- 切换章节时会先清空上一章内容，避免出现“左侧高亮和 URL 已切换，但右侧正文还短暂显示旧章节”的闪烁错位

### 当前作品状态持久化修复
- 修复进入 `/library`、`/ops` 等页面时，工作台在 hydration 前被默认示例小说状态覆盖的问题
- 修复因此导致“明明已选中别的小说，但页面一刷新/一跳转又回到默认示例小说”的问题
- 现在只有在本地 workbench 状态完成加载后，才会开始自动写入 localStorage 和执行首次分支刷新

### 控制台继续拆书入口增强
- 在控制台顶部 Hero 区增加显性的“继续拆书 / 刷新进度 / 导出 / 恢复”按钮组
- 将进度区按钮文案从“继续整理后续章节”改为更直白的“继续拆书到后续章节”
- 减少“功能存在但入口不明显”带来的误判，方便直接进入下一轮批量拆书

### 异步可观测流水线 Phase 0 启动
- 扩展 `chapter_jobs` 可观测字段：`current_stage`、`progress_percent`、`heartbeat_at`、`failure_class` 等
- 新增 `chapter_job_events` 表，用于记录章节任务过程事件
- 现有同步拆书流程开始写入基础事件：`job_started`、`stage_started`、`stage_completed`、`stage_failed`、`artifact_saved`、`job_completed`、`job_failed`
- 新增 `novel-analyzer list-job-events` CLI 命令
- 新增 `GET /api/job-events` 接口，便于后续前端任务控制台接入

### 异步可观测流水线 Phase 1 后端骨架
- 新增 `pipeline_runs` 表，用于持久化一次后台拆书区间任务
- 新增最小可用的后台 daemon pipeline runner：支持从当前 `next_chapter` 连续推进到目标章数
- 新增 API：
  - `POST /api/pipeline/start-range`
  - `GET /api/pipeline/status`
  - `GET /api/pipeline/runs`
  - `POST /api/pipeline/pause`
  - `POST /api/pipeline/resume`
  - `POST /api/pipeline/cancel`
- 当前版本仍是单进程原型级异步执行，但已经完成“控制面/API 与执行线程解耦”的第一步

### 拆书流水线前端控制台接入
- 新增 `/pipeline` 页面与工作台导航入口
- 前端已接入后台流水线 API：启动、暂停、恢复、取消、查看最近 runs、查看章节事件流
- 当前控制台先聚焦“从 next_chapter 连续往后跑”的最小版本，用于先验证后台异步控制链路和事件可视化

### 拆书流水线任务台增强
- 新增 `GET /api/chapter-jobs`，返回章节级任务监控数据
- `/pipeline` 页面新增章节任务表，展示 `status / current_stage / progress_percent / attempts / heartbeat / failure_class`
- `/pipeline` 页面自动刷新频率收紧为 5 秒，更适合盯运行中任务

### 卡住任务保护（保守收口）
- 新增 `chapter_job_stall_timeout_seconds` 配置项，默认 180 秒
- 后端在 run status / chapter-jobs 查询以及 pipeline runner 循环中都会顺手扫描 stalled job
- 超过心跳阈值的 running job 会被保守地标记为 `failed + failure_class=stalled`
- `/pipeline` 页面新增 stalled 告警与汇总标签，优先让操作者看见“假 running / 真卡死”的问题

### Pipeline 任务详情增强
- 新增 `GET /api/chapter-job-events?branch_id=...&chapter_index=...`
- `/pipeline` 页面支持点击章节打开任务详情抽屉，查看该章事件链
- 进一步强化“先看清楚再处理”的操作体验，优先保证可读性与维护性

### Pipeline 过滤与恢复联动增强
- `/pipeline` 章节任务表新增过滤器：全部 / 运行中 / 失败 / stalled
- 单章任务详情抽屉新增失败摘要展示
- 当章节已有失败分类时，可直接从详情抽屉跳转到恢复页继续处理

### Pipeline 总览统计增强
- `/pipeline` 顶部新增章节任务统计卡：已完成 / 运行中 / 失败 / stalled
- 最近章节事件流新增错误/警告筛选，便于更快聚焦异常信号
- 当最近一次后台 run 已记录错误摘要时，会在页面顶部显式提醒

### 多小说上下文与栏目收口修复
- 修复切换到其他小说后，进入章节阅读时偶发丢失 `run_id / branch_id` 上下文并落回默认书第一章的问题
- reader / qa / ops / control / pipeline 路由现在会显式携带当前 `run_id + branch_id`
- 拆书流水线不再单独占用左侧主栏目，改为收纳到“开始整理”内部，以 tab 方式区分“开始整理 / 拆书流水线”

### 交接与下一步优化点补充
- 在 `docs/final-handoff.md` 中补充了下一阶段优化优先级（P0/P1/P2）
- 在 `docs/session-handoff-manual.md` 中补充了下一位继续开发者的执行优先级
- 在 `docs/cli-operations-manual.md` 与 `docs/release-handoff-brief.md` 中补充了维护建议与下一步优化顺序

### 本轮验证
- `cd apps/web && npm exec tsc --noEmit`
- `cd apps/web && NEXT_TELEMETRY_DISABLED=1 npm run build`
- `python3 -m compileall apps/api/app/main.py novel_analyzer/runtime/storage.py novel_analyzer/runtime/provider_health.py novel_analyzer/services/qa_service.py`

## 2026-04-25

### 拆书能力与导出层增强
- 增强章节拆书输出：补充 `state_transition_notes`、`evidence_backed_resolutions`、`unresolved_threads`
- 强化 `writer_learning_notes` fallback，使其优先产出“推进 / 解决 / 留悬念”型 lesson
- 压缩 `chapter_summary`，默认使用更短的卡片化摘要
- 增强 JSON 提取与修复逻辑，降低轻微格式漂移导致的解析失败率

### 推理图与问答层增强
- 完整升级 reasoning graph，补充 richer node/edge taxonomy
- 增加 state machine / state summary
- 将图谱与状态摘要接入 QA、thematic contexts、package/export/report
- 增加 visualization-friendly 字段：`node_refs`、`edge_refs`、`timeline_points`

### QA context 与专题导航增强
- 增加 chapter QA context / branch QA context 导出接口
- 增加 `recommended_questions`、`query_hints`
- 增加 thematic contexts：character/conflict/foreshadow/world-rule
- 增加主题证据链：`reasoning_paths`、`state_signals`、`supporting_facts`
- 增加主题导航结构：`related_chapters`、`evidence_summaries`、`question_sequence`

### 文档与交付面增强
- 新增文档：
  - `docs/interface-manifest.md`
  - `docs/cli-operations-manual.md`
  - `docs/final-handoff.md`
  - `docs/release-handoff-brief.md`
  - `docs/real-run-checklist.md`
  - `docs/review-template.md`
  - `docs/model-eval-template.md`
  - `docs/real-run-evaluation-1-12.md`
  - `docs/README.md`
- 新增样例：
  - `docs/examples/chapter-bundle.sample.json`
  - `docs/examples/branch-bundle.sample.json`
  - `docs/examples/chapter-qa-context.sample.json`
  - `docs/examples/branch-qa-context.sample.json`
- 将核心 Markdown 文档中的文档引用逐步改为相对路径超链接 `[]()`

### 真实试跑结论（前 12 章）
- 前 12 章已形成真实可评估结果
- 当前模型 `Qwen/Qwen3.5-122B-A10B`：
  - 适合做质量验证 / 人工盯跑
  - 不适合长程无人值守生产跑批

### 验证
- `ruff check novel_analyzer tests alembic`
- `mypy`
- `pytest -q`（历史验证已通过 56 passed）

## 2026-04-26

### PostgreSQL-only runtime 收口
- 运行时收口为 PostgreSQL-only
- 去除 SQLite 作为正式 runtime 的假设
- 显式 `database_url` 统一要求 PostgreSQL URL
- 修复 `effective_db_name` / `admin_database_url` / `masked_database_url`
- 支持 IPv6 URL 重写与脱敏

### PostgreSQL 能力检查
- 新增 `scripts/check_postgres.py`
- 新增 `novel-analyzer db-capabilities`
- 检查数据库存在性、连接能力、schema 初始化、扩展能力和 text search config
- 保证 capability check 输出为结构化 `key=value`
- 保证错误配置时非零退出

### Web 工作台原型
- 新增独立前端目录：`apps/web/`
- 新增独立后端目录：`apps/api/`
- 前端支持：
  - 真实导入
  - 真实 run / branch 读取
  - 左侧章节导航 + 右侧详情主视图
  - chapter bundle / chapter QA context 结构化阅读
  - 原始章节正文回看
  - 引用中的 `第N章` 跳转
  - 恢复动作与导出链接
- 后端支持：
  - `/api/import`
  - `/api/start`
  - `/api/recovery`
  - `/api/run-snapshot`
  - `/api/branch-snapshot`
  - `/api/chapter-bundle`
  - `/api/chapter-qa-context`
  - `/api/chapter-source`
  - `/api/branch-exports`
  - `/api/download`

### Web 前端产品化重构（进行中）
- 前端开始从单页静态原型迁移到 Next.js + React + Ant Design
- 开始拆分为多组件 / 多页面结构
- 增补原始章节正文回看与 `第N章` 引用跳转
- 补充 Node.js / npm mirror (`https://registry.npmmirror.com/`) 部署说明

### 测试与测试基座迁移
- 迁移一批旧 CLI 测试，移除对 SQLite runtime 成功的依赖
- 新增 `tests/cli_test_support.py`
- 新增 PG capability / script / API 原型相关测试
- 调整 retrieval / QA 测试以匹配 PG-only 语义

### 验证
- `pytest` 目标与 broadened CLI/runtime 切片共 45+ 用例通过
- `ruff check` 通过
- `mypy` 通过


### 控制台产品化打磨与运行配置收口
- 重做工作台顶部结构、控制台流程区、导出与恢复页，使界面更接近面向作家的产品界面
- Reader / Sidebar / Control / Ops 之间的视觉语言继续统一，减少“技术后台”感
- 文档同步更新为当前推荐运行配置：`vip1129 + gpt-5.4-mini`
- 明确记录章节失败自动重试策略：默认自动重试最多 **5 次**，超过阈值后才进入人工恢复
- 明确从第一章重新创建新 run/branch 进行真实拆书，不再沿用旧 provider 的历史任务

### 本轮验证
- `cd apps/web && ./node_modules/.bin/tsc --noEmit`
- `cd apps/web && npm run build`
- `.venv/bin/pytest tests/test_application_layer.py tests/test_cli_retry_bulk.py -q`
- 真实创建新 run：`run_id=7e22a5d8-eb57-4306-858b-90386f1c2b22`

### 文档补完与仓库清理收口
- 补充 `apps/api/README.md`，明确当前推荐启动方式、provider 与自动恢复机制
- 补充 `docs/release-handoff-brief.md` / `docs/final-handoff.md`，同步当前工作台产品化方向与真实运行配置
- 补充 `.gitignore`，忽略 `apps/web/node_modules`、`.next` 与 ts build 缓存
- 准备将前端从旧静态原型彻底收口到 Next.js 目录结构

### 小说检索 / 问答界面接入
- 新增工作台内的人物/事件检索与基于小说内容的问答面板
- 后端新增 `/api/search-branch` 与 `/api/ask-branch` 接口
- 问答结果保留 `used_chapters`、`evidence`、`reasoning_paths`、`graph_signals`，并在前端可直接跳转章节
- 左侧章节分页增加范围选择与每页条数控制
- 修复章节点击后被旧 query 覆盖、请求竞态回退到旧章节的问题


### 工作台问答 / 检索能力接入与交互修复
- 新增 `BranchQaPanel`，在阅读页内直接提供人物/事件检索与基于小说内容的问答入口
- 后端新增 `/api/search-branch` 与 `/api/ask-branch` 接口，前端直接消费现有 branch retrieval / QA 能力
- 问答结果保留 `used_chapters`、`evidence`、`reasoning_paths`、`graph_signals`，并支持点击跳转章节
- 修复左侧章节点击后被旧 URL query 覆盖回退、请求竞态回退到旧章节、分页无法翻页等交互问题
- 自动拆书任务检查发现第 21 章长期 running，已执行 `clear-running` 并重新继续运行


### 前端构建缓存异常修复
- 定位到一次 `npm run build` 失败并非源码路由缺失，而是 `apps/web/.next` 脏缓存导致 `/ops` 未进入 pages manifest
- 通过删除 `apps/web/.next` 并重新构建恢复正常，新的 build 已重新包含 `/ops` 路由


### 交付纪律补充
- 增补项目约定：每一次修复和变动，都同步更新文档、`CHANGELOG.md` 与 git commit 记录
- 后续所有 UI、API、运行时恢复与自动拆书推进相关修改，均按该约定执行


### 问答区可见性增强
- 将阅读页内的“小说问答 / 检索台”上移为前部主入口，并增加 hero 说明区与能力标签
- 补充文档说明问答区默认优先显示，减少“功能已接入但不易被看到”的问题


### 导出链接从临时目录收口到持久目录
- 修复工作台中导出文件依赖 `/tmp` 临时路径的问题
- `/api/branch-exports` 现在改为输出到项目内 `.omx/runtime-exports/`，避免前端刷新或延迟下载时路径失效


### 控制台首页暴露额度失败与恢复入口
- 当章节因 provider 额度耗尽失败时，控制台首页会直接展示失败提示
- 提示中增加跳转恢复页与刷新进度入口，避免用户只看到章节停住却不知道如何处理


### 上传小说原文持久化，修复 /tmp 源文件丢失
- 修复工作台导入后把原文保存在 `/tmp`，导致后续章节正文回看时报 `No such file or directory` 的问题
- `POST /api/import` 现在把上传小说持久化写入 `.omx/uploads/`
- 同时将当前真实运行任务的 `source_path` 修正为稳定文件路径，恢复前后端展示


### 小说问答改为单独页签
- 将人物检索与基于小说内容的问答从阅读页内联区域拆分为独立的“小说问答”导航页签
- 章节阅读页回归专注阅读，问答与检索改为单独入口，降低信息拥挤度


### 首页重定向改为直接渲染，修复 build 收集 page data 异常
- 将首页 `/` 从运行时 `router.replace("/control")` 改为直接渲染控制台页面
- 修复 Next.js 在构建阶段对 `/` 收集 page data 时的路由异常，新的干净构建已重新包含 `/ /control /reader /qa /ops`
