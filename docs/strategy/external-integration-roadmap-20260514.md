# External Integration Roadmap — 2026-05-14

> **范围**:novel-analyzer 与外部生态的对接策略,覆盖编排面 / 观测面 / 记忆面 / 推理基础设施 / 读者 UI 五个分类。
> **前提**:`docs/strategy/kernel-sota-gap-assessment-20260514.md` §10 的 Week 1-2 内核阻塞拆分必须先完成。
> **不做**:本文档**不**包含实施代码或部署脚本;仅给路线 + 决策。具体落地步骤见同目录 `external-integration-checklist-20260514.md`。

---

## TL;DR

| 分类 | 推荐主选 | 备选/辅助 | 启用阶段 |
|---|---|---|---|
| 1. 编排面 | **Dify** (已用) + **n8n** (已用) | LangGraph(代码侧)、LiteLLM Proxy | 已 GA / 持续扩面 |
| 2. 观测面 | **Helicone proxy** + **Langfuse** (Dify 内置) | OpenTelemetry → 自存 | 立即启用 |
| 3. 记忆面 | **Letta**(评估) | Mem0、Zep | Stage 2 PoC |
| 4. 推理基础设施 | **TEI** + ONNX 双形态 | Infinity、本地 vLLM | 已 GA |
| 5. 读者 UI | **OpenWebUI** (作为 Reader 备选)、**LobeChat**(读者社群分发) | LibreChat | Stage 3 评估 |

**主结论**:外部生态有足够多的成熟选项,**不要再造轮子**。我们已经做出了正确的两个核心决策:

1. **Dify + n8n + Helicone + Langfuse** 这条线是当前最贴合"长篇小说内容平台"工作流的开源组合
2. **TEI + ONNX 双形态** 让我们既能跑本地零配置,也能切走

后续 12 周内的对接重心是**把已有的 4 个外部系统真正闭环用起来**(Dify Writer Copilot 上游、n8n 日报、Helicone 主流量 trace、Langfuse 评估),而不是再加新组件。**记忆面 Letta** 是唯一值得 Stage 2 PoC 的新成员,**读者 UI** 在 Stage 3 才进入议程。

---

## 1. 当前对接清点

按 `infra/`、`.env.example`、`novel_analyzer/runtime/notify.py`、`apps/web/src/components/writer/CopilotIframe.tsx`、`docker-compose.tei.yml` 等代码事实(2026-05-14 扫描)。

### 1.1 状态图例

| 标记 | 含义 |
|---|---|
| ✅ GA | 已在 production / 主分支启用,有真流量 |
| 🟡 Wired | 代码已写,docker-compose / env 已就绪,**未启用** |
| 🟠 Scaffolded | 仅文档/评估,代码侧无入口 |
| 🔴 Planned | 仅出现在路线图,未启动 |

### 1.2 当前清点

| 系统 | 类别 | 状态 | 主入口 | 备注 |
|---|---|---|---|---|
| **Dify** | 编排面 | 🟡 Wired | `infra/dify/`、Writer Copilot iframe | Writer Studio 已嵌 iframe;`NEXT_PUBLIC_DIFY_*` 已配 |
| **n8n** | 编排面 | 🟡 Wired | `infra/n8n/`、`runtime/notify.py` | pipeline-complete webhook 代码已写,`N8N_WEBHOOK_PIPELINE_COMPLETE_URL` 默认未设 |
| **Langfuse** | 观测面 | 🟡 Wired | `infra/langfuse/` 自托管模板 | Dify 内置开关 + 自托管 v3 compose 已就绪 |
| **Helicone** | 观测面 | 🟡 Wired | `llm_base_url_override` 字段 | env 注释中,**未启用** |
| **TEI** | 推理基础设施 | ✅ GA | `scripts/dev/docker-compose.tei.yml` + http backend | 已有 postmortem,backend=http 可切 |
| **ONNX 本地** | 推理基础设施 | ✅ GA | `embedding/service.py`、`rerank/service.py` | bge-m3 + bge-reranker-v2-m3 |
| **PostgreSQL + pgvector + pg_jieba** | 数据/检索 | ✅ GA | DB 层 | jieba 字典生成但未消费(见 kernel 评估 P0-1) |
| **DeepSeek API** | LLM | ✅ GA | `llm/client.py` | provider=deepseek,model=v4-flash |
| **Letta / Mem0 / Zep** | 记忆面 | 🔴 Planned | — | 完全未接入 |
| **OpenWebUI / LobeChat / LibreChat** | UI 面 | 🔴 Planned | — | 自研 Reader Studio 已有,UI shell 暂不需要 |
| **LangGraph / LiteLLM Proxy / DSPy** | 编排面 | 🔴 Planned | — | 暂不需要 |

### 1.3 当前缺口

1. **🟡 → ✅ 转化率为 0**:Dify / n8n / Langfuse / Helicone 四个 Wired 系统,docker-compose 都备好了,业务真流量为 0
2. **观测面有论证无实施**:`docs/observability/helicone-vs-langfuse.md` 已在 1 个月前给出"组合方案",未落
3. **记忆面无 PoC**:Loom Phase 1-2 把"分层记忆"做成了内部模块,但**没评估**Letta 这种成熟外部记忆系统是否更优

---

## 2. 决策原则(贯穿所有分类)

### 2.1 优先级顺序

1. **现有 Wired 必须先 → ✅**(Dify/n8n/Helicone/Langfuse 全部坐落到 production)
2. **新增对接必须有"我们做不好但他们已经做好"的证据**(不是看到流行就接)
3. **能用 OpenAI-compatible 协议的,绝不接私有 SDK**
4. **能 self-host 的,绝不接 SaaS-only**(数据合规 + 成本)
5. **License 必须 Apache/MIT**;BUSL/Fair-code 需评估限制条款

### 2.2 决策基线表

新增任何外部对接必须答以下 5 题:

| # | 问题 |
|---|---|
| 1 | 内核里有没有同等功能?(有的话先用内核) |
| 2 | License 是否可商业 self-host? |
| 3 | 90 天内 commit 活跃? |
| 4 | 是否 OpenAI-compatible 或有 thin SDK? |
| 5 | 退出路径是否清晰?(数据导出 / proxy 拆) |

任何一题答 No 必须明确论证。

---

## 3. 分类 1:编排面(Orchestration)

### 3.1 候选对比

| 系统 | License | 自托管 | 成熟度 | 接入成本(Python/FastAPI) | 当前状态 |
|---|---|---|---|---|---|
| **Dify** | Apache 2.0 + 商业条款 | ✅ | Production | 低(API + iframe) | 🟡 Wired |
| **n8n** | Fair-code(Sustainable) | ✅ | Production | 低(webhook) | 🟡 Wired |
| Langflow | MIT | ✅ | Production | 中 | — |
| Flowise | Apache 2.0 | ✅ | Production | 中 | — |
| LangGraph | MIT | ✅(库) | Production | 高(代码侵入) | — |
| OpenWebUI Tools | MIT | ✅ | Production | 中 | — |
| AutoGen | MIT | ✅(库) | Production | 高 | — |
| CrewAI | MIT | ✅(库) | Beta+ | 高 | — |
| LiteLLM Proxy | MIT | ✅ | Production | 极低(env) | — |
| Pipedream | Proprietary | ❌ | SaaS | 中 | 不考虑 |

### 3.2 推荐分工

```
[作家面 chat / RAG]    → Dify(已选)
[运维侧自动化]        → n8n(已选)
[内核控制流]          → Python 代码 + LangGraph(评估,可选)
[多 provider 路由]    → LiteLLM Proxy(P1 评估,见 §4)
```

### 3.3 路线图

| 阶段 | 时间 | 任务 |
|---|---|---|
| **Stage 1**(本月,Week 3-4) | 2 周 | Dify Writer Copilot 真上线;n8n daily-eval-report 真跑 |
| Stage 2(下月) | 4 周 | Dify 加 Reader Q&A 应用;n8n 加 pipeline-complete-notify |
| Stage 3(后续) | 评估 | LiteLLM Proxy 替代 base_url 切换 |

### 3.4 反对决策(明确不做)

- **不引入 Langflow / Flowise / AutoGen / CrewAI**:Dify 已覆盖 chat+workflow,LangGraph 已覆盖代码侧编排,叠加只增加运维负担
- **不切 FastGPT**:`docs/research/fastgpt-vs-dify.md` 已论证,Dify 更贴合
- **不上 Pipedream**:SaaS-only,数据出境

---

## 4. 分类 2:观测面(Observability)

### 4.1 候选对比

| 系统 | License | 自托管 | 接入方式 | 业务侵入 | 当前 |
|---|---|---|---|---|---|
| **Langfuse** | MIT | ✅ | Dify 内置 / SDK | 0(Dify 内) | 🟡 Wired |
| **Helicone** | Apache 2.0 | ✅(主部分) | Proxy(改 base_url) | 0 | 🟡 Wired |
| Phoenix(Arize) | Elastic 2.0 | ✅ | OTLP / SDK | 中 | — |
| Opik(Comet) | Apache 2.0 | ✅ | SDK | 中 | — |
| Lunary | Apache 2.0 | ✅ | SDK | 中 | — |
| LangSmith | Proprietary | ❌(SaaS) | SDK | 中 | 不考虑 |
| OpenLLMetry / Traceloop | Apache 2.0 | ✅ | OTel auto-instr | 低 | 候选 |

### 4.2 推荐组合(已论证)

`docs/observability/helicone-vs-langfuse.md` 给出的结论照搬:

```
[Dify 应用层调用]  → Dify 内置 Langfuse trace
[novel_analyzer/llm/client 直连] → Helicone proxy → Helicone UI(自存自看)
```

**两套 UI 都接受**,简化版部署。流量覆盖 100%。

### 4.3 路线图

| 阶段 | 时间 | 任务 |
|---|---|---|
| **Stage 1**(本周内) | 1 天 | Helicone proxy 启用 → `NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE` 配置 → 一次 imitation 跑 → trace 验真 |
| Stage 1(本周内) | 1 天 | Langfuse self-host 拉起 + Dify 集成开关打开 |
| Stage 2(下月) | 2-3 天 | Langfuse 评估面板 + dataset 接 pairwise_eval |
| Stage 3(后续) | 评估 | 是否上 OpenLLMetry 接 OTel 给独立 Tempo/Jaeger |

### 4.4 反对决策

- **不上 Phoenix / Opik / Lunary**:Langfuse 已覆盖
- **不上 LangSmith**:SaaS-only,数据出境
- **不双写 Trace**:Helicone → Langfuse OTLP 转发原则上可行,但**先单存,等真用起来再考虑统一**

---

## 5. 分类 3:记忆面(Long-term Memory)

### 5.1 候选对比

| 系统 | License | 自托管 | 模型适配 | 接入成本 | 当前 |
|---|---|---|---|---|---|
| **Letta**(原 MemGPT) | Apache 2.0 | ✅ | OpenAI-compat | 中(REST) | 🔴 Planned |
| Mem0 | Apache 2.0 | ✅ | OpenAI-compat | 低(SDK) | 🔴 Planned |
| Zep | Apache 2.0 | ✅ | 任意 | 低(REST) | 🔴 Planned |
| Cognee | Apache 2.0 | ✅ | OpenAI-compat | 中 | — |
| MemoryScope(阿里) | Apache 2.0 | ✅ | DashScope 优先 | 中 | — |

### 5.2 内核 vs 外部记忆

我们已有的内部记忆模块(`memory_consolidation_service`、`memory_assembler_service`、`arc_memory_service`)做的是**章节内容**的分层记忆,目标是 carry-over。

外部记忆系统(Letta/Mem0/Zep)做的是**会话级**的 episodic memory,场景是 chatbot 跨 session 记住用户。

**两者不冲突**。外部记忆面的真正候选场景是:

1. **Reader Q&A 跨 session**:读者问"上次咱们聊到主角的 X 决策,我现在想问 Y" → 需要会话记忆
2. **Writer Copilot 项目记忆**:作家说"按我上周给你的 character bible" → 需要项目级长期记忆
3. **Dify 应用内**:Dify 自己的 conversation memory 较弱

### 5.3 推荐:Letta PoC,Mem0 备选

**主选 Letta**,理由:

- 论文出身(MemGPT, NeurIPS 2023),抽象最完整(core / archival / recall memory 三层)
- 自带 ADE 管理面板 + REST API,运维友好
- OpenAI-compatible

**备选 Mem0**,理由:

- 接入更轻(单 SDK 调用)
- 无独立服务,可作为内存轻量记忆层
- 适合"先验证有没有用"

**Zep 不选**:重于 graph + 时序,与我们的内核 graph_service 重叠多,价值递减。

### 5.4 路线图

| 阶段 | 时间 | 任务 |
|---|---|---|
| Stage 2(下月) | 1 周 | Letta self-host 拉起 + Reader Q&A 一个 session 接入 PoC |
| Stage 2(下月) | 1 周 | 评估 Letta vs 内核 memory_assembler 在长 session 下的覆盖差 |
| Stage 3(2-3 个月) | 决策 | 真要不要把 Letta 作为 Reader/Writer 跨 session 默认记忆 |

### 5.5 反对决策

- **不替换内核 memory_consolidation/assembler**:Loom Phase 1-2 已经做完,目标不同
- **不接 Zep**:与 graph_service 重叠
- **不接 MemoryScope**:DashScope 偏向

---

## 6. 分类 4:推理基础设施(Embedding / Rerank / LLM Serving)

### 6.1 候选对比

| 系统 | License | 用途 | 接入 | 当前 |
|---|---|---|---|---|
| **TEI**(HF) | Apache 2.0 | embedding + rerank serving | http format=openai/tei | ✅ GA |
| Infinity(Michael Feil) | MIT | embedding serving | http | — |
| BGE-M3 native | Apache 2.0 | 模型本身 | ONNX 已用 | ✅ GA |
| vLLM | Apache 2.0 | LLM serving | OpenAI-compat | — |
| llama.cpp | MIT | 本地 LLM | OpenAI-compat | — |
| Voyage / Cohere / Jina API | 商业 | embedding + rerank | API | 不考虑 |

### 6.2 现状

`embedding/service.py` 与 `rerank/service.py` 已支持 `backend=onnx | http | openai | tei`,可平滑切换。`scripts/dev/docker-compose.tei.yml` 已经有完整 TEI compose。`docs/foundation-optimization/tei-integration-postmortem-20260512.md` 记录了切换教训。

### 6.3 路线图

| 阶段 | 时间 | 任务 |
|---|---|---|
| **Stage 1** | 持续 | 维持 ONNX 主路 + TEI 备选;按 GPU 可用性切换 |
| Stage 2(下月) | 1 周 | bge-m3 三路融合(dense+sparse+colbert)在 TEI 上验证 |
| Stage 3(后续) | 评估 | vLLM 自托管 LLM 路径(若 deepseek-v4-flash 出现限流/价格压力) |

### 6.4 反对决策

- **不接商业 embedding API**(Voyage/Cohere/Jina API):预研已决,见 `foundation-optimization-priority-research-20260512.md`
- **不切 Infinity**:与 TEI 功能等价,无切换收益
- **不自训 embedding**:预研已决

---

## 7. 分类 5:读者 UI 面(Chat-style UI shells)

### 7.1 候选对比

| 系统 | License | 自托管 | 多模型 | 适合"读者端" | 当前 |
|---|---|---|---|---|---|
| **OpenWebUI** | MIT | ✅ | ✅ | 中(偏开发者) | 🔴 Planned |
| **LobeChat** | Apache 2.0 | ✅ | ✅ | 高(社群分发) | 🔴 Planned |
| LibreChat | MIT | ✅ | ✅ | 中 | 🔴 Planned |
| AnythingLLM | MIT | ✅ | ✅ | 低(更像知识库) | — |
| Big-AGI | MIT | ✅ | ✅ | 低 | — |

### 7.2 自研 vs 外部

我们已有 `apps/web/reader/<branch_id>` Reader Studio:三栏布局 + 防剧透 + 4 视角评分 + 1-5 星反馈。**自研已经覆盖核心读者场景。**

外部 UI shell 真正的价值:**社群分发**(把"AI-小说-阅读"以一种通用 chat UI 的形态分发给非自家用户)。

### 7.3 路线图

| 阶段 | 时间 | 任务 |
|---|---|---|
| Stage 3(2-3 个月后,有商业化场景再启动) | — | LobeChat 评估接 Dify 应用 |

**暂时不动**。当前 Reader Studio 的覆盖足够。

### 7.4 反对决策

- **不替换 Reader Studio**:防剧透 + 4 视角评分这些自研功能 chat UI shell 不会做
- **不接 AnythingLLM / Big-AGI**:与我们的图谱/索引层不兼容

---

## 8. 时间线总览

```
                Stage 1 (本月)         Stage 2 (下月)         Stage 3 (3 个月+)
编排面          Dify GA + n8n GA       Dify Reader Q&A        LiteLLM Proxy 评估
观测面          Helicone 启用          Langfuse evaluator     OpenLLMetry 评估
                Langfuse self-host
推理基础设施    TEI 维持               bge-m3 三路融合         vLLM 评估
记忆面          —                      Letta PoC              Letta 决策
读者 UI         —                      —                      LobeChat 评估
```

---

## 9. 风险与回滚

| 风险 | 触发条件 | 回滚 |
|---|---|---|
| Helicone proxy 增加延迟 > 200ms | trace 后实测 P95 增加 | 关 `LLM_BASE_URL_OVERRIDE`,直连 LLM |
| Dify 应用变 critical path | Dify 故障导致 Writer Copilot 不可用 | iframe 改 fallback 到内置 chat;Dify 不进入内核流量 |
| Letta 与内核 memory 冲突 | PoC 中发现状态打架 | 仅在 Reader 跨 session 用,不入 Writer 主链 |
| n8n webhook 噪声污染 | webhook 不可达导致 imitation 卡 | 已实现 fire-and-forget + 2s timeout(`runtime/notify.py`) |
| Langfuse self-host 卷大 | 6 容器部署运维成本 | Stage 1 仅启 worker + web,关 ClickHouse 替换为 PG |

---

## 10. 与内核的接口承诺

外部对接**不允许**:

- 改动 `novel_analyzer/services/*` 的接口签名(只能加,不能改)
- 修改 `novel_analyzer/llm/prompts.py`
- 引入新的 ORM
- 引入新的 IDP(身份层 IdentityMiddleware 已 v3 落)

外部对接**只能**通过:

- HTTP API(`apps/api/app/routers/*`)
- LLM proxy(`llm_base_url_override`)
- Webhook(`runtime/notify.py`)
- Dify iframe(`apps/web/src/components/writer/CopilotIframe.tsx`)
- 文件输出(`export_service`)

这条界线是 v2/v3 plan 已经定的,本路线图不动。

---

## 11. 配套文档

- 本路线对应 checklist:`docs/strategy/external-integration-checklist-20260514.md`
- 本路线对应架构图:`docs/architecture/external-integration-architecture-20260514.md`
- 内核侧前提:`docs/strategy/kernel-sota-gap-assessment-20260514.md`
- 历史决策:
  - `docs/observability/helicone-vs-langfuse.md`
  - `docs/research/fastgpt-vs-dify.md`
  - `.sisyphus/plans/foundation-optimization-priority-research-20260512.md`

---

## 12. 下次评估触发条件

任意一条达成时回到本文档审视:

1. Stage 1 全部 GA(Helicone 启用 + Langfuse 启用 + Dify Writer Copilot 真上线 + n8n daily-eval 真跑)
2. 内核冲刺 §10 Week 1-2 完成
3. 出现新的成熟开源记忆/编排系统(>10k stars,90 天活跃)
4. 现有 Wired 系统出现严重缺陷(性能 / 安全 / 维护)

否则维持本路线 6 周不动。
