# Review Workflow DB-only 切换策略

## 1. 目的

当前 review workflow 已经进入：

- **DB-backed review object / history 为主路径**
- `file-fallback` 为兼容兜底路径

这份文档用于说明：

1. 什么时候可以考虑切到 DB-only
2. 切换前应该满足哪些条件
3. 切换时应如何验证

---

## 2. 当前结论

当前推荐策略不是立即移除 fallback，而是：

> **先保持 DB 主路径 + fallback 兼容，待满足条件后再切 DB-only。**

---

## 3. 进入 DB-only 的建议条件

建议至少满足以下条件：

### A. 结构条件

1. `cluster_review_records` 已在目标数据库存在（迁移 `20260429_01` / `20260430_01`）
2. `cluster_review_event_records` 已在目标数据库存在（迁移 `20260429_01` / `20260430_01`）
3. history 事件包含上一版 `review_result` / `review_notes` / `review_owner` / `resolved_at`，便于审计链追溯
4. 导出层已稳定读取 DB review object / history

### B. 接口条件

1. CLI：
   - `set-cluster-status`
   - `show-cluster-status`
   - `show-cluster-history`
   已稳定走 DB 主路径

2. API：
   - `GET /api/review-clusters`
   - `GET /api/review-cluster-history`
   - `POST /api/review-cluster-update`
   已稳定走 DB 主路径

### C. 回归条件

1. review workflow 相关 targeted regression 稳定通过
2. bundle / report 导出稳定通过
3. 真实本地 API E2E 已至少验证一轮

### D. 运行态条件

1. `review_storage_mode` 在主使用环境下稳定显示为 `db`
2. fallback 不再承接主要读写流量

---

## 4. 切换前建议检查项

### 必查

- review 表是否存在
- API 是否可读可写
- history 是否可读
- report 是否能显示最新 review 元数据
- `review_storage_mode` 是否为 `db`

### 建议

- 保留一次 fallback 验证记录
- 确认团队已知晓切换后 fallback 将不再是主路径

---

## 5. 切换方式建议

### 方式 A：软切换

1. 继续保留 fallback 代码
2. 但在正式环境只接受 `db`
3. fallback 仅保留给测试/紧急排障

优点：

- 风险最低

### 方式 B：硬切换

1. 导出层不再 fallback
2. CLI / API 不再 fallback
3. 缺表即报错

优点：

- 路径更纯粹

缺点：

- 对环境一致性要求更高

### 当前建议

> 先做 **方式 A：软切换**，再考虑方式 B。

---

## 6. 切换验证建议

切换后至少验证：

1. `branch_bundle.review_storage_mode == db`
2. `review-cluster-update` 成功写入
3. `review-cluster-history` 返回 history
4. `branch_report` 中可见：
   - owner
   - result
   - latest review
   - review progress

---

## 7. 切换后的 fallback 策略

切换成 DB-only 后，建议：

- fallback 代码先不立刻删除
- 但明确标记为：
  - 兼容层
  - 测试/排障专用
  - 非正式主路径

这样可以降低回退风险。

---

## 8. 一句话总结

> 当前 review workflow 最合理的推进方式是：  
> 先确认 DB 主路径稳定、回归稳定、API 稳定，再做“软切换到 DB-only”，最后才考虑彻底移除 fallback。
