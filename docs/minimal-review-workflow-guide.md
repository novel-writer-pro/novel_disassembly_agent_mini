# 最小 Review Workflow 使用说明

## 1. 目的

这份文档说明当前最小 review workflow 原型如何使用。

目标不是提供完整工单系统，而是让团队能先做：

1. 查看问题簇
2. 手工写回状态
3. 在交付报告里看到人工复核结果

---

## 2. 当前支持什么

当前最小 review workflow 已支持：

- 问题簇状态：`cluster_status`
- 复核备注：`review_notes`
- 复核人：`review_owner`
- 解决时间：`resolved_at`
- 复核结果：`review_result`
- 审查结论中的复核进度提示：`review_progress_note`

当前推荐的 `review_result` 取值：

- `confirmed-issue`
- `confirmed-benign`
- `needs-escalation`
- `deferred`

当前导出/报告层会把它们映射为更易读的中文标签，例如：

- `confirmed-issue` → `确认有问题`
- `confirmed-benign` → `确认无问题`
- `needs-escalation` → `需要升级处理`
- `deferred` → `暂缓判断`

额外约束：

- 如果 `cluster_status=resolved`
- 则必须同时提供非空 `review_result`
- 如果 `review_result=needs-escalation`
- 则必须同时提供非空 `review_notes`

这些信息可以通过运行时 registry 写回，再在 `branch_bundle` / `branch_report` 中显示。

---

## 3. 当前使用方式

### 第一步：导出 branch report / bundle

先正常导出当前分支的审查结果：

```bash
./.venv/bin/python -m novel_analyzer.cli.app export-branch-bundle <run_id> <branch_id> /tmp/branch.json --database-url <db-url>
./.venv/bin/python -m novel_analyzer.cli.app export-branch-report <run_id> <branch_id> /tmp/branch.md --database-url <db-url>
```

在导出物里找到：

- `review_candidate_clusters`
- `cluster_key`

---

### 第二步：写回 cluster 状态

使用 CLI：

```bash
./.venv/bin/python -m novel_analyzer.cli.app set-cluster-status <branch_id> <cluster_key> resolved \
  --review-notes "已人工确认该问题无需升级" \
  --review-owner "editor-a" \
  --resolved-at "2026-04-29T02:00:00Z" \
  --review-result "confirmed-benign"
```

当前常见状态可用值：

- `open`
- `needs_review`
- `resolved`

---

### 第三步：查看当前已写回状态

```bash
./.venv/bin/python -m novel_analyzer.cli.app show-cluster-status <branch_id>
```

如果要查看单个问题簇的状态变更历史：

```bash
./.venv/bin/python -m novel_analyzer.cli.app show-cluster-history <branch_id> <cluster_key>
```

---

### 第四步：重新导出 branch report / bundle

重新导出后，报告和 bundle 会显示人工写回信息：

- `cluster_status`
- `review_notes`
- `review_owner`
- `resolved_at`
- `review_result`
- `review_progress_note`

---

## 4. 当前状态语义

### `open`

- 当前有问题簇
- 但紧急程度较低

### `needs_review`

- 当前问题簇建议优先进入人工复核

### `resolved`

- 当前问题簇已经被人工标记为已处理

注意：

> 当前 `resolved` 只是最小原型层的人工写回状态，  
> 还不是完整 workflow 的持久化审计闭环。

---

## 5. 当前报告里能看到什么

在 `branch_report` 的 `### Review Candidate Clusters` 区段里，当前可直接看到：

- `status`
- `priority`
- `title`
- `checkers`
- `types`
- `chapters`
- `sample`
- `action`
- `owner`
- `resolved_at`
- `result`
- `notes`

并且在 `## Audit Conclusion` 区段里，当前还可以看到：

- `Review Progress`

---

## 6. 当前限制

当前最小 review workflow 仍有以下限制：

1. 状态写回走运行时 registry，不是数据库正式表
2. 没有真正的 reviewer 审计链
3. 没有 UI 入口
4. 没有并发协作保护
5. 没有“reviewed / rejected / escalated”细分状态

---

## 7. 适用场景

当前原型适合：

- 小团队内部试用
- 编辑手工复核记录
- 阶段性问题状态回写
- 演示“从问题发现到人工处理”的最小闭环

不适合：

- 大规模协作编辑系统
- 严格审计留痕场景
- 多角色并发 review 管理

---

## 8. 一句话总结

> 当前最小 review workflow 原型已经可以让团队手工写回问题簇状态，并在正式交付报告中直接看到结果；  
> 它适合作为第二阶段 review 闭环的起点，但还不是完整工作流系统。

---

## 9. 一个最小 E2E 示例

下面是一条真实可复现的最小闭环示例：

### 步骤 1：先导出 branch bundle，拿到 `cluster_key`

```bash
./.venv/bin/python -m novel_analyzer.cli.app export-branch-bundle <run_id> <branch_id> /tmp/branch.json --database-url <db-url>
```

从 `review_candidate_clusters` 中拿到：

- `cluster_key`

例如：

- `character_ooc|::|human_review_candidate`

### 步骤 2：写回状态

```bash
./.venv/bin/python -m novel_analyzer.cli.app set-cluster-status <branch_id> <cluster_key> resolved \
  --review-notes "已人工确认该问题无需升级" \
  --review-owner "editor-a" \
  --resolved-at "2026-04-29T02:00:00Z"
```

### 步骤 3：重新导出 branch report

```bash
./.venv/bin/python -m novel_analyzer.cli.app export-branch-report <run_id> <branch_id> /tmp/branch.md --database-url <db-url>
```

这时报告中会直接出现：

- `status=resolved`
- `owner: editor-a`
- `resolved_at: 2026-04-29T02:00:00Z`
- `notes: 已人工确认该问题无需升级`

### 步骤 4：恢复默认演示态（如需要）

```bash
./.venv/bin/python -m novel_analyzer.cli.app set-cluster-status <branch_id> <cluster_key> needs_review
```

> 当前真实样例 branch 已经验证过这条最小闭环路径可行。
