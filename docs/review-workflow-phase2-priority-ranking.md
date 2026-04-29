# Review Workflow 第二阶段实施优先级建议

## 1. 结论先行

如果第二阶段现在要真正开始排期，建议优先顺序是：

### P1

**review history / 审计链深化**

### P2

**checker 精度冲刺**

### P3

**review owner / 指派语义正式化**

---

## 2. 为什么这样排

## P1：review history / 审计链深化

### 原因

当前第二阶段已经有：

- DB-backed review object
- DB-backed review history
- CLI / API / bundle / report 已贯通

所以最自然、最值的一步不是再加入口，而是把“历史”做得更完整。

### 直接价值

1. 让 review workflow 更可追踪
2. 让问题处理更能审计
3. 让后续多角色协作有基础

### 适合做的内容

- 状态变更历史增强
- history 在 bundle/report 的进一步利用
- 更明确的 latest review / latest change 汇总

---

## P2：checker 精度冲刺

### 原因

当前第一阶段与第二阶段的骨架已经足够完整，真正影响实用性的，是：

- 误报率
- 证据排序质量
- 候选具体性

### 直接价值

1. 提高编辑/作者对系统结果的信任度
2. 降低 review workflow 噪音
3. 提升问题簇聚合质量

### 适合做的内容

- `character_ooc` 继续降噪
- `world_rule_consistency` 真源增强
- `plot / timeline / power` 继续提质

---

## P3：review owner / 指派语义正式化

### 原因

当前已经有：

- `review_owner`

但还没有：

- 任务指派流程
- owner 的正式规则
- 协作层语义

这条线价值高，但依赖前两条更扎实后再做更稳。

### 适合做的内容

- owner 约束
- owner 统计
- owner 过滤增强
- 指派/交接语义

---

## 3. 为什么不建议现在优先做别的

### 不建议优先做 UI

原因：

- 当前后端主线仍有更高价值的精度与审计链问题

### 不建议优先做 Reader Experience 实现

原因：

- Reader Experience 目前仍属于第二条能力线
- 当前主线是 review workflow 正式化

### 不建议优先扩更多新 checker

原因：

- 现在更缺的是质量和闭环，不是数量

---

## 4. 推荐的具体排期方式

### 近 1 个迭代

- review history / audit trail 深化

### 近 2–3 个迭代

- checker 精度冲刺

### 再往后

- owner / assignment 正式化

---

## 5. 一句话总结

> 第二阶段当前最优先做的不是扩功能面，而是先把 review history / 审计链打深，再提升 checker 精度，最后再把 owner / 指派语义做正式化。
