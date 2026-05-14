# 风险审查体系：下一阶段执行建议（30 / 60 / 90 天）

## 1. 目的

这份文档把“下一阶段 backlog”进一步收口为可执行节奏，帮助后续团队把风险审查体系从：

- 第一阶段可交付

推进到：

- 第二阶段可持续提质与可运营

---

## 2. 总体目标

下一阶段的核心目标不是继续铺功能面，而是：

1. 提升现有 checker 的判断质量
2. 建立 review workflow 闭环
3. 为 Reader Experience 预留稳定扩展接口

---

## 3. 30 天目标（P1：Checker 提质）

### 目标

在不改动大骨架的前提下，显著提升当前 5 个 checker 的可用性与误报抑制能力。

### 重点事项

#### A. 强化 `character_ooc`

- 建立更稳定的人物画像基线
- 区分动机漂移 / 关系漂移 / 能力漂移 / 语气漂移
- 减少“仅标题推断”导致的噪音

#### B. 强化 `world_rule_consistency`

- 增强规则真源抽取
- 区分规则例外与规则破坏
- 增加跨章节规则约束证据

#### C. 强化 `plot / timeline / power`

- plot：事件因果链闭合
- timeline：时间顺序 / 恢复时长 / 同日切换
- power：战力基线 / 跃迁阈值 / 越阶解释链

### 30 天完成标准

- checker 噪音较当前版本可控下降
- review candidate 解释性明显提升
- 不引入新的输出结构破坏

---

## 4. 60 天目标（P2：Review Workflow 闭环）

### 目标

让“问题簇”从只读结果变成可复核对象。

### 重点事项

#### A. 给 cluster 增加真实生命周期

- `open`
- `needs_review`
- `reviewed`
- `resolved`

#### B. 增加 review 元数据

- `review_owner`
- `review_notes`
- `resolved_by`
- `resolved_at`

#### C. 建立最小 review workflow

- 发现问题簇
- 指派复核
- 记录结论
- 标记 resolved / keep-open

### 60 天完成标准

- 问题簇从“报告字段”变成“可管理对象”
- 可形成最小 review 闭环

---

## 5. 90 天目标（P3：Reader Experience 预备落地）

### 目标

在不冲击当前风险审查主线的前提下，开始 Reader Experience 的第一批可落地能力。

### 第一批建议模块

#### A. 踩雷 / 内容预警标签

- 虐主
- 高压苦情
- 长时间压抑
- 重大误会

#### B. 高潮 / 转折章节定位

- 高潮章节
- 转折章节
- 冲突升级章节

#### C. 跳转阅读推荐

- 角色高光章
- 冲突线推荐章
- 关键设定补课章

### 90 天完成标准

- 至少 1 条 reader-facing 能力线可原型化验证
- 不破坏风险审查主线

---

## 6. 建议不要做的事情

在 90 天内，不建议优先做：

1. 大规模新增 checker 数量
2. 复杂主观“好不好看”评分
3. 结尾崩坏全自动强结论
4. 过早做复杂运营面板
5. 过早做大而全 agentOS 迁移

---

## 7. 推荐执行顺序

### 第 1 优先级

- 稳定 `character_ooc`
- 稳定 `world_rule_consistency`
- 强化 `plot / timeline / power`

### 第 2 优先级

- review workflow 闭环

### 第 3 优先级

- Reader Experience 第一批原型

---

## 8. 一句话建议

> 下一阶段最值的方向不是继续“加新名词”，而是先把现有 5 个 checker 做准、把问题簇做成可复核对象，再把 Reader Experience 作为第二条能力线逐步接上。
