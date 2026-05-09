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

## 10. 后续建议

后续可以继续做两件事：

1. 把当前最冗长的 session 字段按“可保留 / 可合并 / 可废弃”做一次中文化治理
2. 在真正进入 apply/resume 持久化实现前，先把核心 operator-facing 字段进一步缩成更少的稳定合同
