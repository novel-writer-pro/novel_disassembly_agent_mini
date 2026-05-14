# Writer Studio v3 — Session Handoff

> 写于 PR #9 提交前。给下一位接手者读这一份就能继续推进。

## 一句话状态

v2 PR #8 已 merge，v3 PR #9 OPEN 等 review。代码层闭环全部就位（92/92 测试绿），手动验证步骤已写成 runbook + checklist，**唯一阻塞是操作员在 docker-enabled 环境跑 6 步 smoke**。

## 在这个 session 里发生了什么

1. **v2 retro 暴露 4 个 gap**（imitation 主流量看不见、X-User-Id 没透传、n8n 是孤岛、owner_user_id 形同虚设）
2. **interview 收敛到「业务闭环优先」**（其他 3 条候选优先级延后）
3. **Plan v3 写定** → 10 task + 3 verification，零侵入硬约束
4. **v3 实施踩到一个 plan 没预见的坑**：用户决定后扩大 T2 scope 允许触碰 main.py 的 `_library_payload` helper（非 dispatch 表）
5. **6 个 atomic commit 落地** + F1 zero-regression APPROVE + PR #9 OPEN
6. **本 commit（这份文档）**：补 roadmap / checklist / handoff / changelog 收口

## 关键决策记录

| 决策 | 时间 | 影响范围 |
|------|------|---------|
| Helicone 经 base_url env override 而非 SDK 接入 | T6 设计期 | 业务代码 0 langfuse/helicone import |
| n8n hook 写在 `run_in_sandbox` 末尾 return 之前 | T4 实施期 | imitation 算法 0 改动，仅 12 行 hook 块 |
| 主受力选「业务闭环」，砍掉「prompt 资产迁移」 | interview | imitation prompts 留 prompts.py，未搬 Dify Studio |
| T2 扩大 scope 允许触碰 `_library_payload` | T2 实施中 | main.py +6 行（dispatch 0 改） |
| 不实际部署 Helicone，留给 docker-enabled 操作员 | T5 实施期 | infra/helicone/README.md 替代 docker-compose.yml |

## 6 个 atomic commits（与 PR #9 一致）

```
9459733  Document end-to-end business loop with troubleshooting runbook
e70caf7  Allow LLM base_url override via env so Helicone proxy can intercept
eb02fdc  Fire-and-forget n8n notification when imitation pipeline completes
6535845  Forward X-User-Id header from Dify tools to ai-books backend
f5d8168  Wire owner_user_id from X-User-Id header through library listing
ffcfa9b  Add ASGI identity middleware reading X-User-Id into RequestContext
```

每个都带完整 Lore Commit Protocol trailers（Constraint/Rejected/Confidence/Tested/Directive）。

## 下一会话接手指引

### 如果你要 review PR #9
- PR url：https://github.com/novel-writer-pro/novel_disassembly_agent_mini/pull/9
- 关注点：F1 verification 已通过，业务零渗透 grep 已确认
- 已知妥协：T2 scope 扩到 main.py helper（plan 已记录）

### 如果你要在 docker 环境跑 v3 smoke
- 入口：`docs/runbook/v3-pickup-checklist.md`
- 配套：`docs/runbook/business-loop.md`（症状排查）
- 时间预估：60 分钟（首次配置）

### 如果你要起 v4
- 候选优先级见 `docs/strategy/writer-studio-roadmap.md` 「v4 候选」章节
- 我的推荐：A 档先做 Reader 端 UI（用户能感受到的扩展）
- B 档运维项做之前必须等 v3 manual smoke 跑通

### 如果代码出问题
- F1 验证证据：`.sisyphus/evidence/F1-zero-regression.txt`（v2 那次的，v3 也用同样审计逻辑）
- 一键回归：`make v2-test && make v3-smoke`（46+21 = 67 测试，约 22 秒）
- 关键约束 grep：
  ```bash
  # 业务代码不应有 langfuse/dify/helicone import
  grep -rn "import langfuse\|import dify\|import helicone" novel_analyzer/services novel_analyzer/agent novel_analyzer/workflows
  # 应为 0 行
  ```

## 已知遗留问题（不阻塞 PR #9 但 v4 要处理）

| 问题 | 严重度 |
|------|-------|
| owner_user_id scoping 仅覆盖 `/api/library`，其他 endpoint 仍全可见 | medium — 等 FastAPI surface |
| Helicone trace 与 Langfuse trace 分两套 UI | low — Helicone 自带 OTLP forward，是开关问题 |
| Dify systemVariables 模板语法跨版本可能改名 | low — runbook 已警示 |
| imitation hook 的 status 字段直接用 `quality_verdict` 字符串 | low — n8n 那边只看是否 success，可后续规范化 |
| `make v3-smoke` 依赖手动 export env | low — 可加 `.env.v3-smoke.example` |

## 心智模型（给下一会话）

```
用户输入
  ↓
[apps/web /writer iframe (v2)]
  ↓
[Dify Chatbot (v2 N4)]
  ↓ Custom Tool with X-User-Id header (v3 T3)
  ↓
[ai-books WSGI :8001]
  ↓ HTTP_X_USER_ID environ (v3 T2)
  ↓ owner_user_id WHERE clause
  ↓
[novel_analyzer/services]
  ↓ build_chat_model() (v3 T6)
  ↓ NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE
  ↓
[Helicone proxy :8585 (v3 T5)] → ClickHouse trace
  ↓ 透明转发
[LLM provider]

并行：
[whole_book_imitation_service.run_in_sandbox 末尾 (v3 T4)]
  ↓ notify_pipeline_complete()
  ↓ N8N_WEBHOOK_PIPELINE_COMPLETE_URL
  ↓
[n8n :5678 webhook (v2 N6)] → Slack/邮件/echo

并行：
[Dify 内置 Langfuse 集成 (v2 N5)]
  ↓
[Langfuse :3030 traces]
```

`v2 X` = v2 PR 提供，`v3 X` = v3 PR 提供。

## 联系方式

- v2/v3 plan 历史：`.sisyphus/plans/writer-studio-*.md`
- v2 retro：见 v2 PR #8 description
- v3 retro：见本文档
