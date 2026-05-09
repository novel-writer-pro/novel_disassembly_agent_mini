# Loom 开发路线图 / Roadmap

---

## 总览

```
Phase 1（2-3周）：分层记忆基础设施
  目标：解决长书记忆退化问题，对接 0509 carry_over_state
  风险：低（只加字段，不改现有逻辑）

Phase 2（2-3周）：张力自动调节 + Pairwise 评估
  目标：情节质量可量化，评估维度可进化
  风险：低（纯计算，不改生成链路）

Phase 3（后续）：Reward Model + 角色认知基
  目标：评估自进化，角色一致性进一步提升
  风险：中（需要训练数据积累）
```

---

## Phase 1：分层记忆基础设施

### 目标

- 三层记忆结构（Working/Episodic/Semantic）落地
- 冲突代谢机制运行
- carry_over_state 质量提升，0509 session_state 无感消费

### 任务清单

**Week 1：DB 扩展 + 基础服务**

```
□ Alembic migration：fact_records 加 importance_score / decay_factor / episodic_status
□ Alembic migration：graph_nodes 加 conflict_status / version / superseded_by_node_id / importance_score
□ Alembic migration：graph_edges 加 conflict_status / version / is_active
□ 新增 memory_consolidation_service.py（冲突检测 + 代谢）
□ 新增 memory_assembler_service.py（三层记忆组装器）
□ 单元测试：conflict_metabolism（contradiction/evolution/ambiguity 分类）
```

**Week 2：集成 + Shadow 模式**

```
□ analysis_service.py：章节分析完成后调用 memory_consolidation_service（feature flag）
□ chapter_imitation_service.py：支持 LOOM_MEMORY_MODE=shadow（并行运行，不使用）
□ 对比实验：同一本书 20 章，旧路径 vs shadow 路径，记录差异
□ 验证 _legacy_compat 字段与现有 carry_over_state 格式 100% 兼容
```

**Week 3：A/B 测试 + 验收**

```
□ chapter_imitation_service.py：支持 LOOM_MEMORY_MODE=ab（50/50 分流）
□ 对比指标：character_ooc 触发率、人工一致性评分
□ 验收：新路径 character_ooc 触发率 < 旧路径 × 80%
□ 文档更新：carry-over-migration.md 记录实验结果
```

### 接口约定（Phase 1 开始前必须确认）

```json
// carry_over_state 标准格式（Loom memory 输出，0509 消费）
{
  "loom_version": "1.0",
  "assembled_at_chapter": 42,
  "working_memory": {...},
  "episodic_anchors": [...],
  "semantic_snapshot": {...},
  "_legacy_compat": {
    "characters": [...],
    "relationships": [...],
    "rules": [...],
    "unresolved_threads": [...]
  }
}
```

### 验收标准

- [ ] Working Memory 始终 ≤ 2000 tokens（不随章节数增长）
- [ ] `character_ooc` 触发率下降 ≥ 20%（同一本书对比实验）
- [ ] 所有新增字段有默认值，现有数据不受影响
- [ ] feature flag 关闭时，现有链路完全不受影响
- [ ] 0509 session_state 无需修改即可消费新的 carry_over_state

---

## Phase 2：张力自动调节 + Pairwise 评估

### 目标

- 三个张力指标（plot_similarity / conflict_density / surprise_index）可计算
- Pairwise 评估框架运行，chapter_quality_score 输出给 0509
- 0509 operator_surface 展示张力信号

### 任务清单

**Week 4：张力指标**

```
□ 新增 tension_service.py（三个指标计算）
□ SQL 优化：plot_similarity 用 pgvector 原生操作
□ preflight_imitation：新增张力检查（feature flag）
□ 单元测试：三个指标在已知"平淡"章节上的表现
□ 接口约定：tension_signal JSON 格式
```

**Week 5：Pairwise 评估**

```
□ 新增 pairwise_eval_service.py（LLM-as-judge）
□ 从现有 manual_eval_record 提取初始 pairwise 数据（50+ pairs）
□ 从 harness 迭代产物提取 pairwise 数据
□ chapter_imitation_service.py：harness 决策接入 pairwise 评估（feature flag）
□ 接口约定：chapter_quality_score JSON 格式
```

**Week 6：0509 对接 + 验收**

```
□ 0509 operator_surface：新增 tension_signal 字段展示
□ 0509 session_primary_verdicts：新增 chapter_quality_score 聚合逻辑
□ 对比实验：有/无张力调节的 10 章仿写，人工评分对比
□ 验收：LLM-as-judge 与人工判断 Kendall's τ ≥ 0.4
```

### 接口约定（Phase 2 开始前必须确认）

```json
// tension_signal（Loom tension 输出，0509 展示）
{
  "chapter_index": 42,
  "tension_score": 0.45,
  "status": "warning",
  "alerts": [...],
  "metrics": {
    "plot_similarity": 0.87,
    "conflict_density": 0.6,
    "surprise_index": 0.15
  }
}

// chapter_quality_score（Loom reward 输出，0509 聚合）
{
  "chapter_index": 42,
  "quality_score": 0.78,
  "confidence": 0.82,
  "dimensions": {...}
}
```

### 验收标准

- [ ] 三个张力指标计算时间 < 1 秒（无 LLM 调用）
- [ ] LLM-as-judge 与人工判断 Kendall's τ ≥ 0.4
- [ ] 张力信号正确展示在 0509 operator_surface
- [ ] chapter_quality_score 正确聚合到 0509 session_primary_verdicts

---

## Phase 3：Reward Model + 角色认知基（后续）

### 触发条件

- Phase 2 稳定运行 1 个月
- 积累 500+ 高质量 pairwise 对比数据

### 方向

```
□ Fine-tune reward model（Qwen-7B，本地部署）
□ 0509 Automated Retirement Gate 接入 Loom quality gate
□ 0509 Consumer Migration Telemetry 接入 Loom eval_data_collection
□ 角色认知基（每个主要角色独立的 memory + 决策逻辑）
□ 多维度 reward model（风格/张力/一致性分离）
```

---

## 风险登记

| 风险 | 严重度 | 缓解措施 | 负责人 |
|------|--------|---------|--------|
| carry_over_state 格式不兼容 | 🔴 高 | Phase 1 开始前确认 schema，加版本号 | Phase 1 负责人 |
| pgvector 查询性能不足 | 🟡 中 | 先用 SQL 实现，必要时加索引 | Phase 2 负责人 |
| LLM-as-judge 结果漂移 | 🟡 中 | 固定 prompt 版本，记录每次评估的 model_name | Phase 2 负责人 |
| 0509 对接延迟 | 🟡 中 | 接口约定先行，Loom 和 0509 并行开发 | 双方负责人 |
| 训练数据不足（Phase 3） | 🟢 低 | Phase 2 开始积累，不急于 Phase 3 | Phase 3 负责人 |

---

## 开发原则

1. **接口先行**：每个 Phase 开始前，先确认与 0509 的接口格式，再分别实现
2. **feature flag 控制**：所有 Loom 功能都通过 feature flag 控制，任何时候可回滚
3. **不破坏现有链路**：Loom 是叠加层，不修改现有服务的核心逻辑
4. **可量化验收**：每个 Phase 都有明确的量化验收标准，不靠主观感受判断
5. **渐进式迁移**：shadow → A/B → 全量，不一步到位

---

返回 [Loom 入口](./README.md) | [架构差异分析](./arch-diff-and-alignment.md)
