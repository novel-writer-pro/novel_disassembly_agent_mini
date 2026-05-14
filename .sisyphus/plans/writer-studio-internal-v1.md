# Writer Studio v1 — 内部 Dogfood 商业化就绪计划

## TL;DR

> **Quick Summary**: 把现有 novel-analyzer 从「分析师工作台」打磨成「作家优先 + 内部 dogfood 就绪」的形态：完成 FastAPI 迁移收口、上 Langfuse 被动观察成本、独立 `/writer/*` 编辑器优先 UI、修流式体验、收敛 imitation 的 session_* 字段膨胀、本地评估 n8n 外围编排。**不做**对外计费、SDK、公开发布。
>
> **Deliverables**:
> - 完成 WSGI → FastAPI 收口（`apps/api/app/main.py` 退役为薄入口）
> - Langfuse 自托管 + LLM 边界自动 trace（成本/延迟/Prompt 版本可见）
> - 独立 `/writer/*` 路由组：编辑器画布 + Loom 信号侧栏 + AI 副驾对话 + 流式 + 版本树
> - SSE 流式体验打磨（取消、重试、进度可视化、断线恢复）
> - imitation `session_*` 字段使用率审计 + 冻结 + 弃用通道
> - 内部多用户支持（header-based，per-user library scoping，非 IDP）
> - n8n 本地 docker-compose + 2 个外围流程跑通（pipeline 完成通知 + 每日评测日报）
> - Contract tests + 烟雾测试 runbook（保护已锁行为）
>
> **Estimated Effort**: Medium-Large（2-3 人 / 2-3 个月）
> **Parallel Execution**: YES — 3 waves + final verification
> **Critical Path**: T1（contract tests）→ T8-T11（FastAPI 迁移）→ T18（cutover）→ F1-F4

---

## Context

### Original Request
> 帮我们看看我们的 UI/API 是否符合商业推广的要求，如果不满足应该怎么优化⋯⋯ 是不是有一些能力可以放到 n8n+langfuse 上⋯⋯ 对外的界面上的能力，应该怎么体现，让对应的作家助手，还有读者⋯⋯ 方便更好地用好我们的这个助手。

### Interview Summary

**Key Discussions**（5 个关键问题已锁定）:
- **商业模式**：先内部 dogfood，**不对外**——所以**不做** Stripe / 公开 SDK / 计费 UI
- **第一阶段目标用户**：**作家优先**（Writer Studio）。Reader UI 推迟到 v2
- **Langfuse / n8n 部署形态**：**本地 docker-compose 评估期**，云 vs 自托管延后决定
- **现状最痛的点**（按优先级）：
  1. UI 对新用户上手太难
  2. imitation 的 session_* 字段膨胀失控
  3. 长任务的流式 UX 体验不好
  4. WSGI 单文件 main.py 难维护
- **团队/时间**：2-3 人 / 2-3 个月

**Research Findings**（基于实地代码扫描）:
- Backend：`apps/api/app/main.py` = 2630 行单文件 WSGI dispatch；`apps/api/app/routers/*` 是**未完成**的 FastAPI 迁移（writer/loom/chapters/library/pipeline/quality/risk_review/steering_character/whole_book/import_recovery 共 10 个路由文件）
- Frontend：Next.js 15 + React 18 + Ant Design 5；8 个页面全走 711 行 `WorkbenchApp.tsx` shell
- Workflows：LangGraph 在 `novel_analyzer/workflows/run_graph.py`
- Observability：DB 模型有 `trace_id` 占位字段，`analysis_service.py` 有 `_prompt_metrics` 雏形，**完全没有** Langfuse / OpenTelemetry
- Auth：全代码库 0 行（`auth/Authorization/tenant/api_key/jwt/user_id` 一个都搜不到）
- 关键现有 endpoints：`/api/import`、`/api/start`、`/api/recovery`、`/api/run-snapshot`、`/api/branch-snapshot`、`/api/chapter-bundle`、`/api/chapter-qa-context`、`/api/chapter-source`、`/api/chapter-jobs`、`/api/library`、`/api/job-events`、`/api/review-clusters`、`/api/review-cluster-update`、`/api/review-batch-execute`、`/api/pipeline/start-range`、`/api/pipeline/status`、`/api/pipeline/runs`、`/api/pipeline/progress-stream`、`/api/runtime-health`、`/api/provider-health`、`/api/quality-dashboard`、`/api/whole-book-imitation-readiness`、`/api/whole-book-imitation-run`、`/api/search-branch`、`/api/ask-branch`、`/api/ask-branch-stream`、`/api/branch-exports`、`/api/download`

### Self-Review (Metis-style gap analysis)

**自我识别的 gap & 已在计划里加固的护栏**：
- Gap: 没明确"行为锁定先于重构"——加在 T1（contract tests 先于任何迁移动作）
- Gap: 没考虑流式 UX 在 reverse proxy（nginx）下的兼容性——加在 T16 的 QA 场景里
- Gap: imitation 字段膨胀如果直接删可能炸——T17 走"先冻结 + 用量统计 + 弃用通道"的安全路径
- Gap: Langfuse 接入点必须**只在 LLM provider 边界**，避免渗透业务代码——T12 的 must-not-do 锁定
- Gap: FastAPI 切换若一次性 cut over 风险大——T8-T11 增量迁移、T18 才 cutover
- Gap: 内部多用户没要求 IDP，但要避免后续接 IDP 时大改——T22 用 `X-User-Id` header + 中间件抽象，未来接 IDP 只换中间件实现

---

## Work Objectives

### Core Objective
让产品从「单租户分析师工作台」演进为「作家优先 + 内部多用户 dogfood 就绪 + 成本/性能可观测 + 后端可扩展」的形态，为下一步对外发布（Reader 端 + 计费 + 公共 API）打好地基。

### Concrete Deliverables
- **D1 后端**：`apps/api` 上 FastAPI、`main.py` 退役为 ≤100 行薄入口
- **D2 可观测**：Langfuse 自托管跑起来，所有 LLM 调用有 trace、cost、prompt version
- **D3 UI**：`/writer/*` 路由组上线，编辑器画布 + Loom 侧栏 + AI 副驾 + 流式 + 版本树 + 新手引导
- **D4 流式**：`/api/ask-branch-stream` 与 imitation 长任务的 UX 在前端完整覆盖（取消/重试/进度/断线恢复）
- **D5 字段瘦身**：imitation 输出 schema 冻结，`session_*` 字段中**0 调用率**字段进入弃用窗口
- **D6 内部多用户**：`X-User-Id` header + library scoping + per-user trace tag
- **D7 n8n 评估**：本地 docker-compose 起来，2 个外围流程（pipeline-complete 通知 + 每日 eval 日报）跑通
- **D8 质量保障**：契约测试 + 烟雾 runbook + 回归基线

### Definition of Done
- [ ] `apps/api/app/main.py` 不再包含路由 dispatch（仅 ASGI 启动入口）
- [ ] 任意 LLM 调用在 Langfuse UI 可见 trace + token 数 + 成本估算
- [ ] `/writer/{branch_id}` 路由可独立访问，**不**经过旧 Workbench shell
- [ ] 长任务前端有「取消」按钮、断线恢复提示、进度数字
- [ ] 至少 1 个 `session_*` 字段进入弃用通道（标 `deprecated_in: v1`）
- [ ] 两个内部 user 同时登录看到的 library 互相隔离
- [ ] n8n 本地 UI 能看到至少 2 个 active workflow，最近一次执行成功
- [ ] 新增的 contract tests + smoke 至少 30 条断言，CI 全绿

### Must Have
- 行为锁定先于重构（contract tests 在 FastAPI 迁移前完成）
- FastAPI 增量迁移 + 单一 cutover 时间点
- Langfuse 仅在 LLM provider 边界拦截，业务代码 0 渗透
- 内部多用户用 header-based stub，但中间件抽象到位（未来换 IDP 不改业务）
- Writer Studio UI 与旧 Workbench 完全隔离路由（共存到 v2 再决定下线）

### Must NOT Have（Guardrails — AI-slop 防护）
- ❌ **不做**用户注册/登录/JWT/OAuth/Stripe 等对外 IDP 与计费（用户明确：内部 dogfood）
- ❌ **不做** Reader 端 UI（推迟到 v2）
- ❌ **不做** SDK 发布、API 公网网关、限流计费
- ❌ **不引入新 ORM/新数据库**——继续 PostgreSQL + SQLAlchemy + Alembic
- ❌ **不引入新前端框架**——继续 Next.js + AntD + React，**不**改 Vue/Tailwind 全家桶
- ❌ **禁止**给 imitation 加任何新的 `session_*` 字段（计划期内冻结）
- ❌ **禁止**给现有领域代码加 Langfuse 装饰器（必须只在 provider/LLM 边界）
- ❌ **禁止**生成"防御性"巨型 try/except 包装一切（保留原本的错误传播路径）
- ❌ **禁止**为 future-proof 而抽象——n8n 的 webhook 接口具体到 1-2 个，不做"通用 webhook 网关"
- ❌ **禁止**为了"覆盖率好看"加 mock 一切的浅测试（contract tests 必须打真 endpoint，烟雾跑真 LLM）
- ❌ **禁止**重命名/重组 `novel_analyzer/` 内既有模块结构（与本次 scope 无关）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — 所有验证都是 agent 执行的。

### Test Decision
- **Infrastructure exists**: YES（pytest + alembic 已就位）
- **Automated tests**: TDD-light（关键迁移类任务先写 contract test 锁行为；UI 类任务用 playwright QA 场景代替 unit）
- **Framework**: pytest（后端） + Playwright（前端 QA） + bash + curl（API 烟雾）
- **TDD 适用任务**：T1, T8-T11（路由迁移）, T17（字段冻结）, T22（多用户隔离）
- **后置 QA-only 任务**：UI 类（T13-T15, T19-T20）、docker-compose 类（T5, T21）、观测类（T12）

### QA Policy
每个任务必须包含：
- ≥1 happy-path scenario
- ≥1 failure/edge-case scenario
- 证据保存到 `.sisyphus/evidence/task-{N}-{slug}.{ext}`

工具映射：
- **UI**：Playwright（点击、断言 DOM、截图）
- **API**：`curl` + `jq` 断言字段
- **CLI/服务**：`interactive_bash`（tmux）跑 `docker compose`、查日志
- **Library**：`python -c` REPL 验

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — 立即开工，全部并行):
├── T1: Contract test 基线 + main.py 行为快照 [unspecified-high]
├── T2: 请求级 trace context 中间件契约（types-only） [quick]
├── T3: SSE 服务端 helper + 客户端 hook 脚手架 [quick]
├── T4: /writer/* 路由组 + Studio 布局骨架 [visual-engineering]
├── T5: Langfuse 自托管 docker-compose [unspecified-high]
├── T6: 内部用户身份方案（X-User-Id 中间件契约） [quick]
└── T7: imitation session_* 字段使用率分析脚本 [unspecified-high]

Wave 2 (Core — 依赖 Wave 1，最大并行):
├── T8:  迁移 import/start/recovery 路由到 FastAPI [unspecified-high]   (依赖 T1, T2, T6)
├── T9:  迁移 chapter/snapshot/library 路由到 FastAPI [unspecified-high] (依赖 T1, T2, T6)
├── T10: 迁移 review/pipeline 路由到 FastAPI [unspecified-high]         (依赖 T1, T2, T6)
├── T11: 迁移 qa/imitation/quality 路由到 FastAPI [unspecified-high]    (依赖 T1, T2, T6)
├── T12: Langfuse SDK 接入 LLM provider 边界 [deep]                     (依赖 T5)
├── T13: Writer Studio 编辑器画布组件 [visual-engineering]              (依赖 T4)
├── T14: Writer Studio Loom 信号侧栏 [visual-engineering]               (依赖 T4)
├── T15: Writer Studio AI 副驾对话面板 [visual-engineering]             (依赖 T3, T4)
├── T16: SSE 流式 UX 打磨（取消/重试/断线/进度） [deep]                 (依赖 T3)
└── T17: imitation session_* 字段冻结 + 弃用通道 [deep]                 (依赖 T7)

Wave 3 (Integration — 依赖 Wave 2):
├── T18: Cutover：main.py 退役、ASGI 入口收口 [deep]                    (依赖 T8-T11)
├── T19: Writer Studio 版本树 + diff/accept/reject [visual-engineering] (依赖 T13)
├── T20: Writer Studio 新手引导 + 空状态 [visual-engineering]           (依赖 T13-T15)
├── T21: n8n 本地 docker-compose + 2 外围流程 [unspecified-high]        (依赖 T18)
├── T22: 内部多用户：library scoping + trace tag [deep]                 (依赖 T18, T6)
└── T23: Contract tests + 烟雾 runbook + 回归基线 [unspecified-high]    (依赖 T18, T22)

Wave FINAL (4 个 review agent 并行 → 用户 OK):
├── F1: Plan compliance audit (oracle)
├── F2: Code quality review (unspecified-high)
├── F3: Real manual QA (unspecified-high)
└── F4: Scope fidelity check (deep)

Critical Path: T1 → T8/T9/T10/T11 → T18 → T22/T23 → F1-F4 → 用户 okay
Max Concurrent: 7 (Wave 1) / 10 (Wave 2) / 6 (Wave 3)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| T1   | —         | T8, T9, T10, T11, T23 |
| T2   | —         | T8, T9, T10, T11, T22 |
| T3   | —         | T15, T16 |
| T4   | —         | T13, T14, T15, T19, T20 |
| T5   | —         | T12 |
| T6   | —         | T8, T9, T10, T11, T22 |
| T7   | —         | T17 |
| T8-11| T1, T2, T6| T18 |
| T12  | T5        | (independent) |
| T13  | T4        | T19, T20 |
| T14  | T4        | T20 |
| T15  | T3, T4    | T20 |
| T16  | T3        | (independent) |
| T17  | T7        | (independent) |
| T18  | T8-T11    | T21, T22, T23 |
| T19  | T13       | (independent) |
| T20  | T13-T15   | (independent) |
| T21  | T18       | (independent) |
| T22  | T18, T6   | T23 |
| T23  | T18, T22  | F1-F4 |

### Agent Dispatch Summary

| Wave | Tasks | Routing |
|------|-------|---------|
| 1    | 7     | T1/T5/T7→`unspecified-high`, T2/T3/T6→`quick`, T4→`visual-engineering` |
| 2    | 10    | T8-T11→`unspecified-high`, T12/T16/T17→`deep`, T13-T15→`visual-engineering` |
| 3    | 6     | T18/T22→`deep`, T19-T20→`visual-engineering`, T21/T23→`unspecified-high` |
| FINAL| 4     | F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high` (+playwright), F4→`deep` |

---

## TODOs

- [ ] 1. **Contract test 基线 + main.py 行为快照**

  **What to do**:
  - 在 `tests/contract/` 新建 `test_main_wsgi_contract.py`，针对 `apps/api/app/main.py` 当前所有 GET endpoint 跑一次基线请求（用 fixture 准备一个最小 branch），断言 status code、关键字段存在、`/api/meta` 返回字段完整
  - POST endpoint 选 5 个高频（import/start/recovery/review-cluster-update/whole-book-imitation-run）做合同断言，用 mock LLM provider
  - 把响应的 JSON shape 用 `jsonschema` 或 `pytest-snapshot` 锁住
  - 输出 `tests/contract/baseline.snapshot.json`，commit 进仓库

  **Must NOT do**:
  - ❌ 不引入新的 ORM 或测试框架
  - ❌ 不修改 main.py 任何业务逻辑（纯只读测试）
  - ❌ 不写"覆盖一切"的浅测——每个断言必须能在 FastAPI 迁移后真的触发回归

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 跨业务面合同测试需理解多个 endpoint 语义
  - **Skills**: `test-driven-development` — 锁行为先于重构

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T8, T9, T10, T11, T23
  - **Blocked By**: None

  **References**:
  - `apps/api/app/main.py:1231` — WSGI `application()` dispatch（需要枚举每个 path）
  - `docs/api-current-surface.md` — 当前真实可用的 endpoint 清单
  - `tests/` — 现有测试结构与 fixture 风格参考

  **Acceptance Criteria**:
  - [ ] `pytest tests/contract/ -v` 全绿，至少 30 个断言
  - [ ] `tests/contract/baseline.snapshot.json` 存在并被 git track

  **QA Scenarios**:
  ```
  Scenario: 基线全绿
    Tool: Bash
    Steps:
      1. 启动 WSGI server（python -m apps.api.app.main 或等价）
      2. 跑 pytest tests/contract/ -v --tb=short
      3. 断言 exit code 0、收集 ≥30 passed
    Expected: all pass, snapshot 文件生成
    Evidence: .sisyphus/evidence/task-1-contract-baseline.txt

  Scenario: 故意改坏一处验证测能抓到
    Tool: Bash
    Steps:
      1. 暂时把 /api/meta 一个字段改名（local-only patch）
      2. 重跑 pytest tests/contract/
      3. 断言至少 1 个测试 FAIL 且报错信息指向被改的字段
      4. 还原 patch
    Expected: 测试能精确定位回归
    Evidence: .sisyphus/evidence/task-1-contract-detect.txt
  ```

  **Commit**: YES — `test(api): lock current main.py contract before fastapi migration`

- [ ] 2. **请求级 trace context 中间件契约**

  **What to do**:
  - 在 `novel_analyzer/runtime/trace_context.py` 新建 `RequestContext` dataclass：`request_id`, `user_id`, `tenant_id`（暂时 None）, `started_at`
  - 提供 `contextvars`-based getter/setter（`get_current_context()` / `with_context()`）
  - **只**写 types + helpers，**不**接到 FastAPI（T8-T11 才接）
  - 写单元测试覆盖嵌套 context、async 边界

  **Must NOT do**:
  - ❌ 不引入 OpenTelemetry SDK（Langfuse 在 T12 接，避免双 trace 系统）
  - ❌ 不在业务代码任何地方调用 `with_context()`（只是定义形状）

  **Recommended Agent Profile**:
  - **Category**: `quick` — Reason: 纯 utility，无外部依赖

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T8, T9, T10, T11, T22
  - **Blocked By**: None

  **References**:
  - `novel_analyzer/database/models.py:157` — 已有的 `trace_id` 字段，命名要对齐

  **Acceptance Criteria**:
  - [ ] `pytest tests/runtime/test_trace_context.py -v` 全绿
  - [ ] `grep -r "trace_context" novel_analyzer/services` → 0 行（确认无渗透）

  **QA Scenarios**:
  ```
  Scenario: contextvars 嵌套与 async 隔离
    Tool: Bash
    Steps:
      1. pytest tests/runtime/test_trace_context.py::test_async_isolation -v
    Expected: pass, 不同 task 看到不同 context
    Evidence: .sisyphus/evidence/task-2-context-async.txt

  Scenario: 业务代码无渗透
    Tool: Bash
    Steps:
      1. grep -rn "from novel_analyzer.runtime.trace_context" novel_analyzer/services novel_analyzer/agent novel_analyzer/workflows
    Expected: 0 matches
    Evidence: .sisyphus/evidence/task-2-no-leak.txt
  ```

  **Commit**: YES — `feat(api): add request-trace context middleware contract`

- [ ] 3. **SSE 服务端 helper + 客户端 hook 脚手架**

  **What to do**:
  - 后端 `novel_analyzer/runtime/sse.py`：`stream_events(generator) → ASGI response`，处理 `:keepalive`、`event: error`、`event: done`、retry id
  - 前端 `apps/web/src/hooks/useSSE.ts`：参数 `{ url, body, onMessage, onError, onDone }`，返回 `{ status, cancel, lastEvent }`
  - 写单元测试：服务端 generator 抛错时正确发 `event: error`；客户端断线 reconnect 用 last-event-id

  **Must NOT do**:
  - ❌ 不直接接到现有 endpoint（T16 才接）
  - ❌ 不引入 `eventsource-polyfill`（现代浏览器 fetch + ReadableStream 即可）

  **Recommended Agent Profile**:
  - **Category**: `quick` — Reason: 边界清晰的 utility

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T15, T16
  - **Blocked By**: None

  **References**:
  - `apps/api/app/main.py:2181` — 现有 `/api/pipeline/progress-stream` 的 SSE 实现参考
  - `apps/api/app/main.py:2494` — `/api/ask-branch-stream` 的现有 streaming

  **Acceptance Criteria**:
  - [ ] 后端单测 + 前端 vitest（如已配）/ tsc 全绿
  - [ ] 提供 README 短范例：3 行服务端 + 5 行客户端

  **QA Scenarios**:
  ```
  Scenario: 服务端正常流 → done
    Tool: Bash (curl)
    Steps:
      1. 起一个 demo route 用 stream_events 推 3 条 + done
      2. curl -N http://localhost:8000/__sse-demo
      3. 断言收到 4 行（3 data + done）
    Expected: 顺序正确
    Evidence: .sisyphus/evidence/task-3-sse-happy.txt

  Scenario: 服务端 generator 抛错
    Tool: Bash (curl)
    Steps:
      1. demo route 模拟 generator 第二条后 raise
      2. curl -N
      3. 断言收到 1 条 data + 1 条 event: error，连接关闭
    Expected: error event payload 含原 exception 类型
    Evidence: .sisyphus/evidence/task-3-sse-error.txt
  ```

  **Commit**: YES — `feat(streaming): SSE helper + client hook scaffolding`

- [ ] 4. **`/writer/*` 路由组 + Studio 布局骨架**

  **What to do**:
  - 在 `apps/web/src/pages/writer/` 新建 `[branchId].tsx`、`index.tsx`，**完全独立**于 `WorkbenchApp.tsx`
  - 新建 `apps/web/src/components/writer/StudioLayout.tsx`：3 栏布局（左 248px 大纲/角色/风格，中弹性编辑器画布，右 360px 信号/AI 副驾切换）
  - 顶部导航条：branch 切换、保存状态、模式切换（草稿/仿写/对照）
  - 用 AntD 现有组件（`Layout`, `Sider`, `Tabs`, `Drawer`），**不**引入新设计系统
  - 空状态、加载态、断网态 placeholder 三件套
  - Mock 数据驱动（暂不接真 API）

  **Must NOT do**:
  - ❌ 不复用 `WorkbenchApp.tsx`、`WorkbenchLayout.tsx`、`WritingPage.tsx`（隔离心智模型）
  - ❌ 不引入 Tailwind / CSS-in-JS 新方案
  - ❌ 不动 `apps/web/src/pages/writing.tsx`（旧入口共存）
  - ❌ 不写"未来通用"的 layout 抽象，只服务 Writer Studio

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — Reason: 编辑器优先 UI 心智，对布局节奏敏感
  - **Skills**: `frontend-ui-ux` — 三栏编辑器结构、空状态打磨

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T13, T14, T15, T19, T20
  - **Blocked By**: None

  **References**:
  - `apps/web/src/components/WorkbenchApp.tsx:53-66` — 旧的 workspace 路由表，**反例**学习
  - `apps/web/src/pages/writing.tsx` — 现有 writing 页面（仅参考字段，不复用）
  - `apps/web/src/types/loom.ts` — Loom 信号类型，T14 会用

  **Acceptance Criteria**:
  - [ ] `next dev` 后 `http://localhost:4173/writer/demo-branch` 可访问且 200
  - [ ] DOM 结构包含 `[data-testid="studio-layout"]`、`studio-sider-left`、`studio-canvas`、`studio-sider-right`
  - [ ] `WorkbenchApp` 在 `/writer/*` 路径下**不**被加载（DevTools 断言）

  **QA Scenarios**:
  ```
  Scenario: 路由独立加载
    Tool: Playwright
    Preconditions: next dev 已启动
    Steps:
      1. goto http://localhost:4173/writer/demo-branch
      2. 等 [data-testid="studio-layout"] 可见
      3. 断言页面源码不含 "WorkbenchApp" / "WorkbenchLayout" 字符串
      4. 截图
    Expected: 三栏可见 + 旧 shell 不出现
    Evidence: .sisyphus/evidence/task-4-studio-route.png

  Scenario: 空状态展示
    Tool: Playwright
    Steps:
      1. goto /writer/__empty
      2. 断言显示"还没有作品，点击导入开始"提示 + 主 CTA 按钮
    Expected: 空态可达，CTA 可点击
    Evidence: .sisyphus/evidence/task-4-empty-state.png
  ```

  **Commit**: YES — `feat(web): writer studio route group + layout shell`

- [ ] 5. **Langfuse 自托管 docker-compose**

  **What to do**:
  - 新建 `infra/langfuse/docker-compose.yml`：langfuse-web + langfuse-worker + Postgres + ClickHouse + Redis（按官方推荐）
  - `.env.example` 增加 `LANGFUSE_HOST=http://localhost:3000`、`LANGFUSE_PUBLIC_KEY=`、`LANGFUSE_SECRET_KEY=`（占位）
  - 写 `infra/langfuse/README.md`：3 步起步（启动、初始化 admin、生成 API key）
  - 启动后用 curl 验证 `/api/public/health` = 200
  - **不**接业务代码（T12 才接）

  **Must NOT do**:
  - ❌ 不与 novel-analyzer 主 docker network 合并（保持隔离便于开关）
  - ❌ 不写"production"配置（generic dev only，标注 self-host prod 是后续工作）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: docker-compose 调试可能踩坑

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T12
  - **Blocked By**: None

  **References**:
  - 官方文档：`https://langfuse.com/self-hosting/docker-compose` — 跟随官方版本号
  - `.env.example` — 现有 env 文件结构参考

  **Acceptance Criteria**:
  - [ ] `docker compose -f infra/langfuse/docker-compose.yml up -d` 后 5 个容器全 healthy
  - [ ] `curl -s http://localhost:3000/api/public/health` 返回 200
  - [ ] README 步骤可被零经验工程师执行通过

  **QA Scenarios**:
  ```
  Scenario: 启动流程
    Tool: interactive_bash (tmux)
    Steps:
      1. docker compose -f infra/langfuse/docker-compose.yml up -d
      2. sleep 30
      3. docker compose ps → 断言所有 service 状态 running
      4. curl -fsS http://localhost:3000/api/public/health
    Expected: 全绿，health 200
    Evidence: .sisyphus/evidence/task-5-langfuse-up.txt

  Scenario: 优雅关闭
    Tool: Bash
    Steps:
      1. docker compose -f infra/langfuse/docker-compose.yml down
      2. docker volume ls | grep langfuse  → 卷仍在（保留数据）
    Expected: 容器停止、卷保留
    Evidence: .sisyphus/evidence/task-5-langfuse-down.txt
  ```

  **Commit**: YES — `chore(infra): self-hosted langfuse docker-compose`

- [ ] 6. **内部用户身份方案（X-User-Id 中间件契约）**

  **What to do**:
  - 在 `apps/api/app/middleware/identity.py` 新建 ASGI middleware：
    - 读 `X-User-Id` header（无值时 fallback `"local-default"`，开发用）
    - 注入到 T2 的 `RequestContext`
    - 暴露 `Depends(get_current_user)` 给路由用
  - **不**做加密/签名/JWT（内部 dogfood 阶段是声明式的）
  - 文档明确：未来接 IDP 只换 middleware 实现，业务代码用 `get_current_user` 不变

  **Must NOT do**:
  - ❌ 不引入 OAuth / Cognito / Auth0 / 任何 IDP（明确推迟）
  - ❌ 不做 session 表/cookie

  **Recommended Agent Profile**:
  - **Category**: `quick` — Reason: 边界清晰、契约导向

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T8, T9, T10, T11, T22
  - **Blocked By**: None

  **References**:
  - `novel_analyzer/runtime/trace_context.py`（T2 产出）— 注入点

  **Acceptance Criteria**:
  - [ ] `pytest tests/api/middleware/test_identity.py -v` 全绿（≥4 case：有值/无值/空字符串/特殊字符）
  - [ ] FastAPI demo route 验证 `Depends(get_current_user)` 工作

  **QA Scenarios**:
  ```
  Scenario: header 注入与读取
    Tool: Bash (curl)
    Steps:
      1. 启动 demo FastAPI app
      2. curl -H "X-User-Id: alice" http://localhost:8000/__whoami
      3. 断言返回 {"user_id":"alice"}
    Expected: 正确读取
    Evidence: .sisyphus/evidence/task-6-whoami.txt

  Scenario: 缺失 header fallback
    Tool: Bash (curl)
    Steps:
      1. curl http://localhost:8000/__whoami
      2. 断言返回 {"user_id":"local-default"}
    Expected: fallback 生效
    Evidence: .sisyphus/evidence/task-6-fallback.txt
  ```

  **Commit**: YES — `feat(api): X-User-Id middleware (internal multi-user stub)`

- [ ] 7. **imitation `session_*` 字段使用率分析脚本**

  **What to do**:
  - 写 `scripts/audit_imitation_fields.py`：
    - 静态扫描：`grep -rn "session_" apps/ novel_analyzer/ tests/` 收集所有 session_* 字段名
    - 动态扫描：sample 一个最近 imitation run 的输出 JSON，对每个字段统计是否有下游引用
    - 输出 `docs/imitation/session-fields-audit.md`：表格列出 `field_name | first_seen | last_modified | static_refs | dynamic_consumers | status (active/orphan/unknown)`
  - 不**做**实际删除——只产生报告，T17 才动手

  **Must NOT do**:
  - ❌ 不修改 imitation 任何业务代码
  - ❌ 不调用 LLM 来"分析"字段含义（纯静态 + 数据驱动）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 跨仓代码扫描 + 报告组织

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 1）
  - **Blocks**: T17
  - **Blocked By**: None

  **References**:
  - `CHANGELOG.md:1112-1158` — `session_*` 字段历次新增点（追溯起源）
  - `novel_analyzer/services/whole_book_imitation_service.py` — 字段产生处

  **Acceptance Criteria**:
  - [ ] `python scripts/audit_imitation_fields.py` 退出码 0
  - [ ] `docs/imitation/session-fields-audit.md` 存在，至少列出 20 个 session_* 字段
  - [ ] 报告中至少标出 1 个 `status=orphan`（0 静态引用且 0 动态消费）

  **QA Scenarios**:
  ```
  Scenario: 报告生成
    Tool: Bash
    Steps:
      1. python scripts/audit_imitation_fields.py
      2. wc -l docs/imitation/session-fields-audit.md → ≥ 20
      3. grep -c "orphan" docs/imitation/session-fields-audit.md → ≥ 1
    Expected: 报告完整且含至少 1 个 orphan
    Evidence: .sisyphus/evidence/task-7-audit-report.txt

  Scenario: 重跑幂等
    Tool: Bash
    Steps:
      1. 第二次跑同一脚本，diff 输出
    Expected: 报告内容一致（除时间戳）
    Evidence: .sisyphus/evidence/task-7-idempotent.txt
  ```

  **Commit**: YES — `chore(imitation): session_* field usage analyzer`

- [ ] 8. **迁移 import / start / recovery 路由到 FastAPI**

  **What to do**:
  - 把 `apps/api/app/main.py` 中 `/api/import`、`/api/start`、`/api/recovery`、`/api/mock/import` 的 dispatch 分支搬到 `apps/api/app/routers/import_recovery.py`（已存在，补全）
  - 用 `Depends(get_current_user)` 拿到 user_id（T6），传给 service 层（service 暂不用，只在 trace 里打 tag）
  - 用 T2 的 RequestContext 注入 trace_id
  - 维持响应 JSON shape **逐字节兼容**（用 T1 的 contract test 验证）
  - main.py 中保留旧 dispatch 暂不删（T18 才退役）

  **Must NOT do**:
  - ❌ 不改 service 层任何代码
  - ❌ 不改响应 schema、字段名、错误码
  - ❌ 不引入新依赖

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 路由迁移需对齐多处细节

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2，与 T9/T10/T11/T12-T17 并行）
  - **Blocks**: T18
  - **Blocked By**: T1, T2, T6

  **References**:
  - `apps/api/app/main.py:1280-1411` — import/start/recovery 现有 dispatch
  - `apps/api/app/routers/import_recovery.py` — 已有 FastAPI 路由文件骨架（补全即可）
  - `tests/contract/test_main_wsgi_contract.py`（T1 产出）— 验证基线

  **Acceptance Criteria**:
  - [ ] FastAPI app 加载这 3 个路由后，contract test 全绿（同时打 wsgi 和 fastapi 端点对比）
  - [ ] 路由内出现 `Depends(get_current_user)` 与 `get_current_context()` 调用

  **QA Scenarios**:
  ```
  Scenario: 双跑对比
    Tool: Bash (curl)
    Steps:
      1. 起 wsgi 在 :8000，fastapi 在 :8001
      2. 同样 payload POST /api/import 到两个端点
      3. diff 响应（除 timestamp / id 类波动字段）
    Expected: shape 逐字节一致
    Evidence: .sisyphus/evidence/task-8-double-run.txt

  Scenario: user header 透传
    Tool: Bash (curl)
    Steps:
      1. curl -H "X-User-Id: alice" -X POST :8001/api/import ...
      2. 检查日志/trace 中 user_id=alice
    Expected: tag 正确
    Evidence: .sisyphus/evidence/task-8-user-tag.txt
  ```

  **Commit**: YES — `refactor(api): migrate import/start/recovery to fastapi`

- [ ] 9. **迁移 chapter / snapshot / library 路由到 FastAPI**

  **What to do**:
  - 搬迁 `/api/run-snapshot`、`/api/branch-snapshot`、`/api/chapter-bundle`、`/api/chapter-qa-context`、`/api/chapter-source`、`/api/chapter-jobs`、`/api/library`、`/api/job-events`、`/api/chapter-job-events` 到 `routers/library.py` + `routers/chapters.py`（已存在，补全）
  - 同样的 user/trace 注入约束
  - main.py 旧 dispatch 保留至 T18

  **Must NOT do**:
  - ❌ 不改 service 调用方式
  - ❌ 不改 query string 参数名

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 多 endpoint，careful 工作量

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T18
  - **Blocked By**: T1, T2, T6

  **References**:
  - `apps/api/app/main.py:1412-1611` — chapter/snapshot/library/job-events dispatch
  - `apps/api/app/routers/library.py` — 已有骨架
  - `apps/api/app/routers/chapters.py` — 已有骨架

  **Acceptance Criteria**:
  - [ ] contract test 双跑对比通过
  - [ ] 9 个 endpoint 全部在 FastAPI 路由表中可见

  **QA Scenarios**:
  ```
  Scenario: 全 endpoint 双跑对比
    Tool: Bash
    Steps:
      1. 起 wsgi:8000 和 fastapi:8001
      2. 跑 scripts/double_run_diff.py（参考 contract test）覆盖 9 个 GET endpoint
    Expected: 0 mismatches（除允许的波动字段）
    Evidence: .sisyphus/evidence/task-9-double-run.txt

  Scenario: 错误路径一致
    Tool: Bash (curl)
    Steps:
      1. curl 不存在的 branch_id 到两个端点
      2. 对比 status code 与错误 JSON
    Expected: 一致
    Evidence: .sisyphus/evidence/task-9-error-shape.txt
  ```

  **Commit**: YES — `refactor(api): migrate chapter/snapshot/library to fastapi`

- [ ] 10. **迁移 review / pipeline 路由到 FastAPI**

  **What to do**:
  - 搬迁 `/api/review-clusters`、`/api/review-cluster-summary`、`/api/review-cluster-history`、`/api/review-cluster-update`、`/api/review-batch-execute`、`/api/review-batch-history`、`/api/pipeline/start-range`、`/api/pipeline/status`、`/api/pipeline/runs`、`/api/pipeline/progress-stream` 到 `routers/risk_review.py` + `routers/pipeline.py`
  - **关键**：`/api/pipeline/progress-stream` 是 SSE，使用 T3 的 `stream_events` helper 重写但保持事件 shape 不变

  **Must NOT do**:
  - ❌ 不改 SSE 事件 schema、event name、retry 间隔
  - ❌ 不改 pipeline 触发的 background task 机制

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 含 SSE 流式细节

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T18
  - **Blocked By**: T1, T2, T6

  **References**:
  - `apps/api/app/main.py:1612-2268` — review/pipeline dispatch
  - `apps/api/app/routers/risk_review.py`、`routers/pipeline.py`
  - T3 产出的 `novel_analyzer/runtime/sse.py`

  **Acceptance Criteria**:
  - [ ] contract test 双跑通过
  - [ ] `/api/pipeline/progress-stream` 在 fastapi 侧 SSE 事件序列与 wsgi 一致

  **QA Scenarios**:
  ```
  Scenario: SSE 事件流对齐
    Tool: Bash
    Steps:
      1. 起一个 mock pipeline run
      2. curl -N :8000/api/pipeline/progress-stream?... > wsgi.log &
      3. curl -N :8001/api/pipeline/progress-stream?... > fastapi.log &
      4. wait, diff wsgi.log fastapi.log（标准化时间字段后）
    Expected: 事件序列一致
    Evidence: .sisyphus/evidence/task-10-sse-diff.txt

  Scenario: review-cluster-update 写路径
    Tool: Bash (curl)
    Steps:
      1. POST 一次到 fastapi 端点
      2. GET review-cluster-history 验证写入
    Expected: 写入可见
    Evidence: .sisyphus/evidence/task-10-write-path.txt
  ```

  **Commit**: YES — `refactor(api): migrate review/pipeline to fastapi`

- [ ] 11. **迁移 qa / imitation / quality 路由到 FastAPI**

  **What to do**:
  - 搬迁 `/api/runtime-health`、`/api/provider-health`、`/api/quality-dashboard`、`/api/whole-book-imitation-readiness`、`/api/whole-book-imitation-run`、`/api/search-branch`、`/api/ask-branch`、`/api/ask-branch-stream`、`/api/branch-exports`、`/api/download` 到 `routers/quality.py` + `routers/whole_book.py` + `routers/writer.py`
  - `/api/ask-branch-stream` 同样用 T3 SSE helper

  **Must NOT do**:
  - ❌ 不改 imitation 输出字段（含 `session_*` 系列；T17 才动）
  - ❌ 不改 download 的 path 参数语义

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: 涉及 imitation 大签名，careful

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T18
  - **Blocked By**: T1, T2, T6

  **References**:
  - `apps/api/app/main.py:2269-2630` — qa/imitation/quality dispatch
  - `apps/api/app/routers/quality.py`、`routers/whole_book.py`、`routers/writer.py`

  **Acceptance Criteria**:
  - [ ] contract test 双跑通过
  - [ ] imitation run 输出字段名清单完全一致（用 jq 列字段名对比）

  **QA Scenarios**:
  ```
  Scenario: imitation 输出 schema 字节对齐
    Tool: Bash
    Steps:
      1. POST 同一个 sample request 到两个端点
      2. jq 'keys_unsorted' 对两份 response，diff
    Expected: 完全一致
    Evidence: .sisyphus/evidence/task-11-imitation-keys.txt

  Scenario: ask-branch-stream 流式
    Tool: Bash
    Steps:
      1. curl -N POST :8001/api/ask-branch-stream ...
      2. 收集 ≥3 条 data event
    Expected: 流式正常输出
    Evidence: .sisyphus/evidence/task-11-ask-stream.txt
  ```

  **Commit**: YES — `refactor(api): migrate qa/imitation/quality to fastapi`

- [ ] 12. **Langfuse SDK 接入 LLM provider 边界**

  **What to do**:
  - 在 `novel_analyzer/llm/`（找到唯一的 LLM 调用边界——provider client/wrapper）外层装一层 `with_langfuse_trace()` decorator，参数：`request_id`（来自 T2 RequestContext）、`user_id`（来自 T6）、`name`（调用点逻辑名）
  - 用 Langfuse Python SDK：每次 LLM call → `generation` span，记录 `model`、`input`、`output`、`usage`（prompt_tokens / completion_tokens）
  - 只有当 `LANGFUSE_PUBLIC_KEY` 设置时才启用，否则 no-op（CI 不需要装 Langfuse）
  - 不动业务代码：所有调用点不感知 Langfuse 的存在

  **Must NOT do**:
  - ❌ 不在 `novel_analyzer/services/`、`novel_analyzer/agent/`、`novel_analyzer/workflows/` 任何地方 `import langfuse`
  - ❌ 不替换/包装 LangChain 的 callback handler（保持现有）
  - ❌ 不做 prompt template 上传（仅观测，prompt versioning 留给后续）
  - ❌ 不强依赖 Langfuse 服务可用（连接失败必须不影响业务请求）

  **Recommended Agent Profile**:
  - **Category**: `deep` — Reason: 边界设计与无渗透原则同时满足
  - **Skills**: `verification-before-completion` — 验证渗透 0、失败降级正常

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: (independent)
  - **Blocked By**: T5

  **References**:
  - `novel_analyzer/llm/` — provider client 所在
  - `novel_analyzer/services/analysis_service.py:286` — 已有的 `_prompt_metrics` 模式（参考 metric 命名）
  - Langfuse Python SDK：`https://langfuse.com/docs/sdk/python`

  **Acceptance Criteria**:
  - [ ] 在本地起的 Langfuse UI 中能看到至少 1 个 trace（跑一次 ask-branch）
  - [ ] `grep -rn "langfuse" novel_analyzer/services novel_analyzer/agent novel_analyzer/workflows` → 0 行
  - [ ] 无 Langfuse 环境变量时，业务请求时延无可观测性引入的退化（基线对比 < 5%）
  - [ ] Langfuse 服务关闭时业务仍正常（手动 docker stop 验证）

  **QA Scenarios**:
  ```
  Scenario: trace 在 UI 可见
    Tool: interactive_bash + Bash
    Steps:
      1. docker compose up langfuse, 配 PUBLIC_KEY/SECRET_KEY
      2. 起后端 + 前端
      3. 发一次 /api/ask-branch
      4. curl Langfuse API 列 traces，断言含 user_id + request_id tag
    Expected: trace 完整含 generation span + token usage
    Evidence: .sisyphus/evidence/task-12-trace-visible.png

  Scenario: Langfuse 不可用降级
    Tool: Bash
    Steps:
      1. docker stop langfuse-web
      2. 发一次 /api/ask-branch
      3. 断言 200 OK + 业务结果正常
      4. 检查日志：仅 warning 级别 Langfuse failure
    Expected: 业务无中断
    Evidence: .sisyphus/evidence/task-12-degraded.txt

  Scenario: 业务代码 0 渗透
    Tool: Bash
    Steps:
      1. grep -rn "langfuse" novel_analyzer/services novel_analyzer/agent novel_analyzer/workflows tests
    Expected: 0 matches
    Evidence: .sisyphus/evidence/task-12-no-leak.txt
  ```

  **Commit**: YES — `feat(observability): langfuse at LLM provider boundary`

- [ ] 13. **Writer Studio 编辑器画布组件**

  **What to do**:
  - 新建 `apps/web/src/components/writer/EditorCanvas.tsx`：基于 `<textarea>` 增强（暂不引入 ProseMirror/Slate，避免重型依赖）
  - 章节段落分块渲染、行号、autosave 防抖（500ms）
  - **流式占位区**：当 AI 在生成时，cursor 处插入只读"流式 ghost"段落，完成后变成可接受/拒绝
  - 段落级 hover 工具条：解释 / 重写 / 仿写 / 提问（按钮先 stub，T15 接 AI）
  - keyboard：Cmd+S 保存、Cmd+Enter 触发当前段落 AI 操作
  - mock data 驱动

  **Must NOT do**:
  - ❌ 不引入 ProseMirror、Slate、Lexical、TipTap（v1 用 textarea）
  - ❌ 不实现协同编辑（CRDT/yjs 等）
  - ❌ 不做 markdown 渲染切换（保持纯文本）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering` — Reason: 编辑器交互节奏感
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T19, T20
  - **Blocked By**: T4

  **References**:
  - `apps/web/src/pages/writing.tsx` — 现有 writing 字段（不复用，仅参考字段）
  - T4 的 `StudioLayout` — 容器约束

  **Acceptance Criteria**:
  - [ ] `[data-testid="editor-canvas"]` 在 `/writer/demo-branch` 可见
  - [ ] autosave 500ms 后 mock 端点收到 patch（用 mock fetch 验证）
  - [ ] 段落 hover 4 个工具按钮 stub 可点击不报错

  **QA Scenarios**:
  ```
  Scenario: 输入与 autosave
    Tool: Playwright
    Steps:
      1. goto /writer/demo-branch
      2. 在编辑器输入"测试段落"
      3. 等 600ms
      4. 断言 mock fetch 被调用 1 次（patch payload 含输入文本）
      5. 截图
    Expected: autosave 触发
    Evidence: .sisyphus/evidence/task-13-autosave.png

  Scenario: 段落 hover 工具条
    Tool: Playwright
    Steps:
      1. hover 到第 2 段
      2. 断言 4 个按钮（解释/重写/仿写/提问）visible
      3. 点"解释" → 断言 mock 被调
    Expected: 工具条出现且响应
    Evidence: .sisyphus/evidence/task-13-toolbar.png
  ```

  **Commit**: YES — `feat(writer-studio): editor canvas with paragraph tools`

- [ ] 14. **Writer Studio Loom 信号侧栏**

  **What to do**:
  - 新建 `apps/web/src/components/writer/LoomSignalsPanel.tsx`，挂在 T4 右侧栏
  - 拉 `/api/loom/signals?branch_id&chapter_index`（已有，见 `apps/web/src/lib/loom-api.ts`），展示：节奏、张力、伏笔密度、风格对照
  - 数值用进度条 + tag color（红/黄/绿，复用 `WritingPage` 的 `SignalTag` 风格）
  - 章节切换时刷新；当前章节由 `EditorCanvas` 通过 prop/context 提供
  - 失败态：显示"信号暂不可用，仿写仍可继续"

  **Must NOT do**:
  - ❌ 不复用 `apps/web/src/pages/writing.tsx` 的 page 级组件（只复用类型 + tag 样式）
  - ❌ 不在面板内做计算（数据全靠 API）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T20
  - **Blocked By**: T4

  **References**:
  - `apps/web/src/lib/loom-api.ts` — fetchLoomSignals 已存在
  - `apps/web/src/types/loom.ts` — `LoomSignals` 类型
  - `apps/web/src/pages/writing.tsx:9-13` — `SignalTag` 风格参考

  **Acceptance Criteria**:
  - [ ] 信号面板在 right sider 可见，4 个指标显示
  - [ ] 章节切换时面板刷新（mock data 驱动）

  **QA Scenarios**:
  ```
  Scenario: 信号正常展示
    Tool: Playwright
    Steps:
      1. goto /writer/demo-branch?chapter=2
      2. 断言 [data-testid="loom-panel"] 可见
      3. 断言 4 个指标 tag 各自 visible（节奏/张力/伏笔/风格）
      4. 截图
    Expected: 全部 visible，颜色按值映射
    Evidence: .sisyphus/evidence/task-14-loom-panel.png

  Scenario: API 失败降级
    Tool: Playwright
    Steps:
      1. mock fetch 返回 500
      2. 刷新
      3. 断言提示"信号暂不可用"，编辑器仍可用
    Expected: 优雅降级
    Evidence: .sisyphus/evidence/task-14-loom-fallback.png
  ```

  **Commit**: YES — `feat(writer-studio): loom signals side panel`

- [ ] 15. **Writer Studio AI 副驾对话面板**

  **What to do**:
  - 新建 `apps/web/src/components/writer/CopilotChat.tsx`，挂在 T4 右侧栏（与 Loom 用 Tabs 切换）
  - 用 T3 的 `useSSE` hook 接 `/api/ask-branch-stream`
  - 上下文注入：当前章节 + 选中段落（来自 EditorCanvas 的 selection）
  - 消息列表：用户/AI 交替，AI 消息流式追加，引用章节链接（点击在 EditorCanvas 跳到该章）
  - 发送时禁用按钮，流式时显示"取消"按钮（调 useSSE.cancel）

  **Must NOT do**:
  - ❌ 不复用 `BranchQaPanel.tsx`（那是 reader 心智，组件粒度也不对）
  - ❌ 不实现多会话历史持久化（v1 内存级即可）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: T20
  - **Blocked By**: T3, T4

  **References**:
  - `apps/web/src/components/BranchQaPanel.tsx` — **反例**参考（不复用，但学交互细节）
  - T3 的 `useSSE` hook
  - `apps/api/app/main.py:2494` — `/api/ask-branch-stream` shape

  **Acceptance Criteria**:
  - [ ] 对话面板 Tab 切换 Loom ↔ Copilot 工作
  - [ ] 发送消息后流式追加可见
  - [ ] 取消按钮在流式期间可见、可点

  **QA Scenarios**:
  ```
  Scenario: 流式对话
    Tool: Playwright
    Steps:
      1. goto /writer/demo-branch
      2. 切到 Copilot tab
      3. 输入"这章的伏笔有哪些？"，发送
      4. 等首字到达（< 3s）
      5. 断言 AI 消息 textContent 长度持续增长（轮询 5 次）
      6. 等流结束，截图
    Expected: 流式输出可见 + 引用章节链接
    Evidence: .sisyphus/evidence/task-15-copilot-stream.png

  Scenario: 取消生成
    Tool: Playwright
    Steps:
      1. 发送一个长问题
      2. 流式开始 ≥1s 后点"取消"
      3. 断言流停止 + 已收到的内容保留
    Expected: cancel 工作，无错误 toast
    Evidence: .sisyphus/evidence/task-15-cancel.png
  ```

  **Commit**: YES — `feat(writer-studio): AI copilot chat with streaming`

- [ ] 16. **SSE 流式 UX 打磨（取消/重试/进度/断线恢复）**

  **What to do**:
  - 强化 T3 产出的 `useSSE`：加 `lastEventId`-based reconnect、指数退避（200ms/500ms/1s/2s/5s 上限）
  - 进度可视化：把后端 `event: progress`（imitation 长任务）的百分比 → 顶部细进度条
  - 错误分类：网络（自动重连）/ 业务（弹 toast 不重连）/ 限流（提示请稍后）
  - 在 `EditorCanvas` 段落工具按钮（T13）+ `CopilotChat`（T15）+ pipeline progress page 上统一接入
  - 关键：nginx/反向代理的 `proxy_buffering off` + `X-Accel-Buffering: no` 头由后端发出（T10 的 SSE 路由也补）

  **Must NOT do**:
  - ❌ 不实现客户端 polling fallback（保持 SSE 单一路径）
  - ❌ 不动后端 event schema（仅消费层增强）

  **Recommended Agent Profile**:
  - **Category**: `deep` — Reason: 网络边缘情况多
  - **Skills**: `systematic-debugging`、`verification-before-completion`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: (independent)
  - **Blocked By**: T3

  **References**:
  - T3 的 `useSSE` hook
  - `apps/api/app/main.py:2181` — pipeline/progress-stream 现有事件 schema
  - 后端响应需补的 header：`X-Accel-Buffering: no`、`Cache-Control: no-cache`

  **Acceptance Criteria**:
  - [ ] 模拟断线 1 次，自动重连成功 + 进度不回退
  - [ ] 取消按钮在流式期间响应 < 200ms
  - [ ] 顶部进度条在 imitation run 中持续更新

  **QA Scenarios**:
  ```
  Scenario: 断线自动重连
    Tool: Playwright
    Steps:
      1. 发起一个长 imitation run
      2. 等收到 ≥1 个 progress 事件
      3. 用 page.context().setOffline(true)，2s 后 setOffline(false)
      4. 断言进度条恢复增长 + 不回退
    Expected: reconnect 成功
    Evidence: .sisyphus/evidence/task-16-reconnect.png

  Scenario: 业务错误不重连
    Tool: Playwright
    Steps:
      1. mock 后端返回 event: error（业务侧错误）
      2. 断言 UI 显示 toast，重连计数 = 0
    Expected: 不会无限重试
    Evidence: .sisyphus/evidence/task-16-business-error.png

  Scenario: 反向代理头部
    Tool: Bash (curl)
    Steps:
      1. curl -I http://localhost:8001/api/pipeline/progress-stream?...
      2. 断言含 X-Accel-Buffering: no、Cache-Control: no-cache
    Expected: 头部正确
    Evidence: .sisyphus/evidence/task-16-headers.txt
  ```

  **Commit**: YES — `feat(streaming): SSE UX polish (cancel/retry/progress/reconnect)`

- [ ] 17. **imitation `session_*` 字段冻结 + 弃用通道**

  **What to do**:
  - 基于 T7 报告，确定 3 类字段：
    - **Active**：保留
    - **Orphan**（0 引用 0 消费）：进入 `deprecated_in: writer-studio-v1` 弃用窗口（仍输出但 schema 标注）
    - **Unknown**：保留 + 加 TODO 注释，下个迭代决定
  - 在 `novel_analyzer/services/whole_book_imitation_service.py` 输出处用 schema 文件（如 `pydantic` model 或 dataclass）**冻结**当前结构
  - 新增 lint：`scripts/check_no_new_session_fields.py`，CI 跑——若发现 main 分支之外新增 session_* 字段 → 失败
  - 在 `docs/imitation/session-fields-audit.md` 末尾追加"冻结决策"段落

  **Must NOT do**:
  - ❌ 不实际删除任何字段（只标 deprecated）
  - ❌ 不改字段值的计算逻辑
  - ❌ 不在 Wave 内引入 pydantic 大改写（仅 schema 锁定）

  **Recommended Agent Profile**:
  - **Category**: `deep` — Reason: 决策密集，需评估每个字段的语义

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 2）
  - **Blocks**: (independent)
  - **Blocked By**: T7

  **References**:
  - T7 产出的 `docs/imitation/session-fields-audit.md`
  - `CHANGELOG.md:1112-1158` — 字段历史溯源
  - `novel_analyzer/services/whole_book_imitation_service.py`

  **Acceptance Criteria**:
  - [ ] 至少 1 个 orphan 字段已标 `deprecated_in: writer-studio-v1`
  - [ ] CI lint 拒绝新增 `session_*` 字段（用一个 PR 模拟）
  - [ ] imitation API 响应 schema 与 T7 报告中 active 集合一致

  **QA Scenarios**:
  ```
  Scenario: 弃用字段标注
    Tool: Bash
    Steps:
      1. python -c "from novel_analyzer.services.whole_book_imitation_service import schema; print(schema.deprecated_fields())"
      2. 断言 ≥ 1 个字段返回
    Expected: 标注成功
    Evidence: .sisyphus/evidence/task-17-deprecated.txt

  Scenario: 新增字段被 lint 拦截
    Tool: Bash
    Steps:
      1. 在临时分支加一个新的 session_foo 字段
      2. python scripts/check_no_new_session_fields.py
      3. 断言退出码非 0 + 错误指向新字段
      4. 还原
    Expected: lint 抓到回归
    Evidence: .sisyphus/evidence/task-17-lint.txt

  Scenario: 现有响应字段未变
    Tool: Bash
    Steps:
      1. POST /api/whole-book-imitation-run sample
      2. jq 'keys_unsorted' 对比 T7 报告中 active 集合
    Expected: 字段集合 = active
    Evidence: .sisyphus/evidence/task-17-schema-stable.txt
  ```

  **Commit**: YES — `chore(imitation): freeze and deprecate unused session_* fields`

- [ ] 18. **Cutover：main.py 退役、ASGI 入口收口**

  **What to do**:
  - 删除 `apps/api/app/main.py` 中所有 path-dispatch 分支（`if path == "/api/..."` 系列），仅保留：
    - 兼容旧的 entry-point（`make api-dev` 或类似 script 用 `python -m apps.api.app.main`）
    - 极小的 ASGI 启动 shim（uvicorn 的入口）
  - 目标：`wc -l apps/api/app/main.py` ≤ 100 行
  - 完整切到 `apps/api/app/fastapi_app.py` 作为唯一入口
  - 在 `Makefile` / scripts 更新启动命令为 `uvicorn apps.api.app.fastapi_app:app --reload`
  - 跑全套 contract test（T1）+ 烟雾，确认无回归

  **Must NOT do**:
  - ❌ 不删 contract test，不改基线 snapshot
  - ❌ 不改 service 层任何代码
  - ❌ 不在此 task 引入新 endpoint

  **Recommended Agent Profile**:
  - **Category**: `deep` — Reason: 不可逆改动，关键 cutover
  - **Skills**: `verification-before-completion`、`systematic-debugging`

  **Parallelization**:
  - **Can Run In Parallel**: NO（关键路径，独占）
  - **Blocks**: T21, T22, T23
  - **Blocked By**: T8, T9, T10, T11

  **References**:
  - `apps/api/app/main.py:1231-2630` — 所有要删的 dispatch
  - `apps/api/app/fastapi_app.py` — 即将成为唯一入口
  - `Makefile` — 启动命令

  **Acceptance Criteria**:
  - [ ] `wc -l apps/api/app/main.py` ≤ 100
  - [ ] `grep -c "if path ==" apps/api/app/main.py` = 0
  - [ ] contract test 全绿（用 fastapi 端点跑）
  - [ ] `make api-dev` 启动后所有原 endpoint 可访问

  **QA Scenarios**:
  ```
  Scenario: cutover 后所有 endpoint 可达
    Tool: Bash
    Steps:
      1. make api-dev &
      2. sleep 3
      3. for ep in $(jq -r '.available_endpoints[]' < curl :8001/api/meta); do curl -s -o /dev/null -w "%{http_code} $ep\n" :8001$ep; done
      4. 断言所有路径返回 200/4xx（不是 404/500 启动失败类）
    Expected: 全部端点 reachable
    Evidence: .sisyphus/evidence/task-18-all-reachable.txt

  Scenario: main.py 行数与 dispatch grep
    Tool: Bash
    Steps:
      1. wc -l apps/api/app/main.py
      2. grep -c "if path ==" apps/api/app/main.py
    Expected: ≤100 行 + 0 dispatch
    Evidence: .sisyphus/evidence/task-18-shrunk.txt

  Scenario: contract test 全绿
    Tool: Bash
    Steps:
      1. pytest tests/contract/ -v --tb=short
    Expected: 全 pass，0 fail
    Evidence: .sisyphus/evidence/task-18-contract-green.txt
  ```

  **Commit**: YES — `refactor(api): retire wsgi main.py, asgi cutover`

- [ ] 19. **Writer Studio 版本树 + diff/accept/reject**

  **What to do**:
  - 新建 `apps/web/src/components/writer/VersionTree.tsx`：树形展示一个章节的 imitation 历史分支
  - 每次发起 imitation → 创建一个新的"虚拟分支节点"挂在当前父节点下
  - 点击节点 → 主画布切换到该版本
  - diff 视图：当前版本 vs 父版本，段落级 diff（新增/删除/修改 颜色标注）
  - accept：把当前版本 promote 为主线（mock，暂不持久化到后端）
  - reject：标记节点为 archived（仍可见，灰色）

  **Must NOT do**:
  - ❌ 不引入 git-like 实际持久化（v1 内存级）
  - ❌ 不接 backend imitation history API（mock data 即可，等后端有了再接）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 3）
  - **Blocks**: (independent)
  - **Blocked By**: T13

  **References**:
  - T13 的 `EditorCanvas` — 主画布交互
  - AntD `Tree` 组件
  - 文本 diff 用 `diff` npm 包（轻量）或自己写 LCS

  **Acceptance Criteria**:
  - [ ] 版本树侧栏 visible，至少 3 个 mock 节点
  - [ ] 点击节点 EditorCanvas 文本切换
  - [ ] diff 视图显示段落级红绿标注

  **QA Scenarios**:
  ```
  Scenario: 节点切换主画布同步
    Tool: Playwright
    Steps:
      1. goto /writer/demo-branch
      2. 打开版本树
      3. 点击第二个节点
      4. 断言主画布文本变化（截图前后对比）
    Expected: 切换生效
    Evidence: .sisyphus/evidence/task-19-tree-switch.png

  Scenario: diff 视图标注
    Tool: Playwright
    Steps:
      1. 打开 diff（节点右键 → diff vs parent）
      2. 断言至少 1 段红色（删除）+ 1 段绿色（新增）
    Expected: 视觉清晰
    Evidence: .sisyphus/evidence/task-19-diff.png
  ```

  **Commit**: YES — `feat(writer-studio): version tree with paragraph-level diff`

- [ ] 20. **Writer Studio 新手引导 + 空状态**

  **What to do**:
  - 新建 `apps/web/src/components/writer/Onboarding.tsx`：
    - 首次进入 `/writer/*`（localStorage 标记）→ 4 步引导：
      1. 这里是编辑器画布
      2. 这里是 Loom 信号
      3. 这里是 AI 副驾，可以问问题或仿写
      4. 试试输入 "/" 唤起命令面板（v1 暂用 hover 工具条替代）
    - "跳过" / "完成" 按钮
  - 空状态打磨：
    - 没有任何 branch → 大 CTA "导入第一本小说"（跳到 `/control` 或新增页内导入）
    - 有 branch 但章节为空 → "章节列表是空的，先跑一遍 pipeline"
  - 错误态：网络/服务器错误统一组件 `<StudioError>`
  - 加载态：骨架屏（AntD `Skeleton`），不要纯 spinner

  **Must NOT do**:
  - ❌ 不加埋点 SDK（埋点是后续工作）
  - ❌ 不引入 `react-joyride` 等大型导览库（自己写 4 步即可）

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-ui-ux`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 3）
  - **Blocks**: (independent)
  - **Blocked By**: T13, T14, T15

  **References**:
  - T4 的 `StudioLayout` 已有空态 placeholder（在此基础上完善）

  **Acceptance Criteria**:
  - [ ] 首次进入显示引导，"完成"后 localStorage 标记
  - [ ] 重新进入不再显示
  - [ ] 空 branch 状态显示 CTA

  **QA Scenarios**:
  ```
  Scenario: 首次引导
    Tool: Playwright
    Steps:
      1. context.clearCookies + clearLocalStorage
      2. goto /writer/demo-branch
      3. 断言 [data-testid="onboarding-step-1"] 可见
      4. 4 次"下一步"
      5. 断言 onboarding 消失，localStorage 含 writer.onboarded=true
    Expected: 完整流程
    Evidence: .sisyphus/evidence/task-20-onboarding.png

  Scenario: 空状态 CTA
    Tool: Playwright
    Steps:
      1. mock /api/library 返回空
      2. goto /writer
      3. 断言"导入第一本小说"按钮可见且可点
    Expected: CTA 引导
    Evidence: .sisyphus/evidence/task-20-empty-cta.png
  ```

  **Commit**: YES — `feat(writer-studio): onboarding + empty/error/loading states`

- [ ] 21. **n8n 本地 docker-compose + 2 外围流程**

  **What to do**:
  - 新建 `infra/n8n/docker-compose.yml`：n8n + Postgres（n8n 自用），队列模式 single 即可（dev）
  - 实现 2 个工作流（用 n8n UI 拖拉，导出 JSON 存 `infra/n8n/workflows/`）：
    1. **pipeline-complete-notify**：监听 `POST :5678/webhook/pipeline-complete`，payload 含 branch_id + status，发送到指定 Slack/飞书 webhook（dev 用 echo 到日志即可）
    2. **daily-eval-report**：cron 每天 9am，调 `GET :8001/api/quality-dashboard`，格式化为 Markdown 发到通知渠道
  - 后端 `whole_book_imitation_service` 完成时调一次 `POST :5678/webhook/pipeline-complete`（fire-and-forget，超时 2s）
  - README：导入 workflow JSON 步骤、配置 webhook URL

  **Must NOT do**:
  - ❌ 不让任何核心 pipeline 流量经过 n8n（仅 fire-and-forget 通知）
  - ❌ 不写"通用 webhook 网关"——只这 2 个具体流程

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — Reason: docker + n8n + 后端 hook 三处协调

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 3）
  - **Blocks**: (independent)
  - **Blocked By**: T18

  **References**:
  - 官方：`https://docs.n8n.io/hosting/installation/docker/`
  - `novel_analyzer/services/whole_book_imitation_service.py` — 完成 hook 注入点

  **Acceptance Criteria**:
  - [ ] `docker compose -f infra/n8n/docker-compose.yml up -d` 后 n8n 在 5678 可访问
  - [ ] 触发一次 pipeline 完成 → n8n execution 历史中可见 1 条新执行
  - [ ] daily-eval-report 工作流可手动 trigger 跑通

  **QA Scenarios**:
  ```
  Scenario: pipeline 完成触发通知
    Tool: interactive_bash + Bash
    Steps:
      1. docker compose up -d n8n
      2. 导入 workflows/pipeline-complete-notify.json
      3. activate workflow
      4. 跑一次 mock imitation 触发完成 hook
      5. curl http://localhost:5678/api/v1/executions?workflowId=...
      6. 断言至少 1 条 success
    Expected: 端到端通
    Evidence: .sisyphus/evidence/task-21-n8n-trigger.txt

  Scenario: 后端 hook 失败不影响业务
    Tool: Bash
    Steps:
      1. docker stop n8n
      2. 跑一次 imitation
      3. 断言 imitation 200 OK，业务结果正常
      4. 检查日志仅 warn 级别
    Expected: fire-and-forget 不阻塞
    Evidence: .sisyphus/evidence/task-21-degraded.txt
  ```

  **Commit**: YES — `chore(infra): n8n local + pipeline-notify and daily-eval workflows`

- [ ] 22. **内部多用户：library scoping + trace tag**

  **What to do**:
  - DB 迁移：在 `NovelSource` / `AnalysisRun` / `RunBranch` 表加 `owner_user_id VARCHAR(64) NOT NULL DEFAULT 'local-default'`
  - alembic migration 文件：`alembic/versions/{timestamp}_add_owner_user_id.py`
  - service 层：`IngestService`、`StatusService` 的查询全部加 `WHERE owner_user_id = :user_id`，写入时填充
  - 路由层：从 T6 的 `get_current_user` 拿 user_id 透传
  - Langfuse trace tag（T12）补 `user_id`
  - **不**改前端（前端默认发 `X-User-Id: local-default` 即可，等需要切用户时再加 UI）

  **Must NOT do**:
  - ❌ 不删数据，不破坏现有数据（migration 用 default 兜底）
  - ❌ 不做用户管理 UI（后续工作）
  - ❌ 不实现 row-level security（PostgreSQL RLS 留给真正多租户阶段）

  **Recommended Agent Profile**:
  - **Category**: `deep` — Reason: DB schema + service 层多处 + 不可逆迁移
  - **Skills**: `verification-before-completion`、`test-driven-development`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 3）
  - **Blocks**: T23
  - **Blocked By**: T18, T6

  **References**:
  - `novel_analyzer/database/models.py` — 模型定义
  - `alembic/` — 现有 migration 风格
  - `novel_analyzer/services/ingest_service.py`、`status_service.py`

  **Acceptance Criteria**:
  - [ ] migration 跑通，老数据 owner_user_id = 'local-default'
  - [ ] 两个不同 user_id 的请求看到不同的 library
  - [ ] Langfuse trace 可按 user_id 过滤

  **QA Scenarios**:
  ```
  Scenario: 双用户隔离
    Tool: Bash
    Steps:
      1. 用 X-User-Id: alice 调 /api/import 上传 sample 1
      2. 用 X-User-Id: bob   调 /api/import 上传 sample 2
      3. curl -H "X-User-Id: alice" /api/library | jq '.items | length' → 1
      4. curl -H "X-User-Id: bob"   /api/library | jq '.items | length' → 1
      5. 断言两份内容不同
    Expected: 完全隔离
    Evidence: .sisyphus/evidence/task-22-isolation.txt

  Scenario: migration 兜底
    Tool: Bash
    Steps:
      1. 老库（migration 前）run alembic upgrade head
      2. 检查所有现有行 owner_user_id = 'local-default'
      3. curl -H "X-User-Id: local-default" /api/library 看到所有老数据
    Expected: 老数据可见
    Evidence: .sisyphus/evidence/task-22-migration.txt

  Scenario: Langfuse trace 含 user_id tag
    Tool: Bash
    Steps:
      1. 用 X-User-Id: alice 发一次 ask-branch
      2. 在 Langfuse UI 按 user_id=alice 过滤 traces
      3. 断言至少 1 条结果
    Expected: tag 可过滤
    Evidence: .sisyphus/evidence/task-22-trace-tag.png
  ```

  **Commit**: YES — `feat(api): per-user library scoping + langfuse user tag`

- [ ] 23. **Contract tests 增强 + 烟雾 runbook + 回归基线**

  **What to do**:
  - 在 T1 的 contract test 基础上扩展：
    - 加 user-scoped 测试（X-User-Id alice/bob 隔离）
    - 加 SSE event 序列对齐（T10/T11 的 streaming endpoint）
    - 加 Langfuse 集成关闭/开启切换测试（环境变量驱动）
  - 写 `docs/runbook/smoke-test.md`：
    - 启动顺序（docker → API → web）
    - 5 分钟 smoke checklist（手工 + 自动化命令）
    - 故障定位 5 个常见症状 → 处理步骤
  - 把 contract + smoke 接到 CI（GitHub Actions / 现有 CI），保证 PR 阻断回归

  **Must NOT do**:
  - ❌ 不引入新 CI 平台（用现有的）
  - ❌ 不为追求覆盖率而 mock 一切（关键 endpoint 必须打真服务）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: `test-driven-development`、`writing-plans`

  **Parallelization**:
  - **Can Run In Parallel**: YES（Wave 3）
  - **Blocks**: F1-F4
  - **Blocked By**: T18, T22

  **References**:
  - T1 产出
  - `.github/workflows/`（如有）— CI 配置位置

  **Acceptance Criteria**:
  - [ ] `pytest tests/contract/` ≥ 50 个断言，全绿
  - [ ] `docs/runbook/smoke-test.md` 存在，含 5 个症状
  - [ ] CI 配置中 contract + smoke 是 required check

  **QA Scenarios**:
  ```
  Scenario: contract 全绿
    Tool: Bash
    Steps:
      1. pytest tests/contract/ -v --tb=short
    Expected: ≥50 passed, 0 failed
    Evidence: .sisyphus/evidence/task-23-contract-50.txt

  Scenario: runbook 可执行
    Tool: interactive_bash (tmux)
    Steps:
      1. 按 docs/runbook/smoke-test.md 第 1-5 步从零起服务
      2. 跑文档中的 smoke 命令
      3. 断言全部通过
    Expected: 文档可被零经验工程师跑通
    Evidence: .sisyphus/evidence/task-23-runbook.txt

  Scenario: CI required check
    Tool: Bash
    Steps:
      1. cat .github/workflows/*.yml | grep -E "contract|smoke"
      2. 断言两者都被 PR workflow 引用
    Expected: 配置已生效
    Evidence: .sisyphus/evidence/task-23-ci.txt
  ```

  **Commit**: YES — `test(quality): contract + smoke runbook + ci wiring`

---

## Final Verification Wave (MANDATORY)

> 4 review agents 并行。所有 APPROVE 后**展示给用户**，等用户明确 "okay" 才算完。

- [ ] F1. **Plan Compliance Audit** — `oracle`
  逐条核对 Must Have / Must NOT Have：read 文件、curl endpoint、grep 禁词。
  - 检查 `apps/api/app/main.py` 不含路由 dispatch（grep `path == "/api"`）
  - 检查 LLM 边界外的代码无 `langfuse` import
  - 检查 imitation schema 没有新增的 `session_*` 字段
  - 检查 `/writer/*` 路由可访问且**不**经过 `WorkbenchApp.tsx`
  - 检查证据文件齐全（`.sisyphus/evidence/task-*` 至少 23 套）
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  跑 `ruff check`、`mypy`、`pytest`、前端 `next lint` + `tsc --noEmit`。
  Review 改动文件：`as any`、`# type: ignore`、空 except、`console.log`、巨型 try/except、AI-slop（generic data/result/item 命名、过抽象）。
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`（+ `playwright` skill）
  从 clean state 起：完整跑一遍每个任务的 QA scenarios；跨任务 integration（编辑器→ AI 副驾 →流式→ Loom 信号 →版本树）；边缘（空 library、断网、取消长任务、两个用户切换）。
  证据：`.sisyphus/evidence/final-qa/`。
  Output: `Scenarios [N/N] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  对每个 task：read 「What to do」与实际 git diff 一一对比。检查 Must NOT Do 合规、跨任务污染（T13 改了 T16 的文件？）、未声明的改动（动了 `novel_analyzer/` 既有模块？）。
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

每个 task 独立 commit；trailers 遵循 Lore Commit Protocol。

- **T1**: `test(api): lock current main.py contract before fastapi migration`
- **T2**: `feat(api): add request-trace context middleware contract`
- **T3**: `feat(streaming): SSE helper + client hook scaffolding`
- **T4**: `feat(web): writer studio route group + layout shell`
- **T5**: `chore(infra): self-hosted langfuse docker-compose`
- **T6**: `feat(api): X-User-Id middleware (internal multi-user stub)`
- **T7**: `chore(imitation): session_* field usage analyzer`
- **T8-T11**: `refactor(api): migrate {scope} routes to fastapi`
- **T12**: `feat(observability): langfuse at LLM provider boundary`
- **T13-T15**: `feat(writer-studio): {component}`
- **T16**: `feat(streaming): SSE UX polish (cancel/retry/progress)`
- **T17**: `chore(imitation): freeze and deprecate unused session_* fields`
- **T18**: `refactor(api): retire wsgi main.py, asgi cutover`
- **T19-T20**: `feat(writer-studio): {feature}`
- **T21**: `chore(infra): n8n local + 2 outer workflows`
- **T22**: `feat(api): per-user library scoping`
- **T23**: `test(quality): contract tests + smoke runbook`

---

## Success Criteria

### Verification Commands
```bash
# Backend FastAPI cutover
wc -l apps/api/app/main.py                    # Expected: < 100
curl -s http://localhost:4173/health | jq .ok # Expected: true
pytest tests/contract/                        # Expected: all pass

# Langfuse
docker compose -f infra/langfuse/docker-compose.yml ps  # All Up
curl -s http://localhost:3000/api/public/health         # Expected: 200

# Writer Studio
curl -s -I http://localhost:4173/writer/<branch_id> | head -1  # 200 OK

# Streaming UX
# (manual via playwright in F3)

# Internal multi-user
curl -H "X-User-Id: alice" http://localhost:4173/api/library | jq '.items | length'
curl -H "X-User-Id: bob"   http://localhost:4173/api/library | jq '.items | length'
# Expected: 不同的数字 / 不同的 branch_id 列表

# imitation 字段冻结
python scripts/audit_imitation_fields.py     # Expected: deprecated >= 1, new = 0

# n8n
docker compose -f infra/n8n/docker-compose.yml ps
curl -s http://localhost:5678/healthz        # Expected: 200
```

### Final Checklist
- [ ] 所有 Must Have 项已验证存在（commands above 全绿）
- [ ] 所有 Must NOT Have 项已验证不存在（F1 grep 检查通过）
- [ ] Contract tests + smoke 全绿（CI 截图为证）
- [ ] F1-F4 全部 APPROVE
- [ ] 用户明确说 "okay"
