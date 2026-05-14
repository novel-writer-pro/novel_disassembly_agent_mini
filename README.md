# novel-analyzer · AI 小说助手平台

> v0.2.4 — 面向作家与读者的 AI 小说理解、创作辅助与阅读增强系统。

---

## 产品定位

这不是通用 AI 写作器，而是面向长篇小说的**内容理解 + 风险门控 + 受控生成**平台，服务两类用户：

| 用户 | 核心价值 |
|------|---------|
| **作家 / 工作室** | 仿写辅助、Loom 信号实时反馈、风险门控、连续性审查 |
| **读者** | 章节 Q&A、引用跳转、人物事件检索、防剧透摘要 |

---

## 核心能力

### 拆书与检索
- 章节切分 + 规范化
- BM25 / trigram / vector 混合检索（PostgreSQL 原生）
- 推理图谱（人物 / 事件 / 因果 / 伏笔）
- 窗口摘要 / 状态机

### 风险门控
- 语义风险信号（OOC / 规则漂移 / 时间线 / 战力）
- 集群审查工作流（review cluster / batch execute）
- 风险证据包导出

### 受控仿写
- 章节级仿写（chapter imitation）
- 整本仿写编排（whole-book orchestration）
- Loom 信号：节奏 / 张力 / 风格对照 / 读者模拟（4 视角）
- 修复通道 + 长篇连续性诊断

### 读者 Q&A
- 流式问答（RAG + 图谱推理）
- 引用章节可跳转
- 人物 / 事件检索
- 证据摘要 + 推理路径渲染

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11 · FastAPI / WSGI · LangGraph · SQLAlchemy |
| 数据库 | PostgreSQL（pg_trgm / pgvector / pg_jieba） |
| 前端 | Next.js 15 · React 18 · Ant Design 5 |
| AI 编排 | Dify（Chatbot / Workflow / Prompt Studio） |
| 外围自动化 | n8n（通知 / 日报 / 第三方集成） |
| 可观测性 | Langfuse（Dify 内置集成）· Helicone（LLM proxy trace） |
| Embedding | ONNX（本地）/ HTTP（TEI / OpenAI / Jina） |

---

## 用户界面入口

### 作家端 — Writer Studio
```
http://127.0.0.1:4173/writer/<branch_id>
```
- 编辑器画布（autosave）
- Loom 信号侧栏（节奏 / 张力 / 风格 / 伏笔密度）
- AI 副驾（Dify Chatbot iframe，流式 + 引用）
- 版本树（仿写分支管理）

### 读者端 — Reader Studio
```
http://127.0.0.1:4173/reader/<branch_id>
```
- 三栏布局：左侧章节导航 / 中央阅读 / 右侧 Q&A
- 章节导航：摘要预览 + 吸引度评分 + 风险标签 + 搜索过滤
- 防剧透 Q&A：默认只用 ≤ 当前章节的数据回答，可关闭
- 读者体验评分：4视角（普通读者 / 资深读者 / 情感满足 / 编辑视角）
- 读者反馈：1-5 星评分 + 评论，汇总展示

### 旧工作台（Workbench）
```
http://127.0.0.1:4173
```
| 页面 | 功能 |
|------|------|
| `/control` | 导入 + 启动 + 恢复 |
| `/reader` | 章节阅读 + 原文回看 |
| `/qa` | 整本问答 / 人物事件检索（流式 + 引用跳转） |
| `/pipeline` | Pipeline 编排与进度 |
| `/quality` | 质量仪表盘 |
| `/ops` | 导出 + 恢复 |

---

## 文档入口

| 我是… | 入口 |
|-------|------|
| 产品 / 业务 | [`docs/roles/product/`](./docs/roles/product/README.md) |
| 后端 / 架构师 | [`docs/roles/backend/`](./docs/roles/backend/README.md) |
| 接入者（API/前端） | [`docs/roles/integrator/`](./docs/roles/integrator/README.md) |
| 维护者 / 接手人 | [`docs/roles/maintainer/`](./docs/roles/maintainer/README.md) |
| 仿写 / 创作 | [`docs/roles/imitation/`](./docs/roles/imitation/README.md) |
| 直接使用 CLI | [`docs/cli-operations-manual.md`](./docs/cli-operations-manual.md) |
| 商业化路线图 | [`docs/strategy/writer-studio-roadmap.md`](./docs/strategy/writer-studio-roadmap.md) |
| 端到端运维 | [`docs/runbook/business-loop.md`](./docs/runbook/business-loop.md) |
| 全部文档 | [`docs/README.md`](./docs/README.md) |

---

## 快速启动

### 1. 安装依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 初始化数据库
```bash
cp .env.example .env.local   # 填写 DB / LLM 配置
.venv/bin/python -m novel_analyzer.cli.app init-db
alembic upgrade head
```

### 3. 启动后端
```bash
make api-dev
# uvicorn 启动 FastAPI on http://127.0.0.1:8011
# legacy fallback (cutover 完成后移除): make api-wsgi-legacy
```

### 4. 启动前端
```bash
cd apps/web
npm install
npm run dev
# 默认监听 :4173
```

### 5. 导入小说并开始分析
```bash
# CLI 一键导入
.venv/bin/python -m novel_analyzer.cli.app auto-run /path/to/novel.txt --max-chapters 0

# 或通过 Workbench UI
open http://127.0.0.1:4173/control
```

---

## 环境变量

### 数据库
```bash
NOVEL_ANALYZER_DB_DIALECT=postgresql
NOVEL_ANALYZER_DB_HOST=127.0.0.1
NOVEL_ANALYZER_DB_PORT=5432
NOVEL_ANALYZER_DB_USER=d2
NOVEL_ANALYZER_DB_PASSWORD=replace-me
NOVEL_ANALYZER_DB_NAME=novel_analyzer
NOVEL_ANALYZER_DB_ADMIN_NAME=postgres
```

### LLM
```bash
NOVEL_ANALYZER_LLM_PROVIDER_NAME=deepseek
NOVEL_ANALYZER_LLM_BASE_URL=https://api.deepseek.com/v1
NOVEL_ANALYZER_LLM_API_KEY=replace-me
NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_QA_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME=deepseek-v4-flash

# v3: 透明 LLM proxy（Helicone），不设则直连
# NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/openai
```

### Embedding
```bash
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=/absolute/path/to/bge-m3-onnx
NOVEL_ANALYZER_EMBEDDING_CACHE_DIR=.cache/embeddings
```

### 外围集成（v3 新增，可选）
```bash
# n8n pipeline 完成通知（不设则静默）
# N8N_WEBHOOK_PIPELINE_COMPLETE_URL=http://localhost:5678/webhook/pipeline-complete

# Dify Writer Copilot（前端 iframe 嵌入）
# NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
# NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxxxxx
```

---

## 自托管 Infra（可选）

所有 infra 组件均为独立 docker-compose，互不依赖，按需启动：

| 组件 | 端口 | 用途 | 启动 |
|------|------|------|------|
| **Dify** | 8080 | Chatbot / Prompt Studio / Workflow | `infra/dify/README.md` |
| **n8n** | 5678 | 通知 / 日报 / 第三方集成 | `cd infra/n8n && docker compose up -d` |
| **Langfuse** | 3030 | LLM trace（Dify 内置集成） | `infra/langfuse/README.md` |
| **Helicone** | 8585 | LLM proxy trace（imitation 主流量） | `infra/helicone/README.md` |

完整启动流程见 [`docs/runbook/v3-pickup-checklist.md`](./docs/runbook/v3-pickup-checklist.md)。

---

## 架构概览

```mermaid
flowchart TD
    A[Novel TXT] --> B[Ingest & Chapter Splitter]
    B --> C[Manifest / Segments]
    C --> D[Run / Branch / Jobs]

    D --> E[Chapter Analysis Pipeline]
    E --> E1[chapter_intake]
    E --> E2[fact_extractor]
    E --> E3[evidence_binder]
    E --> E4[analysis_generator]
    E --> E5[writer_learning_lens]
    E --> E6[anti_fabrication_guard]

    E6 --> F[Chapter Artifact]
    F --> G[Retrieval / BM25+Vector]
    F --> H[Facts / Graph / Window]

    G --> QA[Branch Q&A / Search]
    H --> QA

    F --> RISK[Risk Audit / Review Workflow]
    F --> LOOM[Loom Signals\nRhythm · Tension · Style · Reader Sim]

    LOOM --> WS[Writer Studio UI\n/writer/*]
    QA --> WS
    QA --> RD[Reader UI\n/qa · /reader]

    WS --> DIFY[Dify Chatbot\nAI 副驾 iframe]
    DIFY --> LANGFUSE[Langfuse Traces]

    E6 --> N8N[n8n\nPipeline Complete Notify]
    E6 --> HELICONE[Helicone Proxy\nImitation Trace]
    HELICONE --> LLM[LLM Provider]
```

---

## 开发命令

```bash
make v2-test        # 后端回归测试（contract + runtime + scoping）
make v3-smoke       # v3 e2e 测试套件（21 tests，无需 docker）
make v2-build       # 前端 Next.js 生产构建
make v2-audit       # 重新扫描 imitation session_* 字段
make v2-lint        # 检查是否有新增 session_* 字段
make v2-status      # 查看 plan 进度
make v2-up-all      # 启动 Dify + n8n + Langfuse（需要 docker）
make v2-pickup-checklist  # 打印 infra 启动步骤
```

---

## 重要语义

- 章节是最小提交单元，当前章成功后才能继续下一章
- 回退采用**逻辑隐藏**，默认只读 active branch
- 手工结果允许保留，但默认 `participates_in_downstream = false`
- 拆书失败自动重试上限 **5 次**，超过后进入人工恢复流程
- 中文检索依赖 PostgreSQL 原生扩展（pg_trgm / pgvector / pg_jieba）

---

## 更多文档

- 变更记录：[`CHANGELOG.md`](./CHANGELOG.md)
- 完整文档中心：[`docs/README.md`](./docs/README.md)
- 当前 API surface：[`docs/api-current-surface.md`](./docs/api-current-surface.md)
- 商业化路线图：[`docs/strategy/writer-studio-roadmap.md`](./docs/strategy/writer-studio-roadmap.md)
