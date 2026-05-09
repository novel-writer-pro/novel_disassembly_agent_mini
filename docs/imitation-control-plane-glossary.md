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

## 13. 后续建议

后续可以继续做两件事：

1. 把当前最冗长的 session 字段按“可保留 / 可合并 / 可废弃”做一次中文化治理
2. 在真正进入 apply/resume 持久化实现前，先把核心 operator-facing 字段进一步缩成更少的稳定合同
