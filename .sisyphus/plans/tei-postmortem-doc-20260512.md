# TEI 集成复盘文档发布 — 2026-05-12

## TL;DR

> **Quick Summary**:把这次 "ONNX → HTTP/TEI 双后端" 的完整集成过程(9 个坑、9 个 commit、决策回顾、性能发现)沉淀为一份给项目长期受益的复盘文档,放进 `docs/foundation-optimization/`。
>
> **Deliverables**:
> - `docs/foundation-optimization/tei-integration-postmortem-20260512.md`(完整复盘)
> - `docs/foundation-optimization/README.md` 索引更新
>
> **Estimated Effort**: 小项目(0.5 人天 = 1 个 commit)
> **Parallel Execution**: NO
> **Critical Path**: Prometheus(本计划)→ executor 搬运成 docs/

---

## Context

### Original Request

用户原话(在 TEI 集成全跑通且 doctor 16/16 后):
> "效果好就保留,进行测试和尝试,另外关于过程复盘到 docs 也是必须的"

复盘的目的:
1. 沉淀 **9 个真实踩过的坑**,让下一个接手或加新模型的人不重蹈
2. 记录 **决策依据**(为什么不走商业 API,为什么不自研微调,为什么 HTTP+ONNX 双后端)
3. 记录 **性能边界**(CPU TEI 处理长中文文本的实测限制)
4. 给出 **验收 / 运营 / 升级 SOP**

### 已有的事实素材(写复盘必须基于)

**已交付的 9 个 commit**:
```
eb9b572 docs(tei): comprehensive production guide and Makefile targets
7e3c11e test(integration): expand TEI integration tests with batch chunking coverage
77ebaff feat(embedding): HTTP connection reuse and optional ONNX fallback cascade
098411a feat(embedding,rerank): batch-chunk HTTP requests per format limits
ab6d87a feat(scripts): add tei-doctor.py end-to-end diagnostics
dad9c0f feat(scripts): add docker-compose.tei.yml for declarative TEI startup
87aa0af feat(scripts): rewrite tei-up.sh with preflight checks and real readiness probe
089dbfd feat(scripts): add TEI model prefetch with hf-mirror fallback
847a046 feat(settings): validate HTTP backend config and add fallback fields

(plus initial 7 commits from previous round: a7a3578..db61a93)
```

**已交付的工件**:
- `Makefile`(根目录,5 个 target)
- `scripts/dev/{tei-prefetch.py, tei-up.sh, tei-down.sh, tei-doctor.py, docker-compose.tei.yml}`
- `tests/integration/{conftest.py, test_tei_integration.py}`(7 个集成测试)
- `novel_analyzer/embedding/service.py`(HttpEmbeddingProvider 含批分片+连接复用+fallback)
- `novel_analyzer/rerank/service.py`(HttpRerankProvider 含批分片+连接复用)
- `novel_analyzer/config/settings.py`(HTTP 字段+验证)
- `docs/foundation-optimization/http-backend-guide.md`(已重写)
- `.env.example`(HTTP 字段示例)

**实测性能数据**:
- `tei-doctor` 16/16 通过
- 单次 embed P50=902ms / P95=1582ms(短文本)
- 集成测试 `7 passed in 104.40s`(含 batch chunking)
- **CPU 边界**:bge-m3 + batch 30 + avg 290 字中文 → 进程卡死(CPU 不够)
- bge-reranker-v2-m3 没有 ONNX 分片 → TEI 自动 fallback Candle+safetensors,加载慢约 40s

**9 个真实踩过的坑**(已在 plan §Context 中详列):
1. `ghcr.io` 拉镜像在国内卡死 → 需 daemon 级 HTTP_PROXY
2. 容器内网络 ≠ daemon 网络 → daemon proxy 不影响容器
3. `HF_HUB_OFFLINE=1` 不可靠 → TEI 仍尝试 HF 远程,2 分钟超时
4. `hf-mirror.com` 给容器用,缺 `content-range` 头报错
5. `snapshot_download(allow_patterns)` 漏 `*.bin` → bge-m3 只下了 38M 启动失败
6. 漏 `model.onnx_data` → TEI 加载 ONNX 时还是要远程下
7. bge-reranker-v2-m3 无 ONNX 分片 → 走 Candle+safetensors,启动慢
8. `sudo docker` 权限差异 → 用户环境不同
9. 长中文文本 + 较大 batch 在 CPU 上会卡死 / OOM(本次 benchmark 实测)

**决策回顾(从 priority-and-roi-research-20260512 文档继承)**:
- 不走商业 embedding API(数据主权 + 成本 + 中文能力)
- 不自研微调 embedding(数据不足 + 基座迭代快 + 评测集成本高)
- 走 "ONNX(本地默认) + HTTP/TEI(可选切换) + 可选 fallback" 的双后端策略

---

## Work Objectives

### Must Have

- 文档**真诚**:9 个坑必须每个都有"症状/原因/规避"
- 文档**可执行**:任何新手按文档能复现成功路径
- 文档**有数据**:性能数字、内存占用、加载时间都用真实测量
- 文档**有边界**:CPU TEI 不适合什么场景必须明说
- 索引可达:在 `docs/foundation-optimization/README.md` 有显眼链接

### Must NOT Have (Guardrails)

- 不写假设(没测过的不要写)
- 不替代已有 `http-backend-guide.md` — 这是 **复盘**,不是 guide
- 不在文档里贴大段日志(摘要+原始命令)
- 不替换或修改已有 commit
- 不改 `tei-doctor.py` 等代码工件 — 复盘只写文档

### Verification Strategy

- 文档创建后,Prometheus 不能直接写,委派 executor 搬运
- 索引项添加后人工 walkthrough 一次,确认链接正常
- 这是 docs-only 任务,无 lsp/test 验证

---

## TODOs

### Phase 1 — 复盘文档生成

- [ ] 1. **创建 `docs/foundation-optimization/tei-integration-postmortem-20260512.md`**

  **What to do**:

  文档结构(必须 7 个章节,顺序如下):

  ```
  # TEI 集成复盘 — 2026-05-12

  ## 0. 一句话结论
  [TEI 已成为项目一等后端,与本地 ONNX 并列。CPU 部署适合 dev/低并发场景,
  生产长文本高并发需 GPU 部署或继续走 ONNX。]

  ## 1. 起点与目标
  - 用户原始诉求(原话引用)
  - 启动时的现状(只有 ONNX,无 HTTP,无 TEI)
  - 真正的目标解读("不是单纯加 HTTP 接口,是让 TEI 成为一等公民")

  ## 2. 最终交付的能力(成果对照)
  - 表格列出 16 个交付项(Makefile, scripts, tests, providers, docs, env)
  - 每行: 工件 / 文件 / 一句话价值
  - 引用关键 commit hash

  ## 3. 关键技术决策
  - 决策 1: 双后端共存(ONNX 默认 + HTTP 可选)— 为什么
  - 决策 2: 不走商业 API — 数据/成本/中文 三因素表
  - 决策 3: 不自研微调 — 数据/基座/评测 三因素表
  - 决策 4: TEI 而非自建 inference server — 维护性 vs 灵活性
  - 决策 5: HTTP 走 urllib 不引入 httpx — 零新依赖
  - 决策 6: 仅 embedding 加 fallback,rerank 不加 — 语义边界
  - 决策 7: doctor 是 Python 不是 bash — 输出可结构化

  ## 4. 9 个真实踩过的坑(技术心跳)
  每个坑用相同模板:
  - **症状**: 现象描述
  - **根因**: 一两句技术解释
  - **规避**: 配置/脚本/文档怎么躲
  - **沉淀**: 项目里哪个文件/检查项防止重犯

  9 个坑(顺序参考 plan §Context):
  1. ghcr.io 国内拉镜像
  2. daemon proxy ≠ container network
  3. HF_HUB_OFFLINE 不完全生效
  4. hf-mirror content-range 头缺失
  5. allow_patterns 漏 *.bin
  6. allow_patterns 漏 model.onnx_data
  7. bge-reranker-v2-m3 无 ONNX → Candle 慢
  8. sudo docker 权限差异
  9. 长中文 + 大 batch CPU 卡死

  ## 5. 性能数据(实测)
  - 表格: 单次 embed / batch / rerank 的延迟数字
  - 来自 tei-doctor 和集成测试的真数据
  - 成本对比: TEI CPU vs ONNX 本地 vs 商业 API
  - 边界声明: CPU 不适合长文本+高并发

  ## 6. 全 lifecycle SOP
  - 新机器接入(`make tei-prefetch && make tei-up && make tei-doctor`)
  - 升级模型(改 .env + prefetch + restart)
  - 紧急回滚(把 backend 切回 onnx)
  - 健康监控(tei-doctor 定期跑)

  ## 7. 失败的尝试与放弃路径
  - 直连 huggingface.co(放弃,网络问题)
  - hf-mirror 直接给容器(放弃,content-range 问题)
  - HF_HUB_OFFLINE=1 离线模式(放弃,TEI 不可靠)
  - 完整 ONNX vs TEI 性能对比 benchmark(放弃,长文本 OOM,改用 doctor 数据)

  ## 8. 给未来的建议
  - GPU 部署评估(若需要长文本高并发)
  - 商业 API 切换的 trigger 条件(规模到什么程度才值得)
  - 模型升级路径(bge-m3 → Conan-v2 / Qwen3-Embedding)的 checklist
  - rerank fallback 何时考虑加上

  ## 附录 A: Lore commit 历史
  9 个 commits 一行总结

  ## 附录 B: 失败的 benchmark 复现命令
  让别人能在更强机器上重跑长文本 batch 测试

  ## 附录 C: 相关文档链接
  - http-backend-guide.md(操作手册)
  - priority-and-roi-research-20260512.md(决策依据)
  - architecture/risk-audit-embedding-pgvector-implementation-spec.md(整体规划)
  ```

  **写作约束**:
  - 第一人称视角"我们" / "项目"
  - 每个数字标注来源 ("tei-doctor 16 项检查实测" / "集成测试 7 passed in 104.40s")
  - 不夸张,不隐藏失败
  - Markdown 锚点保持稳定(`#9-个真实踩过的坑` 等),让 doctor 失败提示能引用

  **Must NOT do**:
  - 不写"展望未来 AI 写作的革命"这种空话
  - 不引入新承诺(比如承诺 GPU 部署一定做)
  - 不修改现有 9 个 commit
  - 不动代码

  **Acceptance Criteria**:
  - [ ] 文件存在于指定路径
  - [ ] 7 主章节 + 3 附录都齐全
  - [ ] 9 个坑各有完整模板填充
  - [ ] 性能数字都有来源标注

  **Commit**: YES — `docs(tei): write integration postmortem with 9 lessons learned`

### Phase 2 — README 索引更新

- [ ] 2. **更新 `docs/foundation-optimization/README.md` 的 "专题备忘录" 小节**

  **What to do**:
  - 在已有的两条记录(priority-and-roi-research, http-backend-guide)之后追加:
    ```
    | [tei-integration-postmortem-20260512.md](./tei-integration-postmortem-20260512.md) | TEI 集成复盘:9 个坑 / 决策回顾 / 性能边界 / SOP |
    ```
  - 不修改其他章节

  **Must NOT do**:
  - 不重排已有项

  **Acceptance Criteria**:
  - [ ] README 含新条目
  - [ ] 链接可点开

  **Commit**: 与 Phase 1 合一个 commit(同主题)

---

## Commit Strategy

**1 个 atomic commit**(Phase 1 + 2 合并),Lore 格式:

```
docs(tei): write integration postmortem with 9 lessons learned

Comprehensive retrospective of the TEI HTTP-backend integration:
gotchas, decisions, performance boundaries, lifecycle SOP. Written
after tei-doctor 16/16 green and 7 integration tests passing on
real TEI containers, so future contributors don't re-discover the
same proxy/network/cache pitfalls.

Constraint: CPU TEI cannot handle long Chinese (290+ chars) at batch 30 — documented
Constraint: hf-mirror.com cannot be used directly by TEI container due to content-range header gap
Rejected: full ONNX vs TEI performance benchmark | OOM on dev box with 14GB RAM, deferred to GPU box
Confidence: high
Scope-risk: narrow
Directive: Update §4 (9 gotchas) when adding new model or new TEI version
Tested: doctor 16/16 / integration 7/7 pass at time of writing
Not-tested: postmortem reflects state at HEAD; will need refresh as code evolves
```

---

## Success Criteria

- [ ] 复盘文档存在且 7 章 + 3 附录齐全
- [ ] 9 个坑模板填充完整
- [ ] README 索引更新
- [ ] 1 个 atomic commit Lore 格式
- [ ] 任何新同事读完此文档,能从 0 到 `make tei-doctor` 通过,且理解为什么有这些设计

---

## Notes for the Executor

1. 读源素材(已在 §Context 列全):本计划 + http-backend-guide.md + priority-and-roi-research 文档 + 9 个 commit 的 message
2. **不要复制粘贴本计划**,要重新组织成给读者(而非给 Prometheus)读的复盘
3. 性能数字必须**真实**,不能编造 — 实在没有的标注 "未测"
4. 9 个坑的"沉淀"字段要点出**项目里哪个具体文件/check 防止重犯**(让坑→工件双向可追溯)
5. 写完后过一遍:**有没有承诺没做的事?**有就改成 "建议" / "未来"
6. 写完报:文件路径 + 字数 + commit hash
