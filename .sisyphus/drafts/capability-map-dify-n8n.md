# Capability Map: Dify / n8n / Langfuse 能吃下多少现有需求

> 目的：决定哪些自研代码可以删掉，哪些必须保留。
> 原则：能用现成的就不自研。不动现有服务一行代码。

---

## 一、Dify 能直接替代的能力（强）

| 我们的需求 | Dify 原生能力 | 替代度 | 节省的工作 |
|-----------|-------------|--------|----------|
| AI 对话 UI（流式/取消/重试） | Chatbot 应用 + iframe/chat-bubble/JS widget 嵌入 | **95%** | 删掉原计划 T15、T16 大半 |
| Langfuse 接入 | Dify Monitoring 设置里填 3 个 key 即可 | **100%** | 删掉原计划 T12 业务集成层 |
| Prompt 版本管理 | Prompt Studio + 历史版本 + A/B | **80%** | imitation prompts 搬进去就有版本了 |
| RAG / 知识库 | 内置 Knowledge Base + 多种 retrieval 策略 | **70%** | 我们已有 RAG，但**新流程**可直接用 |
| 多工作区 | Workspace 隔离 + API Key | **60%** | T22 内部多用户大头解决，library scoping 仍要 |
| Workflow 编排 | Workflow / Chatflow 节点编辑器 | **50%** | 简单链路可视化拖拽 |
| Tool / Function calling | 内置 tool + 自定义 API tool | **70%** | 把"查章节"做成 Dify tool 即可 |
| API 暴露 | 每个应用自动有 OpenAI-compatible API | **100%** | 前端直接 fetch dify api |

### Dify 能做、但不建议挪的

| 能力 | 为什么不挪 |
|------|----------|
| 整本仿写 imitation pipeline | 我们的 LangGraph 已经很复杂，挪过去等于重写 |
| Loom 信号 / 节奏分析 | 是数值计算和 SQL，不是 LLM 链路，Dify 不擅长 |
| 章节切分 / 整理 | 同上 |

---

## 二、n8n 能直接替代的能力

| 需求 | n8n 节点 | 替代度 |
|------|---------|--------|
| Pipeline 完成通知（飞书/Slack/邮件） | Webhook trigger + Slack/邮件节点 | **100%** |
| 每日评测日报 | Schedule trigger + HTTP + Markdown 输出 | **100%** |
| 上传新书 → 自动启动 pipeline | Webhook + HTTP + Wait for completion | **90%** |
| 内容审核人工介入 | Webhook + IF + Manual approval | **80%** |
| 跨系统同步（Notion/Obsidian） | 原生集成节点 | **100%** |
| Stripe webhook → 配额更新 | 原生 Stripe 节点（未来计费用） | **100%** |
| LangChain 链路 | 自带 LangChain 节点 | **70%**（简单的可以挪） |

### n8n 不适合做的

- 章节分析 pipeline（强 stateful，n8n 的 workflow execution 适合无状态/短）
- whole-book-imitation 多 agent 编排（吞吐与 DB 状态耦合超出 n8n 范围）
- Q&A retrieval（同步、低延迟，没必要进 workflow 引擎）

---

## 三、Langfuse 接入路径

**两条路并行**：

1. **走 Dify 内置集成**：所有经过 Dify 的 LLM 调用自动 trace（零代码）
2. **直连 SDK**：现有 Python 代码（如果有 LLM 调用不经过 Dify）用 Langfuse Python SDK 装在 `novel_analyzer/llm/client.py` 外层（保留计划中的 T12，但优先级降低）

---

## 四、必须保留的自研

| 模块 | 理由 |
|------|------|
| **`novel_analyzer/services/*`**（26 个 service） | 领域逻辑，Dify/n8n 不做小说分析 |
| **`novel_analyzer/workflows/run_graph.py`** | LangGraph 章节分析 pipeline，Dify 表达不了 |
| **Loom 信号 / 节奏 / 张力分析** | 数值计算 + SQL，Dify 不擅长 |
| **章节切分 / 整理** | 文本处理强逻辑 |
| **作家 Studio 编辑器画布**（T13） | 差异化 UI，Dify 不提供编辑器 |
| **Loom 信号侧栏**（T14） | 同上 |
| **library scoping by user_id**（T22） | DB schema 改动，Dify workspace 解决不了 owner 问题 |

---

## 五、决策建议

### 砍掉/弱化的原计划任务

| 原 Task | 决策 | 替代方案 |
|---------|-----|---------|
| T8-T11 FastAPI 迁移 | **延后**（不动现有 WSGI） | 让旧服务继续跑，新需求走 Dify |
| T12 Langfuse SDK | **降优先级** | 优先靠 Dify 内置集成 |
| T15 AI 副驾对话面板 | **取消** | iframe 嵌入 Dify Chatbot |
| T16 SSE UX 打磨 | **降级到 Dify 自带** | 我们只在编辑器里做"打开对话框"按钮 |
| T18 Cutover | **取消** | 不需要 |

### 保留的原计划任务

| Task | 状态 |
|------|------|
| T1 Contract tests | ✅ 已完成 |
| T2 trace_context | ✅ 已完成（保留为未来集成预留） |
| T7 session_* 字段审计 | 保留（脚本，零侵入） |
| T17 session_* 冻结 | 保留（schema 锁定） |
| T22 library scoping | 保留（owner_user_id migration） |
| T13 编辑器画布 | 保留（差异化） |
| T14 Loom 侧栏 | 保留（差异化） |

### 新增任务

| New Task | 内容 |
|---------|------|
| **N1** | Dify self-host docker-compose（infra 文件，零业务侵入） |
| **N2** | n8n self-host docker-compose（infra 文件，零业务侵入） |
| **N3** | Langfuse self-host docker-compose（已在原计划 T5） |
| **N4** | Dify "Writer Copilot" Chatbot 应用配置（Prompt + Tool + KB） |
| **N5** | Dify "Reader Q&A" Chatbot 应用（reader 端预备） |
| **N6** | n8n workflow: pipeline-complete-notify |
| **N7** | n8n workflow: daily-eval-report |
| **N8** | Writer Studio iframe 嵌入 Dify Chatbot |

---

## 六、收益估算

- 自研代码减少：**~60%**（删 T15/T16/T12 的大头）
- 部署组件增加：**3 个** docker-compose（Dify/n8n/Langfuse），都是开源、自托管、零业务侵入
- 时间预算：原 2-3 个月 → **1-1.5 个月**
- 风险：3 个外部依赖的运维负担（但都有大社区，文档齐全）
