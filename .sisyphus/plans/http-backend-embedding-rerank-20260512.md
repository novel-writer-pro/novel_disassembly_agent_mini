# Pluggable HTTP Embedding & Rerank Backend(OpenAI / TEI 协议)— 2026-05-12

## TL;DR

> **Quick Summary**:给 `embedding/` 和 `rerank/` 加一套 HTTP backend,复用现有 Protocol,支持 OpenAI `/v1/embeddings` 和 TEI native 两种协议;配置层一个开关从 `onnx` 切到 `http`,下游无感知。用本机 docker 启动两个 TEI 容器做真实验证。
>
> **Deliverables**:
> - `novel_analyzer/embedding/service.py` 新增 `HttpEmbeddingProvider` + 工厂分支
> - `novel_analyzer/rerank/service.py` 新增 `HttpRerankProvider` + 工厂分支
> - `novel_analyzer/config/settings.py` 新增 HTTP backend 相关字段(base url / api key / format / timeout / retries)
> - `tests/test_embedding_service.py` + `tests/test_rerank_service.py` 新增 HTTP 路径单元测试(mocked httpx)
> - 新建 `scripts/dev/tei-embedding-server.sh` + `scripts/dev/tei-rerank-server.sh` 启动本机 TEI docker
> - 新建 `tests/integration/test_tei_integration.py` 集成测试(标记 `@pytest.mark.integration`,CI 可选跳过)
> - `.env.example` 追加 HTTP backend 变量示例
> - `docs/foundation-optimization/http-backend-guide.md` 使用指南
>
> **Estimated Effort**: 小项目(1-2 人天工程 + 0.5 天 docker 集成验证)
> **Parallel Execution**: NO — embedding 和 rerank 结构高度镜像,同一 agent 一次写完两端更省回归成本
> **Critical Path**:
> 1. 先落 Settings + Protocol 的 HTTP provider 骨架(纯逻辑)
> 2. 补单元测试(httpx mock),跑过
> 3. 跑 docker TEI,做集成测试
> 4. 文档 + example env

## Context

### Original Request
用户原话:
> 关于 embedding 和 rerank 我们当前是采用的 onnx 的形式,但是我准备也暴露 openai 的接口功能,你可以先帮我把这个功能实现吗,就是挂在 rerank/embedding 可以从 onnx 加载,也可以从远程的 text embedding interface 的接口进行加载。当然你可以使用 docker 在我本地启动两个 TEI 的 docker 镜像测试这个功能。

澄清点:用户把"OpenAI 接口"和"TEI"并列说。实际上 TEI 自己同时支持两种格式:
- OpenAI-compatible:`POST /v1/embeddings`
- TEI native:`POST /embed` / `POST /rerank`

OpenAI 官方没有 rerank API,rerank 的事实标准由 Cohere(`/v2/rerank`)和 TEI(`/rerank`)定义。因此本计划:
- Embedding:默认支持 OpenAI 与 TEI native 两种格式,配置切换
- Rerank:默认支持 TEI `/rerank`,为 Cohere 格式预留扩展点

### 本地事实核对

**Embedding 侧(`novel_analyzer/embedding/service.py`)**
- Protocol:`EmbeddingProvider.embed_texts(texts: list[str]) -> list[list[float]]`
- 已有实现:
  - `DeterministicStubEmbeddingProvider`(stub,dim 可配)
  - `OnnxBgeEmbeddingProvider`(ONNX + AutoTokenizer + CLS/Mean pooling + CPU)
- 工厂:`_cached_embedding_provider(backend, model_name, model_path, cache_dir, max_length, dim)` 走 `@lru_cache(maxsize=8)`
- 入口:`get_embedding_provider(settings)` 读 `settings.embedding_*` 字段

**Rerank 侧(`novel_analyzer/rerank/service.py`)**
- Protocol:`RerankProvider.rerank(query: str, documents: list[str]) -> list[float]`
- 已有实现:
  - `DisabledRerankProvider`(返回全 0,保持原顺序)
  - `OnnxCrossEncoderRerankProvider`(ONNX 交叉编码器,CPU)
- 工厂:`_cached_rerank_provider(...)` 同样 `@lru_cache(maxsize=8)`

**Settings 相关字段(`novel_analyzer/config/settings.py:51-62`)**
```
embedding_model_name  默认 "BAAI/bge-m3"
embedding_backend     默认 "onnx"       <-- 新增 "http" / "openai"
embedding_model_path  默认 ""
embedding_cache_dir   默认 ".cache/embeddings"
embedding_max_length  默认 2048
embedding_stub_dim    默认 16
rerank_backend        默认 "onnx"       <-- 新增 "http" / "tei"
rerank_model_name     默认 "onnx-community/bge-reranker-v2-m3-ONNX"
rerank_model_path     默认 ""
rerank_cache_dir      默认 ".cache/rerank-models"
rerank_max_length     默认 512
```

**.env.example 相关行**:`.env.example:18-21` 已定义 ONNX 相关变量

**既有测试位置**
- `tests/test_embedding_service.py`
- `tests/test_retrieval_service.py`(间接用到)
- 没有单独的 `tests/test_rerank_service.py` — 新建

### 协议细节

**OpenAI 格式 embeddings**
```
POST {base}/v1/embeddings
Authorization: Bearer {api_key}   (可选,本地 TEI 无需)
Content-Type: application/json

{"input": ["text1", "text2"], "model": "bge-m3", "encoding_format": "float"}

→ 200 OK
{"object": "list",
 "data": [{"object": "embedding", "embedding": [...], "index": 0},
          {"object": "embedding", "embedding": [...], "index": 1}],
 "model": "bge-m3",
 "usage": {...}}
```

**TEI native embeddings**
```
POST {base}/embed
Content-Type: application/json

{"inputs": ["text1", "text2"], "truncate": true}

→ 200 OK
[[...], [...]]    # 直接的 2D 数组
```

**TEI rerank**
```
POST {base}/rerank
Content-Type: application/json

{"query": "q", "texts": ["d1", "d2"], "raw_scores": false, "return_text": false, "truncate": true}

→ 200 OK
[{"index": 0, "score": 0.93},
 {"index": 1, "score": 0.12}]   # 按分数降序;需要按原 index 回填
```

**Cohere rerank(备选,后续再加)**
```
POST https://api.cohere.com/v2/rerank
{"model": "rerank-v3.5", "query": "q", "documents": ["d1","d2"], "top_n": 2}
→ {"results": [{"index": 0, "relevance_score": 0.93}, ...]}
```

### 两个 TEI docker 镜像(用于本地验证)

**Embedding server**(`BAAI/bge-m3`,dim=1024,和当前 pgvector 列兼容)
```
docker run -d --name tei-embed \
  -p 8080:80 \
  -v $PWD/.cache/tei:/data \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.6 \
  --model-id BAAI/bge-m3 --max-client-batch-size 32
```

**Rerank server**(`BAAI/bge-reranker-v2-m3`)
```
docker run -d --name tei-rerank \
  -p 8081:80 \
  -v $PWD/.cache/tei:/data \
  ghcr.io/huggingface/text-embeddings-inference:cpu-1.6 \
  --model-id BAAI/bge-reranker-v2-m3 --max-client-batch-size 32
```

备注:如果本机有 NVIDIA GPU,可以换成 `text-embeddings-inference:89-1.6` 等 GPU 镜像,但本计划以 CPU 镜像为准(最通用)。

---

## Work Objectives

### Must Have

- **向后兼容**:`embedding_backend=onnx`(默认值)路径的行为完全不变,现有测试继续通过
- **一个开关切换**:`embedding_backend=http` 或 `embedding_backend=openai` 即可走远程接口,无需改下游代码
- **格式可配**:`embedding_api_format=openai|tei` 控制请求/响应格式;`rerank_api_format=tei|cohere` 预留
- **错误可诊断**:HTTP 失败(4xx / 5xx / 超时 / 连接拒绝)都要有清晰的 `RuntimeError` 消息,明确告知如何复现
- **超时/重试**:HTTP 调用必须有超时(默认 30s)+ 有限重试(默认 2 次,指数退避)
- **批量支持**:embedding 支持一次发多个 text,rerank 支持一次发多文档(TEI/OpenAI 都天然支持)
- **真实验证**:本机跑通 2 个 TEI docker,集成测试至少覆盖 embedding + rerank 各一条调用链

### Must NOT Have (Guardrails)

- **不动 Protocol 签名** — `embed_texts` / `rerank` 的输入输出类型维持不变,否则下游服务需要跟着改
- **不改 pgvector 列** — bge-m3 dim=1024 保持不变
- **不引入新的重型依赖** — 用标准库 `urllib` 或已有的 `httpx`(如果项目已用过),不引入 `aiohttp` / `httpcore` 裸依赖
- **不在生产代码里硬编码 api_key** — 所有 secret 走 Settings → `.env.local`
- **不让 docker 启动逻辑影响单元测试** — 单元测试必须用 mock,不能依赖 docker 运行中
- **不替换 onnx 路径为默认** — ONNX 仍是本地生产默认,HTTP 是可选
- **不把 docker scripts 写到 production docker-compose** — 放在 `scripts/dev/`,只用于开发验证
- **不把 lru_cache key 里塞 dict/list** — 保持字符串 / 数值,这是目前设计;对 HTTP provider 来说 lru 要拿 base_url + api_format + model_name 做 key
- **不跳过 SSL 验证** — 除非配置明确写 `verify=false`;默认开启

### Verification Strategy

- **Infrastructure**:pytest / docker 已在项目中使用
- **单元测试**:
  - 用 `unittest.mock` patch HTTP 客户端,验证请求体格式、URL、header、超时行为、重试行为、响应解析
  - 每种格式(OpenAI / TEI)至少一个成功路径 + 一个失败路径(4xx / 5xx / 超时)
  - `embed_texts([])` 和 `rerank(q, [])` 的空输入短路行为不变
- **集成测试**(`@pytest.mark.integration`):
  - 启动本机 TEI docker 前置条件检查(探针 `curl -sf http://localhost:8080/health`)
  - 对 embedding server 发一批小说片段,断言:
    - 返回 dim == 1024
    - 对同一段文本发两次,向量相同(确定性)
    - 批量 N 条文本 → 返回 N 个向量
  - 对 rerank server 发 query + 5 个文档,断言:
    - 返回 5 个分数
    - 相关文档分数 > 不相关文档分数
  - **CI 默认跳过**(通过 marker);开发者本机跑过即可
- **回归**:
  - 运行现有 `tests/test_embedding_service.py` — 必须全绿
  - 全项目 `.venv/bin/python -m pytest -x` — 必须全绿
- **QA Policy**:
  - lsp_diagnostics 在所有修改文件上 clean
  - 单元测试必须 in-repo 可跑无需网络
  - 集成测试必须在本机 docker 可跑,报告中附延迟 + 成功率

---

## TODOs

### Phase 1 — Settings 扩展

- [ ] 1. **扩展 `novel_analyzer/config/settings.py` 的 embedding/rerank HTTP 字段**

  **What to do**:
  在现有 embedding/rerank 字段组后追加:
  ```
  # HTTP backend (OpenAI / TEI compatible)
  embedding_api_base: str = Field(default="")           # e.g. http://localhost:8080
  embedding_api_key: str = Field(default="")            # optional (TEI local: empty)
  embedding_api_format: str = Field(default="openai")   # openai | tei
  embedding_http_timeout: float = Field(default=30.0)
  embedding_http_max_retries: int = Field(default=2)
  embedding_http_verify_ssl: bool = Field(default=True)

  rerank_api_base: str = Field(default="")
  rerank_api_key: str = Field(default="")
  rerank_api_format: str = Field(default="tei")          # tei | cohere
  rerank_http_timeout: float = Field(default=30.0)
  rerank_http_max_retries: int = Field(default=2)
  rerank_http_verify_ssl: bool = Field(default=True)
  ```
  保留 pydantic `env_prefix="NOVEL_ANALYZER_"` 约定

  **Must NOT do**:
  - 不改已有字段的默认值
  - 不把新字段设为必填

  **Acceptance Criteria**:
  - [ ] `get_settings()` 以空默认值加载不报错
  - [ ] 设置 env `NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8080` 能被读到
  - [ ] 现有 `tests/test_embedding_service.py` 全绿

  **Commit**: YES
  - Message: `feat(settings): add HTTP backend fields for embedding/rerank`

### Phase 2 — Embedding HTTP Provider

- [ ] 2. **在 `novel_analyzer/embedding/service.py` 新增 `HttpEmbeddingProvider`**

  **What to do**:
  - 新 `@dataclass(slots=True)` 类 `HttpEmbeddingProvider`,字段:
    - `model_name: str`
    - `api_base: str`(形如 `http://localhost:8080`,trailing slash 需规整)
    - `api_key: str = ""`
    - `api_format: str = "openai"`  # or "tei"
    - `timeout: float = 30.0`
    - `max_retries: int = 2`
    - `verify_ssl: bool = True`
  - 实现 `embed_texts`:
    - 空输入短路:`return []`
    - 根据 `api_format` 构造请求:
      - `openai`:`POST {api_base}/v1/embeddings`, body=`{"input": texts, "model": model_name, "encoding_format": "float"}`,header 带 Authorization(若 api_key 非空)
      - `tei`:`POST {api_base}/embed`, body=`{"inputs": texts, "truncate": True}`
    - HTTP 调用用标准库 `urllib.request` + `json`,避免引入新依赖(若项目已有 `httpx`,优先用 `httpx`,先 `grep` 确认)
    - 指数退避重试 `max_retries` 次(初始 0.5s),仅对超时 + 5xx 重试,4xx 直接抛
    - 响应解析:
      - `openai`:读 `response["data"]` 按 `index` 排序,取 `embedding`
      - `tei`:直接 `list[list[float]]`
    - 异常封装为 `RuntimeError`,消息包含 URL + 状态码 + 截断后的响应片段
  - 添加对应的 `lru_cache` 工厂分支:`backend in ("http", "openai")` → 返回 HTTP provider
  - 注意:`_cached_embedding_provider` 的 key 要包含 `api_base / api_key / api_format / timeout / max_retries / verify_ssl`(lru 可哈希)

  **Must NOT do**:
  - 不破坏 `OnnxBgeEmbeddingProvider`
  - 不默认跳过 SSL
  - 不用 `requests` 裸依赖(先 grep 项目是否已有)
  - 不在 HTTP path 里依赖 AutoTokenizer / ONNX 资源

  **Acceptance Criteria**:
  - [ ] `lsp_diagnostics` 在 service.py 上 clean
  - [ ] Mock 测试:`openai` 格式成功路径、`tei` 格式成功路径、超时重试、4xx 不重试
  - [ ] 工厂缓存命中:同参数二次调用返回同一实例

  **Commit**: YES
  - Message: `feat(embedding): add HTTP backend with OpenAI/TEI format support`

### Phase 3 — Rerank HTTP Provider

- [ ] 3. **在 `novel_analyzer/rerank/service.py` 新增 `HttpRerankProvider`**

  **What to do**:
  - 新 `@dataclass(slots=True)` 类 `HttpRerankProvider`,字段同 embedding 侧但 `api_format` 默认 `tei`
  - 实现 `rerank(query, documents)`:
    - 空输入短路:`return []`
    - `tei` 格式:`POST {api_base}/rerank`, body=`{"query": query, "texts": documents, "raw_scores": False, "return_text": False, "truncate": True}`
    - 响应:`list[{"index": int, "score": float}]`,按 `index` 升序回填到原 documents 顺序,得到 `list[float]`
    - `cohere` 预留(本 TODO 不实装):`POST {api_base}/v2/rerank`, body 含 `documents` 字段,响应 `results[{index, relevance_score}]`;本次只声明 TODO 注释
  - 工厂分支:`backend in ("http", "tei")` → 返回 HTTP provider

  **Must NOT do**:
  - 不在本 TODO 实装 Cohere 格式 — 先注释标记 `# TODO: cohere format`
  - 不直接原样返回响应 — 必须按 index 回填顺序

  **Acceptance Criteria**:
  - [ ] Mock 测试:tei 成功路径、回填顺序正确、空文档短路、超时重试
  - [ ] `lsp_diagnostics` clean

  **Commit**: YES
  - Message: `feat(rerank): add HTTP backend with TEI format support`

### Phase 4 — 单元测试

- [ ] 4. **扩展 `tests/test_embedding_service.py` + 新建 `tests/test_rerank_service.py`**

  **What to do**:
  - 先读已有 `test_embedding_service.py` 理解风格
  - 新增测试类 `TestHttpEmbeddingProvider`:
    - `test_openai_format_success`:mock HTTP 200 响应 OpenAI 格式,断言请求 URL / body / header / 解析
    - `test_tei_format_success`:同上走 TEI 格式
    - `test_empty_input_short_circuit`:空输入不发请求
    - `test_5xx_retry_then_fail`:前 2 次 503,第 3 次 503,最终抛 RuntimeError
    - `test_5xx_retry_then_recover`:前 2 次 503,第 3 次 200,成功
    - `test_4xx_no_retry`:400 立即抛,不重试
    - `test_timeout_retried`:模拟 timeout 异常
  - 新建 `tests/test_rerank_service.py`:
    - `test_disabled_provider_returns_zeros`
    - `test_http_tei_success`
    - `test_http_tei_index_reorder`:服务端返回 `[{index:2,...},{index:0,...},{index:1,...}]`,断言回填后顺序正确
    - `test_http_empty_documents_short_circuit`
  - Mock 方式:取决于实装用的客户端
    - 如用 `urllib.request`,patch `urllib.request.urlopen`
    - 如用 `httpx`,用 `respx` 或 `httpx.MockTransport`
  - 不依赖 docker / 外网

  **Must NOT do**:
  - 不在测试里调用真实网络
  - 不把测试时间拉到 >5 秒(timeout 测试用 0.01s timeout + 实时 mock)
  - 不跳过清理(每个测试用 fixture 清 lru_cache)

  **Acceptance Criteria**:
  - [ ] `.venv/bin/python -m pytest tests/test_embedding_service.py tests/test_rerank_service.py -v` 全绿
  - [ ] 覆盖率覆盖新增 HTTP provider 类的主要分支

  **Commit**: YES
  - Message: `test(embedding,rerank): cover HTTP backend provider paths`

### Phase 5 — Docker TEI 开发脚本

- [ ] 5. **新建 `scripts/dev/tei-up.sh` 和 `scripts/dev/tei-down.sh`**

  **What to do**:
  - `scripts/dev/tei-up.sh`:
    ```bash
    #!/usr/bin/env bash
    set -euo pipefail

    CACHE_DIR="${TEI_CACHE_DIR:-$PWD/.cache/tei}"
    mkdir -p "$CACHE_DIR"

    EMBED_IMAGE="ghcr.io/huggingface/text-embeddings-inference:cpu-1.6"
    EMBED_MODEL="${TEI_EMBED_MODEL:-BAAI/bge-m3}"
    EMBED_PORT="${TEI_EMBED_PORT:-8080}"

    RERANK_IMAGE="ghcr.io/huggingface/text-embeddings-inference:cpu-1.6"
    RERANK_MODEL="${TEI_RERANK_MODEL:-BAAI/bge-reranker-v2-m3}"
    RERANK_PORT="${TEI_RERANK_PORT:-8081}"

    docker rm -f tei-embed tei-rerank 2>/dev/null || true

    docker run -d --name tei-embed \
      -p "${EMBED_PORT}:80" \
      -v "${CACHE_DIR}:/data" \
      "${EMBED_IMAGE}" \
      --model-id "${EMBED_MODEL}" \
      --max-client-batch-size 32

    docker run -d --name tei-rerank \
      -p "${RERANK_PORT}:80" \
      -v "${CACHE_DIR}:/data" \
      "${RERANK_IMAGE}" \
      --model-id "${RERANK_MODEL}" \
      --max-client-batch-size 32

    echo "Waiting for servers (up to 180s)..."
    for _ in $(seq 1 60); do
      if curl -sf "http://localhost:${EMBED_PORT}/health" >/dev/null && \
         curl -sf "http://localhost:${RERANK_PORT}/health" >/dev/null; then
        echo "TEI up: embed=${EMBED_PORT}, rerank=${RERANK_PORT}"
        exit 0
      fi
      sleep 3
    done
    echo "Timed out waiting for TEI servers"
    exit 1
    ```
  - `scripts/dev/tei-down.sh`:
    ```bash
    #!/usr/bin/env bash
    docker rm -f tei-embed tei-rerank 2>/dev/null || true
    ```
  - `chmod +x` 两个文件

  **Must NOT do**:
  - 不用 GPU 镜像(确保能在大多数开发机跑)
  - 不覆盖用户已有的 `.cache/tei`(-v mount 即可复用)
  - 不把这俩脚本纳入生产 docker-compose

  **Acceptance Criteria**:
  - [ ] 本机执行 `bash scripts/dev/tei-up.sh` 后两个容器都 `healthy`
  - [ ] `curl -sf http://localhost:8080/health` 返回 200
  - [ ] `curl -sf http://localhost:8081/health` 返回 200
  - [ ] `bash scripts/dev/tei-down.sh` 能干净清理

  **Commit**: YES
  - Message: `chore(dev): add TEI docker up/down scripts for HTTP backend testing`

### Phase 6 — 集成测试

- [ ] 6. **新建 `tests/integration/test_tei_integration.py`**

  **What to do**:
  - 标记 `@pytest.mark.integration`,用 autouse fixture 检测 `curl -sf http://localhost:{port}/health`,失败则 `pytest.skip("TEI not up. Run scripts/dev/tei-up.sh")`
  - 测试矩阵:
    - embedding OpenAI 格式(`POST /v1/embeddings`,base=`http://localhost:8080`)
    - embedding TEI 格式(`POST /embed`)
    - rerank TEI 格式(`POST /rerank`,base=`http://localhost:8081`)
  - 断言:
    - embedding:返回 dim == 1024,N 入 N 出,确定性(同输入两次向量近似相等,cosine > 0.999)
    - rerank:5 个文档返回 5 个分数,query 相关文档分数高于无关文档
  - 在 `pyproject.toml` / `pytest.ini` 注册 `integration` marker(如尚未注册)
  - 提供一个命令行示例:
    ```
    bash scripts/dev/tei-up.sh
    .venv/bin/python -m pytest tests/integration/test_tei_integration.py -m integration -v
    bash scripts/dev/tei-down.sh
    ```

  **Must NOT do**:
  - 不让这个测试在 CI 默认跑
  - 不把 docker 启动逻辑塞进测试内(测试只检测健康,不拉起容器)

  **Acceptance Criteria**:
  - [ ] 本机 TEI 起来后 `pytest -m integration` 全绿
  - [ ] 未启动 TEI 时 `pytest -m integration` 显示 skip 而非 fail
  - [ ] `pytest` 默认不跑 integration(走 marker 过滤)

  **Commit**: YES
  - Message: `test(integration): add TEI-backed HTTP backend integration tests`

### Phase 7 — 文档与 .env.example

- [ ] 7. **追加 `.env.example` 并新建 `docs/foundation-optimization/http-backend-guide.md`**

  **What to do**:
  - `.env.example` 追加一段:
    ```
    # ---- HTTP backend for embedding/rerank (optional) ----
    # Set backend to "http" or "openai" to route through a remote HTTP service
    # (e.g. local TEI docker, OpenAI, Jina, Voyage, Alibaba DashScope)
    #
    # NOVEL_ANALYZER_EMBEDDING_BACKEND=http
    # NOVEL_ANALYZER_EMBEDDING_API_BASE=http://localhost:8080
    # NOVEL_ANALYZER_EMBEDDING_API_KEY=
    # NOVEL_ANALYZER_EMBEDDING_API_FORMAT=openai        # openai | tei
    #
    # NOVEL_ANALYZER_RERANK_BACKEND=http
    # NOVEL_ANALYZER_RERANK_API_BASE=http://localhost:8081
    # NOVEL_ANALYZER_RERANK_API_KEY=
    # NOVEL_ANALYZER_RERANK_API_FORMAT=tei              # tei | cohere (future)
    ```
  - 新建 `docs/foundation-optimization/http-backend-guide.md`:
    - 架构图(一句话):配置切换 → 同一 Protocol → HTTP / ONNX
    - 使用场景(何时选 HTTP、何时选 ONNX)
    - 配置示例(本地 TEI / OpenAI / Jina)
    - `scripts/dev/tei-up.sh` 用法
    - 集成测试跑法
    - 已知限制 / 回滚办法
  - 在 `docs/foundation-optimization/README.md` 的"详细建设指南"表追加一行链接该文档

  **Must NOT do**:
  - 不把 api_key 写进任何跟 git 相关的文件
  - 不在文档中承诺 Cohere / Jina 格式已实装(仅开放式 roadmap)

  **Acceptance Criteria**:
  - [ ] `.env.example` 包含新段
  - [ ] 新 guide 存在且在 README 索引中

  **Commit**: YES
  - Message: `docs(foundation-optimization): add HTTP backend guide + .env example`

---

## Commit Strategy

七次 atomic commit,顺序对应 Phase 1-7。每个 commit 必须:
- 跑过 `lsp_diagnostics` 对改动文件
- Phase 1-4 的 commit 必须跑过 `.venv/bin/python -m pytest tests/test_embedding_service.py tests/test_rerank_service.py -v`(相关项)
- Phase 5-6 单独提交;Phase 6 commit 前本机跑过一次 `pytest -m integration` 通过

**每个 commit 都走 Lore 格式**:
- 第一行 intent line
- 必要 trailers:`Tested:` / `Not-tested:` / 可能的 `Directive:`
- 示例(Phase 2):
  ```
  Enable remote embedding providers via OpenAI/TEI-compatible HTTP

  Add HttpEmbeddingProvider that preserves embed_texts protocol while
  routing through a remote service. Supports both OpenAI /v1/embeddings
  and TEI native /embed formats via api_format switch.

  Constraint: must not break existing ONNX path or change pgvector dim
  Rejected: async httpx as hard dependency | sync path keeps parity with ONNX provider
  Confidence: medium
  Scope-risk: narrow
  Directive: HTTP path must keep returning list[list[float]] shape
  Tested: unit (mocked http success / 5xx retry / 4xx no-retry / empty input)
  Not-tested: real upstream latency (covered in Phase 6 integration test)
  ```

---

## Success Criteria

- [ ] `embedding_backend=http` + `embedding_api_format=openai` 对接本机 TEI → 通过集成测试
- [ ] `embedding_backend=http` + `embedding_api_format=tei` → 通过集成测试
- [ ] `rerank_backend=http` + `rerank_api_format=tei` → 通过集成测试
- [ ] 默认 `embedding_backend=onnx` / `rerank_backend=onnx` 行为完全不变
- [ ] 全项目 `.venv/bin/python -m pytest -x` 全绿(marker 默认过滤 integration)
- [ ] `docs/foundation-optimization/http-backend-guide.md` 可供未来切换到 OpenAI / Jina / Voyage / DashScope 的参考
- [ ] 所有 7 个 commit 都遵循 Lore 格式

---

## Open Questions (defer if non-blocking)

- **是否用 `httpx` 替代 `urllib`**:如项目已依赖 `httpx`,直接用;若没有,本计划用 `urllib.request` + `json` 实现,不引入新依赖。执行阶段先 grep 确认。
- **Cohere 格式 rerank**:本计划标注 TODO,不在 Phase 3 实装。后续如果真要接 Cohere,再开独立 plan。
- **批大小限制**:OpenAI 单次请求限制 2048 inputs,TEI 默认 32。本计划暂不在 HTTP provider 内做分片,由调用方控制;若未来遇到溢出,再加 chunked 逻辑。
- **连接池**:单个 provider 实例复用同一 HTTP client(尤其在 `httpx` 路径下)。`urllib` 没有这个问题,每次新建连接。延迟可接受再说。
- **观测**:是否加 prometheus 指标 / OpenTelemetry?本计划不加,避免 scope creep。

---

## Rollback Plan

任何阶段失败 / 回归出现,回滚到前一 commit 即可:
- Phase 1-3 失败:`git revert` 对应 commit,ONNX 路径无影响
- Phase 4 失败:只是测试红,不影响生产代码,修测试
- Phase 5-6 失败:纯开发工具 + 标记跳过,不阻塞主链
- 生产切换失败(用户把 env 切到 http 后出问题):把 env 切回 `onnx` 即可,HTTP 代码即使保留也不会被触发
