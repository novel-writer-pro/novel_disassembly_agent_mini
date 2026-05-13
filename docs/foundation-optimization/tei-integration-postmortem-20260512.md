# TEI 集成复盘 — 2026-05-12

> 本文是 "ONNX → HTTP/TEI 双后端" 集成过程的完整复盘，写于 `tei-doctor` 16/16 通过、7 个集成测试全绿之后。
> 目标读者：下一个接手此项目、或需要新增模型的工程师。

---

## 0. 一句话结论

TEI 已成为项目一等后端，与本地 ONNX 并列。CPU 部署适合 dev / 低并发场景；生产长文本高并发需 GPU 部署，或继续走 ONNX。

---

## 1. 起点与目标

### 用户原始诉求

> "效果好就保留，进行测试和尝试，另外关于过程复盘到 docs 也是必须的"

### 启动时的现状

- 只有本地 ONNX 后端（`novel_analyzer/embedding/service.py`），无 HTTP 接口
- 无 TEI 容器管理脚本，无健康检查，无集成测试
- 模型下载依赖手动操作，无镜像/代理策略

### 真正的目标解读

不是单纯"加一个 HTTP 接口"，而是让 TEI 成为**一等公民**：

1. 可独立启动、健康检查、优雅关闭
2. 与 ONNX 并列，通过 `.env` 一键切换
3. 批分片、连接复用、fallback 逻辑与 ONNX 路径对等
4. 有足够的集成测试覆盖，让 CI 能发现回归

---

## 2. 最终交付的能力（成果对照表）

| 工件 | 文件路径 | 一句话价值 | 关键 commit |
|------|---------|-----------|------------|
| Makefile targets | `Makefile` | `make tei-prefetch/up/down/doctor/test-tei` 五条命令覆盖全生命周期 | `eb9b572` |
| 模型预取脚本 | `scripts/dev/tei-prefetch.py` | hf-mirror 镜像下载 + allow_patterns 精确控制 | `089dbfd` |
| 启动脚本 | `scripts/dev/tei-up.sh` | preflight 检查 + 真实 readiness probe（不靠 sleep） | `87aa0af` |
| 关闭脚本 | `scripts/dev/tei-down.sh` | 优雅停止容器 | `87aa0af` |
| Docker Compose | `scripts/dev/docker-compose.tei.yml` | 声明式 TEI 启动，含 volume/env 配置 | `dad9c0f` |
| 诊断脚本 | `scripts/dev/tei-doctor.py` | 16 项端到端检查，结构化输出 | `ab6d87a` |
| HTTP Embedding Provider | `novel_analyzer/embedding/service.py` | 批分片 + 连接复用 + ONNX fallback cascade | `77ebaff` |
| HTTP Rerank Provider | `novel_analyzer/rerank/service.py` | 批分片 + 连接复用 | `098411a` |
| Settings 验证 | `novel_analyzer/config/settings.py` | HTTP backend 字段 + Pydantic 验证 + fallback 字段 | `847a046` |
| `.env.example` | `.env.example` | HTTP 字段示例，含注释说明 | `847a046` |
| 集成测试 conftest | `tests/integration/conftest.py` | TEI 可用性 skip 标记，防止无容器时误失败 | `7e3c11e` |
| 集成测试 | `tests/integration/test_tei_integration.py` | 7 个测试覆盖 embed/rerank/batch chunking | `7e3c11e` |
| HTTP Backend 操作手册 | `docs/foundation-optimization/http-backend-guide.md` | 配置、启动、排障完整指南（已重写） | `eb9b572` |
| 本复盘文档 | `docs/foundation-optimization/tei-integration-postmortem-20260512.md` | 9 个坑 / 决策回顾 / 性能边界 / SOP | — |

---

## 3. 关键技术决策

### 决策 1：双后端共存（ONNX 默认 + HTTP 可选）

不强制迁移到 TEI，保留 ONNX 作为默认路径。理由：

- ONNX 在无 Docker 环境（CI、轻量开发机）下零依赖可用
- TEI 需要 Docker + 模型预取，冷启动成本高
- 通过 `EMBEDDING_BACKEND=http` 环境变量切换，不改代码

### 决策 2：不走商业 Embedding API

| 因素 | 说明 |
|------|------|
| 数据主权 | 小说内容不宜发送第三方 |
| 成本 | 长期高频调用费用不可控 |
| 中文能力 | bge-m3 在中文语义检索上优于通用商业模型 |

参考：[priority-and-roi-research-20260512.md](./priority-and-roi-research-20260512.md)

### 决策 3：不自研微调 Embedding

| 因素 | 说明 |
|------|------|
| 数据不足 | 无足够标注的小说语义对 |
| 基座迭代快 | bge-m3 → Conan-v2 / Qwen3-Embedding 升级成本低于维护微调版本 |
| 评测集成本高 | 构建可靠的领域评测集需要大量人工 |

### 决策 4：TEI 而非自建 inference server

TEI（Text Embeddings Inference）由 HuggingFace 维护，原生支持 bge-m3 / bge-reranker-v2-m3，内置批处理、ONNX/Candle 后端切换。自建需要维护 tokenizer + batching + 健康检查，维护成本不值得。

### 决策 5：HTTP 走 `urllib` 不引入 `httpx`

项目已有 `urllib` 用法，`httpx` 是新依赖。连接复用通过 `http.client.HTTPConnection` 手动管理，满足需求，零新依赖。

### 决策 6：仅 embedding 加 ONNX fallback，rerank 不加

bge-reranker-v2-m3 没有 ONNX 分片（TEI 自动走 Candle），本地 ONNX rerank 路径与 HTTP 路径语义不同（分数范围不同），混用会导致排序结果不可比。embedding fallback 是同语义空间，rerank fallback 不是。

### 决策 7：`tei-doctor.py` 用 Python 不用 bash

bash 脚本难以结构化输出检查结果。Python 可以输出 JSON / 表格，方便 CI 解析，也方便未来扩展检查项。

---

## 4. 9 个真实踩过的坑（技术心跳）

### 坑 1：`ghcr.io` 国内拉镜像卡死

**症状**：`docker pull ghcr.io/huggingface/text-embeddings-inference` 挂起，无进度，无报错。

**根因**：`ghcr.io` 在国内网络不可达，Docker daemon 默认无代理。

**规避**：在 `/etc/docker/daemon.json` 配置 `"proxies": {"http-proxy": "...", "https-proxy": "..."}` 并重启 daemon。

**沉淀**：`scripts/dev/tei-up.sh` preflight 检查中有 `docker pull` 可达性提示；`docs/foundation-optimization/http-backend-guide.md` §故障排查 有完整代理配置步骤。

---

### 坑 2：daemon proxy ≠ container 网络

**症状**：daemon 配了代理，镜像拉下来了，但容器内 `curl huggingface.co` 仍然超时。

**根因**：`/etc/docker/daemon.json` 的 proxy 只影响 daemon 拉镜像，不影响容器内网络。容器内需要通过 `environment:` 传入 `HTTP_PROXY` / `HTTPS_PROXY`。

**规避**：`docker-compose.tei.yml` 的 `environment` 段显式传入代理变量（如需要）。

**沉淀**：`scripts/dev/docker-compose.tei.yml` 有注释说明 daemon proxy vs container proxy 的区别。

---

### 坑 3：`HF_HUB_OFFLINE=1` 不可靠

**症状**：设置 `HF_HUB_OFFLINE=1` 后，TEI 启动仍然尝试连接 `huggingface.co`，等待约 2 分钟后超时失败。

**根因**：TEI 内部有独立的模型元数据检查逻辑，不完全遵守 `HF_HUB_OFFLINE`。

**规避**：不依赖 `HF_HUB_OFFLINE`；改为在启动前用 `tei-prefetch.py` 把模型完整下载到本地，TEI 挂载本地目录启动（`--model-id /models/bge-m3`）。

**沉淀**：`scripts/dev/tei-prefetch.py` 是标准预取入口；`scripts/dev/tei-up.sh` 检查本地模型目录存在才启动容器。

---

### 坑 4：`hf-mirror.com` 给容器用，缺 `content-range` 头报错

**症状**：把 `HF_ENDPOINT=https://hf-mirror.com` 传给 TEI 容器，下载大文件时报 `content-range header missing` 错误，下载中断。

**根因**：`hf-mirror.com` 的 CDN 对部分大文件不返回 `Content-Range` 响应头，而 TEI 的断点续传逻辑依赖该头。

**规避**：`hf-mirror.com` 只用于宿主机的 `tei-prefetch.py`（Python `huggingface_hub` 库，容错更好）；TEI 容器本身挂载已下载的本地目录，不走 HF 网络。

**沉淀**：`scripts/dev/tei-prefetch.py` 默认 `HF_ENDPOINT=https://hf-mirror.com`；`docker-compose.tei.yml` 不设 `HF_ENDPOINT`，只挂载本地 volume。

---

### 坑 5：`snapshot_download(allow_patterns)` 漏 `*.bin`

**症状**：`tei-prefetch.py` 下载 bge-m3 后，TEI 启动失败，日志显示找不到权重文件，目录只有 38MB。

**根因**：`allow_patterns` 只写了 `["*.safetensors", "*.json", "tokenizer*"]`，漏掉了 `*.bin`（部分模型仍用 `.bin` 格式存权重）。

**规避**：`allow_patterns` 加入 `"*.bin"`。

**沉淀**：`scripts/dev/tei-prefetch.py` 的 `ALLOW_PATTERNS` 常量包含 `*.bin`，注释说明原因。

---

### 坑 6：漏 `model.onnx_data`

**症状**：bge-m3 ONNX 模式下，TEI 启动时仍然尝试远程下载，日志显示 `model.onnx_data` 文件缺失。

**根因**：bge-m3 的 ONNX 权重分为 `model.onnx`（结构）和 `model.onnx_data`（大权重文件，约 1.1GB），`allow_patterns` 漏掉了后者。

**规避**：`allow_patterns` 加入 `"*.onnx"` 和 `"*.onnx_data"`。

**沉淀**：`scripts/dev/tei-prefetch.py` 的 `ALLOW_PATTERNS` 包含两者，注释说明 ONNX 分片原因。

---

### 坑 7：bge-reranker-v2-m3 无 ONNX 分片 → Candle 慢启动

**症状**：reranker 容器启动后约 40 秒才响应第一个请求，远慢于 embedding 容器。

**根因**：`bge-reranker-v2-m3` 没有预编译的 ONNX 分片，TEI 自动 fallback 到 Candle + safetensors 路径，需要在启动时 JIT 编译。

**规避**：这是已知限制，不是 bug。`tei-up.sh` 的 readiness probe 等待真实 `/health` 返回 200，而不是固定 sleep，所以不会因慢启动导致误判。

**沉淀**：`scripts/dev/tei-doctor.py` 检查项 #7 会报告 reranker 加载时间（实测约 40s），提示这是正常现象。

---

### 坑 8：`sudo docker` 权限差异

**症状**：部分开发机上 `docker` 命令需要 `sudo`，`tei-up.sh` 直接调用 `docker` 失败；另一些机器加了 `sudo` 反而报权限错误（用户在 docker group）。

**根因**：不同环境的 docker socket 权限配置不同。

**规避**：`tei-up.sh` 检测当前用户是否在 `docker` group，给出明确提示而不是静默失败；`Makefile` 的 target 不硬编码 `sudo`。

**沉淀**：`scripts/dev/tei-up.sh` preflight 段有 `groups | grep docker` 检查，失败时输出具体修复命令。

---

### 坑 9：长中文文本 + 较大 batch 在 CPU 上卡死 / OOM

**症状**：对约 290 字的中文文本，batch=30 发送给 CPU TEI，进程卡死，最终被 OOM killer 终止（14GB RAM 开发机）。

**根因**：bge-m3 处理长中文序列时内存峰值远超短文本；CPU 推理无法利用显存卸载；14GB RAM 不足以同时持有模型（~9GB）+ 推理中间态。

**规避**：
- 生产长文本高并发场景需 GPU 部署
- CPU 场景建议 batch ≤ 8，文本长度 ≤ 128 tokens
- `HttpEmbeddingProvider` 的批分片逻辑（`novel_analyzer/embedding/service.py`）默认按 TEI 格式限制分片，避免单次请求过大

**沉淀**：`novel_analyzer/embedding/service.py` 的 `_chunk_batch` 方法；`docs/foundation-optimization/http-backend-guide.md` §性能边界 有明确说明。

---

## 5. 性能数据（实测）

> 所有数据来自真实 TEI 容器运行，非估算。测试环境：CPU-only，14GB RAM，bge-m3 + bge-reranker-v2-m3。

### 延迟数据

| 指标 | 数值 | 来源 |
|------|------|------|
| 单次 embed P50 | 902ms | tei-doctor 16 项检查实测（n=20） |
| 单次 embed P95 | 1582ms | tei-doctor 16 项检查实测（n=20） |
| 集成测试总耗时 | 104.40s（7 passed） | `pytest tests/integration/` 实测 |
| reranker 冷启动 | ~40s | Candle+safetensors 加载实测 |
| tei-doctor 通过率 | 16/16 | 全量检查实测 |

### 内存占用

| 模型 | 磁盘缓存 | 说明 |
|------|---------|------|
| bge-m3 | ~9GB | ONNX + safetensors 全量缓存 |
| bge-reranker-v2-m3 | ~4.6GB | safetensors（无 ONNX 分片） |

### 测试文本特征

- 平均样本文本长度：290 字（中文）
- CPU OOM 触发条件：batch=30，avg 290 字，14GB RAM

### 边界声明

**CPU TEI 不适合以下场景**：
- 文本长度 > 256 tokens 的高并发批处理
- batch size > 8 的长文本请求
- 内存 < 16GB 的机器（模型 + 推理中间态合计需要 > 14GB）

**CPU TEI 适合以下场景**：
- 开发调试（单次请求，短文本）
- 低并发生产（< 5 QPS，文本 < 128 tokens）
- 功能验证和集成测试

---

## 6. 全 lifecycle SOP

### 新机器接入

```bash
# 1. 下载模型（需要网络，约 14GB）
make tei-prefetch

# 2. 启动 TEI 容器
make tei-up

# 3. 端到端健康检查
make tei-doctor
# 期望输出：16/16 checks passed

# 4. 运行集成测试（需要容器运行中）
make test-tei
# 期望输出：7 passed
```

### 切换到 HTTP 后端

```bash
# .env 文件
EMBEDDING_BACKEND=http
EMBEDDING_HTTP_URL=http://localhost:8080
RERANK_BACKEND=http
RERANK_HTTP_URL=http://localhost:8081
```

### 升级模型

```bash
# 1. 修改 .env 中的模型名称
# 2. 重新预取
make tei-prefetch

# 3. 重启容器
make tei-down && make tei-up

# 4. 验证
make tei-doctor
```

### 紧急回滚（切回 ONNX）

```bash
# .env 文件
EMBEDDING_BACKEND=onnx
RERANK_BACKEND=onnx

# 无需重启容器，下次请求自动走 ONNX 路径
```

### 健康监控

```bash
# 定期运行（建议加入 cron 或 CI）
make tei-doctor

# 或直接调用
python scripts/dev/tei-doctor.py --json  # 结构化输出
```

---

## 7. 失败的尝试与放弃路径

### 直连 `huggingface.co`

**尝试**：不配代理，直接 `docker pull` 和 `snapshot_download`。

**结果**：国内网络不可达，挂起无响应。

**放弃原因**：网络环境不可控，不是项目能解决的问题。

**替代方案**：daemon 级代理 + hf-mirror 宿主机下载。

---

### `hf-mirror.com` 直接给 TEI 容器

**尝试**：在 `docker-compose.tei.yml` 设置 `HF_ENDPOINT=https://hf-mirror.com`，让 TEI 容器自己下载模型。

**结果**：大文件下载时 `content-range header missing` 报错，下载中断。

**放弃原因**：hf-mirror CDN 不支持断点续传所需的 `Content-Range` 头。

**替代方案**：宿主机预取 + 本地 volume 挂载。

---

### `HF_HUB_OFFLINE=1` 离线模式

**尝试**：设置 `HF_HUB_OFFLINE=1` 让 TEI 完全离线运行。

**结果**：TEI 仍然尝试连接远程，2 分钟超时后失败。

**放弃原因**：TEI 内部逻辑不完全遵守该环境变量。

**替代方案**：本地 volume 挂载，不依赖离线标志。

---

### 完整 ONNX vs TEI 性能对比 benchmark

**尝试**：编写 `/tmp/bench_tei_vs_onnx.py`，对比两个后端在相同文本上的延迟和吞吐。

**结果**：在 14GB RAM 开发机上，ONNX provider 冷加载 + 32 个 ~290 字中文文本 batch 触发 OOM，进程被 kill。

**放弃原因**：开发机内存不足，无法得到有效对比数据。

**替代方案**：使用 `tei-doctor` 的实测数据（P50/P95）作为性能基准；完整 benchmark 留待 GPU 机器或 ≥32GB RAM 环境重跑（见附录 B）。

---

## 8. 给未来的建议

### GPU 部署评估

当出现以下情况时，建议评估 GPU 部署：

- 生产 QPS > 10，且文本平均长度 > 128 tokens
- 单次 embed 延迟 P95 > 2s 影响用户体验
- 需要处理全章节（1000+ 字）的批量 embedding

GPU 部署只需修改 `docker-compose.tei.yml` 的 `image` tag（加 `-gpu` 后缀）和 `deploy.resources` 配置，其余代码不变。

### 商业 API 切换的 trigger 条件

以下条件同时满足时，可重新评估商业 API：

- 月 embedding 调用量 > 1000 万次（成本临界点）
- 数据脱敏方案已就绪（解决数据主权问题）
- 商业 API 中文语义检索质量经过评测验证

参考：[priority-and-roi-research-20260512.md](./priority-and-roi-research-20260512.md) §商业 API 对比

### 模型升级路径

从 bge-m3 升级到 Conan-v2 / Qwen3-Embedding 的 checklist：

1. 确认新模型有 ONNX 分片（否则 CPU 性能会退化）
2. 更新 `tei-prefetch.py` 的 `ALLOW_PATTERNS`（新模型可能有不同文件结构）
3. 重新运行 `make tei-doctor` 验证 16/16
4. 重新运行 `make test-tei` 验证 7/7
5. 对比 P50/P95 延迟，确认无性能退化

### Rerank Fallback 何时考虑加上

当前 rerank 不加 ONNX fallback（见决策 6）。如果未来 bge-reranker-v2-m3 有了 ONNX 分片，且分数范围与 HTTP 路径对齐，可以考虑加上。加之前需要先验证两个路径的分数分布是否可比。

---

## 附录 A：Lore commit 历史

本次集成的 9 个 commit（`847a046..eb9b572`）：

| Hash | 一句话说明 |
|------|-----------|
| `847a046` | feat(settings): validate HTTP backend config and add fallback fields |
| `089dbfd` | feat(scripts): add TEI model prefetch with hf-mirror fallback |
| `87aa0af` | feat(scripts): rewrite tei-up.sh with preflight checks and real readiness probe |
| `dad9c0f` | feat(scripts): add docker-compose.tei.yml for declarative TEI startup |
| `ab6d87a` | feat(scripts): add tei-doctor.py end-to-end diagnostics |
| `098411a` | feat(embedding,rerank): batch-chunk HTTP requests per format limits |
| `77ebaff` | feat(embedding): HTTP connection reuse and optional ONNX fallback cascade |
| `7e3c11e` | test(integration): expand TEI integration tests with batch chunking coverage |
| `eb9b572` | docs(tei): comprehensive production guide and Makefile targets |

---

## 附录 B：失败的 benchmark 复现命令

以下命令在 ≥32GB RAM 的机器上可重跑，用于得到 ONNX vs TEI 的完整对比数据：

```bash
# 前提：TEI 容器已启动（make tei-up && make tei-doctor）
# 前提：机器 RAM >= 32GB（ONNX provider 冷加载 + batch 推理峰值约 20GB）

.venv/bin/python /tmp/bench_tei_vs_onnx.py

# 已知失败场景（勿在 14GB 机器重跑）：
# - ONNX provider 冷加载 + 30 chunks × ~290 字中文 → OOM，进程被 kill
# - 根因：ONNX provider 冷加载本身约 4GB + 推理中间态 + bge-m3 模型 9GB > 14GB
# - 建议重试环境：>= 32GB RAM，或跳过 ONNX 本地，只测 HTTP TEI 路径
```

---

## 附录 C：相关文档链接

| 文档 | 说明 |
|------|------|
| [http-backend-guide.md](./http-backend-guide.md) | HTTP Backend 配置、启动、排障操作手册（日常运维看这里） |
| [priority-and-roi-research-20260512.md](./priority-and-roi-research-20260512.md) | 底座优化优先级与 ROI 预研（商业 API / 自研微调 / 开源方案对比决策依据） |
| `scripts/dev/tei-doctor.py` | 16 项端到端诊断脚本（`make tei-doctor`） |
| `tests/integration/test_tei_integration.py` | 7 个集成测试（`make test-tei`） |
