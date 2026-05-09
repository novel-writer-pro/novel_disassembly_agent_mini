# Imitation Control-Plane Glossary / 仿写控制层术语表

这份文档专门解释当前仿写商业 Agent 控制层中反复出现的英文术语。

目标不是做学术定义，而是帮助团队快速回答 3 个问题：

1. 这个词在我们这里是什么意思  
2. 它为什么会出现在当前架构里  
3. 它和真实商业化可运营 Agent 有什么关系

---

## 1. 核心总览

可以先把这些词粗略分成 6 层：

1. **Control / Runtime 层**：系统现在要做什么、怎么跑  
2. **Queue / Transition / Checkpoint 层**：任务如何流转、状态如何回写  
3. **Governance / Authority 层**：谁有权决策、谁来审批、什么情况下升级  
4. **Assurance / Attestation / Certificate 层**：我们凭什么相信当前状态和结论  
5. **Recovery / Resume 层**：出问题后怎么恢复、怎么继续  
6. **Meta-Governance 层**：治理系统本身如何被治理

---

## 2. 运行与控制类术语

### control plane
- 中文：控制面
- 含义：负责“决策、编排、分流、约束”的那一层，不直接产出正文，而是决定系统怎么运行。
- 在本项目里：主要对应 `writer-imitate-index.md`、session state、action queue、execution state 这条链。

### runtime
- 中文：运行时
- 含义：系统此刻正在执行的状态与环境。
- 在本项目里：比如当前 lane、当前 ticket 状态、当前 recovery owner、当前 run_status。

### orchestration
- 中文：编排
- 含义：把多个动作、阶段、队列、责任人组织成一个有顺序的执行流。
- 在本项目里：从 experiment -> action backlog -> execution state -> replay/apply/resume。

### execution
- 中文：执行
- 含义：真正把某个 ticket、transition、checkpoint 推进下去。
- 在本项目里：现在还主要是“预演执行”和“合同化执行”，下一步才会进入真实 apply。

### action backlog
- 中文：动作积压队列 / 待办动作池
- 含义：当前有哪些 ticket 待推进。
- 在本项目里：每个 experiment 被压成一个可操作 ticket。

### transition
- 中文：状态迁移 / lane 迁移
- 含义：系统从一个状态走到另一个状态。
- 在本项目里：如 `pilot-lane -> expansion-lane`。

### checkpoint
- 中文：检查点 / 状态回写点
- 含义：执行到某一步后，需要把关键状态保存下来。
- 在本项目里：如 `promotion_verdict`、`risk_register`、`session_ship_decision` 的待回写记录。

---

## 3. 治理与权限类术语

### governance
- 中文：治理
- 含义：确保系统不是“能跑就行”，而是“按规则跑、可审计地跑”。
- 在本项目里：谁审批、谁兜底、何时升级、何时冻结，都是治理问题。

### authority
- 中文：权限 / 授权 / 决策权
- 含义：谁有资格拍板。
- 在本项目里：例如 `writer-operator`、`risk-approver`、`business-owner` 的责任边界。

### escalation
- 中文：升级路径
- 含义：当前处理不了时，向更高责任层交由谁处理。
- 在本项目里：从 continuity-reviewer 升级到 risk-approver，再升级到 business-owner。

### policy
- 中文：策略 / 规则集
- 含义：系统在面对不同信号时，应该按什么规则行动。
- 在本项目里：如 promote/de-risk/pilot 的切换逻辑。

### governance mesh
- 中文：治理网格
- 含义：多个治理节点不是单点串行，而是形成协同网络。
- 在本项目里：强调治理不是单一 verdict，而是 authority / review / fallback / recovery 的组合。

### authority fabric
- 中文：权限织面 / 权限网络
- 含义：谁能决策、谁能 override、谁能恢复，不是孤立字段，而是一整张关系网。
- 在本项目里：是“权限关系被结构化表达”的意思。

### charter
- 中文：章程 / 操作章程
- 含义：高层规则声明，定义哪些行为是被允许、被期望、被约束的。
- 在本项目里：`operating_charter`、`control_charter`、`governance_charter` 表达的是高层治理约束。

### meta-governance
- 中文：元治理
- 含义：不是治理业务本身，而是治理“治理系统自己”。
- 在本项目里：比如谁能修改 governance rule、谁能解释 override 的合法性。

---

## 4. 可信性与证明类术语

### assurance
- 中文：保障 / 可信保障
- 含义：我们如何确认系统当前的判断和状态足够可靠。
- 在本项目里：通常表示“不是随便推出来的，而是带有校验与责任链”。

### alignment
- 中文：对齐
- 含义：系统行为是否和目标、规则、业务约束一致。
- 在本项目里：例如 runtime alignment，强调执行态不能偏离治理目标。

### attestation
- 中文：证明 / 见证证明
- 含义：某个状态、事件或结论有记录可证。
- 在本项目里：偏向“这个阶段真的发生过 / 真的满足过某条件”。

### certificate
- 中文：证书 / 凭证
- 含义：一种更正式的“已验证”表达。
- 在本项目里：通常不是密码学证书，而是“治理上被确认的凭据层”。

### digest
- 中文：摘要
- 含义：把复杂状态压缩成便于消费的总结。
- 在本项目里：帮助 operator / agent / downstream surface 不必每次读全量字段。

### signature
- 中文：签名
- 含义：谁对当前状态或结论负责。
- 在本项目里：更偏责任签名，而非严格密码学签名。

### verdict
- 中文：裁决 / 结论
- 含义：当前系统对某个阶段的最终判断。
- 在本项目里：如 `promotion_verdict`、`runtime_verdict`、`operating_system_verdict`。

### witness
- 中文：见证
- 含义：某一步被记录、可回看、可佐证。
- 在本项目里：强调执行痕迹不是黑盒。

---

## 5. 恢复与连续执行类术语

### recovery
- 中文：恢复
- 含义：出现阻断、风险升级、执行失败后，如何回到可推进状态。
- 在本项目里：blocked ticket 的处理、risk lane 的兜底、恢复 owner 的接手。

### resume
- 中文：续跑 / 恢复推进
- 含义：恢复之后，如何继续往下走。
- 在本项目里：`writer-imitate-resume-replay` 已开始把这层命令显式化。

### replay
- 中文：回放 / 预演回放
- 含义：按照当前合同模拟“如果现在执行，会发生什么”。
- 在本项目里：是进入真实 apply 前的安全层。

### apply
- 中文：应用 / 落地执行
- 含义：把预演过的状态迁移和 checkpoint 真正写入。
- 在本项目里：目前还是 preview，下一步会往真实 apply mechanics 推进。

### recovery cursor
- 中文：恢复游标
- 含义：恢复流程当前停在哪、接下来该从哪继续。
- 在本项目里：主要记录 blocked/review/replay-ready ticket 集合。

---

## 6. 结构形态类术语

### mesh
- 中文：网格
- 含义：多点协同、非单链路结构。
- 常见用法：governance mesh / command mesh / runtime mesh。

### fabric
- 中文：织面 / 织构
- 含义：强调多个控制点被编织成整体。
- 常见用法：control fabric / authority fabric / exec fabric。

### lattice
- 中文：格 / 格状结构
- 含义：多个层次之间有清晰关系，不是平铺列表。
- 在本项目里：用来表达 decision -> governance -> runtime -> recovery 这样的分层关系。

### ledger
- 中文：账本
- 含义：强调记录可追踪、可审计、可回放。
- 在本项目里：experiment ledger / operating ledger 都属于这个思路。

### bus
- 中文：总线
- 含义：多个决策或信号通过统一通道传播。
- 在本项目里：decision bus / authority bus / enforcement bus。

### kernel
- 中文：内核
- 含义：最核心、最基础、最不应轻易漂移的部分。
- 在本项目里：control kernel / policy kernel 强调的是控制系统的核心约束。

### topology
- 中文：拓扑
- 含义：节点之间如何连接。
- 在本项目里：谁和谁互相作用、谁能升级给谁、谁能授权给谁。

---

## 7. 为什么会有这么多英文词

主要原因有 4 个：

1. **这些词来自通用系统/治理/分布式/平台工程语境**  
   比如 runtime、checkpoint、ledger、policy、resume，本来就是工程里常见词。

2. **我们现在做的不是 demo，而是在把“仿写实验输出”往“商业 Agent 控制层”推**  
   一旦进入控制层、编排层、恢复层，术语复杂度会自然上升。

3. **部分词是为了表达“层次感”，不是为了炫技**  
   比如 mesh / fabric / lattice / ledger / kernel，本质是在区分“网络关系 / 织面关系 / 分层关系 / 审计记录 / 核心约束”。

4. **之前这些词分散在字段名里，没有统一中文解释，所以显得特别乱**  
   这也是为什么现在需要单独做 glossary。

---

## 8. 阅读建议：如何快速看懂这些词

建议按下面顺序理解：

1. 先看 `control / runtime / execution / queue / transition / checkpoint`
2. 再看 `governance / authority / escalation / policy`
3. 再看 `assurance / attestation / certificate / verdict`
4. 最后看 `meta-governance / fabric / mesh / lattice / topology`

如果只想抓最关键的 10 个词，优先看：

- control plane
- runtime
- execution
- transition
- checkpoint
- governance
- authority
- assurance
- recovery
- resume

---

## 9. 这个术语表解决什么问题

它主要解决 3 个问题：

1. **降低理解成本**：新人不必对着一串英文字段硬猜
2. **降低沟通噪音**：同一个词在团队里尽量只有一种主语义
3. **给后续重构留下锚点**：以后如果要把字段收敛、重命名、中文化，有统一参照面

---

## 10. session_* 字段族快速映射

下面这张表不是逐字段解释，而是帮助大家看到“这一大族字段大概在解决什么问题”。

| 字段族 | 可理解成什么 | 主要回答的问题 |
| --- | --- | --- |
| `session_control_*` | 控制核心 / 控制摘要 / 控制章程 | 系统到底想怎么控 |
| `session_runtime_*` | 运行时状态 / 运行合同 / 运行结论 | 系统现在怎么跑、跑到哪 |
| `session_governance_*` | 治理规则 / 治理网络 / 治理总结 | 谁审批、谁兜底、规则是什么 |
| `session_authority_*` | 权限关系 / 决策权边界 | 谁能拍板、谁能 override |
| `session_policy_*` | 策略、约束、版本化规则 | 系统按什么原则切换 |
| `session_assurance_*` | 可信保障 / 对齐保障 | 为什么可以相信当前结论 |
| `session_attestation_*` | 见证、证明、留痕 | 哪些状态是可验证的 |
| `session_checkpoint_*` | 检查点 / 回写锚点 | 哪些状态需要被保存 |
| `session_recovery_*` | 恢复、回滚、兜底 | 卡住后怎么回来 |
| `session_execution_*` | 执行图 / 执行合同 / 执行票据 | 具体动作如何推进 |
| `session_action_*` | 动作池 / backlog | 下一步要做什么 |
| `session_transition_*` | 状态迁移 / lane 迁移 | 从哪切到哪 |
| `session_override_*` | 人工覆盖 / 特权操作 | 什么时候允许人工改写 |
| `session_operating_*` | 操作系统式摘要 / 高层运行结论 | 从业务运营角度怎么看当前状态 |
| `session_meta_*` | 治理治理者本身 | 谁来约束治理系统自己 |

### 怎么用这张映射表

如果你看到类似下面的字段：

- `session_assurance_contract`
- `session_assurance_digest`
- `session_operator_assurance`

不要先逐个字面硬读，可以先归到 **assurance 族**，理解为：

> 这一组字段都在回答“为什么我们可以相信当前状态/结论”。

同理：

- `session_recovery_plan`
- `session_recovery_posture`
- `session_recovery_cursor`
- `session_recovery_escalation_mesh`

可以先统一归到 **recovery 族**，理解为：

> 这一组字段都在回答“出问题后怎么恢复、恢复到哪、谁来恢复”。

---

## 11. 英文术语 -> 字段例子 -> 商业问题 对照表

这张表更偏实战，帮助快速把“词汇”映射到“字段”和“运营问题”。

| 英文术语 | 中文理解 | 典型字段例子 | 它在回答什么商业问题 |
| --- | --- | --- | --- |
| assurance | 可信保障 | `session_assurance_contract` / `session_assurance_digest` | 我们为什么能相信当前这轮仿写/实验结论 |
| alignment | 对齐 | `session_runtime_alignment` | 当前执行是否仍和业务目标、风险边界一致 |
| governance | 治理 | `session_governance_registry` / `session_governance_mesh` | 谁在管、按什么规则管 |
| authority | 权限 / 决策权 | `session_authority_routes` / `session_authority_verdict` | 谁能拍板、谁能兜底 |
| policy | 策略 | `session_policy_mesh` / `session_policy_fallbacks` | 当前切 lane / 切策略的依据是什么 |
| checkpoint | 检查点 | `session_checkpoint_mutations` / `session_control_checkpoint_digest` | 哪些关键状态需要保存，避免下次从头看 |
| replay | 预演回放 | `writer-imitate-execution-replay.json` | 如果现在推进，会发生什么 |
| apply | 应用执行 | `writer-imitate-execution-apply.json` | 哪些 ticket / checkpoint 准备真正落地 |
| resume | 恢复续跑 | `writer-imitate-execution-resume.json` | 卡住之后怎么继续，不丢上下文 |
| recovery | 恢复 | `session_recovery_plan` / `session_recovery_cursor` | 出问题之后谁接手、从哪恢复 |
| attestation | 见证证明 | `session_attestation_budget` / `session_control_attestation` | 哪些状态是可留痕、可审计的 |
| certificate | 凭证 / 证书 | `session_runtime_certificate` / `session_authority_certificate` | 哪些结论是“被确认过”的 |
| verdict | 裁决 | `promotion_verdict` / `session_runtime_verdict` | 当前到底是 promote、pilot、de-risk 还是 blocked |
| mesh | 网格 | `session_runtime_mesh` / `session_governance_mesh` | 当前不是单点控制，而是多点协同控制 |
| fabric | 织面 | `session_control_fabric` / `session_authority_fabric` | 当前控制/授权关系是被编织成整体的 |
| lattice | 格状结构 | `session_control_lattice` | 控制层之间的分层关系是什么 |
| ledger | 账本 | `session_operating_ledger` / Experiment Ledger | 我们能否回看历史实验与操作轨迹 |
| kernel | 内核 | `session_control_kernel` | 哪些约束是系统最不应漂移的核心 |
| topology | 拓扑 | `session_governance_topology` | 角色、节点、责任路径是怎么连接的 |
| meta-governance | 元治理 | `session_meta_governor` | 谁来约束治理系统本身 |

### 如何使用这张对照表

如果业务同学问：

> “为什么这里又有 assurance，又有 attestation，又有 certificate？”

可以快速这样回答：

- `assurance`：偏“我们是否可以相信”
- `attestation`：偏“有没有被记录和证明”
- `certificate`：偏“有没有被正式确认”

如果运营同学问：

> “为什么这里又有 recovery，又有 resume，又有 replay？”

可以快速这样回答：

- `replay`：先预演接下来会怎么走
- `apply`：再决定哪些动作真正落地
- `resume`：最后决定卡住后如何继续
- `recovery`：是整个异常恢复与兜底框架

---

## 12. 哪些词后续更适合中文化，哪些适合保留英文

### 更适合中文化的

这些词在团队日常讨论中可以优先说中文：

- assurance -> 可信保障
- alignment -> 对齐
- checkpoint -> 检查点
- recovery -> 恢复
- resume -> 续跑 / 恢复推进
- verdict -> 裁决 / 结论
- ledger -> 账本

原因：
- 业务、产品、运营同学更容易理解
- 中文表达不会明显损失技术精度

### 更适合暂时保留英文的

这些词可以先保留英文，再配中文解释：

- governance
- runtime
- orchestration
- mesh
- fabric
- lattice
- topology
- meta-governance

原因：
- 这些词已经是系统/平台/分布式语境里的常见术语
- 直接硬翻中文，反而容易让不同人脑补成不同意思

### 推荐实践

更推荐用下面这种写法，而不是只写一种语言：

- `governance（治理）`
- `runtime（运行时）`
- `checkpoint（检查点）`
- `recovery（恢复）`

这样既保留工程上下文，也降低理解门槛。

---

## 13. 字段收敛建议表（第一版）

这一节不是马上改代码，而是先给后续字段治理一个“讨论底稿”。

原则：

1. **保留**：对真实控制/编排/恢复直接有用
2. **合并**：语义相近，未来可以折叠进聚合注册表
3. **下沉**：不必放在 operator 第一层，但可以保留在深层执行态
4. **候选废弃**：如果后续没有真实执行价值，可以逐步退出主表面

| 字段/字段族 | 当前建议 | 原因 |
| --- | --- | --- |
| `session_control_loop` | 保留 | 已经是最重要的控制逻辑聚合面 |
| `session_queue_registry` | 保留 | 对运营/编排最直接 |
| `session_execution_registry` | 保留 | 对 runtime 与执行器最关键 |
| `session_governance_registry` | 保留 | 对审批/升级/owner 边界最关键 |
| `session_digest_registry` | 保留 | 方便下游消费，不必每次读全量字段 |
| `session_live_ops_board` | 保留 | 适合作为 operator 最浅入口 |
| `session_action_backlog` | 保留 | 已经进入可执行动作面 |
| `session_transition_queue` | 保留 | 对 lane 迁移最关键 |
| `session_checkpoint_mutations` | 保留 | 是后续真实状态回写的核心 |
| `writer-imitate-action-queue.*` | 保留 | 已是浅动作合同 |
| `writer-imitate-execution-state.*` | 保留 | 已是持久化执行态雏形 |
| `writer-imitate-execution-replay.*` | 保留 | 是 apply 前的安全预演层 |
| `writer-imitate-execution-apply.*` | 保留 | 是显式 apply 命令入口 |
| `writer-imitate-execution-resume.*` | 保留 | 是显式 resume 命令入口 |
| `session_runtime_contract` + `session_state_snapshot` | 合并候选 | 长期可以更多并入 `session_digest_registry` |
| `session_operating_signature` + `session_authority_signature` | 合并候选 | 都偏“签名/摘要层”，未来可收敛 |
| `session_governance_checksum` + `session_governance_checksum_v2` | 合并候选 | 明显有重复演进痕迹 |
| `session_control_verdict` + `session_runtime_verdict` + `session_operating_system_verdict` | 合并候选 | verdict 层级较多，未来需要收口 |
| `session_authority_certificate` + `session_runtime_certificate` | 下沉候选 | 更像深层可信执行信息，不必始终暴露在主控制面 |
| `session_protocol_stack` + `session_governance_topology` + `session_control_lattice` | 下沉候选 | 更像架构解释层，而不是日常 operator 层 |
| `session_meta_governor` | 下沉候选 | 重要但更偏治理系统自解释 |
| `session_exec_fabric` / `session_control_fabric` / `session_authority_fabric` | 合并候选 | “fabric” 家族过多，未来应收缩成更少稳定面 |
| `session_command_mesh` / `session_runtime_mesh` / `session_governance_mesh` | 合并候选 | “mesh” 家族过多，未来应收缩成更清晰分层 |
| 仅用于命名扩写但无真实执行消费的高阶摘要字段 | 候选废弃 | 若后续没有 apply/resume/runtime 消费，就不该留在主表面 |

### 推荐治理顺序

1. **先保留 execution/apply/resume 相关字段**
   - 因为这些已经开始接近真实商业 Agent 的执行面
2. **再合并重复的 digest / signature / verdict / checksum 家族**
   - 因为这些最容易继续膨胀
3. **最后再处理 mesh / fabric / topology / charter 这类解释层字段**
   - 因为这些更多影响可读性，而不是立即影响执行正确性

### 一个简单判断标准

如果一个字段不能回答下面任一问题，就应进入“合并/下沉/候选废弃”清单：

- 它能帮助 operator 决定下一步动作吗？
- 它能帮助 runtime/执行器决定下一步状态迁移吗？
- 它能帮助 recovery/resume 决定如何恢复吗？
- 它能帮助审计/追责/复盘提供关键证据吗？

如果都不能，说明它更可能只是“命名扩写”，不该长期停留在主控制面。

---

## 14. 最小 operator-facing 稳定合同建议（第一版）

如果后续要把当前复杂控制层真正收敛成一个更适合商业运营/控制台使用的“稳定合同”，建议第一版先只暴露下面这些核心字段：

### A. 当前状态

- `promotion_verdict`
- `risk_register`
- `session_ship_decision`
- `session_lane_status`
- `session_execution_mode`
- `session_release_readiness`

这组字段回答的是：

> 当前这轮实验/仿写，到底处于什么状态，能不能继续推，属于扩张还是降风险。

### B. 当前待办

- `session_action_backlog`
- `session_priority_queue`
- `session_ready_queue`
- `session_blocked_queue`

这组字段回答的是：

> 现在具体还有哪些动作待推进，哪些可做，哪些被卡住。

### C. 当前责任链

- `session_recovery_owner`
- `session_required_review`
- `session_escalation_path`
- `session_owner_handoff`

这组字段回答的是：

> 这件事该谁看、谁接、谁审批、谁兜底。

### D. 当前迁移与回写

- `session_transition_queue`
- `session_checkpoint_mutations`
- `writer-imitate-execution-apply.json`
- `writer-imitate-execution-resume.json`

这组字段回答的是：

> 下一步准备怎么迁移、哪些状态要回写、apply/resume 怎么走。

### E. 当前运营摘要

- `session_live_ops_board`
- `session_digest_registry`
- `writer-imitate-action-queue.json`

这组字段回答的是：

> 如果业务/运营/管理层不想看全量细节，最浅层应该看什么。

### 为什么只保留这几类

因为它们已经能覆盖商业运营闭环里最关键的 5 个问题：

1. **当前状态是什么**
2. **下一步动作是什么**
3. **谁来负责**
4. **怎么迁移/怎么回写**
5. **如果只看摘要，最小看什么**

换句话说：

如果一个字段既不影响这 5 个问题，又不会被执行器/恢复链直接消费，它就不该长期停留在 operator 第一层。

### 第一层不建议继续膨胀的字段类型

后续不建议再往 operator 第一层继续堆这些类型：

- 纯命名扩写型 `mesh/fabric/lattice` 字段
- 多层重复 `verdict/signature/checksum/digest`
- 偏架构解释但不直接驱动动作的 `topology/protocol/charter`

这些字段并不是没价值，而是更适合：

1. 下沉到深层执行态
2. 作为解释文档存在
3. 被聚合进 digest，而不是继续平铺在主控制面

---

## 15. 控制面精简路线图（建议执行顺序）

既然已经有了：

- 术语解释
- 字段族映射
- 商业问题映射
- 字段收敛建议
- 最小 operator-facing 稳定合同

下一步就不应再停留在“理解层”，而应进入“精简落地层”。

下面是一版建议路线图：

### Phase 1：先做展示层收敛（低风险）

目标：

- 不删底层字段
- 先把 operator 第一层只展示“最小稳定合同”
- 其余字段收进折叠区 / 深层摘要区 / 诊断区

建议动作：

1. `writer-imitate-index.md` 第一屏只保留最小 operator-facing 字段
2. `session_live_ops_board` 与 `session_digest_registry` 成为默认摘要入口
3. `session_action_backlog` / `session_transition_queue` / `session_checkpoint_mutations` 成为默认动作入口

验收标准：

- 业务/运营首次打开控制面时，不必滚过几十个 `session_*` 字段
- 第一屏能回答“当前状态 / 下一步 / 谁负责 / 怎么迁移”

### Phase 2：再做聚合字段收敛（中风险）

目标：

- 不改变已有真实执行入口
- 先合并重复 digest / signature / verdict / checksum 家族

建议动作：

1. 明确只保留 1 组主 `verdict`
2. 明确只保留 1 组主 `checksum/digest`
3. 把重复 `signature/certificate/attestation` 重新分层：
   - operator-facing 一层
   - deep execution 一层

验收标准：

- 同类字段不再出现三四套平行命名
- 新接手的人能快速判断“哪个 verdict 才是主 verdict”

### Phase 3：最后做深层解释字段下沉（中高风险）

目标：

- 把 mesh / fabric / topology / charter / protocol 这类更偏解释层字段下沉
- 主控制面只留下真正驱动动作和恢复的字段

建议动作：

1. 将 `mesh/fabric/lattice/topology/protocol/charter` 系列归入深层诊断区
2. 主控制面只保留可驱动 operator 决策的聚合结论
3. 若某字段长期没有被 apply/resume/runtime 消费，进入候选废弃清单

验收标准：

- operator 主控制面只剩“能驱动动作”的字段
- 深层解释字段仍可追溯，但不再污染第一层阅读体验

### 不建议的做法

不建议一步到位直接删字段，因为现在控制层仍在快速演进期。

更稳妥的方式是：

1. **先隐藏**
2. **再聚合**
3. **再下沉**
4. **最后再删除**

这样不会破坏当前已有的：

- session-state
- action-queue
- execution-state
- execution-replay
- execution-apply
- execution-resume

这几层合同。

---

## 16. 控制面瘦身实施清单（可执行版）

这一节把上面的路线图进一步落成 checklist，方便后续真正进入控制面瘦身时直接执行。

### Phase 1 checklist：展示层收敛

- [ ] 把 `writer-imitate-index.md` 第一屏改成只展示最小 operator-facing 合同
- [ ] 把 `session_live_ops_board` 提升为默认摘要块
- [ ] 把 `session_action_backlog / session_transition_queue / session_checkpoint_mutations` 提升为默认动作块
- [ ] 把重复 `session_*` 明细移动到折叠区或深层诊断区

验收标准：

- [ ] 第一屏不再出现几十个平铺 `session_*`
- [ ] 第一屏 30 秒内可回答：当前状态 / 下一步 / 谁负责 / 怎么迁移

回滚信号：

- [ ] 如果 operator 无法从第一屏判断 blocked/ready 状态，则回滚展示层收敛
- [ ] 如果 apply/resume 入口被隐藏到难以发现的位置，则回滚展示层收敛

### Phase 2 checklist：聚合字段收敛

- [ ] 指定 1 组主 `verdict`
- [ ] 指定 1 组主 `digest/checksum`
- [ ] 指定 1 组主 `signature/certificate/attestation` 暴露面
- [ ] 明确哪些字段只保留在 deep execution 层

验收标准：

- [ ] 团队能明确说出“主 verdict 是哪个”
- [ ] 团队能明确说出“主 digest/checksum 是哪个”
- [ ] 同类字段不会继续无限新增平行命名

回滚信号：

- [ ] 如果 runtime/apply/resume 需要同时依赖多套平行 verdict，则暂停聚合
- [ ] 如果下游消费方还无法迁移到主字段，则先不删旧字段

### Phase 3 checklist：深层字段下沉

- [ ] 把 `mesh/fabric/lattice/topology/protocol/charter` 归入深层解释区
- [ ] 仅保留能驱动 operator 动作的聚合字段在主控制面
- [ ] 为下沉字段补文档索引，避免信息丢失

验收标准：

- [ ] operator 主面只剩动作、责任、迁移、回写、摘要
- [ ] 深层解释字段仍然可检索、可追溯、可审计

回滚信号：

- [ ] 如果排障时必须频繁回到老的平铺字段列表，说明下沉过度
- [ ] 如果治理/审计链断裂，说明下沉位置不合理

### 总体执行原则

建议整个瘦身过程都遵循下面 4 条：

1. **先隐藏，再删除**
2. **先聚合，再重命名**
3. **先保留兼容层，再推动消费者迁移**
4. **每一步都要有 operator-facing 验收标准**

### 最终目标

最终希望把控制面稳定成两层：

- **第一层：operator-facing 稳定合同**
  - 给业务/运营/控制台直接看
- **第二层：deep execution / governance 诊断层**
  - 给排障、治理、追责、恢复链使用

这样既能保留商业 Agent 控制层的完整性，又能避免第一层继续失控膨胀。

---

## 17. 控制面字段改造优先级矩阵（第一版）

为了避免后续瘦身工作陷入“看起来都该改，但不知道先改谁”，这里给出一个优先级矩阵。

判断维度：

- **收益高**：改完后，operator/运营/下游消费者会明显更易理解
- **风险低**：改动不容易破坏现有 replay/apply/resume 或状态合同

### P0：高收益 + 低风险，优先改

| 字段族 | 为什么优先 |
| --- | --- |
| `session_live_ops_board` | 已经天然适合作为第一屏摘要 |
| `session_digest_registry` | 适合作为统一摘要收口点 |
| `session_action_backlog` | 已进入动作合同，直接影响 operator 使用 |
| `session_transition_queue` | 直接影响迁移理解 |
| `session_checkpoint_mutations` | 直接影响回写理解 |
| `session_priority_queue / ready_queue / blocked_queue` | 直接影响当前待办与阻塞态理解 |

建议动作：
- 优先把这些字段提升到第一层
- 优先围绕这些字段做 UI/展示简化

### P1：高收益 + 中风险，第二批改

| 字段族 | 为什么在第二批 |
| --- | --- |
| `verdict` 家族 | 收敛收益高，但要小心下游依赖 |
| `digest/checksum` 家族 | 重复度高，但可能被多个层消费 |
| `signature/certificate/attestation` 家族 | 可信层语义相近，适合分层收敛 |
| `recovery/resume/replay/apply` 家族 | 需要保证恢复链语义不丢失 |

建议动作：
- 先定义主字段
- 保留兼容层
- 不要立刻删除旧字段

### P2：中收益 + 低风险，可后置

| 字段族 | 为什么可后置 |
| --- | --- |
| `mesh/fabric/lattice` 家族 | 主要影响可读性，不直接破坏执行 |
| `topology/protocol/charter` 家族 | 更偏解释层，不是第一优先 |
| `meta-governance` 家族 | 重要但不影响第一层 operator 行为 |

建议动作：
- 先文档化归类
- 再做下沉

### P3：高风险项，最后处理

| 类型 | 为什么高风险 |
| --- | --- |
| 直接删字段 | 容易破坏已有消费者 |
| 直接重命名主字段 | 容易破坏脚本/文档/后续 apply-resume 设计 |
| 一次性大规模合并 | 很难定位问题来源 |

建议动作：
- 这些动作只有在前面 3 层都稳定后再考虑

### 一句话策略

优先顺序应是：

1. **先把 operator 真正在看的字段抬上来**
2. **再把重复命名的字段收口**
3. **最后才处理那些解释层/历史演进层字段**

如果顺序反了，就容易出现：

- 第一层仍然难看懂
- 但底层字段却已经被改乱
- 最后既没瘦身成功，也损害了可维护性

---

## 18. 后续建议

后续可以继续做两件事：

1. 把当前最冗长的 session 字段按“可保留 / 可合并 / 可废弃”做一次中文化治理
2. 在真正进入 apply/resume 持久化实现前，先把核心 operator-facing 字段进一步缩成更少的稳定合同
