# Review Workflow 第二阶段 Team 并行实施规范

## 1. 目的

这份文档用于说明：

1. 第二阶段 review workflow 实施时，哪些工作适合并行
2. 哪些文件不适合多个 worker 同时修改
3. 如何降低合流冲突与噪音
4. 如何给 worker 分配更清晰的写域

---

## 2. 这份规范为什么需要

真实 `omx team` 执行已经证明：

- worker 可以并行推进第二阶段实现
- 但如果多个 lane 同时修改：
  - `apps/api/app/main.py`
  - `novel_analyzer/services/export_service.py`
  - `novel_analyzer/services/cluster_review_service.py`
  - `tests/test_api_main.py`
  这类高热点文件，合流冲突风险会明显上升

另外，`.pyc` 二进制文件也会放大 shutdown 报告噪音。

因此：

> 第二阶段不是不能并行，而是需要更明确的 team 写域治理。

---

## 3. 当前建议的并行 lane

### Lane A：实现主线

职责：

- `review object / history`
- `summary API`
- `bundle/report` 核心逻辑

建议写域：

- `novel_analyzer/services/cluster_review_service.py`
- `novel_analyzer/runtime/cluster_review_state.py`
- `novel_analyzer/services/export_service.py`
- `novel_analyzer/reporting/branch_report.py`

### Lane B：接口主线

职责：

- `apps/api/app/main.py`
- review API surface
- request / response / filter / summary 接口

建议写域：

- `apps/api/app/main.py`
- `docs/review-workflow-api.md`
- `docs/api-contract.md`
- `docs/interface-manifest.md`

### Lane C：验证主线

职责：

- pytest
- 本地 API E2E
- branch bundle / report fresh evidence

建议写域：

- `tests/test_api_main.py`
- `tests/test_export_risk_card.py`
- `tests/test_export_report.py`
- `tests/test_risk_audit_service.py`

### Lane D：文档主线

职责：

- phase2 设计稿
- 样例
- README/docs 索引

建议写域：

- `docs/examples/*`
- `docs/review-workflow-*.md`
- `README.md`
- `docs/README.md`

---

## 4. 哪些文件不建议多个 worker 同时改

高冲突文件：

1. `apps/api/app/main.py`
2. `novel_analyzer/services/export_service.py`
3. `novel_analyzer/services/cluster_review_service.py`
4. `tests/test_api_main.py`
5. `README.md`
6. `docs/README.md`

规则：

- 同一轮 team 执行中，尽量只指定 **一个 lane** 拥有这些文件的主写权

---

## 5. 哪些文件适合并行改

相对低冲突区域：

- 新增 `docs/examples/*.json`
- 新增 `docs/review-workflow-*.md`
- 独立测试文件
- 新增小型 runtime/service 文件

这些区域更适合并行推进。

---

## 6. .pyc 噪音处理建议

当前真实 team shutdown 报告中，`.pyc` 二进制冲突会造成大量噪音。

建议：

1. team worker 不要提交 `__pycache__`
2. shutdown 前优先清理 worker worktree 中的 `.pyc`
3. 如有必要，把 `.pyc` 冲突明确视为噪音，而不是业务逻辑冲突

---

## 7. 推荐 team 使用方式

### 适合 team 的场景

- review history / 审计链
- API surface
- 测试与验证
- 文档与样例

### 不适合 team 的场景

- 多个 worker 同改同一个核心服务文件
- 小改动却强行 4 lane 并行

---

## 8. 最推荐的 team 分工模式

### 3 worker 模式（更稳）

- worker-1：实现主线
- worker-2：验证主线
- worker-3：文档/样例主线

### 4 worker 模式（更快）

- worker-1：review history / service
- worker-2：API / summary
- worker-3：测试 / E2E
- worker-4：文档 / 样例

前提：

- 必须明确高冲突文件的单 lane 主写权

---

## 9. 一句话总结

> 第二阶段可以并行推进，但必须把高冲突文件的主写权分清；  
> 推荐采用“实现 / 接口 / 验证 / 文档”分 lane 的 team 模式，而不是多个 worker 同时改同一核心文件。
