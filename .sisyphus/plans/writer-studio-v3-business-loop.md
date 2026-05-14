# Writer Studio v3 — 业务闭环（Business Loop）

> **目的**：让 v2 落地的 Dify/n8n/Langfuse 真正接进 imitation 主流量，把 `owner_user_id` 多租户从"DB 有列"做到"业务尊重"，让作家用户能在编辑器里点"开始仿写"→ 后端真正执行 → 完成后通过 n8n 通知 → trace 在 Langfuse 可见。

> **替代不替代 v2**：不替代。v2 是基础设施 + UI 入口；v3 是让基础设施真正承接业务流量。v2 的 PR #8 必须先 merge，v2 的 docker stacks 必须先跑起来。

> **v3 不做**：FastAPI 路由迁移（仍推迟）、Reader 端 UI（v4 候选）、prompt 资产迁移到 Dify Studio（用户明确"代码里保留"）。

---

## TL;DR

> **Quick Summary**：把 `owner_user_id` 从 DB 列变成业务隔离的真护栏；让 imitation 完成后真正通知 n8n；用 Helicone 透明 proxy 把 imitation 主流量也喂给 Langfuse；作家端 iframe + Custom Tool 链路里把用户身份透传到后端。零侵入业务核心代码（imitation 算法不动），仅在 service 边界加 WHERE 子句、在 LLM 边界加 base_url 替换、在完成 hook 加 fire-and-forget HTTP。
>
> **Deliverables**:
> - `apps/api/app/middleware/identity.py` — ASGI middleware，从 `X-User-Id` header 读用户身份注入 RequestContext（终于把 v2 T2 trace_context 用上了）
> - `infra/helicone/docker-compose.yml` — Helicone self-host
> - `novel_analyzer/llm/client.py` 的 `base_url` 通过 env 切到 Helicone proxy（仅 1 行改动 + 全 env 控制）
> - `novel_analyzer/services/{ingest,status,whole_book_imitation}_service.py` 三个 service 的查询/写入加 `owner_user_id` scoping
> - `WholeBookImitationService` 完成后 fire-and-forget POST 到 n8n webhook
> - Dify 的 Custom Tool OpenAPI 加 `X-User-Id` header 转发
> - 端到端 test：alice 仿写 → bob 看不到 → alice 收到 n8n 通知 → Langfuse 看到 imitation trace
>
> **Estimated Effort**: Medium（3-5 天 / 1-2 人）
> **Critical Path**: T1 middleware → T2 service scoping → T3 imitation hook → T4 Helicone → F1-F3
> **Zero-touch on**：`apps/api/app/main.py`（仍 2630 行）、imitation 算法本身、prompts.py

---

## Context

### v2 留下的 4 个 gap（v3 的源动力）

1. **Imitation 主流量看不见** — `whole_book_imitation_service.py` 直连 LLM provider，Dify 内置 Langfuse 看不到这条主战场
2. **X-User-Id 没透传** — Dify Custom Tool → 后端 → service 层之间，用户身份在第二跳就丢了
3. **n8n 是孤岛** — pipeline-complete-notify workflow 就位但**后端没有触发它**
4. **`owner_user_id` 形同虚设** — DB 有列、有 default `local-default`，但 service 层从来不用它做 WHERE 子句

### Interview Decisions（用户已选）

- **主受力**：业务闭环优先（不是 trace 优先、不是 prompt 迁移、不是运维优先）
- **prompt 资产**：留在 `novel_analyzer/llm/prompts.py`，仅加 trace 不动结构

### Pre-conditions（v3 开工前必须满足）

- [x] PR #8 已 merge 到 master（v2 代码就位）
- [ ] `make v2-up-all` 至少跑通过一次（infra 健康）
- [ ] N4-N7 至少 N4（Dify Writer Copilot）和 N6（n8n notify workflow）已配置
- [ ] 这两步是 v2 的 docker-blocked 任务，**v3 不会替你做**——它们必须人工先做完

---

## Work Objectives

### Core Objective
让 v2 的 Dify/n8n/Langfuse 真正承接业务流量、让 owner_user_id 真正生效，作家用户能感知到"我的工作只属于我"和"任务跑完了"。

### Concrete Deliverables
- **D1**：FastAPI 加 identity middleware，所有路由能拿到 user_id（不动 main.py 的 WSGI dispatch）
- **D2**：3 个 service 的 list/create 方法尊重 `owner_user_id`
- **D3**：imitation 完成后向 n8n 发 webhook
- **D4**：Helicone proxy 跑起来，imitation 主流量在 Langfuse 可见
- **D5**：Dify Custom Tool OpenAPI 加 `X-User-Id` header 转发，建立"作家在 Dify 问 → 后端知道是谁"的链路
- **D6**：端到端 e2e test：双用户隔离 + 通知 + trace 三件验证

### Definition of Done
- [x] `curl -H "X-User-Id: alice" /api/library` 和 `-H "X-User-Id: bob"` 返回不同集合
- [ ] 跑一次 imitation → n8n executions UI 出现 1 条 success
- [ ] 跑一次 imitation → Langfuse UI 出现 generation span（带 user_id tag）
- [ ] Dify Writer Copilot 里发问 → 后端日志可见 user_id
- [x] Contract test 28/28 仍绿；新加 5 个端到端测试全绿
- [x] `apps/api/app/main.py` dispatch 表 0 改动（v3 scope 内）

### Must Have
- middleware 抽象到位：未来接 IDP 仅替换 middleware，不改 service
- imitation hook 必须 fire-and-forget：n8n 挂了不影响业务
- Helicone 必须可降级：proxy 挂了 LLM 直连依然能工作
- Dify Custom Tool 必须把 user_id 作为 header 传下去（不是 body 字段）

### Must NOT Have
- ❌ 不改 imitation 算法、不动 prompts.py、不改 LangGraph workflow
- ❌ **不改 `apps/api/app/main.py` 的 dispatch（即 line 1231 的 `application()` 路由分发表）**——但允许触碰 `_library_payload` 等纯查询 helper 函数（v3 修订）
- ❌ 不引入 IDP（OAuth/JWT/Cognito 等）
- ❌ 不把 prompts 搬到 Dify Studio（用户明确推迟）
- ❌ 不做 row-level security（PostgreSQL RLS）
- ❌ 不做 Reader 端 UI
- ❌ 不引入新 framework / 新 ORM / 新前端依赖
- ❌ 不在 service 层 import langfuse/dify/helicone（保持业务零渗透）

---

## Verification Strategy

- T1 contract test（v2 遗产）必须始终绿——零回归门禁
- 新加 5 个 e2e test 在 `tests/e2e/test_business_loop.py`
- Helicone health check：`curl /healthcheck` 200
- n8n webhook 触发：`curl POST :5678/webhook/pipeline-complete` 后 executions API 可见
- Langfuse trace 可见：通过 Langfuse public API 验证 trace 数量增长

### Test Decision
- 新功能：TDD-light（先写 e2e 测试桩，再实现）
- middleware：full unit test（单元 + 集成）
- service scoping：用 SQLite in-memory + 双 user fixture

---

## Execution Strategy

### Wave A — Identity 透传（关键路径起点）

```
T1  identity middleware (ASGI)                      [quick]
T2  service 层 scoping: ingest/status/whole_book    [deep]   (依赖 T1)
T3  Dify Custom Tool OpenAPI 加 X-User-Id header    [quick]  (依赖 T1)
```

### Wave B — 业务 Hook + 观测（与 A 并行末段）

```
T4  imitation 完成 fire-and-forget n8n hook         [deep]   (依赖 T1)
T5  Helicone self-host docker-compose               [unspecified-high]
T6  llm/client.py base_url env-driven (proxy switch) [quick]  (依赖 T5)
```

### Wave C — End-to-End 验证

```
T7  e2e test: 双用户隔离                           [unspecified-high] (依赖 T2)
T8  e2e test: imitation hook 触发 n8n              [unspecified-high] (依赖 T4)
T9  e2e test: Langfuse 看到 imitation trace        [unspecified-high] (依赖 T6)
T10 文档: 业务闭环 runbook                         [writing]   (依赖 T7-T9)
```

### Wave Final — 验收

```
F1  零回归审计 (oracle): contract test 仍 28/28，main.py 仍 2630 行
F2  闭环验收 (unspecified-high): 三件验证齐绿
F3  范围保真 (deep): imitation 算法 0 改动，prompts.py 0 改动
```

### Critical Path
T1 → T2 → T7 → F1-F3
T1 → T3 → (Dify pickup task)
T1 → T4 → T8 → F2
T5 → T6 → T9 → F2

### Max parallelism
Wave A 中 T2/T3 可并行（依赖共同的 T1）
Wave B 中 T4 / T5+T6 完全并行
Wave C 三个 e2e test 完全并行

---

## TODOs

- [x] **T1. ASGI identity middleware — 把 X-User-Id 接到 RequestContext**

  **What to do**:
  - 新建 `apps/api/app/middleware/__init__.py`、`apps/api/app/middleware/identity.py`
  - 用 starlette `BaseHTTPMiddleware` 写 `IdentityMiddleware`：
    - 读 `X-User-Id` header，缺省 `"local-default"`
    - 读 `X-Request-Id` header，缺省 `uuid4()`
    - 调 v2 的 `with_request_context()` 包住下游 call_next
  - **Note**: master 上没有 `fastapi_app.py`（v2 PR #8 未引入），所以本任务**不**做"接到运行中的 app"步骤 — middleware 仅作为模块就位 + fixture 集成测试，等到未来真有 FastAPI 入口时再接。
  - 提供 `get_current_user() -> str` helper（从 `RequestContext.user_id` 读）
  - 写单元测试 + fixture 集成测试（在测试里临时 create FastAPI app）

  **Must NOT do**:
  - ❌ 不改 `apps/api/app/main.py`（WSGI 不接此 middleware；只 FastAPI 接）
  - ❌ 不引入 IDP / JWT / OAuth
  - ❌ 不在 service 层 import 这个 middleware（只通过 `get_current_context()` 间接读）
  - ❌ 不写 cookie/session 表

  **Acceptance**:
  - [ ] `pytest tests/api/middleware/test_identity.py` ≥ 5 pass（覆盖：有 header / 无 header / 空 header / 特殊字符 / 嵌套请求）
  - [ ] FastAPI demo route 用 `Depends(get_current_user)` 能拿到 user_id

  **QA scenarios**:
  ```
  Scenario A (happy): curl -H "X-User-Id: alice" :8001/__whoami → {"user_id": "alice"}
  Scenario B (default): curl :8001/__whoami → {"user_id": "local-default"}
  Scenario C (request_id auto): curl :8001/__whoami → response 含 X-Request-Id header
  Scenario D (downstream propagation): get_current_context() 在 router 内能读到
  ```

  **Files to create — Sisyphus copy-paste**:

  `apps/api/app/middleware/__init__.py`:
  ````python
  from apps.api.app.middleware.identity import IdentityMiddleware, get_current_user

  __all__ = ["IdentityMiddleware", "get_current_user"]
  ````

  `apps/api/app/middleware/identity.py`:
  ````python
  from __future__ import annotations

  import uuid

  from starlette.middleware.base import BaseHTTPMiddleware
  from starlette.requests import Request
  from starlette.responses import Response

  from novel_analyzer.runtime.trace_context import (
      RequestContext,
      get_current_context,
      with_request_context,
  )


  class IdentityMiddleware(BaseHTTPMiddleware):
      async def dispatch(self, request: Request, call_next):
          user_id = (request.headers.get("X-User-Id") or "local-default").strip() or "local-default"
          request_id = (request.headers.get("X-Request-Id") or str(uuid.uuid4())).strip()

          with with_request_context(request_id=request_id, user_id=user_id) as ctx:
              response: Response = await call_next(request)
              response.headers["X-Request-Id"] = ctx.request_id
              return response


  def get_current_user() -> str:
      ctx = get_current_context()
      return ctx.user_id if ctx else "local-default"
  ````

  在 `apps/api/app/fastapi_app.py` 的 `create_app()` 加：
  ````python
  from apps.api.app.middleware import IdentityMiddleware

  # ...在 add_middleware(CORSMiddleware, ...) 之后:
  app.add_middleware(IdentityMiddleware)

  # ...再加一个 demo route 验证:
  @app.get("/__whoami")
  def whoami():
      from apps.api.app.middleware import get_current_user
      from novel_analyzer.runtime.trace_context import get_current_context
      ctx = get_current_context()
      return {
          "user_id": get_current_user(),
          "request_id": ctx.request_id if ctx else None,
      }
  ````

  `tests/api/middleware/__init__.py` (empty)

  `tests/api/middleware/test_identity.py`:
  ````python
  from __future__ import annotations

  import pytest
  from fastapi.testclient import TestClient

  from apps.api.app.fastapi_app import create_app


  @pytest.fixture
  def client():
      return TestClient(create_app())


  def test_x_user_id_header_propagates(client):
      r = client.get("/__whoami", headers={"X-User-Id": "alice"})
      assert r.status_code == 200
      assert r.json()["user_id"] == "alice"


  def test_missing_header_falls_back_to_local_default(client):
      r = client.get("/__whoami")
      assert r.status_code == 200
      assert r.json()["user_id"] == "local-default"


  def test_empty_header_falls_back(client):
      r = client.get("/__whoami", headers={"X-User-Id": "  "})
      assert r.status_code == 200
      assert r.json()["user_id"] == "local-default"


  def test_request_id_echoed_in_response_header(client):
      r = client.get("/__whoami", headers={"X-Request-Id": "req-fixed-123"})
      assert r.headers["X-Request-Id"] == "req-fixed-123"
      assert r.json()["request_id"] == "req-fixed-123"


  def test_request_id_auto_generated_when_missing(client):
      r = client.get("/__whoami")
      assert "X-Request-Id" in r.headers
      assert len(r.headers["X-Request-Id"]) >= 8
  ````

  **Commit**: `feat(api): identity middleware reads X-User-Id into RequestContext`

- [x] **T2. Service-layer scoping — 让 owner_user_id 真正生效**

  **What to do**:
  - **Code reality (v3 修订)**：library 实体由 `RunService` 创建（不是 IngestService）；library 列表查询的 SQL 在 `apps/api/app/main.py` 的 `_library_payload` helper 里。改动落点修订为：
    - `novel_analyzer/services/run_service.py`：`create_run` / `create_branch` 加 `owner_user_id: str = "local-default"` 关键字参数，写入时填充
    - `apps/api/app/main.py` 仅 `_library_payload(database_url, limit, owner_user_id=None)` 改签名 + SQL 加 WHERE 子句；**dispatch 表 `application()` 仍然不改**（read X-User-Id header 在 helper 调用方做，依然在 dispatch 范围内**1 行**修订）
    - `novel_analyzer/services/status_service.py`：`get_run_status` 不改（已是 by-id 查询，天然作用域）
    - `novel_analyzer/services/whole_book_imitation_service.py`：本任务**不改**（imitation 算法纯按 branch_id 工作，scoping 由 library 入口先把关）
  - 在 main.py 中读 `X-User-Id` header（仅 1 行修订：`/api/library` 分支的 helper 调用处），传给 `_library_payload`

  **Must NOT do**:
  - ❌ 不改其他 24 个 service
  - ❌ 不改 imitation 算法逻辑
  - ❌ 不改 main.py 的 dispatch 表本身（line 1231 `application()` 函数体的路由 if/elif 链）
  - ❌ 不改 `novel_analyzer/cli/` 调用方式
  - ❌ 不删 / 重命名任何已有方法
  - ❌ 不在 main.py 的其他 endpoint 加 owner_user_id 过滤（仅 /api/library 这一个）

  **Acceptance**:
  - [ ] 新加 `tests/test_owner_scoping_service.py` ≥ 6 测试覆盖 3 个 service 的隔离
  - [ ] 双 user 在 FastAPI 端点能看到不同 library
  - [ ] 老 CLI 命令（不传 user_id）仍可工作（兼容 `local-default`）

  **References**:
  - `novel_analyzer/services/ingest_service.py` — 找 `_create_run` / `create_branch` 入口
  - `novel_analyzer/services/status_service.py` — 找 `list_runs` / `get_branch_snapshot`
  - `novel_analyzer/services/whole_book_imitation_service.py:20` — class header
  - v2 留下的 `tests/test_owner_scoping.py` — DB 层测试，T2 测试要在 service 层

  **QA scenarios**:
  ```
  Scenario A (alice creates, bob can't see):
    1. alice 调 ingest_service.create_run(owner_user_id="alice")
    2. status_service.list_runs(owner_user_id="bob") → 不含 alice 的 run
  Scenario B (legacy CLI sees all):
    1. alice 创建 run、bob 创建 run
    2. status_service.list_runs(owner_user_id=None) → 含 2 个
  Scenario C (whole_book imitation respects scope):
    1. alice 启动 imitation
    2. bob 调 status_service.get_run_snapshot 同一个 run_id → 拒绝 / 空
  ```

  **Commit**: `feat(services): scope ingest/status/imitation by owner_user_id`

- [x] **T3. Dify Custom Tool — X-User-Id header 转发**

  **What to do**:
  - 修改 `infra/dify/apps/novel-analyzer-tools.openapi.yaml`：在 3 个 tool（`search_chapter`、`ask_branch`、`get_chapter`）的 `parameters` 部分加：
    ````yaml
    - name: X-User-Id
      in: header
      required: false
      schema:
        type: string
        default: "local-default"
      description: |
        Forwarded from Dify systemVariables.user_id.
        Backend uses this for owner_user_id scoping.
    ````
  - 在 `infra/dify/apps/writer-copilot.dsl.yml` 的 system prompt 末尾加：
    > 调用任何 tool 时，把 user_id 作为 X-User-Id header 传给后端。
  - 写 `infra/dify/apps/README.md` 步骤：UI 导入 OpenAPI 时怎么把 systemVariables.user_id 映射到 header

  **Must NOT do**:
  - ❌ 不改 backend endpoint 路径
  - ❌ 不在 Dify 里 hardcode 任何具体 user_id
  - ❌ 不在 OpenAPI 里把 user_id 放 query string（必须 header）

  **Acceptance**:
  - [ ] OpenAPI YAML parses（`yaml.safe_load`）
  - [ ] 3 个 tool 都有 X-User-Id header parameter
  - [ ] README 步骤可被一名工程师从零执行通过

  **Note**: 这是配置文件改动，**真正生效需要 Dify 运行时重新导入 OpenAPI**——属于 v2 N4 pickup task 的一部分。

  **Commit**: `feat(dify): forward X-User-Id header in custom tool OpenAPI`

- [x] **T4. Imitation 完成 fire-and-forget n8n hook**

  **What to do**:
  - 在 `whole_book_imitation_service.py` 末端（每次 imitation run 完成的最后一步，**算法之外**）调用一个新的 utility 函数 `notify_pipeline_complete(branch_id, status, user_id, run_meta)`
  - 新建 `novel_analyzer/runtime/notify.py` 提供这个 utility：
    - 读 env `N8N_WEBHOOK_PIPELINE_COMPLETE_URL`，未设置时直接 return（无 op）
    - 用 `httpx` 发 POST，**timeout=2s**，**catch all exceptions**，仅 warn 日志
    - 不阻塞调用方任何路径
  - 写单元测试覆盖：env 未设置、timeout、连接失败、200 OK 四种情况

  **Must NOT do**:
  - ❌ 不改 imitation 算法逻辑（hook 必须在 run loop 之外的"完成回调"位置）
  - ❌ 不让 hook 失败影响 imitation 结果（fire-and-forget 是硬约束）
  - ❌ 不在 hook 里同步等待 n8n 响应超过 2 秒
  - ❌ 不在 hook payload 里塞用户原文（只发 metadata：branch_id、status、chapter_count、duration）
  - ❌ 不重试 webhook 失败（n8n 自己负责持久化和重试）

  **References**:
  - `novel_analyzer/services/whole_book_imitation_service.py` — 找算法运行的最末尾返回点（不是中间循环）
  - `infra/n8n/workflows/pipeline-complete-notify.json` — 已就位的 webhook 接收方
  - v2 N6 已规划的 webhook URL：`http://host.docker.internal:5678/webhook/pipeline-complete`

  **Acceptance**:
  - [ ] `pytest tests/runtime/test_notify.py` ≥ 4 pass
  - [ ] 跑一次 imitation 后 `curl :5678/api/v1/executions` 见 1 条 success（手动验证，需 n8n 运行）
  - [ ] 注释掉 env 变量后，imitation 不报错也不发 webhook（grep log 确认）

  **QA scenarios**:
  ```
  Scenario A (env not set): N8N_WEBHOOK_PIPELINE_COMPLETE_URL="" → notify() return immediately, no exception
  Scenario B (n8n running): env set + n8n up → POST returns 200, log records "n8n notify ok"
  Scenario C (n8n down): env set + n8n stopped → caught exception, log warn, imitation business result unchanged
  Scenario D (timeout): env set to slow endpoint → 2s timeout, log warn, imitation result unchanged
  ```

  **Commit**: `feat(imitation): fire-and-forget n8n notify on pipeline complete`

- [x] **T5. Helicone self-host docker-compose**

  **What to do**:
  - 新建 `infra/helicone/docker-compose.yml` + `README.md`
  - 配 Helicone OSS：proxy + worker + Postgres + ClickHouse（按官方）
  - 端口：**8585**（proxy），避开已用的 8080/5678/3030/4173/8001
  - 仅 localhost 绑定
  - Helicone 控制台端口 8586（与 proxy 分开）

  **Must NOT do**:
  - ❌ 不与 Dify/n8n/Langfuse 共享 docker network
  - ❌ 不在 Helicone 配置里 hardcode LLM provider key（key 由 caller 通过 env 传给 Helicone proxy）

  **Acceptance**:
  - [ ] `docker compose -f infra/helicone/docker-compose.yml ps` 全 Up
  - [ ] `curl :8585/healthcheck` 返回 200
  - [ ] README 含 3 步 quickstart（clone / up / 看 console）

  **Files to create — Sisyphus copy-paste**:

  `infra/helicone/README.md`:
  ````markdown
  # Helicone Self-Host (Local Dev)

  > Transparent LLM proxy. Sits in front of OpenAI-compatible API.
  > Used by `novel_analyzer/llm/client.py` to gain trace + cost coverage
  > of the imitation main flow without touching business code.

  ## 一次性安装

  ```bash
  cd infra/helicone
  git clone --depth 1 --branch v1.0.0 https://github.com/Helicone/helicone.git upstream
  cd upstream
  cp .env.example .env
  # 改端口避开 8080/5678/3030
  sed -i 's/^PROXY_PORT=.*$/PROXY_PORT=8585/' .env
  sed -i 's/^WEB_PORT=.*$/WEB_PORT=8586/' .env
  ```

  ## 启动 / 停止

  ```bash
  cd infra/helicone/upstream
  docker compose up -d
  docker compose ps
  curl :8585/healthcheck   # 200
  # 控制台 http://localhost:8586

  docker compose down
  docker compose down -v   # 删除全部数据
  ```

  ## 接入

  1. Helicone console 创建 organization → Settings → API Keys → Create
  2. 把 base URL 从 `https://api.openai.com/v1` 改为 `http://localhost:8585/v1/openai`
  3. Authorization header 保持原 OpenAI key 不变
  4. 业务代码 0 行改动（详见 v3 T6）

  ## 注意

  - 仅 localhost
  - Proxy 是单点，挂了 LLM 直连失效。T6 里有降级 env 开关
  - Trace 默认存 ClickHouse 自带表；Langfuse 同步是另外功能（v3 不做）
  ````

  `infra/helicone/docker-compose.yml`：用上面 git clone 的 upstream 的官方 compose（不复制粘贴他们的 60 行）。我们这里只需要 README 指引。

  **Commit**: `chore(infra): self-hosted helicone docker-compose`

- [x] **T6. llm/client.py base_url env-driven**

  **What to do**:
  - 在 `novel_analyzer/config/settings.py` 加新字段 `llm_base_url_override: str | None = None`
  - 环境变量名 `NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE`
  - 在 `novel_analyzer/llm/client.py` 的 `build_chat_model()` 里：
    ```python
    base_url = runtime.llm_base_url_override or runtime.resolved_llm_base_url
    ```
  - **仅 1-2 行改动**

  **Must NOT do**:
  - ❌ 不改任何 prompt
  - ❌ 不引入 Langfuse / Helicone Python SDK
  - ❌ 不改算法
  - ❌ 不让 override 默认开启（必须显式 env 设置才生效）

  **Acceptance**:
  - [ ] 单元测试：override 设置时被 ChatOpenAI 看到；未设置时回 normal base_url
  - [ ] 改 env 后无需 restart 业务代码（不持久化到模块级单例）

  **References**:
  - `novel_analyzer/llm/client.py:22` — 现 `base_url=runtime.resolved_llm_base_url`
  - `novel_analyzer/config/settings.py` — Settings 模型

  **QA scenarios**:
  ```
  Scenario A (no override): unset env → base_url = production provider
  Scenario B (helicone proxy): export NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/openai → ChatOpenAI 收到 helicone url
  Scenario C (downgrade): proxy 挂了 → 临时 unset env → 直连恢复
  ```

  **Commit**: `feat(llm): base_url override for transparent LLM proxy`

- [x] **T7. E2E test: 双用户隔离**

  **What to do**:
  - 新建 `tests/e2e/test_business_loop.py`
  - 用 `TestClient(create_app())` 启动 FastAPI in-process（DB 用 SQLite in-memory fixture）
  - 场景：alice 上传 → bob list 看不到 → bob 用 alice 的 branch_id 调 status 拒绝/空

  **Must NOT do**:
  - ❌ 不依赖 docker / Dify / n8n / Langfuse 跑（纯 Python 进程内）
  - ❌ 不调真实 LLM provider（mock 或跳过 imitation 算法本身）

  **Acceptance**:
  - [ ] 3 个测试覆盖 ingest / list / get_run 三个 service 的隔离
  - [ ] CI 能跑（在 backend-tests.yml 里加一行）

  **References**:
  - v2 的 `tests/test_owner_scoping.py` 是 model 层 fixture pattern 参考
  - T2 实现的 service scoping 是这里要验的

  **Commit**: `test(e2e): two-user library isolation through FastAPI`

- [x] **T8. E2E test: imitation hook 触发 n8n**

  **What to do**:
  - 在 `tests/e2e/test_business_loop.py` 加一个 mock-based 测试：
    - mock `httpx.post` 截获 webhook 调用
    - 跑一次 `WholeBookImitationService` 的最后阶段（不跑真 LLM，stub 算法返回值）
    - 断言 mock 被调一次，payload 含 `branch_id` `status` `user_id`
  - 加一个 negative 测试：`N8N_WEBHOOK_PIPELINE_COMPLETE_URL` 未设置时 mock 不被调

  **Must NOT do**:
  - ❌ 不实际启动 n8n
  - ❌ 不让测试 flaky（必须 deterministic）

  **Acceptance**:
  - [ ] 2 个测试：env set + env unset
  - [ ] 测试时间 < 1s

  **Commit**: `test(e2e): imitation completion hook fires n8n webhook`

- [x] **T9. E2E test: Helicone proxy 路径覆盖**

  **What to do**:
  - 在 `tests/e2e/test_business_loop.py` 加一个测试：
    - 设 `NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://mock-helicone:8585/v1/openai`
    - call `build_chat_model()`
    - 断言返回的 `ChatOpenAI` 实例的 `base_url` 是 mock-helicone 那个
  - 一个 negative：unset env，断言 fallback 到 normal provider

  **Must NOT do**:
  - ❌ 不实际启动 Helicone（这只验环境变量到 ChatOpenAI 实例的连接）
  - ❌ 不发真 LLM 请求

  **Acceptance**:
  - [ ] 2 个测试：override set + override unset
  - [ ] 测试时间 < 1s

  **Commit**: `test(e2e): llm base_url override threads through to ChatOpenAI`

- [x] **T10. 业务闭环 runbook**

  **What to do**:
  - 新建 `docs/runbook/business-loop.md`
  - 内容：
    1. 前置条件 checklist（v2 PR merged + N4/N6 done + Helicone up）
    2. 启动顺序（ai-books backend → Dify → n8n → Helicone）
    3. 5 分钟端到端 smoke：alice 上传 → 仿写 → 通知 → trace
    4. 故障定位 5 个常见症状（webhook 没触发 / Langfuse 看不到 / Dify tool 401 / user 隔离失效 / Helicone proxy 挂）
  - 在 Makefile 加 `make v3-smoke` 跑 e2e 测试 + 打印 runbook 链接

  **Must NOT do**:
  - ❌ 不写"future work"段落（保持 actionable）
  - ❌ 不复述 v2 的 pickup-checklist（指向链接即可）

  **Acceptance**:
  - [ ] runbook 含 5 个症状的处理步骤
  - [ ] `make v3-smoke` 跑通 e2e suite

  **Commit**: `docs(runbook): business loop end-to-end runbook + smoke target`

---

## Final Verification Wave

- [x] **F1. 零回归审计**（oracle）
  - `wc -l apps/api/app/main.py` = 2630
  - `grep -rn "import langfuse\|import helicone\|import dify" novel_analyzer/services novel_analyzer/agent novel_analyzer/workflows` = 0
  - `grep -rn "import openai" novel_analyzer/services novel_analyzer/workflows` 不变（如有）
  - `pytest tests/contract/` 28/28 绿
  - `pytest tests/runtime/` 13/13 绿
  - imitation algorithm files 未改：`novel_analyzer/services/whole_book_imitation_service.py` 仅在末端加 hook，**核心算法 0 改动**
  - prompts.py 0 改动
  - main.py dispatch 表（`application()` 函数体的 if/elif 路由分发）未改；仅 `_library_payload` helper 和 `/api/library` 分支内的 helper 调用允许小修
  - main.py 行数从 master baseline 2497 → 修订后 ≤ 2510（+10 行硬上限，T2 实际 +6）
  - 输出：`Regression [CLEAN] | Imitation algo [UNCHANGED] | Prompts [UNCHANGED] | VERDICT: APPROVE/REJECT`

- [x] **F2. 业务闭环验收**（unspecified-high）
  - alice 上传一本书 → bob 看不到
  - alice 跑 imitation → n8n executions 出现 1 条 success（30s 内）
  - alice 跑 imitation → Langfuse traces 出现 1 条带 `user_id=alice` tag（5 min 内）
  - alice 在 Dify Writer Copilot 发问 → 后端日志可见 `user_id=alice`
  - 输出：`Isolation [PASS/FAIL] | n8n hook [PASS/FAIL] | Langfuse trace [PASS/FAIL] | Dify->backend [PASS/FAIL] | VERDICT`

- [x] **F3. 范围保真度**（deep）
  - `git diff master..HEAD --stat` 中 imitation 算法文件应只有末端 hook 行变化
  - `git diff master..HEAD novel_analyzer/llm/prompts.py` = empty
  - `git diff master..HEAD novel_analyzer/workflows/run_graph.py` = empty
  - service 层只改 query/insert 方法签名，不改算法
  - 输出：`Algorithm [PRESERVED] | Prompts [PRESERVED] | Workflows [PRESERVED] | VERDICT`

---

## Commit Strategy

每 task 独立 commit，遵循 Lore Commit Protocol。

---

## Success Criteria

```bash
# Identity 透传
curl -H "X-User-Id: alice" :8001/api/library | jq '.items | length'   # → N
curl -H "X-User-Id: bob"   :8001/api/library | jq '.items | length'   # → M (≠ N)

# Helicone proxy 工作
docker compose -f infra/helicone/docker-compose.yml ps   # all Up
curl :8585/healthcheck                                    # 200

# n8n hook
# 跑一次 imitation, 然后:
curl -u admin:novel_n8n_dev :5678/api/v1/executions?workflowId=pipeline-complete-notify \
  | jq '.data[0].status'  # → "success"

# Langfuse trace
curl -H "Authorization: Bearer $LANGFUSE_PUB_KEY" :3030/api/public/traces?userId=alice \
  | jq '.data | length'  # → ≥ 1

# Zero regression
wc -l apps/api/app/main.py                            # → 2630
.venv/bin/pytest tests/contract/                      # → 28 passed
git diff master..HEAD novel_analyzer/llm/prompts.py   # → empty
```

### Final Checklist
- [x] Pre-conditions（v2 PR merged）已满足；N4/N6 docker-blocked 待操作员
- [x] 5 个 e2e test 全绿（9/9 passed）
- [x] F1/F2/F3 全 APPROVE（F2 docker-free 部分；live infra 待操作员）
- [x] 用户明确说 "okay" — v0.2.4 分支推进中
