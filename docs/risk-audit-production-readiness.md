# 风险审查正式生产收尾与外部条件清单

这份文档回答两个问题：

1. 当前统一风险审查体系离“正式稳定生产”还差什么
2. 哪些缺口属于代码问题，哪些属于外部运行条件问题

---

## 1. 当前判断

当前风险审查体系已经完成：

- 第一阶段 checker 主链
- semantic middle layer
- risk card / review summary / report 导出链
- review workflow 最小交付链

因此当前状态更准确地说是：

> **已具备内部试运行 / 人审辅助生产能力，但正式稳定生产仍取决于外部条件闭环。**

---

## 2. 正式稳定生产的最低外部条件

以下条件缺一不可。

### A. PostgreSQL 真环境可连通

最低要求：

- PostgreSQL 实例实际运行
- `127.0.0.1:5432` 可连接
- 目标账号/密码可用
- 目标数据库存在或可自动创建

建议验收：

```bash
set -a
source .env.local
set +a
.venv/bin/python scripts/check_postgres.py
```

如果结果中出现：

- `can_connect=false`
- `database_exists=false`

则当前不能称为正式生产。

### B. `pgvector` 与必要扩展已安装

最低要求：

- `vector`
- `pg_trgm`

建议验收目标：

- `missing_extensions=` 为空
- `ok=true`

### C. 风险审查 schema 已完成真库初始化

最低要求：

- 已执行 `init-db`
- 风险审查相关表已建好
- 从空库重建到可运行有固定步骤

建议命令：

```bash
set -a
source .env.local
set +a
.venv/bin/python -m novel_analyzer.cli.app init-db
.venv/bin/python -m novel_analyzer.cli.app db-capabilities
```

### D. Python 运行壳层可重复

最低要求：

- `.venv` 可用
- `pytest` 可用
- `alembic` 可用
- CLI / API 启动命令固定

如果只能在某个临时 shell 中偶然跑通，而无法稳定重现，也不能称为正式生产。

### E. LLM provider 长链稳定

当前推荐配置：

- provider: `vip1129`
- model: `gpt-5.4-mini`

正式生产最低要求：

- 长章节分析不会频繁 `provider_connection`
- 超时率、503、连接中断处于可接受水平
- 自动重试后整体成功率可接受
- 失败分类可见

如果 provider 层持续抖动，那么内容链即使代码无误，也只能算“能力具备但外部条件未闭环”。

### F. ONNX embedding 资源稳定

当前推荐：

- backend: `onnx`
- model: `BAAI/bge-m3`
- 本地导出目录：例如 `/home/user/huggingface/bge-m3-onnx-int8`

最低要求：

- 模型目录真实存在
- tokenizer / onnx 文件完整
- `test-embedding` 可稳定通过

建议命令：

```bash
set -a
source .env.local
set +a
.venv/bin/python -m novel_analyzer.cli.app test-embedding
```

### G. 全链路验收至少通过一次

建议至少完成一次完整验收：

1. DB capability OK
2. embedding smoke OK
3. 一段章节分析成功
4. risk card 成功生成
5. branch bundle / report 可导出
6. review workflow 查询可读

---

## 3. 当前已确认的真实阻塞

截至 **2026-05-02**，当前会话内已确认：

1. `127.0.0.1:5432` 当前 **connection refused**
2. 因数据库未连通，`postgres_capability_report(...)` 返回：
   - `database_exists=false`
   - `can_connect=false`
   - `initialized_schema=false`
   - `missing_extensions=['pg_trgm', 'vector']`
3. 因此当前会话下：
   - 无法完成 pgvector 真环境验收
   - 无法在真库上直接重跑示例小说前 10 章风险链

这意味着：

> 当前主要阻塞已经不是风险审查主链代码骨架，而是 **数据库真环境未闭环**。

---

## 4. 当前可以如何定义“可生产”

建议分三档：

### 研发验证

满足：

- 代码主链存在
- 测试可跑
- 样例结果可复查

### 内部试运行

满足：

- 可以对真实小说做辅助审查
- 能产出风险卡 / 报告 / 审计链
- 结果用于人工复核

### 正式稳定生产

必须额外满足：

- PostgreSQL + pgvector 真环境 OK
- provider 长链稳定
- embedding 真环境稳定
- 空库初始化 / 重跑 / 回归路径固定

---

## 5. 当前推荐的收尾验收顺序

1. 启动 PostgreSQL，并确认 `5432` 可连
2. 执行 `init-db`
3. 执行 `scripts/check_postgres.py`
4. 执行 `test-embedding`
5. 对示例小说重新做一段小范围真环境复跑（建议前 10 章）
6. 导出 branch report / chapter bundle / review history
7. 再进行整体验收结论签收

---

## 6. 一句话结论

> 当前风险审查体系已经接近正式生产；真正剩余的收尾重点是 **PostgreSQL/pgvector 真环境、provider 长链稳定性、以及可重复运行壳层** 的闭环证明。
