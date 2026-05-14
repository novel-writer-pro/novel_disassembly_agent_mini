# Writer Studio v5 — FastAPI Cutover

> **目的**：把 v2/v3/v4 累积的"两套 backend"债收掉。`apps/api/app/main.py`（2708 行 WSGI）退役为薄入口，唯一对外服务通过 `apps/api/app/fastapi_app.py` 提供。让 v3 的 `IdentityMiddleware` 终于挂上去，所有 endpoint 自动有 `user_id` / `request_id` / OpenAPI / 一致的错误处理。
>
> **背景**：v2 计划撤回过这件事，v3 plan 显式 must-not，v4 plan 也跳过了。每加一个 endpoint 这笔债就涨一点。**v5 之后做 v6 Reader 长期记忆**——那时候新 endpoint 自动有 IdentityMiddleware 透传，不用再回头补。

---

## TL;DR

> **Quick Summary**：FastAPI 脚手架比想象的成熟很多——10 个 router 文件、40 个 endpoint 已就位。v5 的工作不是"从零迁"，而是 (1) 验 18 个双实现端点的等价性、(2) 把 19 个 WSGI-only endpoint 补到 router、(3) 挂 v3 的 IdentityMiddleware、(4) 切换默认启动入口为 uvicorn、(5) 让 contract test 同时验 WSGI 和 FastAPI 直到 cutover 完成。
>
> **Deliverables**:
> - 双实现 parity test：18 个 endpoint 的 WSGI vs FastAPI 响应等价（schema + status code）
> - 19 个 WSGI-only endpoint 补到现有 router（不新建 router 文件）
> - `IdentityMiddleware` 挂到 `fastapi_app.py`（v3 留下的悬置组件终于生效）
> - 默认启动入口切到 `uvicorn apps.api.app.fastapi_app:app`，端口仍 8011
> - `apps/api/app/main.py` 退役为 ≤100 行 compat shim（保留 application() 给老消费者）
> - Contract test 28/28 同时通过 WSGI 和 FastAPI（双验证期）
> - Makefile / README / runbook 更新启动命令
>
> **Estimated Effort**: Medium-Large（2-3 周 / 1 人）
> **Critical Path**: T1（parity harness）→ T2-T6（修 drift + 补 endpoint）→ T7（middleware）→ T8（cutover）
> **Zero-touch on**：service 层、imitation 算法、prompts、reader/writer 前端、infra 配置
> **不动**：`novel_analyzer/services/*`、`novel_analyzer/llm/*`、`novel_analyzer/workflows/*`

---

## Context

### 真实现状（基于本次摸底）

| 类别 | 数量 | 文件 |
|------|------|------|
| WSGI dispatch | 37 | `main.py` 第 1234-2708 行 |
| FastAPI router 已注册 | 10 | `routers/{loom,writer,quality,library,chapters,risk_review,pipeline,import_recovery,whole_book,steering_character}.py` |
| FastAPI endpoint 总数 | 40 | 不含 `/docs`、`/openapi.json` 等自动 endpoint |
| **双实现端点** | **18** | **WSGI 和 FastAPI 都有** |
| WSGI 独有 | 19 | 未迁 |
| FastAPI 独有 | 22 | router 已实现，WSGI 没有（包括 `/api/loom/*`、`/api/quality/*`、`/api/whole-book/*`、`/api/writer/*` 等 v3/v4 时代的能力） |

### 18 个双实现端点（最大风险）

```
/api/ask-branch                  ← pipeline.py
/api/ask-branch-stream           ← pipeline.py
/api/branch-exports              ← import_recovery.py
/api/branch-snapshot             ← chapters.py
/api/chapter-bundle              ← chapters.py
/api/chapter-jobs                ← chapters.py
/api/chapter-qa-context          ← chapters.py
/api/chapter-source              ← chapters.py
/api/import                      ← import_recovery.py
/api/library                     ← library.py
/api/pipeline/runs               ← pipeline.py
/api/pipeline/start-range        ← pipeline.py
/api/recovery                    ← import_recovery.py
/api/review-cluster-summary      ← risk_review.py
/api/review-cluster-update       ← risk_review.py
/api/review-clusters             ← risk_review.py
/api/run-snapshot                ← library.py
/api/search-branch               ← pipeline.py
```

任何一对的 schema 不一致，cutover 都会破坏调用方契约。**这是 v5 第一个里程碑必须验完的事**，也是为什么 plan 不直接进入"删 WSGI"。

### 19 个 WSGI-only endpoint（需要迁）

```
基础                     /health, /api/meta, /api/mock/import
导入/启动                /api/start (注：/api/import 在双实现, /api/start 是 WSGI-only)
章节副表                /api/chapter-job-events, /api/job-events
评估/监控                /api/runtime-health, /api/provider-health, /api/quality-dashboard
仿写整本                 /api/whole-book-imitation-readiness, /api/whole-book-imitation-run
                         (注：whole_book.py router 里是 /api/whole-book/* 不同前缀，需要决定保留哪一套)
Pipeline 流              /api/pipeline/status, /api/pipeline/progress-stream
Review 历史              /api/review-cluster-history, /api/review-batch-execute, /api/review-batch-history
读者反馈                 /api/reader/feedback, /api/reader/feedback-summary  (v4 新增)
导出                     /api/download
```

### v3 IdentityMiddleware 悬置中

`apps/api/app/middleware/identity.py` 在 v3 commit `b0bbe9d` 时就位但**从未被 `add_middleware` 引用**。`get_current_context()` 在 service 层和 main.py 里都没人调。v5 是它生效的自然时机。

### 启动现状

- WSGI 跑在 `127.0.0.1:8011`（README/runbook 里有处写 8001 的——文档漂移待修）
- `requirements.txt` **没有** `fastapi` / `uvicorn` 显式条目，但 `.venv` 装了（很可能由 `pydantic` 等传递进来或之前手装的）
- 没有 Makefile target 启动 backend（v3 的 `make v2-up-all` 是起 Dify/n8n/Langfuse，不含 backend）

### Contract Test 现状

`tests/contract/test_main_wsgi_contract.py` 直接 `from apps.api.app.main import application` 然后调 `application(environ, start_response)`——纯进程内 WSGI 调用，不走 HTTP。28 测试全绿。

要让它"也验 FastAPI"，需要加一个 parametrize 维度：用 `TestClient(create_app())` 发同样的请求，断言响应等价。

---

## Decisions

### 已定（写入 plan，无需再问）

| 决策点 | 选择 |
|------|------|
| 双实现优先级 | **保留 WSGI 行为为 canonical**，FastAPI 实现需要对齐 WSGI（因为 client 当前打 WSGI） |
| Pydantic schema | **本期不引入**，response 仍 `dict`（迁移聚焦在拓扑，不变信号；schema 留给 v6 候选） |
| WSGI 退役粒度 | **保留 `application()` callable**（≤100 行 compat shim），删 dispatch 表，删 main()。老消费者如果直接 import `application` 不破坏 |
| FastAPI 启动端口 | **保持 8011**，不变 |
| `/api/whole-book-imitation-*` vs `/api/whole-book/*` | **保留 WSGI 那对（带连字符）**，`whole_book.py` 里 `/api/whole-book/*` 这一套先标 deprecated（与 WSGI 不在同一个 path 上，不是 schema 等价问题，是命名空间问题） |
| IdentityMiddleware 接入 | `fastapi_app.py` 的 `create_app()`，放在 CORSMiddleware 之后（即先 CORS 再 Identity） |

### 仍需用户确认（写在 Open Questions）

1. **v6 的边界**：v5 完成后 WSGI main.py 是否真的可以**删掉** application() 函数本身（不是 dispatch 表）？还是说有外部消费者在 import `apps.api.app.main:application`，必须保留？
2. **22 个 FastAPI-only endpoint** 中是否有不该暴露的（比如旧实验路径）？v5 默认全部保留，等用户给清单再说

---

## Work Objectives

### Core Objective
让 backend 只有一个真理来源（`fastapi_app.py`），WSGI dispatch 表退役。把 v3 IdentityMiddleware 挂上去，让 v4 加的 `/api/reader/*` 和未来所有新 endpoint 自动有 user_id 透传。

### Concrete Deliverables

- **D1**：`tests/contract/test_dual_parity.py` — 18 个双实现端点的 WSGI vs FastAPI parity 测试（schema + status + 关键字段）
- **D2**：所有 18 个双实现端点 schema 等价（parity test 全绿）
- **D3**：19 个 WSGI-only endpoint 补到现有 router 文件（不新建 router）
- **D4**：`IdentityMiddleware` 挂到 `fastapi_app.py`，所有 endpoint 经过它
- **D5**：`uvicorn apps.api.app.fastapi_app:app --port 8011` 是默认启动方式（Makefile + README + runbook 更新）
- **D6**：`apps/api/app/main.py` ≤100 行（compat shim，application() 仍可 import）
- **D7**：Contract test 28/28 同时通过 WSGI 和 FastAPI 直到 cutover 当周；之后只走 FastAPI

### Definition of Done

- [ ] `pytest tests/contract/test_dual_parity.py` 18 个 endpoint 全绿
- [ ] `pytest tests/contract/test_main_wsgi_contract.py` 仍 28/28（向后兼容）
- [ ] `pytest tests/contract/test_main_fastapi_contract.py` 28/28（新增，对应 FastAPI 入口）
- [ ] `wc -l apps/api/app/main.py` ≤ 100
- [ ] `grep -c '^    if path ==' apps/api/app/main.py` = 0
- [ ] `curl -H "X-User-Id: alice" :8011/api/library` 返回 alice scoped 数据（IdentityMiddleware 真生效）
- [ ] FastAPI app boots: `uvicorn apps.api.app.fastapi_app:app --port 8011 &` 后 `curl :8011/health` 返回 200
- [ ] OpenAPI docs 可访问：`curl :8011/docs`、`curl :8011/openapi.json` 返回 200
- [ ] 77/77 backend 测试套全绿（v2/v3/v4 累积）
- [ ] 前端调用方（apps/web）无任何改动（端口/路径不变）

### Must Have

- 双实现 parity 必须先验完才动 WSGI 退役
- IdentityMiddleware 必须挂在 CORSMiddleware 之后（保证 CORS preflight 不需要 user_id）
- `application()` callable 保留为 compat 入口（防止外部调用方破坏）
- 端口保持 8011 不变

### Must NOT Have

- ❌ 不引入 Pydantic Request/Response schema（本期不做强类型化）
- ❌ 不动 `novel_analyzer/services/*`、`novel_analyzer/llm/*`、`novel_analyzer/workflows/*`
- ❌ 不动 `apps/web/*`（前端调用 path/port 不变）
- ❌ 不删 `application()` callable（可被外部脚本 import）
- ❌ 不引入新 framework / 新 ORM / 新依赖
- ❌ 不改 v4 的 `/api/reader/*` 行为（迁移而非重写）
- ❌ 不打开 22 个 FastAPI-only endpoint 的"是否合规"审计（推迟）
- ❌ 不引入新 auth / IDP（保持 X-User-Id header stub）

---

## Verification Strategy

### Test Plan

| 类别 | 文件 | 用途 |
|------|------|------|
| 现有 WSGI contract | `tests/contract/test_main_wsgi_contract.py` | 28/28，迁移期间继续守门 |
| 新增 dual parity | `tests/contract/test_dual_parity.py` | 18 个双实现端点 schema 等价（每个 endpoint 调两次，断言关键字段一致） |
| 新增 FastAPI contract | `tests/contract/test_main_fastapi_contract.py` | 同 28 个断言但走 `TestClient(create_app())` |
| 现有所有测试 | `tests/{contract,runtime,api,e2e,test_owner_scoping}` | 77/77 必须全绿 |

### Cutover Gate

WSGI dispatch 表删除（T8）必须满足以下**全部**条件，否则不动手：
1. `test_dual_parity.py` 18/18 绿超过一周
2. `test_main_fastapi_contract.py` 28/28 绿
3. 在 staging（如有）观察过至少 24 小时无 5xx 升高
4. 用户明确批准 cutover

---

## Execution Strategy

### Phases

```
Phase 1 — Parity（不改任何 router/main.py，只读）
  T1  Parity test harness: 18 个双实现端点同步对比

Phase 2 — Drift Fix（按 router 文件分批修）
  T2  library + chapters router parity 修齐
  T3  pipeline + import_recovery router parity 修齐
  T4  risk_review router parity 修齐

Phase 3 — Migration（19 个 WSGI-only 补到现有 router）
  T5  meta/health/mock-import → 新建 routers/meta.py
  T6  reader/start/recovery 收尾、whole-book-imitation 命名空间统一
  T7  pipeline/review/quality/runtime/provider 余下 endpoint

Phase 4 — Middleware（v3 IdentityMiddleware 终于上场）
  T8  IdentityMiddleware 挂入 create_app()，加新版 contract 测试

Phase 5 — Cutover（不可逆）
  T9  Makefile + uvicorn 启动入口、README、runbook 更新
  T10 main.py 退役（删 dispatch 表，保留 application() compat shim）

Phase 6 — Verification
  F1  零回归审计 (oracle)
  F2  双实现下线验收 (deep)
  F3  IdentityMiddleware 端到端验收
```

### Critical Path

```
T1 → T2 → T3 → T4   (Phase 1-2，可串行修各 router)
              ↓
              T5 → T6 → T7   (Phase 3，按 router 分批补)
                       ↓
                       T8     (middleware 接入)
                       ↓
                       T9 → T10  (cutover，不可逆)
                            ↓
                            F1 → F2 → F3
```

### Parallelism

T2/T3/T4 可并行（不同 router），T5/T6/T7 可并行（不同 router）。但 T1 必须先做。

---

## TODOs

- [x] **T1. Parity test harness — 18 个双实现端点同步对比**

  **What to do**:
  - 新建 `tests/contract/test_dual_parity.py`
  - 对 18 个双实现端点，每个写一个测试：
    1. 用 `application()` 调 WSGI（参考现有 contract test 的 fixture）
    2. 用 `TestClient(create_app()).get/post(...)` 调 FastAPI
    3. 断言：status code 相同；JSON keys 相同（深度递归到 1 层）；error 字段含义相同
  - 不断言完全 byte-equal —— 时间戳、UUID、动态 ID 是允许变化的，只断言 schema 等价
  - 输出 fail 时打印 diff（哪些 keys 多/少/类型不同）
  - 测试用 SQLite in-memory 或 mock，不依赖真实 DB（参考 `tests/test_owner_scoping.py` fixture）

  **Must NOT do**:
  - ❌ 不修改任何 router 或 main.py 让测试过（T1 只是定基线，drift 留给 T2-T4 修）
  - ❌ 不引入新依赖

  **Acceptance**:
  - [ ] `pytest tests/contract/test_dual_parity.py -v` 跑出 18 个 case
  - [ ] 至少 1 个 case fail（如果 0 fail 反而可疑——大概率有未发现的 drift）
  - [ ] 失败信息明确指出 drift 位置

  **Commit**: `test(contract): dual-implementation parity harness for 18 endpoints`

- [x] **T2. library + chapters router parity 修齐**

  **What to do**:
  - 看 T1 报告里 `library_list` / `run-snapshot` / `chapter-bundle` / `chapter-source` / `chapter-jobs` / `chapter-qa-context` / `branch-snapshot` 的 drift
  - 修 FastAPI 实现以对齐 WSGI（不改 WSGI 行为）
  - 注意 `/api/library` 在 v3 加过 `owner_user_id` 过滤（X-User-Id header），FastAPI 实现也要加上（用 `Depends(get_current_user)`，T8 接 middleware 之前可以先用 query/header 直接读）
  - 重跑 T1 parity 测试，对应的 case 必须全绿

  **Must NOT do**:
  - ❌ 不改 service 层
  - ❌ 不改 WSGI 实现（保持 canonical）

  **Files**:
  - `apps/api/app/routers/library.py`
  - `apps/api/app/routers/chapters.py`

  **Acceptance**:
  - [ ] T1 中 library + chapters 相关 7 个 case 绿
  - [ ] 现有 contract test 28/28 仍绿

  **Commit**: `fix(api/routers): align library and chapters with WSGI canonical schema`

- [x] **T3. pipeline + import_recovery router parity 修齐**

  **What to do**:
  - 同 T2 模式，针对 `pipeline.py` 和 `import_recovery.py`
  - 涉及端点：`/api/ask-branch`、`/api/ask-branch-stream`、`/api/search-branch`、`/api/pipeline/runs`、`/api/pipeline/start-range`、`/api/import`、`/api/recovery`、`/api/branch-exports`
  - 注意 `/api/ask-branch-stream` 是 SSE 流式，parity 测试只断言事件 type 序列等价（不断言 delta 内容等价）

  **Acceptance**:
  - [ ] T1 中对应 8 个 case 绿
  - [ ] SSE 流式行为一致（type 序列：status → retrieval → status → delta+ → final 或 error）

  **Commit**: `fix(api/routers): align pipeline and import_recovery with WSGI canonical schema`

- [x] **T4. risk_review router parity 修齐**

  **What to do**:
  - 同模式针对 `risk_review.py`
  - 涉及端点：`/api/review-clusters`、`/api/review-cluster-summary`、`/api/review-cluster-update`

  **Acceptance**:
  - [ ] T1 中对应 3 个 case 绿
  - [ ] 现有 contract test 28/28 仍绿

  **Commit**: `fix(api/routers): align risk_review with WSGI canonical schema`

- [x] **T5. meta/health/mock-import → 新建 routers/meta.py**

  **What to do**:
  - 新建 `apps/api/app/routers/meta.py`
  - 迁移：`/health`、`/api/meta`、`/api/mock/import`
  - `/api/meta` 必须返回 `available_endpoints` 列表（保持 schema），但**生成方式改为遍历 FastAPI app.routes**，不再 hardcode `_API_ENDPOINT_SPECS`
  - 在 `fastapi_app.py` 注册新 router

  **Must NOT do**:
  - ❌ 不改 `/api/meta` 的输出 schema（available_endpoints + available_endpoint_specs 都保留）

  **Acceptance**:
  - [ ] `curl :8011/api/meta` 返回 endpoint 列表（应该比 WSGI 多 — 包含 22 个 FastAPI-only 的）
  - [ ] `_API_ENDPOINT_SPECS` 在 main.py 可以删除

  **Commit**: `feat(api/routers): add meta router (health, meta, mock-import)`

- [x] **T6. start/recovery 加固、whole-book-imitation 命名空间统一**

  **What to do**:
  - 把 `/api/start` 加到 `import_recovery.py`（与 `/api/import`、`/api/recovery` 一组）
  - 决定 `/api/whole-book-imitation-readiness`、`/api/whole-book-imitation-run` 怎么处理：
    - 选项 A：保留 WSGI 命名空间（带连字符），加到现有 `whole_book.py` router；废弃 router 里 `/api/whole-book/*` 命名空间
    - 选项 B：用 router 已有的 `/api/whole-book/*` 命名空间，更新前端引用
  - **默认选 A**（前端改动 = 0）；如果用户在 v5 review 时倾向 B，再改

  **Must NOT do**:
  - ❌ 不改 service 调用方式

  **Acceptance**:
  - [ ] `/api/start` 在 FastAPI 可访问
  - [ ] `/api/whole-book-imitation-*` 在 FastAPI 可访问，schema 与 WSGI 等价

  **Commit**: `feat(api/routers): migrate start, recovery, whole-book-imitation endpoints`

- [x] **T7. pipeline/review/quality/runtime/provider/reader/download/job-events 收尾**

  **What to do**:
  - 一次性把剩余 14 个 WSGI-only endpoint 迁完：
    - `pipeline.py`：`/api/pipeline/status`、`/api/pipeline/progress-stream`
    - `risk_review.py`：`/api/review-cluster-history`、`/api/review-batch-execute`、`/api/review-batch-history`
    - `quality.py`：`/api/quality-dashboard`
    - 新建/扩展：`/api/runtime-health`、`/api/provider-health`、`/api/download`、`/api/job-events`、`/api/chapter-job-events`、`/api/reader/feedback`、`/api/reader/feedback-summary`
  - `/api/pipeline/progress-stream` 是 SSE 流式，参考 `/api/ask-branch-stream` 的 `StreamingResponse` 模式
  - `/api/reader/*` (v4 加的) 进新 `reader.py` router，`fastapi_app.py` 注册

  **Acceptance**:
  - [ ] WSGI-only endpoint 数量降为 0（不算 main.py 的 dispatch 函数本身）
  - [ ] 所有 14 个 endpoint 在 FastAPI TestClient 调通
  - [ ] `/api/pipeline/progress-stream` SSE 在 FastAPI 下事件序列与 WSGI 等价

  **Commit**: `feat(api/routers): migrate remaining WSGI-only endpoints to FastAPI`

- [x] **T8. 挂 IdentityMiddleware + 新版 contract 测试**

  **What to do**:
  - `fastapi_app.py` 的 `create_app()` 加 `app.add_middleware(IdentityMiddleware)`，**在 `add_middleware(CORSMiddleware, ...)` 之后**
  - `requirements.txt` 加 `fastapi>=0.115` 和 `uvicorn[standard]>=0.30`（避免依赖隐式安装）
  - 新建 `tests/contract/test_main_fastapi_contract.py`：与 `test_main_wsgi_contract.py` 同样的 28 个断言，但用 `TestClient(create_app())` 触发
  - 在双实现的端点（T2-T4 涉及）加一个新断言：传 `X-User-Id: alice` header → response header 含 `X-Request-Id`、context 在 router 里可读

  **Must NOT do**:
  - ❌ 不在 service 层调 `get_current_user()` / `get_current_context()`（保持业务零渗透；只在 router 层读）

  **Acceptance**:
  - [ ] `pytest tests/contract/test_main_fastapi_contract.py` 28/28 绿
  - [ ] FastAPI 请求带 `X-User-Id: alice` 时，`/api/library` 返回 alice scoped 数据（v3 行为继承）
  - [ ] FastAPI 响应所有都含 `X-Request-Id` header（middleware 自动加）
  - [ ] OpenAPI docs (`/docs`) 可访问
  - [ ] 77/77 测试套全绿

  **Commit**: `feat(api): wire IdentityMiddleware into FastAPI app + add fastapi contract tests`

- [x] **T9. Makefile / uvicorn 启动 / README / runbook 更新**

  **What to do**:
  - Makefile 加：
    ```
    api-dev:
        .venv/bin/uvicorn apps.api.app.fastapi_app:app --host 127.0.0.1 --port 8011 --reload
    api-wsgi-legacy:
        .venv/bin/python -m apps.api.app.main
    ```
  - README "快速启动" 第 3 步改为 `make api-dev`，并标注 `make api-wsgi-legacy` 仅迁移期回滚用
  - runbook (`docs/runbook/business-loop.md`、`docs/runbook/v3-pickup-checklist.md`) 同步
  - 修 README 里 8001 → 8011 的文档漂移

  **Must NOT do**:
  - ❌ 不改端口（保持 8011）
  - ❌ 不在 Makefile 里删除 wsgi-legacy 入口（迁移期保留回滚通道）

  **Acceptance**:
  - [ ] `make api-dev` 启 uvicorn 成功，`curl :8011/health` 返回 200
  - [ ] `make api-wsgi-legacy` 仍可用（兼容期）
  - [ ] README/runbook 中的端口和命令一致

  **Commit**: `chore(api): default launch via uvicorn, keep wsgi-legacy as fallback`

- [x] **T10. main.py 退役（删 dispatch 表，保留 compat shim）**

  **What to do**:
  - 删 `main.py` 第 1234-2702 行的 `application()` 函数体（dispatch 表 37 个分支 + 辅助 helper）
  - 把 `application()` 改成 thin shim：
    ```python
    from apps.api.app.fastapi_app import app as _fastapi_app
    from a2wsgi import ASGIMiddleware  # 或自己写一个最小 ASGI→WSGI bridge

    application = ASGIMiddleware(_fastapi_app)  # 同 ASGI 兼容 WSGI 接口
    ```
    或者更简单：保留 `application` 名字但内容改为
    ```python
    from apps.api.app.fastapi_app import app as application  # 直接当 ASGI 应用导出
    ```
    （取决于是否有 WSGI-only 调用方）
  - main() 函数改为 print "请用 uvicorn 启动" 并退出
  - **决策点**：如果 a2wsgi 引入新依赖不可接受，简化为"`application` 不再保留 WSGI 兼容；外部调用方必须升级到 ASGI"
  - 默认选简化方案；如有外部消费者明确反对再加 a2wsgi

  **Must NOT do**:
  - ❌ 不在 cutover 同一个 commit 里改 schema / 改 service / 改 router 内容
  - ❌ 不删 fastapi_app.py 中的任何 endpoint

  **Acceptance**:
  - [ ] `wc -l apps/api/app/main.py` ≤ 100
  - [ ] `grep -c '^    if path ==' apps/api/app/main.py` = 0
  - [ ] 77/77 测试套全绿
  - [ ] `make api-wsgi-legacy` 退出码为非 0（带友好提示），或者改为 alias 到 `api-dev`

  **Commit**: `refactor(api): retire WSGI dispatch table, FastAPI is the single source of truth`

---

## Final Verification Wave

- [x] **F1. 零回归审计**（oracle）
  - 77/77 backend 测试套全绿
  - `apps/api/app/main.py` ≤ 100 行
  - `service/agent/workflows` 0 改动（git diff master..HEAD 验证）
  - `apps/web/*` 0 改动
  - prompts.py 0 改动
  - 业务代码 0 langfuse/dify/helicone import
  - 输出：`Regression [CLEAN] | VERDICT: APPROVE/REJECT`

- [x] **F2. 双实现下线验收**（deep）
  - `test_dual_parity.py` 18/18 绿
  - `test_main_fastapi_contract.py` 28/28 绿
  - WSGI 和 FastAPI 在 18 个端点上 byte-level 对比（除允许漂移字段）
  - `_API_ENDPOINT_SPECS` 已删除（meta endpoint 改为遍历 app.routes）
  - 输出：`Parity [PASS] | VERDICT`

- [x] **F3. IdentityMiddleware 端到端验收**
  - `curl -H "X-User-Id: alice" :8011/api/library` 返回 alice scoped 数据
  - `curl -H "X-User-Id: bob" :8011/api/library` 返回 bob scoped 数据
  - 任何 response 都含 `X-Request-Id` header
  - 后端日志可见 `user_id=alice` / `user_id=bob` 标记
  - 输出：`Identity [PASS] | VERDICT`

---

## Open Questions

1. **`application()` callable 的外部消费者**：有没有非本仓库的脚本/测试 import `apps.api.app.main:application`？
   - 默认假设：**没有**，T10 选简化方案（`application = fastapi_app` 直接 alias，不引入 a2wsgi）
   - 如果有，告诉我具体位置，T10 改方案

2. **22 个 FastAPI-only endpoint** 是否要审计是否对外暴露？
   - 默认：v5 不动，全部暴露
   - 如果有不该暴露的（比如旧实验），用户列出来，加到 v5.1 删除清单

3. **Pydantic schema 化**：v5 决定不做，留给 v6 候选
   - 若用户希望 v5 顺手做，告诉我，**plan 工时增加 1-2 周**

---

## Commit Strategy

每 task 独立 commit。Lore Commit Protocol。

cutover commit (T10) 必须独立成 commit，不与任何 schema/router 改动混合。

---

## Success Criteria

```bash
make api-dev &
sleep 3

# Identity 透传
curl -H "X-User-Id: alice" :8011/api/library | jq '.items | length'

# 18 双实现 parity
.venv/bin/pytest tests/contract/test_dual_parity.py -q

# FastAPI contract
.venv/bin/pytest tests/contract/test_main_fastapi_contract.py -q

# 全套
.venv/bin/pytest tests/ -q

# main.py 退役
wc -l apps/api/app/main.py   # ≤ 100
grep -c '^    if path ==' apps/api/app/main.py   # = 0

# OpenAPI docs
curl :8011/docs   # 200
curl :8011/openapi.json | jq '.paths | keys | length'   # ≥ 50
```

### Final Checklist
- [ ] D1-D7 全部交付
- [ ] F1/F2/F3 全 APPROVE
- [ ] 用户明确说 "okay"
- [ ] cutover 后至少 24 小时无 5xx 异常（如有 staging）
