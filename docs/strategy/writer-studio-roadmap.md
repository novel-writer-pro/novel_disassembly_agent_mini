# Writer Studio Roadmap

> 商业化推进的整体路线图。覆盖 v1（已撤回）→ v2（PR #8 merged）→ v3（PR #9，本期）→ v4+ 候选。
> 每个阶段都遵循「框架优先、零侵入业务核心、可降级」三原则。

## 目标谱

| 阶段 | 用户体感 | 技术达成 |
|------|---------|---------|
| **v1** | （未发布，被 v2 取代） | 重自研版本 — 撤回 |
| **v2** | 作家有独立编辑器入口 `/writer/*` + Dify Chatbot iframe | Infra 三件套就位（Dify/n8n/Langfuse），DB 加 `owner_user_id` 列，UI shell 与旧 Workbench 隔离 |
| **v3** | 作家在 Dify 问问题，后端能识别 user_id；imitation 跑完收到 n8n 通知；Helicone trace 覆盖 imitation 主流量 | IdentityMiddleware + service 层 owner_user_id WHERE + n8n hook + LLM proxy env override |
| **v4** | （候选）Reader 端 UI；FastAPI cutover；prompt 资产管理 | 见下方候选清单 |

## v1 → v2 转向（已发生）

**v1 原计划**：自研 SSE chat、自研 prompt 版本管理、Langfuse SDK 业务侵入、FastAPI 大迁移
**v2 实际做**：Dify 替代自研 chat、Dify Prompt Studio 替代自研版本、Langfuse 走 Dify 内置、FastAPI 推迟

砍掉自研工作 60%，时间从 2-3 个月压到 1 个月（实际工时）。

## v2 → v3 闭环（本期）

v2 retro 暴露 4 个 gap：
1. ❌ Imitation 主流量看不见 → ✅ v3 T5/T6 Helicone proxy
2. ❌ X-User-Id 没透传 → ✅ v3 T1/T2/T3 三层透传
3. ❌ n8n 是孤岛 → ✅ v3 T4 完成 hook
4. ❌ owner_user_id 形同虚设 → ✅ v3 T2 service WHERE 子句

闭环后第一次出现"alice 看不到 bob 的书 + 跑完仿写 alice 收到通知"的能力。

## v4 候选（按优先级建议）

### 优先级 A — 用户已能感受到的扩展

| 候选 | 解决什么 |
|------|---------|
| **Reader 端 UI** | v2/v3 都只服务作家。读者跳章/防剧透 Q&A 是另一条产品线 |
| **多用户管理 UI** | v3 用 X-User-Id 字符串透传，没有用户切换/管理界面；目前依赖 Dify systemVariables 单向传 |

### 优先级 B — 商业化前必须的运维

| 候选 | 解决什么 |
|------|---------|
| **Prompt 资产托管** | imitation prompts 仍在 `prompts.py` 中。改 prompt 要发版。Dify Prompt Studio 一次搬完后续可热更新 |
| **Langfuse + Helicone trace 合并** | 两套 UI 各看一半。需要 Helicone OTLP forward 到 Langfuse |
| **secret 管理** | Langfuse keys / Dify token / Helicone key 仍 hardcode 在 .env.local。需要 Vault / SOPS / 1Password CLI |
| **prod / staging 拆分** | 当前所有 docker-compose 都是 dev only。prod 需要 backup、HA、cost cap |

### 优先级 C — 内部体验提升

| 候选 | 解决什么 |
|------|---------|
| **FastAPI surface** | main.py 仍 2503 行 WSGI。FastAPI 落地后 IdentityMiddleware 自动接入所有 endpoint |
| **每用户配额 / 计费** | 目前无任何 quota；商业化必须 |
| **Reader 端的 Letta/Mem0 长期记忆** | 跨章节阅读连续性 |

## 不做（明确放弃）

| 拒绝项 | 理由 |
|--------|------|
| Coze SaaS 替代 Dify | 数据上云不符合 self-host 约束 |
| LangFlow / Bisheng | 与 Dify 同质，引入二个 framework 维护成本 |
| OpenManus 替代 LangGraph | 自主性太强，imitation 需要精细控制 |
| PostgreSQL Row-Level Security | 内部 dogfood 阶段不需要，等 v4 商业化再讨论 |

## 决策时间线

- **2026-05-13**：v2 plan 写定，确认 framework-first 方向
- **2026-05-14 上午**：v2 全部代码 commit，PR #8 提交
- **2026-05-14 上午**：v2 PR #8 merged
- **2026-05-14 下午**：v3 plan 写定（业务闭环优先）
- **2026-05-14 下午**：v3 全部代码 commit，PR #9 提交（本期）
- **下一步（待操作员）**：在 docker-enabled 环境跑 docs/runbook/business-loop.md 6 步 smoke

## 引用文档

- `.sisyphus/plans/writer-studio-v2-framework-first.md` — v2 plan
- `.sisyphus/plans/writer-studio-v3-business-loop.md` — v3 plan
- `docs/runbook/business-loop.md` — v3 端到端验证 runbook
- `docs/runbook/v3-pickup-checklist.md` — v3 pickup 步骤清单
- `docs/process/writer-studio-v3-handoff.md` — session 交接
- `docs/research/fastgpt-vs-dify.md` — 框架选型决策
- `docs/observability/helicone-vs-langfuse.md` — observability 评估
