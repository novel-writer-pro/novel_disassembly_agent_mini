# Review Workflow 持久化策略说明

## 1. 当前策略

当前第二阶段 review workflow 采用：

1. **DB-backed review object / history 作为主路径**
2. **runtime file registry 作为兼容 fallback**

也就是说：

- 正常情况下优先读写数据库
- 只有在 review 表缺失或路径不可用时，才回退到 file fallback

---

## 2. 为什么保留 fallback

当前保留 fallback 的原因主要有三个：

1. 兼容早期原型阶段
2. 避免真实库未同步时直接完全不可用
3. 让测试 / 本地试验时有兜底路径

---

## 3. 当前建议

如果第二阶段继续深入，推荐目标是：

> **逐步把 DB 变成唯一正式持久化路径**

也就是说：

- file fallback 只保留短期兼容价值
- 长期不应作为正式主路径

---

## 4. 当前导出层如何告知使用者

当前 `branch_bundle` 顶层已经带有：

- `review_storage_mode`

取值：

- `db`
- `file-fallback`

这让接入方能明确知道：

> 当前 review 状态到底来自数据库，还是来自兼容 fallback。

---

## 5. 后续可选推进路线

### 路线 A：继续双轨一段时间

适合：

- 还在快速迭代
- 仍需兼容原型环境

缺点：

- 维护复杂度更高

### 路线 B：阶段性切到 DB-only

适合：

- review workflow 已进入正式化实施
- 数据结构已稳定

优点：

- 路径更清晰
- 后续 API / report / 统计更稳定

---

## 6. 当前推荐做法

短期：

- 保留 fallback
- 但所有正式接入与团队试用都优先走 DB

中期：

- 补齐 review history / object 的正式表说明
- 明确 fallback 何时移除

长期：

- 转为 DB-only

---

## 7. 一句话总结

> 当前 review workflow 已进入 DB 主路径阶段，file fallback 仅作为兼容兜底；  
> 后续正式化的方向应是逐步转向 DB-only。
