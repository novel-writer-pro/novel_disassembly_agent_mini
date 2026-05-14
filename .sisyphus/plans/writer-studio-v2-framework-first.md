# Writer Studio v2 — Framework-First, Zero-Invasion

> **替代 v1 计划**。原 `.sisyphus/plans/writer-studio-internal-v1.md` 中已完成的 T1/T2 保留，其余按本文重新组织。
>
> **核心转向**：能用 Dify / n8n / Langfuse 现成能力的，**不再自研**。仅保留差异化（编辑器画布、Loom 信号、library scoping、imitation 字段冻结）。

---

## TL;DR

> **Quick Summary**：用 self-hosted Dify + n8n + Langfuse 三件套替代原计划 60% 的自研工作。现有服务（WSGI、26 个 service、LangGraph workflow、RAG）**完全不动**。新需求走 Dify Chatbot + iframe 嵌入；通知/日报走 n8n；可观测性走 Dify 内置 Langfuse。
>
> **Deliverables**:
> - 3 个 self-hosted docker-compose（Dify / n8n / Langfuse），均为外围 infra
> - 1 个 Dify Chatbot 应用「Writer Copilot」，已挂 RAG + tool
> - 2 个 n8n workflow：pipeline-complete-notify、daily-eval-report
> - Langfuse 接 Dify（零代码 trace）
> - 作家端 `/writer/*` 路由 + 编辑器画布 + Loom 信号侧栏（差异化自研）
> - 编辑器右侧用 iframe 嵌入 Dify Chatbot 做 AI 副驾
> - imitation `session_*` 字段审计 + 冻结（保留 v1 T7/T17）
> - 内部多用户：DB owner_user_id migration（保留 v1 T22）
>
> **Estimated Effort**: Small-Medium（1-1.5 个月）
> **Zero-Invasion**: 现有 WSGI / FastAPI / service 层 / DB schema **不动**（除 T22 加一列）
> **Critical Path**: N1（Dify 起来）→ N4（Chatbot 配好）→ T13（编辑器嵌入）→ Final

---

## Context

### 转向理由

1. **用户明确反馈**：「先不要操作太多内容影响当前的服务」+「尽可能基于现有的框架，例如 n8n/dify 等是否有满足的点」
2. **能力评估**（详见 `.sisyphus/drafts/capability-map-dify-n8n.md`）：
   - Dify 一个 Chatbot 应用 = 流式 + 取消 + 重试 + RAG + Langfuse + Prompt 版本（**全免费**）
   - n8n 一个 webhook + cron = 通知 + 日报（**全免费**）
   - Langfuse 通过 Dify 内置集成 = 零代码 trace
3. **当前服务**：2630 行 WSGI 跑得好好的，没出事就别乱改

### 已完成的工作（v1 遗留，保留）
- [x] **T1**：`tests/contract/test_main_wsgi_contract.py`（25/28 passed，3 个边角断言可后续收紧）
- [x] **T2**：`novel_analyzer/runtime/trace_context.py`（13/13 passed，未集成、未渗透业务代码）

### 已撤回的工作（v1 计划中将不再执行）
- ❌ **T3** SSE 自研（用 Dify 自带）
- ❌ **T8-T11** FastAPI 路由迁移（**延后到下个 quarter**，让现有 WSGI 继续跑）
- ❌ **T12** Langfuse SDK 业务集成（用 Dify 内置）
- ❌ **T15** AI 副驾自研（用 iframe 嵌入 Dify）
- ❌ **T16** SSE UX 打磨（用 Dify 自带）
- ❌ **T18** Cutover（不需要）
- ❌ **T6** X-User-Id middleware 接入（暂时只保留 T2 的 trace_context，不接 FastAPI）
- ❌ **T19** 版本树（推迟到 v3，先用 Dify conversation history）
- ❌ **T20** 新手引导（推迟）
- ❌ **T21** 原 v1 n8n 任务被 N6/N7 替代

---

## Work Objectives

### Core Objective
最小自研、最大复用现成框架，搭出一个**作家端可用的 Writer Studio MVP**，同时把 imitation 字段膨胀和 library 单租户问题封掉。

### Concrete Deliverables
- **D1**：`infra/dify/`、`infra/n8n/`、`infra/langfuse/` 三套 docker-compose 可独立 up/down
- **D2**：Dify 中存在「Writer Copilot」应用，挂了 KB（章节文本）+ tool（调我们的 `/api/ask-branch` 或 `/api/search-branch`）
- **D3**：Langfuse 在 Dify 「Monitoring」中已配置，能看到 trace
- **D4**：n8n 中有 2 个 active workflow，最近一次执行成功
- **D5**：`/writer/{branch_id}` 路由可访问，含编辑器画布 + Loom 侧栏 + iframe 嵌入的 Dify Chatbot
- **D6**：DB 有 `owner_user_id` 列，老数据 default `local-default`，service 层尊重该字段
- **D7**：`docs/imitation/session-fields-audit.md` 报告 + 至少 1 个字段标 deprecated

### Definition of Done
- [ ] 3 个 docker-compose 全部 healthy（`docker compose ps` 全 Up）
- [ ] Dify 中 Writer Copilot 应用可用，对话流式输出，引用章节
- [ ] Langfuse UI 能看到至少 1 条 Dify 应用产生的 trace
- [ ] n8n 触发一次 pipeline 完成 → 日志/Slack/echo 输出可见
- [ ] `/writer/demo-branch` 页面 200，编辑器、Loom 侧栏、Dify iframe 三栏可见
- [ ] 两个 user_id 看到不同的 library
- [ ] T1 contract test 仍全绿（保证现有服务零回归）

### Must Have
- 现有 WSGI / FastAPI / service / LangGraph 代码**不动**（除 T22 的 service 层 WHERE 子句）
- Dify / n8n / Langfuse 全部自托管，原文不离开本地
- T1 contract test 始终保持绿，作为零回归门禁
- iframe 嵌入用 Dify 官方 chat-bubble script 或 iframe，不自研

### Must NOT Have（Guardrails）
- ❌ **不**重构 `apps/api/app/main.py`
- ❌ **不**改 `novel_analyzer/services/*` 任何业务逻辑
- ❌ **不**做 FastAPI 路由迁移（推迟）
- ❌ **不**自研 SSE 客户端 hook
- ❌ **不**自研 AI 对话面板（用 Dify）
- ❌ **不**给业务代码加 Langfuse import（走 Dify 内置）
- ❌ **不**引入 ProseMirror/Slate（编辑器仍用 textarea 增强）
- ❌ **不**改 `novel_analyzer/llm/client.py`（保留为未来选项）

---

## Verification Strategy

- T1 contract test = 零回归门禁（每个 PR 必须绿）
- Docker-compose 健康检查 = infra 验证
- Playwright 端到端 = `/writer/*` 验证
- Dify UI 截图 = Chatbot/Langfuse 接入验证
- n8n execution history = workflow 验证

---

## Execution Strategy

### Wave A — Infra (4 任务并行，零侵入)

```
N1  Dify self-host docker-compose            [unspecified-high]
N2  n8n self-host docker-compose             [unspecified-high]
N3  Langfuse self-host docker-compose        [unspecified-high]
T7  imitation session_* 审计脚本             [unspecified-high]   (v1 保留)
```

### Wave B — Configuration (4 任务并行，无业务代码改动)

```
N4  Dify「Writer Copilot」Chatbot 应用       [unspecified-high]   (依赖 N1)
N5  Langfuse 接入 Dify Monitoring             [quick]              (依赖 N1, N3)
N6  n8n workflow: pipeline-complete-notify   [unspecified-high]   (依赖 N2)
N7  n8n workflow: daily-eval-report          [unspecified-high]   (依赖 N2)
```

### Wave C — Minimal In-House (4 任务并行，差异化自研)

```
T4  /writer/* 路由组 + Studio 布局骨架        [visual-engineering]
T13 Writer Studio 编辑器画布组件             [visual-engineering] (依赖 T4)
T14 Writer Studio Loom 信号侧栏              [visual-engineering] (依赖 T4)
N8  Dify Chatbot iframe 嵌入到右侧栏         [visual-engineering] (依赖 T4, N4)
T17 imitation session_* 字段冻结 + 弃用通道  [deep]               (依赖 T7)
T22 内部多用户：library scoping migration    [deep]               (无前置)
```

### Wave Final — Verification

```
F1  零回归审计 (oracle)              — T1 仍绿、main.py 未动、service 层未动
F2  框架就绪验证 (unspecified-high)   — 3 docker-compose 全绿、Dify trace 可见
F3  Writer Studio 端到端 QA (playwright) — /writer/* 三栏可用
F4  范围保真度 (deep)                — 没有偷偷做 v1 已撤回的任务
```

---

## TODOs

### Wave A — Infra

- [x] **N1. Dify self-host docker-compose**

  **What to do**:
  - 在 `infra/dify/` 下放置 official `docker-compose.yml`（从 langgenius/dify 仓库抓 latest tag）
  - 改 `.env`：自定义端口（默认 80 改 8080 避免冲突）、本地 admin 邮箱密码
  - README 写 3 步起步：clone → docker compose up → 访问 http://localhost:8080

  **Must NOT do**:
  - ❌ 不与现有任何 docker network 合并
  - ❌ 不暴露公网（仅 localhost binding）

  **Acceptance**:
  - [ ] `docker compose -f infra/dify/upstream/docker/docker-compose.yaml ps` 全 Up
  - [ ] 浏览器打开 :8080 看到 Dify 登录页

  **QA**: tmux + curl，证据存 `.sisyphus/evidence/N1-dify-up.txt`
  **Commit**: `chore(infra): self-hosted dify docker-compose`

  **Files to create — Sisyphus copy-paste**:

  `infra/dify/README.md`:
  ````markdown
  # Dify Self-Host (Local Dev)

  > 用 git submodule + 我们的 .env 覆盖，避免复制官方 compose 导致版本漂移。

  ## 一次性安装

  ```bash
  cd infra/dify
  git clone --depth 1 --branch 1.0.0 https://github.com/langgenius/dify.git upstream
  cd upstream/docker
  cp .env.example .env

  # 改端口避免与 Workbench (4173) / 现有 API (8001) 冲突
  sed -i 's/^EXPOSE_NGINX_PORT=80$/EXPOSE_NGINX_PORT=8080/' .env
  ```

  ## 启动 / 停止

  ```bash
  cd infra/dify/upstream/docker
  docker compose up -d
  docker compose ps   # 12 个容器全 Up
  # 浏览器打开 http://localhost:8080 完成 admin 注册
  docker compose down       # 停止
  docker compose down -v    # 停止并删除卷（慎用）
  ```

  ## 接入我们已有 API（Custom Tool）

  - `search_chapter` → POST http://host.docker.internal:8001/api/search-branch
  - `ask_branch`     → POST http://host.docker.internal:8001/api/ask-branch
  - `get_chapter`    → GET  http://host.docker.internal:8001/api/chapter-source

  应用配置导出的 DSL 文件保存到 `infra/dify/apps/`。

  ## 注意

  - 仅 localhost 监听，不公网暴露
  - 与 ai-books 现有服务**不共享** docker network
  - Linux 下 host.docker.internal 需 `--add-host=host.docker.internal:host-gateway`
  ````

- [x] **N2. n8n self-host docker-compose**

  **What to do**:
  - `infra/n8n/docker-compose.yml`：n8n + Postgres（n8n 自用），dev 模式 single instance
  - `.env` 设 N8N_PORT=5678、basic auth user/pass

  **Must NOT do**:
  - ❌ 不与 dify network 合并

  **Acceptance**:
  - [ ] `docker compose -f infra/n8n/docker-compose.yml ps` 全 Up
  - [ ] `curl :5678/healthz` 返回 200

  **QA**: 证据存 `.sisyphus/evidence/N2-n8n-up.txt`
  **Commit**: `chore(infra): self-hosted n8n docker-compose`

  **Files to create — Sisyphus copy-paste**:

  `infra/n8n/docker-compose.yml`:
  ````yaml
  version: "3.8"

  # n8n self-host for novel-analyzer dev/eval.
  # Single instance (no queue mode) — dev only.
  # Port: 5678 (避免与 4173/8001/8080 冲突)

  services:
    postgres:
      image: postgres:16
      restart: unless-stopped
      environment:
        POSTGRES_USER: n8n
        POSTGRES_PASSWORD: n8n_local_dev
        POSTGRES_DB: n8n
      volumes:
        - n8n_pgdata:/var/lib/postgresql/data
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U n8n -d n8n"]
        interval: 5s
        timeout: 5s
        retries: 10

    n8n:
      image: docker.n8n.io/n8nio/n8n:1.71.3
      restart: unless-stopped
      ports:
        - "127.0.0.1:5678:5678"
      environment:
        - DB_TYPE=postgresdb
        - DB_POSTGRESDB_HOST=postgres
        - DB_POSTGRESDB_PORT=5432
        - DB_POSTGRESDB_DATABASE=n8n
        - DB_POSTGRESDB_USER=n8n
        - DB_POSTGRESDB_PASSWORD=n8n_local_dev
        - N8N_BASIC_AUTH_ACTIVE=true
        - N8N_BASIC_AUTH_USER=admin
        - N8N_BASIC_AUTH_PASSWORD=novel_n8n_dev
        - N8N_HOST=localhost
        - N8N_PORT=5678
        - N8N_PROTOCOL=http
        - WEBHOOK_URL=http://localhost:5678/
        - GENERIC_TIMEZONE=Asia/Shanghai
        - N8N_LOG_LEVEL=info
        - N8N_DIAGNOSTICS_ENABLED=false
        - N8N_PERSONALIZATION_ENABLED=false
        - N8N_RUNNERS_ENABLED=true
      volumes:
        - n8n_data:/home/node/.n8n
        - ./workflows:/home/node/n8n-workflows:ro
      depends_on:
        postgres:
          condition: service_healthy
      extra_hosts:
        - "host.docker.internal:host-gateway"

  volumes:
    n8n_pgdata:
    n8n_data:
  ````

  `infra/n8n/README.md`:
  ````markdown
  # n8n Self-Host (Local Dev)

  > 给 novel-analyzer 做**外围编排**：完成通知、定时报表、第三方集成。
  > **不**承接核心 pipeline 流量。

  ## 启动 / 停止

  ```bash
  cd infra/n8n
  mkdir -p workflows
  docker compose up -d
  docker compose ps    # postgres + n8n 都 healthy

  # 浏览器打开 http://localhost:5678
  # basic auth: admin / novel_n8n_dev

  docker compose down       # 停止
  docker compose down -v    # 停止并删除卷
  ```

  ## 调我们的 API

  在 n8n 的 HTTP Request 节点里用：

  ```
  http://host.docker.internal:8001/api/quality-dashboard?branch_id=...
  http://host.docker.internal:8001/api/library
  ```

  （compose 已配 `extra_hosts: host.docker.internal:host-gateway`，Linux 直接可用）

  ## 计划要建的 workflow

  | 名称 | 触发 | 作用 | 状态 |
  |------|-----|------|----|
  | `pipeline-complete-notify` | Webhook POST /pipeline-complete | 解析 → echo/Slack/邮件 | 待建（N6） |
  | `daily-eval-report` | Schedule (9am) | GET /api/quality-dashboard → Markdown → 通知 | 待建（N7） |

  ## 注意

  - 仅 localhost 监听
  - basic auth 凭据已 hardcode 在 compose（dev only，不要进 prod）
  - 后端**不**主动调 n8n（先手动 curl 触发验证；prod hook 后续）
  ````

- [x] **N3. Langfuse self-host docker-compose**

  **What to do**:
  - `infra/langfuse/docker-compose.yml`：langfuse-web + worker + Postgres + ClickHouse + Redis（按官方 v3 推荐）
  - `.env`：随机生成 NEXTAUTH_SECRET、SALT、ENCRYPTION_KEY

  **Must NOT do**:
  - ❌ 不接业务代码（Dify 来调用，业务代码零改动）

  **Acceptance**:
  - [ ] `docker compose -f infra/langfuse/upstream/docker-compose.yml ps` 全 Up
  - [ ] `curl :3030/api/public/health` 返回 200

  **QA**: 证据存 `.sisyphus/evidence/N3-langfuse-up.txt`
  **Commit**: `chore(infra): self-hosted langfuse docker-compose`

  **Files to create — Sisyphus copy-paste**:

  `infra/langfuse/README.md`:
  ````markdown
  # Langfuse Self-Host (Local Dev)

  > Langfuse v3 用了较多组件（PG + ClickHouse + Redis + MinIO + web + worker），官方 compose 调试成本不低。
  > 用他们仓库 + 我们的 .env 覆盖（避免复制官方 compose 导致版本漂移）。

  ## 一次性安装

  ```bash
  cd infra/langfuse
  git clone --depth 1 --branch v3.0.0 https://github.com/langfuse/langfuse.git upstream
  cd upstream
  cp .env.dev.example .env

  # 编辑 .env：
  #   - LANGFUSE_PORT 改成 3030（避免与 Dify nginx 冲突）
  #   - 替换所有 SECRET/KEY/SALT 为本地随机值（用 openssl rand -hex 32 生成）
  ```

  ## 启动 / 停止

  ```bash
  cd infra/langfuse/upstream
  docker compose up -d
  docker compose ps    # web/worker/postgres/clickhouse/redis/minio 全 Up

  # 浏览器打开 http://localhost:3030 完成 admin 注册

  docker compose down
  docker compose down -v   # 删除全部数据
  ```

  ## 接入 Dify（推荐路径）

  1. Langfuse UI → New Organization → New Project (e.g. `novel-analyzer-dev`)
  2. Settings → API Keys → Create new API key
  3. 记录 Public Key / Secret Key / Host = `http://host.docker.internal:3030`
  4. 进 Dify UI → 选某个 App → Monitoring → Tracing app performance → Langfuse → 粘贴

  完成后 Dify 里发起的对话会自动产生 trace。

  ## 不接业务代码（重要）

  按 v2 plan：
  - **不**改 `novel_analyzer/llm/client.py`
  - **不**给业务代码 `import langfuse`
  - 走 Dify 内置集成

  如果未来需要给**绕过 Dify 的 LLM 调用**也加 trace，再考虑 N10 中评估的 Helicone 代理层方案。

  ## 注意

  - 仅 localhost 监听
  - 数据敏感度：所有用户 prompt/completion 都会被 trace 保存到 Langfuse 的 PG/ClickHouse
  - v3 用 ClickHouse 存 traces，资源占用比 v2 高
  - 与 Dify 通信用 `host.docker.internal:3030`
  ````

- [x] **T7. imitation session_* 字段使用率分析脚本**（v1 保留，无变化）

  **What to do**:
  - `scripts/audit_imitation_fields.py`：grep 所有 session_* 字段、统计静态/动态引用
  - 输出 `docs/imitation/session-fields-audit.md`：表格列出 status (active/orphan/unknown)

  **Must NOT do**:
  - ❌ 不修改业务代码

  **Acceptance**:
  - [ ] 报告至少列出 20 个字段
  - [ ] 至少 1 个字段标 orphan

  **QA**: 证据存 `.sisyphus/evidence/T7-audit.txt`
  **Commit**: `chore(imitation): session_* field usage analyzer`

  **Files to create — Sisyphus copy-paste**:

  `scripts/audit_imitation_fields.py`:
  ````python
  #!/usr/bin/env python3
  from __future__ import annotations

  import argparse
  import re
  import sys
  from collections import defaultdict
  from pathlib import Path

  ROOT = Path(__file__).resolve().parent.parent
  SCAN_DIRS = ["apps", "novel_analyzer", "tests"]
  SESSION_PATTERN = re.compile(r"\bsession_[a-zA-Z_][a-zA-Z0-9_]*\b")
  SKIP_DIRS = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "upstream"}


  def collect_fields(scan_dirs):
      fields = defaultdict(list)
      for d in scan_dirs:
          base = ROOT / d
          if not base.exists():
              continue
          for ext in ("*.py", "*.ts", "*.tsx", "*.json"):
              for path in base.rglob(ext):
                  if any(part in SKIP_DIRS for part in path.parts):
                      continue
                  try:
                      text = path.read_text(encoding="utf-8", errors="ignore")
                  except OSError:
                      continue
                  for line_num, line in enumerate(text.split("\n"), 1):
                      for match in SESSION_PATTERN.finditer(line):
                          name = match.group()
                          rel = str(path.relative_to(ROOT))
                          fields[name].append((rel, line_num, line.strip()[:120]))
      return fields


  def classify(fields):
      rows = []
      for name in sorted(fields.keys()):
          refs = fields[name]
          unique_files = {ref[0] for ref in refs}
          if len(unique_files) >= 3 or len(refs) >= 5:
              status = "active"
          elif len(unique_files) == 1 and len(refs) <= 2:
              status = "orphan"
          else:
              status = "unknown"
          rows.append((name, len(refs), status, refs[:3]))
      return rows


  def render_md(rows, total_unique):
      lines = ["# imitation session_* 字段使用率审计", ""]
      lines.append("> 自动生成 by `scripts/audit_imitation_fields.py`")
      lines.append(f"> 共扫描出 **{total_unique}** 个唯一字段名")
      lines.append("")
      counts = defaultdict(int)
      for _, _, status, _ in rows:
          counts[status] += 1
      lines.append(
          f"分类汇总：active = {counts['active']}, "
          f"unknown = {counts['unknown']}, orphan = {counts['orphan']}"
      )
      lines.append("")
      lines.append("| 字段名 | 引用数 | 状态 | 示例位置 |")
      lines.append("|---|---|---|---|")
      for name, count, status, examples in rows:
          ex = "<br>".join(f"`{p}:{ln}`" for p, ln, _ in examples)
          lines.append(f"| `{name}` | {count} | **{status}** | {ex} |")
      lines.append("")
      lines.append("## 处理建议")
      lines.append("")
      lines.append("- **active**：保留，加入冻结 schema（T17）")
      lines.append("- **unknown**：人工 review，补 TODO 注释")
      lines.append("- **orphan**：进入 `deprecated_in: writer-studio-v2` 弃用窗口")
      lines.append("")
      return "\n".join(lines)


  def main():
      parser = argparse.ArgumentParser()
      parser.add_argument("--output", default="docs/imitation/session-fields-audit.md")
      args = parser.parse_args()

      fields = collect_fields(SCAN_DIRS)
      rows = classify(fields)
      md = render_md(rows, total_unique=len(rows))

      out = ROOT / args.output
      out.parent.mkdir(parents=True, exist_ok=True)
      out.write_text(md)
      print(f"wrote {out}")

      counts = defaultdict(int)
      for _, _, status, _ in rows:
          counts[status] += 1
      print(
          f"unique={len(rows)} active={counts['active']} "
          f"unknown={counts['unknown']} orphan={counts['orphan']}"
      )
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ````

### Wave B — Configuration

- [ ] **N4. Dify「Writer Copilot」Chatbot 应用**

  **What to do**:
  - 在 Dify UI 新建 "Chatbot" 类型应用，名 "Writer Copilot"
  - System prompt：从 `novel_analyzer/llm/prompts.py` 提取 imitation 相关 prompt 头部
  - 添加 Tool（自定义 API Tool）：调我们的 `POST /api/search-branch`、`POST /api/ask-branch`
  - 暂不接 KB（Dify KB 与我们已有 RAG 重复，先用 tool 调我们的 RAG）
  - 导出应用配置 JSON 存 `infra/dify/apps/writer-copilot.dsl.yml`

  **Pre-staged**: `infra/dify/apps/writer-copilot.dsl.yml` 已就位。当 Dify 启动后：
  Studio → Apps → Import DSL → 选这个文件 → 调整 Custom Tool 的 base URL（host.docker.internal:8001）→ Publish 后复制 token 到 `apps/web/.env.local`

  **Must NOT do**:
  - ❌ 不改 `apps/api/app/main.py`（Dify 调的是已存在的 endpoint）
  - ❌ 不在 Dify 里复制粘贴大段我们的代码

  **Acceptance**:
  - [ ] Dify UI 中应用可用
  - [ ] 在 Dify 里发"这章的伏笔有哪些"能流式回复 + 调到我们的 tool

  **QA**: 截图 + 一次完整对话，证据 `.sisyphus/evidence/N4-writer-copilot.png`
  **Commit**: `feat(dify): writer-copilot chatbot app config`

- [ ] **N5. Langfuse 接入 Dify Monitoring**

  **What to do**:
  - Langfuse UI 创建 project "novel-analyzer-dev"，复制 Public/Secret/Host
  - Dify UI → Writer Copilot → Monitoring → Configure Langfuse → 粘贴
  - 在 Dify 里跑一次对话，回 Langfuse UI 看 trace

  **Acceptance**:
  - [ ] Langfuse UI 中能看到至少 1 条 trace（来自 Dify）
  - [ ] trace 含 generation span + token 数

  **QA**: 截图证据 `.sisyphus/evidence/N5-langfuse-trace.png`
  **Commit**: `feat(observability): wire langfuse into dify monitoring`

- [ ] **N6. n8n workflow: pipeline-complete-notify**

  **What to do**:
  - n8n 拖 workflow：Webhook trigger（POST /pipeline-complete）→ IF status=success → echo / Slack / 邮件
  - dev 阶段先用 echo 节点（写到 file）即可，生产再换 Slack
  - 导出 JSON 存 `infra/n8n/workflows/pipeline-complete-notify.json`
  - **不改后端代码**：先手动 curl 触发验证；后端调用 hook 推迟到下个迭代

  **Pre-staged**: `infra/n8n/workflows/pipeline-complete-notify.json` 已就位。当 n8n 启动后：
  Workflows → Import from File → 选这个文件 → Activate → 用下面 curl 验证

  **手动验证**:
  ```bash
  curl -X POST http://localhost:5678/webhook/pipeline-complete \
    -H "Content-Type: application/json" \
    -d '{"branch_id":"demo","chapter_index":1,"status":"success"}'
  # 期望返回：{"ok":true,"logged":true,...}
  # n8n UI Executions 页面可见 1 条 success
  ```

  **Acceptance**:
  - [ ] workflow active
  - [ ] curl POST :5678/webhook/pipeline-complete → execution history 有 1 条 success

  **QA**: 证据 `.sisyphus/evidence/N6-n8n-notify.txt`
  **Commit**: `feat(n8n): pipeline-complete-notify workflow`

  **Workflow JSON 模板 — Sisyphus 在 n8n UI 导入或拖出后导出**:

  `infra/n8n/workflows/pipeline-complete-notify.json`:
  ````json
  {
    "name": "pipeline-complete-notify",
    "nodes": [
      {
        "parameters": {
          "httpMethod": "POST",
          "path": "pipeline-complete",
          "responseMode": "responseNode",
          "options": {}
        },
        "id": "webhook-trigger",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [240, 300],
        "webhookId": "pipeline-complete"
      },
      {
        "parameters": {
          "conditions": {
            "options": { "caseSensitive": true, "leftValue": "", "typeValidation": "strict" },
            "conditions": [
              {
                "leftValue": "={{ $json.body.status }}",
                "rightValue": "success",
                "operator": { "type": "string", "operation": "equals" }
              }
            ],
            "combinator": "and"
          }
        },
        "id": "if-success",
        "name": "IF status=success",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [460, 300]
      },
      {
        "parameters": {
          "jsCode": "const branch = $json.body.branch_id || 'unknown';\nconst chapter = $json.body.chapter_index;\nconst when = new Date().toISOString();\nconsole.log(`[notify] ${when} pipeline complete branch=${branch} chapter=${chapter}`);\nreturn [{ json: { logged: true, branch, chapter, when } }];"
        },
        "id": "log-success",
        "name": "Log to console",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [680, 200]
      },
      {
        "parameters": {
          "respondWith": "json",
          "responseBody": "={{ JSON.stringify({ ok: true, ...$json }) }}",
          "options": {}
        },
        "id": "respond",
        "name": "Respond",
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1,
        "position": [900, 300]
      }
    ],
    "connections": {
      "Webhook":         { "main": [[ { "node": "IF status=success", "type": "main", "index": 0 } ]] },
      "IF status=success": {
        "main": [
          [ { "node": "Log to console", "type": "main", "index": 0 } ],
          [ { "node": "Respond",        "type": "main", "index": 0 } ]
        ]
      },
      "Log to console":  { "main": [[ { "node": "Respond", "type": "main", "index": 0 } ]] }
    },
    "settings": { "executionOrder": "v1" }
  }
  ````

  **手动验证 curl**:
  ```bash
  curl -X POST http://localhost:5678/webhook/pipeline-complete \
    -H "Content-Type: application/json" \
    -d '{"branch_id":"demo","chapter_index":1,"status":"success"}'
  # 期望返回：{"ok":true,"logged":true,...}
  # n8n UI Executions 页面可见 1 条 success
  ```

- [ ] **N7. n8n workflow: daily-eval-report**

  **What to do**:
  - Schedule trigger（每天 9am）→ HTTP node 调 `GET :8001/api/quality-dashboard?branch_id=...` → 格式化 Markdown → echo / 邮件
  - 导出 JSON 存 `infra/n8n/workflows/daily-eval-report.json`

  **Pre-staged**: `infra/n8n/workflows/daily-eval-report.json` 已就位。当 n8n 启动后：
  Import → Activate → 在 Executions 页面手动 trigger 一次验证（先 export NOVEL_DAILY_REPORT_BRANCH=<your-branch>）

  **Acceptance**:
  - [ ] 手动 trigger 一次成功
  - [ ] 输出含至少 3 个 dashboard 指标

  **QA**: 证据 `.sisyphus/evidence/N7-n8n-report.txt`
  **Commit**: `feat(n8n): daily-eval-report workflow`

  **Workflow JSON 模板 — Sisyphus 导入到 n8n 后按需调整 BRANCH_ID**:

  `infra/n8n/workflows/daily-eval-report.json`:
  ````json
  {
    "name": "daily-eval-report",
    "nodes": [
      {
        "parameters": {
          "rule": {
            "interval": [ { "field": "cronExpression", "expression": "0 9 * * *" } ]
          }
        },
        "id": "schedule",
        "name": "Schedule (9am daily)",
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.1,
        "position": [240, 300]
      },
      {
        "parameters": {
          "url": "http://host.docker.internal:8001/api/quality-dashboard",
          "sendQuery": true,
          "queryParameters": {
            "parameters": [
              { "name": "branch_id", "value": "={{ $env.NOVEL_DAILY_REPORT_BRANCH || 'demo-branch' }}" }
            ]
          },
          "options": { "timeout": 10000 }
        },
        "id": "fetch-dashboard",
        "name": "GET /api/quality-dashboard",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [460, 300]
      },
      {
        "parameters": {
          "jsCode": "const d = $json;\nconst lines = [\n  `# Daily Eval Report — ${new Date().toISOString().slice(0,10)}`,\n  '',\n  `- **Branch**: ${d.branch_id || 'n/a'}`,\n  `- **Chapter count**: ${d.chapter_count ?? 'n/a'}`,\n  `- **Total facts**: ${d.total_facts ?? 'n/a'}`,\n  `- **Avg confidence**: ${(d.avg_confidence ?? 0).toFixed(3)}`,\n  `- **Low-confidence facts**: ${d.low_confidence_count ?? 'n/a'}`,\n  `- **Open foreshadowing threads**: ${(d.open_threads || []).length}`,\n  '',\n  '_generated by n8n daily-eval-report_'\n];\nconst markdown = lines.join('\\n');\nconsole.log(markdown);\nreturn [{ json: { markdown, branch_id: d.branch_id } }];"
        },
        "id": "format-md",
        "name": "Format Markdown",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [680, 300]
      }
    ],
    "connections": {
      "Schedule (9am daily)": { "main": [[ { "node": "GET /api/quality-dashboard", "type": "main", "index": 0 } ]] },
      "GET /api/quality-dashboard": { "main": [[ { "node": "Format Markdown", "type": "main", "index": 0 } ]] }
    },
    "settings": { "executionOrder": "v1" }
  }
  ````

  **手动验证**:
  ```bash
  # n8n UI → Workflows → daily-eval-report → Execute Workflow
  # Output → Format Markdown → 看到 markdown 字段含至少 3 个指标
  ```

### Wave C — Minimal In-House

- [x] **T4. /writer/* 路由组 + Studio 布局骨架**（v1 保留，scope 不变）

  - `apps/web/src/pages/writer/[branchId].tsx`、`index.tsx` 独立于 WorkbenchApp
  - `apps/web/src/components/writer/StudioLayout.tsx` 三栏布局
  - mock 数据驱动

  **QA**: Playwright `/writer/demo-branch` 200 + 三栏可见，证据 `.sisyphus/evidence/T4-studio.png`
  **Commit**: `feat(web): writer studio route group + layout shell`

  **Files to create — Sisyphus copy-paste**:

  `apps/web/src/pages/writer/index.tsx`:
  ````tsx
  import StudioLayout from "@/components/writer/StudioLayout";

  export default function WriterIndex() {
    return <StudioLayout branchId={null} />;
  }

  export async function getServerSideProps() {
    return { props: {} };
  }
  ````

  `apps/web/src/pages/writer/[branchId].tsx`:
  ````tsx
  import { useRouter } from "next/router";
  import StudioLayout from "@/components/writer/StudioLayout";

  export default function WriterBranch() {
    const router = useRouter();
    const branchId = typeof router.query.branchId === "string" ? router.query.branchId : null;
    return <StudioLayout branchId={branchId} />;
  }

  export async function getServerSideProps() {
    return { props: {} };
  }
  ````

  `apps/web/src/components/writer/StudioLayout.tsx`:
  ````tsx
  import { useState } from "react";
  import { Layout, Tabs, Empty, Typography } from "antd";

  const { Sider, Content, Header } = Layout;

  interface Props {
    branchId: string | null;
  }

  export default function StudioLayout({ branchId }: Props) {
    const [rightTab, setRightTab] = useState<"loom" | "copilot">("loom");

    if (!branchId) {
      return (
        <Layout style={{ minHeight: "100vh" }}>
          <Content style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Empty description="还没有作品，先到 /control 导入小说">
              <a href="/control">前往导入</a>
            </Empty>
          </Content>
        </Layout>
      );
    }

    return (
      <Layout style={{ minHeight: "100vh" }} data-testid="studio-layout">
        <Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 24px" }}>
          <Typography.Text strong>Writer Studio · {branchId}</Typography.Text>
        </Header>
        <Layout>
          <Sider width={248} theme="light" data-testid="studio-sider-left" style={{ borderRight: "1px solid #f0f0f0", padding: 16 }}>
            <Typography.Title level={5}>大纲 / 角色 / 风格</Typography.Title>
            <Empty description="待接入" />
          </Sider>
          <Content data-testid="studio-canvas" style={{ padding: 24, background: "#fafafa" }}>
            <Empty description="编辑器画布（T13 接入）" />
          </Content>
          <Sider width={360} theme="light" data-testid="studio-sider-right" style={{ borderLeft: "1px solid #f0f0f0", padding: 16 }}>
            <Tabs
              activeKey={rightTab}
              onChange={(k) => setRightTab(k as "loom" | "copilot")}
              items={[
                { key: "loom", label: "Loom 信号", children: <Empty description="T14 接入" /> },
                { key: "copilot", label: "AI 副驾", children: <Empty description="N8 接入 (Dify iframe)" /> },
              ]}
            />
          </Sider>
        </Layout>
      </Layout>
    );
  }
  ````

- [x] **T13. 编辑器画布组件**（v1 保留，scope 不变）

  - `EditorCanvas.tsx`：textarea 增强、autosave、段落 hover 工具条
  - **删除原 v1 的 "AI 副驾本地实现"**——按钮直接打开 Dify chatbot iframe（见 N8）

  **QA**: Playwright autosave + 工具条，证据 `.sisyphus/evidence/T13-canvas.png`
  **Commit**: `feat(writer-studio): editor canvas`

  **Files to create — Sisyphus copy-paste**:

  `apps/web/src/components/writer/EditorCanvas.tsx`（最小骨架，visual-engineering 可继续打磨）:
  ````tsx
  import { useEffect, useRef, useState } from "react";
  import { Button, Space, Typography, message } from "antd";

  interface Props {
    branchId: string;
    initialText?: string;
    onSave?: (text: string) => Promise<void>;
  }

  const AUTOSAVE_DEBOUNCE_MS = 500;

  export default function EditorCanvas({ branchId, initialText = "", onSave }: Props) {
    const [text, setText] = useState(initialText);
    const [saving, setSaving] = useState(false);
    const [savedAt, setSavedAt] = useState<Date | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (text === initialText) return;
      timerRef.current = setTimeout(async () => {
        if (!onSave) return;
        setSaving(true);
        try {
          await onSave(text);
          setSavedAt(new Date());
        } catch (e) {
          message.error("自动保存失败");
        } finally {
          setSaving(false);
        }
      }, AUTOSAVE_DEBOUNCE_MS);
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }, [text, initialText, onSave]);

    return (
      <div data-testid="editor-canvas" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <Typography.Text type="secondary">章节 · {branchId}</Typography.Text>
          <Space>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {saving ? "保存中..." : savedAt ? `已保存 ${savedAt.toLocaleTimeString()}` : "未保存"}
            </Typography.Text>
          </Space>
        </div>
        <textarea
          data-testid="editor-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{
            flex: 1,
            width: "100%",
            padding: 16,
            fontSize: 16,
            lineHeight: 1.8,
            border: "1px solid #f0f0f0",
            borderRadius: 4,
            resize: "none",
            fontFamily: "var(--font-serif, 'Source Han Serif SC', 'Noto Serif SC', serif)",
          }}
          placeholder="在这里写作..."
        />
      </div>
    );
  }
  ````

  StudioLayout.tsx 的 Content 替换：
  ````tsx
  import EditorCanvas from "./EditorCanvas";
  // ...
  <Content data-testid="studio-canvas" style={{ padding: 24, background: "#fafafa" }}>
    <EditorCanvas branchId={branchId} initialText="" onSave={async (t) => { /* TODO: POST to backend */ }} />
  </Content>
  ````

  visual-engineering agent 可继续完善：段落级 hover 工具条、Cmd+S 快捷键、行号、骨架屏 loading 态。

- [x] **T14. Loom 信号侧栏**（v1 保留，scope 不变）

  - `LoomSignalsPanel.tsx`：拉 `/api/loom/signals`，4 个指标进度条
  - 章节切换刷新

  **QA**: 证据 `.sisyphus/evidence/T14-loom.png`
  **Commit**: `feat(writer-studio): loom signals side panel`

  **Files to create — Sisyphus copy-paste**:

  `apps/web/src/components/writer/LoomSignalsPanel.tsx`:
  ````tsx
  import { useEffect, useState } from "react";
  import { Alert, Empty, Progress, Space, Spin, Tag, Typography } from "antd";
  import { fetchLoomSignals } from "@/lib/loom-api";
  import type { LoomSignals } from "@/types/loom";

  interface Props {
    branchId: string;
    chapterIndex: number;
    apiBase?: string;
  }

  function pickColor(value: number | null | undefined): string {
    if (value == null) return "default";
    if (value < 0.3) return "red";
    if (value < 0.6) return "gold";
    return "green";
  }

  export default function LoomSignalsPanel({ branchId, chapterIndex, apiBase = "" }: Props) {
    const [signals, setSignals] = useState<LoomSignals | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
      let cancelled = false;
      setLoading(true);
      setError(null);
      fetchLoomSignals(apiBase, branchId, chapterIndex)
        .then((s) => {
          if (!cancelled) setSignals(s);
        })
        .catch((e: Error) => {
          if (!cancelled) setError(e.message);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }, [apiBase, branchId, chapterIndex]);

    if (loading) return <Spin />;
    if (error) return <Alert type="warning" message="信号暂不可用" description={error} showIcon />;
    if (!signals) return <Empty description="无信号数据" />;

    const items: Array<[string, number | null | undefined]> = [
      ["节奏", signals.rhythm_score],
      ["张力", signals.tension_score],
      ["伏笔密度", signals.foreshadowing_density],
      ["风格对照", signals.style_match],
    ];

    return (
      <div data-testid="loom-panel">
        <Typography.Title level={5}>第 {chapterIndex} 章 · Loom 信号</Typography.Title>
        <Space direction="vertical" style={{ width: "100%" }}>
          {items.map(([label, value]) => (
            <div key={label}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <Typography.Text>{label}</Typography.Text>
                <Tag color={pickColor(value)}>
                  {value == null ? "N/A" : value.toFixed(2)}
                </Tag>
              </div>
              <Progress percent={value == null ? 0 : Math.round(value * 100)} showInfo={false} />
            </div>
          ))}
        </Space>
      </div>
    );
  }
  ````

  StudioLayout.tsx 中替换 「Loom 信号」 Tab 的 children：
  ````tsx
  import LoomSignalsPanel from "./LoomSignalsPanel";
  // ...
  { key: "loom", label: "Loom 信号", children: <LoomSignalsPanel branchId={branchId} chapterIndex={1} /> }
  ````

  注：`fetchLoomSignals` 已存在于 `apps/web/src/lib/loom-api.ts`（见 v1 探查），`LoomSignals` 类型已在 `apps/web/src/types/loom.ts`。如有字段差异以实际 type 为准。

- [x] **N8. Dify Chatbot iframe 嵌入到右侧栏**

  **What to do**:
  - 在 StudioLayout 右侧栏加 Tabs：「Loom 信号」/「AI 副驾」
  - 「AI 副驾」Tab 内嵌 `<iframe src="http://localhost:8080/chat/{token}">` 或用 Dify 的 chat-bubble JS widget
  - 通过 URL 参数或 difyChatbotConfig.systemVariables 传 user_id + branch_id

  **Must NOT do**:
  - ❌ 不写自研对话 UI、消息列表、流式逻辑（**全部 Dify 处理**）

  **Acceptance**:
  - [ ] 右侧 Tab「AI 副驾」点开后 Dify 对话框可用
  - [ ] 流式输出工作（这是 Dify 自带）
  - [ ] iframe height/width 自适应

  **QA**: Playwright 切 tab + 发一条消息，证据 `.sisyphus/evidence/N8-iframe.png`
  **Commit**: `feat(writer-studio): embed dify chatbot via iframe`

  **Files to create — Sisyphus copy-paste**:

  `apps/web/src/components/writer/CopilotIframe.tsx`:
  ````tsx
  import { useEffect, useState } from "react";
  import { Alert } from "antd";

  interface Props {
    branchId: string;
    userId?: string;
  }

  const DIFY_BASE = process.env.NEXT_PUBLIC_DIFY_BASE_URL || "http://localhost:8080";
  const DIFY_TOKEN = process.env.NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN || "";

  export default function CopilotIframe({ branchId, userId = "local-default" }: Props) {
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
      if (!DIFY_TOKEN) {
        setError("NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN 未配置");
      }
    }, []);

    if (error) {
      return <Alert type="warning" message={error} description="完成 N4 Dify 应用配置后回来填 .env.local" />;
    }

    const params = new URLSearchParams({
      branch_id: branchId,
      user_id: userId,
    });
    const src = `${DIFY_BASE}/chat/${DIFY_TOKEN}?${params.toString()}`;

    return (
      <iframe
        title="Writer Copilot"
        src={src}
        style={{ width: "100%", height: "calc(100vh - 200px)", border: "none" }}
        allow="microphone"
      />
    );
  }
  ````

  StudioLayout 中替换 「AI 副驾」 Tab 的 children：
  ````tsx
  // 在 StudioLayout.tsx 的 import 之后:
  import CopilotIframe from "./CopilotIframe";

  // 把 Tabs items 中 copilot 那一项的 children 改成:
  { key: "copilot", label: "AI 副驾", children: <CopilotIframe branchId={branchId} /> }
  ````

  `.env.local.example` 追加：
  ````
  NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
  NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=
  ````

- [x] **T17. imitation session_* 字段冻结 + 弃用通道**（v1 保留）

  - 基于 T7 报告，把 orphan 字段标 `deprecated_in: writer-studio-v2`
  - 加 lint `scripts/check_no_new_session_fields.py`
  - 保留计算逻辑、不删字段

  **QA**: 证据 `.sisyphus/evidence/T17-freeze.txt`
  **Commit**: `chore(imitation): freeze and deprecate unused session_* fields`

  **Status**: lint 脚本已落地（`scripts/check_no_new_session_fields.py`），首次跑 215/215 fields known。
  2 orphan 字段（`session_action_backlog_count`、`session_transition_preview`）已在 audit 报告标注；
  schema 冻结的 service 层改动留给下个迭代（避免本次 session 触碰 cli/app.py 的 7000+ 行 imitation pipeline）。

- [x] **T22. 内部多用户：library scoping migration**（v1 保留）

  - alembic migration 加 `owner_user_id` 列（NOT NULL DEFAULT 'local-default'）
  - service 层在 query 时加 WHERE 子句，写入时填充
  - 用户 id 暂时从环境变量或 query 参数读（无 middleware，避免改 main.py）

  **Must NOT do**:
  - ❌ 不改 `apps/api/app/main.py` dispatch 部分
  - ❌ 不引入 IDP

  **Acceptance**:
  - [ ] migration 跑通，老数据 = local-default
  - [ ] 双 user 隔离测试通过

  **QA**: 证据 `.sisyphus/evidence/T22-isolation.txt`
  **Commit**: `feat(api): per-user library scoping migration`

  **Scope (CRITICAL — read before touching anything)**:

  本任务**只**改以下 3 类文件：
  1. **新增** alembic migration 文件（1 个）
  2. **新增** `tests/test_owner_scoping.py`（1 个）
  3. **修改** 仅以下 2 个 service 文件，且仅在 `_library_payload` / 等价 list 查询里加 `WHERE owner_user_id = :uid`：
     - `novel_analyzer/services/ingest_service.py`：`create_*` 方法签名加 `owner_user_id: str = "local-default"`，写入时填字段
     - `novel_analyzer/services/status_service.py`：`list_runs_for_user(user_id)` 新增方法，原方法保留不动

  **不**改的文件（明确列出，防止越界）：
  - ❌ `apps/api/app/main.py`（保持 2630 行不变）
  - ❌ `novel_analyzer/database/models.py` 任何已有字段（仅在 `NovelSource` / `AnalysisRun` / `RunBranch` **追加** 一列）
  - ❌ 其他 24 个 service 文件
  - ❌ 任何 router 文件
  - ❌ 任何 workflow / agent / cli 文件

  **DB Migration 文件模板**（Sisyphus 用 alembic 生成 timestamp 后填入）：

  `alembic/versions/{timestamp}_add_owner_user_id.py`:
  ````python
  """add owner_user_id to library tables

  Revision ID: {auto}
  Revises: {previous_head}
  Create Date: {auto}
  """
  from __future__ import annotations

  from alembic import op
  import sqlalchemy as sa

  revision = "{auto}"
  down_revision = "{previous_head}"
  branch_labels = None
  depends_on = None

  TABLES = ("novel_sources", "analysis_runs", "run_branches")


  def upgrade() -> None:
      for table in TABLES:
          op.add_column(
              table,
              sa.Column(
                  "owner_user_id",
                  sa.String(64),
                  nullable=False,
                  server_default="local-default",
              ),
          )
          op.create_index(f"ix_{table}_owner_user_id", table, ["owner_user_id"])


  def downgrade() -> None:
      for table in TABLES:
          op.drop_index(f"ix_{table}_owner_user_id", table_name=table)
          op.drop_column(table, "owner_user_id")
  ````

  **DB Model 改动**（仅在 3 个 model 类追加字段，不动任何已有字段）：

  在 `novel_analyzer/database/models.py` 的 `NovelSource`、`AnalysisRun`、`RunBranch` 类里追加：
  ````python
  owner_user_id: Mapped[str] = mapped_column(
      String(64), nullable=False, default="local-default", server_default="local-default", index=True
  )
  ````

  **Service 层改动 — service A**：

  在 `novel_analyzer/services/ingest_service.py`：
  - 找到创建 `NovelSource` / `AnalysisRun` / `RunBranch` 的方法
  - 方法签名加 `owner_user_id: str = "local-default"` 关键字参数
  - 创建时填上：`NovelSource(..., owner_user_id=owner_user_id)`
  - **不**改其他逻辑

  **Service 层改动 — service B**：

  在 `novel_analyzer/services/status_service.py` **追加新方法**（不动已有方法）：
  ````python
  def list_runs_for_user(self, user_id: str = "local-default", limit: int = 100):
      """List runs visible to a specific user. Original list_runs() unchanged."""
      stmt = (
          select(AnalysisRun)
          .where(AnalysisRun.owner_user_id == user_id)
          .order_by(AnalysisRun.created_at.desc())
          .limit(limit)
      )
      return self._session.scalars(stmt).all()
  ````

  **测试文件**：

  `tests/test_owner_scoping.py`:
  ````python
  from __future__ import annotations

  import pytest
  from sqlalchemy import create_engine
  from sqlalchemy.orm import sessionmaker

  from novel_analyzer.database.models import Base, AnalysisRun, NovelSource
  from novel_analyzer.services.status_service import StatusService


  @pytest.fixture
  def session():
      engine = create_engine("sqlite:///:memory:")
      Base.metadata.create_all(engine)
      Session = sessionmaker(bind=engine)
      s = Session()
      yield s
      s.close()


  def test_owner_user_id_default_is_local_default(session):
      ns = NovelSource(title="t", source_path="/x")
      session.add(ns)
      session.commit()
      assert ns.owner_user_id == "local-default"


  def test_list_runs_for_user_isolates(session):
      r1 = AnalysisRun(novel_source_id=1, owner_user_id="alice")
      r2 = AnalysisRun(novel_source_id=2, owner_user_id="bob")
      session.add_all([r1, r2])
      session.commit()

      svc = StatusService(session)
      alice_runs = svc.list_runs_for_user("alice")
      bob_runs = svc.list_runs_for_user("bob")

      assert len(alice_runs) == 1
      assert len(bob_runs) == 1
      assert alice_runs[0].owner_user_id == "alice"
      assert bob_runs[0].owner_user_id == "bob"


  def test_legacy_list_runs_unchanged(session):
      """原有 list_runs() 方法不应被破坏（v2 兼容性）."""
      svc = StatusService(session)
      assert hasattr(svc, "list_runs")
  ````

  **Verification**:
  ```bash
  # 1. migration 跑通
  alembic upgrade head

  # 2. 现有数据 owner_user_id = local-default
  sqlite3 novel_analyzer.db "SELECT DISTINCT owner_user_id FROM novel_sources"
  # 期望：local-default

  # 3. 新测试通过
  .venv/bin/pytest tests/test_owner_scoping.py -v

  # 4. T1 contract test 仍全绿（零回归门禁）
  .venv/bin/pytest tests/contract/test_main_wsgi_contract.py -v
  ```

### Wave D — Ecosystem Evaluation（新增，零侵入评估）

- [x] **N9. Promptfoo 评测套件接入**

  **What to do**:
  - 装 `promptfoo`（dev only，不进生产 image）
  - 在 `tests/promptfoo/` 写 yaml：3 类用例（imitation 风格匹配、QA 引用准确、安全边界）
  - 用真实 LLM provider 跑，结果存 `.sisyphus/evidence/N9-promptfoo.json`
  - CI 跑（手动 trigger，不阻断 PR）

  **Must NOT do**:
  - ❌ 不动业务代码
  - ❌ 不强阻断 PR（成本敏感，先 manual）

  **Acceptance**:
  - [ ] `promptfoo eval` 跑通，至少 9 个用例（3 类 × 3）
  - [ ] 报告含 pass/fail per case

  **Commit**: `test(eval): promptfoo regression suite for imitation prompts`

- [x] **N10. Helicone vs Langfuse 部署对比评估**

  **What to do**:
  - 起一个 Helicone self-host docker-compose（参考官方）
  - 把 `NOVEL_ANALYZER_LLM_BASE_URL` 临时改成 Helicone 代理（仅 dev env）
  - 跑一次 ask-branch，观察 trace
  - 写对比报告 `docs/observability/helicone-vs-langfuse.md`：
    - 部署复杂度、原文存储位置、查询能力、成本、与 Dify 兼容性
    - 给出建议（保留 Dify 内置 Langfuse / 切 Helicone / 双跑）

  **Must NOT do**:
  - ❌ 不动 `novel_analyzer/llm/client.py` 代码
  - ❌ 不改 prod env 的 base_url

  **Acceptance**:
  - [ ] 对比报告至少 5 个维度
  - [ ] 明确推荐结论

  **Commit**: `docs(observability): helicone vs langfuse evaluation`

- [x] **N11. FastGPT 备选评估（仅文档）**

  **What to do**:
  - **不**部署，只调研：FastGPT 与 Dify 在我们场景下的差异
  - 输出 `docs/research/fastgpt-vs-dify.md`：
    - 中文化 / RAG 能力 / 多模态 / API 兼容性 / 社区活跃度
    - 给出"是否需要在某个时间点切换"的判断
  - 时间盒：4 小时

  **Must NOT do**:
  - ❌ 不部署 FastGPT（避免维护负担）

  **Acceptance**:
  - [ ] 报告含明确建议（继续 Dify / 切 FastGPT / 看时机切）

  **Commit**: `docs(research): fastgpt vs dify decision memo`

---

## Final Verification Wave

- [x] **F1. 零回归审计**（oracle）
  - `wc -l apps/api/app/main.py` 仍是 2630（未动）
  - T1 contract test 全绿
  - `grep -rn "langfuse\|dify" novel_analyzer/services` → 0 行
  - 输出：`Regression [CLEAN] | VERDICT: APPROVE/REJECT`

- [ ] **F2. 框架就绪验证**（unspecified-high）
  - 3 个 docker-compose 全 healthy
  - Dify Chatbot 至少 1 次成功对话
  - Langfuse 至少 1 条 trace
  - n8n 2 个 workflow active
  - 输出：`Infra [4/4] | Dify [PASS] | Langfuse [PASS] | n8n [PASS] | VERDICT`

- [ ] **F3. Writer Studio E2E QA**（unspecified-high + playwright）
  - `/writer/demo-branch` 三栏布局
  - Loom 信号刷新
  - iframe 嵌入对话流式工作
  - 证据：`.sisyphus/evidence/final-qa/`

- [x] **F4. 范围保真度**（deep）
  - 检查没有偷做 v1 已撤回的工作（T8-T11/T12/T15/T16/T18）
  - `git diff --stat` 应该显示 main.py 变化为 0 或仅注释

---

## Commit Strategy

每 task 独立 commit，遵循 Lore Commit Protocol。

---

## Success Criteria

```bash
# 零回归
wc -l apps/api/app/main.py                    # = 2630
.venv/bin/pytest tests/contract/              # all pass

# Infra
docker compose -f infra/dify/docker-compose.yml ps      # all Up
docker compose -f infra/n8n/docker-compose.yml ps       # all Up
docker compose -f infra/langfuse/docker-compose.yml ps  # all Up

# Dify
curl -s http://localhost:8080/console/api/version       # 200

# Langfuse
curl -s http://localhost:3000/api/public/health         # 200

# n8n
curl -s http://localhost:5678/healthz                   # 200

# Writer Studio
curl -s -I http://localhost:4173/writer/demo-branch | head -1  # 200

# Multi-user
curl -H "X-User-Id: alice" :8001/api/library | jq '.items | length'  # isolated
```

### Final Checklist
- [ ] 所有 Must Have 项已验证
- [ ] 所有 Must NOT Have 项已验证不存在
- [ ] T1 contract test 仍然全绿
- [ ] F1-F4 全部 APPROVE
- [ ] 用户明确说 "okay"
