# TEI 一等集成:从 "跑通" 到 "生产就绪" — 2026-05-12

## TL;DR

> **Quick Summary**:当前 HTTP backend 代码已落地且真 TEI 集成测试跑过,但要让 TEI 成为项目里**和 ONNX 平起平坐的一等后端**,还缺 9 个子系统:模型预热 / 国内网络兜底 / docker-compose 化 / doctor 诊断 / 批大小分片 / 连接复用 / 降级兜底 / 运营 runbook / CI 集成。本计划把这些都补齐,让任何新同事 `make tei-up && pytest -m integration` 就能跑起来。
>
> **Deliverables**:
> - `scripts/dev/tei-prefetch.py`(主机侧模型预下载,hf-mirror 兜底)
> - `scripts/dev/tei-up.sh` 重写(HF_ENDPOINT 兜底 + 等待完整就绪)
> - `scripts/dev/tei-doctor.py`(端到端诊断:镜像/cache/容器/health/provider/latency)
> - `scripts/dev/docker-compose.tei.yml`(声明式启动,取代 bash run)
> - `novel_analyzer/embedding/service.py` + `rerank/service.py`:**批大小分片** + **连接复用**(urllib opener)+ **fallback cascade**(可选 ONNX 回落)
> - `novel_analyzer/config/settings.py`:HTTP 字段验证(backend=http 时 base 必填)
> - `tests/integration/`:覆盖所有新路径 + 集合一个 `tei_live` 夹具
> - `docs/foundation-optimization/http-backend-guide.md` 大幅重写(含国内网络坑、诊断流程、迁移 runbook、观测、降级)
> - `Makefile` 新增 `tei-up` / `tei-down` / `tei-doctor` / `tei-prefetch` 目标
>
> **Estimated Effort**: 中等(2-3 人天,分 9 个 atomic commit)
> **Parallel Execution**: NO — 子系统彼此有依赖(预热 → up → doctor → 分片 → fallback → 文档),一次性串行委派给一个 executor 更安全
> **Critical Path**:Phase 1 (Settings validation) → Phase 2-3 (预热 + up 重写) → Phase 4 (doctor) → Phase 5-7 (provider 增强) → Phase 8 (测试) → Phase 9 (docs + Makefile)

---

## Context

### Original Request

用户原话:
> "关于 embedding 和 rerank 我们当前是采用的 onnx 的形式,但是我准备也暴露 openai 的接口功能"
>
> "请根据你的思路进行持续完善,我的要求是可以集成 tei 到项目里,而不是单纯的 onnx"

两条组合起来的真正意图:
- 不只是"加个 HTTP backend 能调用"(✓ 已做)
- 而是让 TEI 成为**项目运维 / CI / 文档 / 诊断 / 降级**的**一等公民**
- 任何新同事接手,能在合理时间内**独立**把 TEI 跑起来并理解整条链路

### 已完成的前序工作(commits `a7a3578..db61a93`)

- Settings 新增 `embedding_backend / embedding_api_base / embedding_api_format` 等字段
- `HttpEmbeddingProvider` 支持 OpenAI / TEI 两种 wire
- `HttpRerankProvider` 支持 TEI `/rerank`,正确处理乱序回填
- 14 个 unit test 全绿
- `scripts/dev/tei-up.sh` / `tei-down.sh` 已在
- `tests/integration/test_tei_integration.py`(5 个测试)
- 真实 TEI 集成测试通过(5/5 passed, 35s),通过主机预下载模型到 `.cache/tei` + 容器侧 `HF_ENDPOINT=https://hf-mirror.com`

### 手工调通时踩过的真实坑(这些必须沉淀到项目)

| # | 坑 | 原因 | 当前是否文档化 |
|---|-----|------|----------------|
| 1 | `docker pull ghcr.io/...:cpu-1.6` 在国内卡死 | 需要 daemon 级代理 `HTTP_PROXY=127.0.0.1:54321` | ❌ |
| 2 | 容器起来后 TEI 下载模型失败 | 容器内网络 ≠ daemon,daemon 代理不影响容器 | ❌ |
| 3 | `HF_HUB_OFFLINE=1` 不能让 TEI 真离线 | TEI 的 ONNX 加载阶段仍尝试 HF,超时 2 分钟 | ❌ |
| 4 | `hf-mirror.com` 直接给容器用,config 能下但 `content-range` 头缺失报错 | hf-mirror 代理不完整,主机侧 `huggingface_hub` 能容忍,TEI 的 rust downloader 不行 | ❌ |
| 5 | `snapshot_download(allow_patterns=...)` 漏 `*.bin` → bge-m3 只有 38M 启动失败 | bge-m3 用 `pytorch_model.bin` 不是 safetensors | ❌ |
| 6 | `snapshot_download` 漏 `model.onnx_data` → TEI 加载 ONNX 时还是要远程下 | bge-m3 的 ONNX 是外部数据文件形式 | ❌ |
| 7 | bge-reranker-v2-m3 没有 ONNX 分片 → TEI 自动 fallback 到 Candle+safetensors,加载慢 40s | TEI 行为正确,文档要说明 | ❌ |
| 8 | `sudo docker` 需要密码 — 新同事不知道 daemon 是否要 sudo | 用户环境差异 | ❌ |

**9 个坑,一个都没有进文档**。这正是"集成到项目"和"跑通一次"的差距。

### 事实核对(本地)

- `scripts/dev/` 只有 2 个脚本,都是 bash
- `scripts/` 下已有 `check_postgres.py` / `check_runtime_storage.py` 等 doctor-like 脚本 — 约定:Python 写 doctor
- 项目**无 `.github/workflows/`** — 没有 CI 集成需求(不做 CI 适配)
- 项目**无 Makefile** — 需要新建(且要评估是否符合仓库约定)
- `pyproject.toml` 已有 `integration` pytest marker
- `docs/foundation-optimization/http-backend-guide.md` 写得过于乐观,没反映国内网络现实

---

## Work Objectives

### 核心目标

**"让接手的同事 10 分钟内把 TEI 跑起来,且知道失败时怎么排查。"**

具体 4 条:

1. **零手动踩坑**:网络、路径、环境变量、权限 — 所有已知坑自动规避或明确报错
2. **诊断可观测**:一个 `tei-doctor` 命令告诉你每一步状态,失败时指向文档的对应章节
3. **生产就绪边界**:HTTP provider 能处理批大小溢出、连接复用、超时失败的降级
4. **运营闭环**:启停 / 升级模型 / 切换服务 / 回滚到 ONNX 都有 runbook

### Must Have

- [x] 背景兼容:`embedding_backend=onnx`(默认)路径完全不变
- [ ] 国内网络兜底:`TEI_HF_ENDPOINT` 默认 `https://hf-mirror.com`,主机侧和容器侧一致
- [ ] 模型预热:一个命令把两个模型完整下到 `.cache/tei/`,不依赖容器
- [ ] 启动可验证:`tei-up.sh` 退出时服务真的 ready(不是 health 一响应就算)
- [ ] 诊断清晰:`tei-doctor.py` 输出 10+ 项检查,失败指向具体文档章节
- [ ] 批大小安全:HTTP provider 自动分片,不会因为 32/2048 上限而 500
- [ ] 连接复用:HTTP provider 保持连接池(减少 TCP 握手开销)
- [ ] 降级兜底:可选配置 `embedding_fallback_backend=onnx`,HTTP 连续失败 N 次自动切 ONNX
- [ ] 文档真实:guide 包含 9 个已踩过的坑 + 明确的"如果你遇到 X,做 Y"
- [ ] Settings 验证:`backend=http` 时 `api_base` 必填,启动就报错,不是运行时才崩

### Must NOT Have (Guardrails)

- **不改 embed_texts / rerank Protocol 签名**
- **不改 pgvector 列维度**(bge-m3 维持 dim=1024)
- **不引入新的生产依赖**(`httpx` 等)— 保持 stdlib `urllib`
- **不把 docker-compose 设成生产默认**(dev 工具而已)
- **不在生产 CI 跑 TEI 集成测试**(项目当前没 CI,但即使有也要 marker 隔离)
- **不改 ONNX provider 的任何行为**
- **不引入 `sudo docker` 假设**— 脚本内部探测,用户 docker 组成员可无 sudo,否则提示
- **不硬编码 `http-proxy.conf` 到任何脚本**— 代理是用户环境,只在文档说明
- **不自动降级 rerank 到 ONNX**(rerank 当前 ONNX 路径工作良好,HTTP 降级的语义边界不清)— 只 embedding 做 fallback

### Verification Strategy

- **Infrastructure**:docker, pytest, lsp_diagnostics 都已在项目
- **Unit**:
  - batch chunking(OpenAI 2048 上限 / TEI 32 上限)
  - connection pool 复用(同一 provider 实例连续调用共享 opener)
  - fallback cascade(HTTP 连续 N 次失败后,embed_texts 走 ONNX)
  - Settings 验证(backend=http 缺 api_base → ValidationError)
- **Integration**:
  - 重跑现有 5 个,再加 2 个:批分片 / fallback 从 HTTP 转 ONNX
  - `tei-doctor.py` 退出码 0 在全就绪时,非 0 在任一步失败时
- **Manual QA**:
  - 新同事模拟:`make tei-prefetch && make tei-up && make tei-doctor && pytest -m integration` 应 10 分钟内全绿
  - 断网场景:`sudo iptables -A OUTPUT -d huggingface.co -j DROP` → prefetch 仍可用(因为走 hf-mirror)
- **QA Policy**:
  - 每 phase commit 前 lsp_diagnostics clean
  - 文档 guide 重写后,人工 walk-through 一遍(模拟 "什么都不懂的我" 读)
  - 所有 9 个已知坑都在文档有对应章节

---

## TODOs

### Phase 1 — Settings 强化

- [ ] 1. **`novel_analyzer/config/settings.py` 新增 HTTP 字段验证 + fallback 配置**

  **What to do**:
  - 新字段:
    ```
    embedding_fallback_backend: str = Field(default="")   # "onnx" | ""
    embedding_fallback_after_failures: int = Field(default=3)
    embedding_http_batch_size: int = Field(default=0)     # 0 = auto-detect by format
    rerank_http_batch_size: int = Field(default=0)
    ```
  - pydantic `model_validator`(after):
    - 若 `embedding_backend in ("http", "openai")` 且 `embedding_api_base == ""` → 抛 ValidationError
    - 若 `rerank_backend in ("http", "tei")` 且 `rerank_api_base == ""` → 同上
    - 若 `embedding_fallback_backend not in ("", "onnx")` → ValidationError(rerank 不支持 fallback,不做校验)
    - `api_format` 值在允许集合内
  - 添加 helper `settings.effective_embedding_batch_size()`:
    - 用户显式设置 → 返回用户值
    - `api_format==openai` → 2048
    - `api_format==tei` → 32
    - ONNX → 0(不分片)

  **Must NOT do**:
  - 不改已有字段默认值 / 名称
  - 不让 validator 在默认 ONNX 路径抛错

  **Acceptance Criteria**:
  - [ ] `Settings()` 默认构造不抛错
  - [ ] `Settings(embedding_backend="http")` 无 api_base 时抛 ValidationError,消息含 "NOVEL_ANALYZER_EMBEDDING_API_BASE"
  - [ ] `Settings(embedding_backend="http", embedding_api_base="http://x")` 合法
  - [ ] 现有 `tests/test_embedding_service.py` 全绿
  - [ ] lsp_diagnostics clean

  **Commit**: YES — `feat(settings): validate HTTP backend config and add fallback fields`

### Phase 2 — 模型预热脚本

- [ ] 2. **`scripts/dev/tei-prefetch.py`**

  **What to do**:
  - 纯 Python,用项目 `.venv` 的 `huggingface_hub`
  - 默认下载 `BAAI/bge-m3` + `BAAI/bge-reranker-v2-m3` 到 `.cache/tei/`
  - 可通过环境变量覆盖:
    - `TEI_EMBED_MODEL` / `TEI_RERANK_MODEL`
    - `TEI_CACHE_DIR`(默认 `$REPO/.cache/tei`)
    - `HF_ENDPOINT`(默认 `https://hf-mirror.com`,显式设置优先)
  - 每个模型的 `allow_patterns` 要包含踩过坑之后的完整列表:
    ```python
    DEFAULT_PATTERNS = [
        "*.json", "*.txt", "*.model",
        "*.bin", "*.safetensors",           # 坑 5: bge-m3 用 bin
        "tokenizer.json", "sentencepiece.bpe.model",
        "1_Pooling/*",
        "onnx/*",                           # 坑 6: TEI 优先 ONNX 分片
        "model.onnx_data",                  # 坑 6: 外部数据文件
    ]
    ```
  - 下载完后对每个模型 sanity check:
    - 至少存在 `config.json` + (`model.safetensors` OR `pytorch_model.bin`)
    - rerank 不要求 ONNX(显式 log:"no ONNX shard, TEI will use Candle+safetensors")
  - 输出:每个模型的 snapshot path、大小、耗时
  - 非零退出码在任一步失败
  - 支持 `--dry-run`(只 sanity check 已有的,不下新的)

  **Must NOT do**:
  - 不写死 HF_ENDPOINT(用户可能有企业镜像)
  - 不删除 cache(即使 sanity check 发现部分缺失,也只补齐不删)
  - 不调用 docker

  **Acceptance Criteria**:
  - [ ] `python scripts/dev/tei-prefetch.py` 在 `.cache/tei` 已齐全时应在 10s 内完成(只校验)
  - [ ] 空 cache 全新下载应在合理时间内完成(bge-m3 ~2.3GB + reranker ~2.2GB,通过 hf-mirror)
  - [ ] `--dry-run` 绝不发起网络请求
  - [ ] 下载后 `du -sh .cache/tei/models--BAAI--bge-m3/` 应 > 2 GB

  **Commit**: YES — `chore(dev): add tei-prefetch.py for model pre-caching via hf-mirror`

### Phase 3 — tei-up.sh 重写

- [ ] 3. **重写 `scripts/dev/tei-up.sh`**

  **What to do**:
  - 顶部注释明确说明:此脚本必须在 `tei-prefetch.py` 后运行,否则容器会尝试 HF 远程下载
  - 探测 docker 权限:
    ```
    DOCKER="docker"
    if ! docker info >/dev/null 2>&1; then
      if sudo -n docker info >/dev/null 2>&1; then
        DOCKER="sudo docker"
      else
        echo "docker not accessible; add yourself to docker group or configure passwordless sudo" >&2
        exit 1
      fi
    fi
    ```
  - 默认环境:
    - `TEI_IMAGE=ghcr.io/huggingface/text-embeddings-inference:cpu-1.6`
    - `TEI_HF_ENDPOINT=https://hf-mirror.com`(坑 1/2 兜底)
    - `TEI_CACHE_DIR=$PWD/.cache/tei`
  - 启动前检查:
    - `$TEI_CACHE_DIR/models--BAAI--bge-m3` 存在且 >1GB(否则提示先跑 prefetch)
    - 同上 reranker
    - 端口 `8080` `8081` 没被占用(否则 err)
  - 启动时传 `-e HF_ENDPOINT=$TEI_HF_ENDPOINT` 给容器(坑 3/4 兜底 — 本地 cache miss 时还能走 mirror)
  - 等待就绪的逻辑升级:
    - 不只是 `/health` 200,还要实际发一次 `/embed` 请求(`{"inputs":["ok"]}`)响应 200 才算真 ready
    - 最长等 300s,每 5s 一次
    - 若超时,dump 最近 20 行容器日志后退出
  - 打印最终就绪时的 embed dim 和 rerank 的 hello score,给人眼见为实的确认

  **Must NOT do**:
  - 不删除旧容器之外的东西(别误删用户其它 docker 资源)
  - 不修改 `/etc/systemd` 或主机配置(仅提示用户)
  - 不假设 `sudo` 可用

  **Acceptance Criteria**:
  - [ ] 模型 cache 不存在 → 脚本提示先跑 prefetch,退出码非 0
  - [ ] 模型 cache 齐全 → 脚本 5 分钟内让两个服务 ready,退出码 0
  - [ ] 8080 被占用时明确报错(不是 docker 运行时才崩)
  - [ ] 最终输出包含 embed dim(应为 1024)和 rerank 示例分数

  **Commit**: YES — `chore(dev): rewrite tei-up.sh with prefetch check, port check, real readiness probe`

### Phase 4 — Docker Compose 化

- [ ] 4. **`scripts/dev/docker-compose.tei.yml`**

  **What to do**:
  - 声明两个 service:`tei-embed` / `tei-rerank`
  - 用 env_file 支持 `.env.tei`(可选)
  - volume 挂载同一个 `.cache/tei`
  - healthcheck 配置(`curl -sf http://localhost:80/health`)
  - restart policy:`no`(dev 工具,不自启)
  - 在 `tei-up.sh` 里加一段判断:
    ```
    if command -v docker-compose >/dev/null 2>&1 || $DOCKER compose version >/dev/null 2>&1; then
      echo "Using docker-compose path"
      exec $DOCKER compose -f scripts/dev/docker-compose.tei.yml up -d
    fi
    ```
    然后回退到手动 run

  **Must NOT do**:
  - 不把此文件提到仓库根(放 `scripts/dev/` 下)
  - 不写成 v2 的 `services:` 空根格式(用标准 `version: "3.9"` 或 compose spec 格式)
  - 不把 api_key 等敏感信息写进 YAML

  **Acceptance Criteria**:
  - [ ] `docker compose -f scripts/dev/docker-compose.tei.yml config` 能解析
  - [ ] `docker compose -f scripts/dev/docker-compose.tei.yml up -d` 能起两个容器
  - [ ] `docker compose -f scripts/dev/docker-compose.tei.yml down` 能干净清理

  **Commit**: YES — `chore(dev): add docker-compose.tei.yml for declarative TEI startup`

### Phase 5 — Doctor 脚本

- [ ] 5. **`scripts/dev/tei-doctor.py`**

  **What to do**:
  - 按顺序检查以下项(每项用表格化输出,颜色提示):
    1. Python venv 存在
    2. `huggingface_hub` 已装
    3. docker 可访问(无 sudo / 需 sudo / 不可访问)
    4. docker image `text-embeddings-inference:cpu-1.6` 已拉(否则提示 `docker pull` + 代理说明)
    5. 模型 cache:`.cache/tei/models--BAAI--bge-m3/` 存在且 >1GB
    6. 模型 cache:`.cache/tei/models--BAAI--bge-reranker-v2-m3/` 存在且 >1GB
    7. 端口 `8080` `8081` 状态(free / 占用 by tei / 占用 by other)
    8. 容器 `tei-embed` `tei-rerank` 状态(不存在 / Exited / Up / healthy)
    9. `/health`:embed 响应 200
    10. `/health`:rerank 响应 200
    11. `/embed` 端到端:发 hello,响应 dim=1024
    12. `/rerank` 端到端:发 query,响应正确排序
    13. 从 novel_analyzer 导入 `HttpEmbeddingProvider` 实跑一次 `embed_texts(["hi"])` 成功
    14. 延迟采样:`/embed` P50 / P95(发 20 次)
  - 每项失败时给出:
    - 失败原因(具体)
    - 下一步动作(指向 `docs/foundation-optimization/http-backend-guide.md#` 对应锚点)
  - 全部通过时退出码 0,任何失败退出码 1

  **Must NOT do**:
  - 不自动修复(只诊断 + 提示)
  - 不启动 / 停止容器

  **Acceptance Criteria**:
  - [ ] 在当前就绪环境跑一次,全部 14 项通过,退出码 0
  - [ ] `sudo docker stop tei-embed` 后再跑,在第 9/10 步失败,退出码 1,错误消息指向 guide 的启动章节
  - [ ] 清空 cache 后再跑,在第 5 步失败,指向 prefetch 章节

  **Commit**: YES — `chore(dev): add tei-doctor.py end-to-end diagnostics`

### Phase 6 — HTTP Provider 批大小分片

- [ ] 6. **`novel_analyzer/embedding/service.py` + `rerank/service.py`:批大小分片**

  **What to do**:
  - embedding:
    - 新增私有 `_batch_size` 属性(从 Settings.effective_embedding_batch_size() 传入)
    - `embed_texts(texts)`:
      - 若 `len(texts) <= batch_size` 或 `batch_size == 0` → 原路径
      - 否则按 `batch_size` 切块,逐块请求,合并结果
      - 块间失败:继续尝试剩余块,最后抛 RuntimeError 并包含所有失败块索引
  - rerank:同理,按 `rerank_http_batch_size` 分片 `documents`(query 保持一致,文档分批 rerank 后把所有分数拼接)
  - 注意:rerank 分片后,要保持"越大越相关"的 score 语义可跨批比较吗?
    - 对 cross-encoder 是可以的,score 是绝对相关性分
    - 加注释说明:"对 TEI cross-encoder 有效,对 ListWise 不一定"

  **Must NOT do**:
  - 不改 Protocol 签名
  - 不引入异步(保持同步接口)
  - 不在空 texts 时进入分片逻辑

  **Acceptance Criteria**:
  - [ ] Unit test:`embed_texts([...100 items])` 走 openai 格式,mock 下应发 1 次请求(openai 默认 2048);走 tei 格式应发 4 次(32 + 32 + 32 + 4)
  - [ ] 某块返回 4xx,应累积错误并在最后抛出,不吞
  - [ ] lsp_diagnostics clean

  **Commit**: YES — `feat(embedding,rerank): batch-chunk HTTP requests per format limits`

### Phase 7 — 连接复用 + Fallback Cascade

- [ ] 7. **HTTP provider 连接复用 + embedding fallback**

  **What to do**:
  - 连接复用:
    - `HttpEmbeddingProvider` / `HttpRerankProvider` 各持一个 `urllib.request.OpenerDirector`
    - 首次请求时 `build_opener()`,后续复用
    - 确保 `@dataclass(slots=True)` 不阻碍私有字段(加 `_opener: Any = None`)
  - Fallback cascade(仅 embedding):
    - `HttpEmbeddingProvider` 持一个 `_consecutive_failures: int = 0`
    - 成功调用 → 重置为 0
    - 连续失败 `>= settings.embedding_fallback_after_failures` →
      - 若 `settings.embedding_fallback_backend == "onnx"`,下一次调用直接走 ONNX(lazy 加载 ONNX provider)
      - 若 `== ""`,维持原行为(抛错)
    - 落到 ONNX 后,每 60 秒重试一次 HTTP health,成功就切回
    - 日志:每次切换打印 INFO
  - 注意 lru_cache 现在持的是 provider 单例,失败计数不会漏
  - 保持 thread-safety 警告在 docstring(当前项目单进程使用,不加锁)

  **Must NOT do**:
  - 不加全局锁(Settings 已是 singleton)
  - 不对 rerank 做 fallback(语义边界不清,避免静默换算法)
  - 不改 ONNX provider

  **Acceptance Criteria**:
  - [ ] Unit test:3 次连续失败后,第 4 次调用走 ONNX(mock 出 ONNX 被创建)
  - [ ] HTTP 恢复后,自动切回 HTTP(通过 mock 时间快进)
  - [ ] `fallback_backend=""` 时行为和现在一致(纯错误)
  - [ ] 连接复用:同一 provider 连续调 5 次,应只 build_opener 一次(用 mock 验证)

  **Commit**: YES — `feat(embedding): HTTP connection reuse and optional ONNX fallback cascade`

### Phase 8 — 集成测试扩展

- [ ] 8. **扩展 `tests/integration/test_tei_integration.py`**

  **What to do**:
  - 共享 fixture 抽到 `tests/integration/conftest.py`:`tei_live`(autouse=False 的版本),复用 health 探针
  - 新增测试:
    - `test_embedding_batch_chunking`:发 40 个文本(超过 TEI 的 32 上限),验证返回 40 个向量且内容正确
    - `test_embedding_fallback_to_onnx`:临时改 `api_base` 到不存在的端口,跑 embed_texts,验证连续失败后自动切 ONNX(前提是本机 ONNX 能跑)
    - `test_rerank_batch_chunking`:10 query + 50 documents,分片后返回 50 个分数,排序合理
  - 所有测试仍然 skip when TEI 不 live

  **Must NOT do**:
  - 不让 fallback test 要求完整 ONNX(可以 xfail / skip if ONNX not available)

  **Acceptance Criteria**:
  - [ ] TEI 就绪时 `pytest -m integration` 全绿
  - [ ] TEI 停机时 `pytest -m integration` 全部 skip,无 fail

  **Commit**: YES — `test(integration): extend TEI coverage with chunking and fallback scenarios`

### Phase 9 — 文档 + Makefile + .env.example 重写

- [ ] 9. **文档全面更新 + Makefile**

  **What to do**:

  **9a. 重写 `docs/foundation-optimization/http-backend-guide.md`**:
  - 新增章节 `## 国内网络快速入门`(最靠前),5 步上手:
    1. `make tei-prefetch`(用 hf-mirror,1 次下 ~4.5GB)
    2. `docker login` 如需(可选)
    3. `docker pull` 检查(镜像需预先 pull,必要时走代理,配置示例)
    4. `make tei-up`
    5. `make tei-doctor` 验证
  - 新增章节 `## 已知坑与规避`(8-9 项,一一对应踩过的坑):
    1. docker daemon 代理(系统级配置)
    2. 容器网络 ≠ daemon 网络
    3. HF_HUB_OFFLINE 不完全生效 → 用 HF_ENDPOINT
    4. hf-mirror 的 content-range 问题 → 不要直接给容器用(除非 TEI ≥ 1.7 修了)
    5. allow_patterns 必须覆盖 bin/onnx/onnx_data
    6. reranker 无 ONNX → Candle fallback 较慢
    7. sudo / docker 组
    8. 端口冲突
    9. 模型 cache 不完整 → 用 `--dry-run` 检查
  - 新增章节 `## 运营 Runbook`:
    - 切换模型(e.g. bge-m3 → Conan-v2)
    - 回滚到 ONNX(紧急)
    - 升级 TEI 版本
    - 容器日志排查
  - 删除 / 修正当前过于乐观的段落
  - 加入 `## 观测`(简单版):延迟指标从 `tei-doctor` 拿,若未来接 Prometheus 的扩展点在哪

  **9b. `.env.example` 追加**:
  ```
  NOVEL_ANALYZER_EMBEDDING_FALLBACK_BACKEND=onnx
  NOVEL_ANALYZER_EMBEDDING_FALLBACK_AFTER_FAILURES=3
  NOVEL_ANALYZER_EMBEDDING_HTTP_BATCH_SIZE=0
  NOVEL_ANALYZER_RERANK_HTTP_BATCH_SIZE=0
  ```

  **9c. 新建 `Makefile`(仓库根)**:
  ```makefile
  .PHONY: tei-prefetch tei-up tei-down tei-doctor tei-logs tei-restart

  tei-prefetch:
  	.venv/bin/python scripts/dev/tei-prefetch.py

  tei-up:
  	bash scripts/dev/tei-up.sh

  tei-down:
  	bash scripts/dev/tei-down.sh

  tei-doctor:
  	.venv/bin/python scripts/dev/tei-doctor.py

  tei-logs:
  	$${DOCKER:-docker} logs --tail 100 tei-embed
  	$${DOCKER:-docker} logs --tail 100 tei-rerank

  tei-restart: tei-down tei-up
  ```

  **9d. 更新 `docs/foundation-optimization/README.md`** 的"专题备忘录"或"详细建设指南"把此 guide 放显眼位置

  **Must NOT do**:
  - Makefile 不覆盖已有(若已有,追加;若没有则新建)
  - 不把 `make tei-up` 写成默认 `make`(PHONY only)

  **Acceptance Criteria**:
  - [ ] `make tei-doctor` 等价于 `python scripts/dev/tei-doctor.py`
  - [ ] Guide 9 个坑都有对应章节和锚点
  - [ ] `.env.example` 包含新字段
  - [ ] Guide 5 步上手能让陌生人照抄跑通

  **Commit**: YES — `docs(foundation-optimization): rewrite HTTP backend guide for production integration, add Makefile`

---

## Commit Strategy

9 个 atomic commits,每个走 Lore 格式。示例(Phase 2):

```
Pre-cache TEI models locally to bypass in-container HF fetches

tei-prefetch.py downloads bge-m3 + bge-reranker-v2-m3 to .cache/tei
using huggingface_hub with HF_ENDPOINT=hf-mirror by default. Covers
the allow_patterns gap where bge-m3 uses *.bin and ONNX shards need
model.onnx + model.onnx_data explicitly.

Constraint: hf-mirror content-range headers break TEI's rust downloader,
            but huggingface_hub tolerates them fine
Rejected: rely on TEI's in-container HF fetch | fails without proxy and
          HF_HUB_OFFLINE=1 does not work correctly in TEI 1.6
Confidence: high
Scope-risk: narrow
Directive: Keep prefetch patterns list updated when changing models
Tested: manual run filling empty cache with both models
Not-tested: behavior when partial cache present (handled by snapshot_download resume)
```

---

## Success Criteria

- [ ] 新同事模拟:`git clone → make tei-prefetch → make tei-up → make tei-doctor → pytest -m integration` 10 分钟内全绿
- [ ] 所有 9 个已知坑在 guide 有章节 + `tei-doctor` 失败时指向该章节
- [ ] `embedding_backend=onnx` 默认路径行为完全不变
- [ ] 单元测试 + 集成测试全绿(TEI up 时)
- [ ] 9 个 commit Lore 格式
- [ ] `make tei-up && make tei-doctor && make tei-down` 完整生命周期可跑
- [ ] HTTP provider:批分片 / 连接复用 / fallback cascade 三项都有测试证据

---

## Open Questions

- **国内网络场景的 ghcr.io 镜像拉取**:当前需要 daemon 代理(用户已配过 `127.0.0.1:54321`)。是否要 script 自动探测并提示?**本计划决定不做** — 代理是主机管理员级事务,脚本只在 doctor 中检测 `docker pull` 成功并提示。
- **是否要提供 modelscope 镜像路径作为第二兜底**:`tei-prefetch.py` 的 `HF_ENDPOINT` 可改 modelscope URL,但 modelscope 不完全兼容 HF API,可能需要适配层。**本计划决定不做**,记 open question 到 guide。
- **rerank fallback**:是否给 rerank 也加 fallback?当前 ONNX reranker 路径工作良好,HTTP fallback 语义是"相同文本排序接近",但两个模型权重可能微不同。**本计划决定不做** — 留后续单独评估。
- **是否做 Prometheus /metrics 端点**:TEI 自带 `/metrics`,但项目当前没 Prometheus。guide 说明存在即可。
- **multi-tenant API key 轮换**:当前 `api_key` 是单个 string。未来如果真接商业 API 做 SaaS,需要 key 池。**本计划不涉及**。

---

## Rollback Plan

每个 phase 都是独立 commit,`git revert <hash>` 即可回滚单一改动。主要风险 + 缓解:

| 改动 | 风险 | 缓解 |
|------|------|------|
| Settings validator | 用户 `.env` 配置不全 → 启动直接崩 | 默认值保持,只在显式 `backend=http` 时才校验 |
| Batch chunking | 分片逻辑 bug → 结果错误 | 新增 unit test 覆盖,ONNX 路径不受影响 |
| Fallback cascade | 悄悄切到 ONNX 导致结果维度不符 | 只在 `embedding_fallback_backend=onnx` 显式配置时启用;默认空 |
| Connection reuse | opener 泄漏连接 | urllib 对象随 provider 实例 GC 回收 |
| Makefile | 覆盖用户既有 | Phase 9 前先 check 仓库有无 Makefile |

---

## Dependencies Between Phases

```
Phase 1 (Settings) ──┐
                     ├→ Phase 6 (batch) ──┐
Phase 2 (prefetch) ──┤                    ├→ Phase 8 (integration tests)
                     ├→ Phase 3 (up.sh) ──┤
Phase 4 (compose) ───┘                    ├→ Phase 5 (doctor) ──┐
                                          │                     ├→ Phase 9 (docs + Makefile)
Phase 7 (reuse+fallback) ─────────────────┘                     │
                                                                │
                                                          (verify end-to-end)
```

Phase 1-7 可以由一个 executor 串行做(彼此代码关联紧密),Phase 8-9 收尾。

---

## Notes for the Executor

1. **先通读整份 plan**,再读 `a7a3578..db61a93` 的 diff 了解已有代码
2. 每个 phase 开始前:把当前 phase 的 Must Have / Must NOT Have / Acceptance 复述一遍(在内心),确保不走偏
3. 每个 phase 结束前:lsp_diagnostics clean、相关 pytest 绿、commit 带 Lore trailers
4. 遇到计划和现实不符(比如 `@dataclass(slots=True)` 不能加私有可变字段),按**最小偏离**处理并在 commit 消息 `Not-tested:` 或 `Constraint:` 里写清楚
5. 不要自作主张扩范围
6. 最终报告格式(见顶部 Deliverables 对照表)必须真实,不许"基本完成"这种糊弄
7. 集成测试 Phase 8 必须真跑一次(TEI 当前在 localhost:8080/8081 运行中,可以直接用)
