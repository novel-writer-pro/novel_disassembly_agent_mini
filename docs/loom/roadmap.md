# Loom 开发路线图 / Roadmap

---

## 总览

```
Phase 1 ✅ 已完成（2026-05-09）：分层记忆基础设施
  目标：解决长书记忆退化问题，对接 0509 carry_over_state
  结果：4 个新服务 + 23 个单元测试，全部通过

Phase 2 ✅ 已完成（2026-05-09）：张力自动调节 + Pairwise 评估
  目标：情节质量可量化，评估维度可进化
  结果：feature flags + 3 个 CLI 命令 + 15 个集成测试，全部通过

Phase 3 🔲 待开始：Reward Model + 角色认知基 + 生产部署
  目标：评估自进化，角色一致性进一步提升，PostgreSQL 生产启用
  前提：积累 500+ pairwise 对比数据；Alembic migration 在生产 PG 上运行
```

---

## Phase 1 ✅：分层记忆基础设施

### 完成状态

**Week 1：DB 扩展 + 基础服务**

```
✅ Alembic migration：fact_records 加 importance_score / decay_factor / episodic_status
   → alembic/versions/20260509_01_loom_memory_fields.py
✅ Alembic migration：graph_nodes 加 conflict_status / loom_version / superseded_by_node_id / importance_score
✅ Alembic migration：graph_edges 加 conflict_status / loom_version / is_active
✅ 新增 memory_consolidation_service.py（冲突检测 + 代谢）
✅ 新增 memory_assembler_service.py（三层记忆组装器）
✅ 单元测试：conflict_metabolism（contradiction/evolution/ambiguity 分类）
```

**Week 2：集成 + Shadow 模式**

```
✅ analysis_service.py：章节分析完成后调用 memory_consolidation_service（feature flag）
✅ imitation_harness_service.py：_build_carry_over_json 支持 shadow/enabled/ab 模式
✅ 验证 _legacy_compat 字段与现有 carry_over_state 格式 100% 兼容
```

**Week 3：CLI + 验收**

```
✅ CLI 命令：loom-status / loom-consolidate / loom-assemble
✅ Settings：5 个 Loom feature flags（默认 shadow 模式）
✅ 集成测试：15 个测试覆盖 settings / analysis hook / harness / CLI
```

### 验收标准（已验证）

- ✅ 所有新增字段有默认值，现有数据不受影响
- ✅ feature flag 关闭时，现有链路完全不受影响（`loom_memory_mode=disabled`）
- ✅ 0509 session_state 无需修改即可消费新的 carry_over_state（`_legacy_compat` 字段）
- 🔲 Working Memory 始终 ≤ 2000 tokens（需真实 20 章对比实验验证）
- 🔲 `character_ooc` 触发率下降 ≥ 20%（需真实对比实验）

### 接口约定（已实现）

```json
{
  "loom_version": "1.0",
  "assembled_at_chapter": 42,
  "working_memory": {"active_characters": [...], "active_threads": [...], "recent_summary": "..."},
  "episodic_anchors": [{"label": "...", "effective_score": 0.85, ...}],
  "semantic_snapshot": {"character_count": 12, "active_rules": [...], "key_relationships": [...]},
  "_legacy_compat": {
    "characters": [...],
    "rules": [...],
    "unresolved_threads": [...],
    "previous_chapter_summary": "..."
  }
}
```

---

## Phase 2 ✅：张力自动调节 + Pairwise 评估

### 完成状态

**Week 4：张力指标**

```
✅ 新增 tension_service.py（三个指标计算，零 LLM 调用）
   - plot_similarity_score：pgvector cosine 相似度（fallback: Jaccard keyword）
   - conflict_density：冲突边密度（GraphEdge 统计）
   - surprise_index：新颖度指数（FactRecord 新标签比例）
✅ preflight_imitation：新增 loom_tension 检查（feature flag loom_tension_enabled）
✅ 单元测试：4 个张力指标测试
✅ 接口约定：tension_signal JSON 格式（to_operator_signal()）
```

**Week 5：Pairwise 评估**

```
✅ 新增 pairwise_eval_service.py（LLM-as-judge + heuristic fallback）
✅ 四个评估维度：character_consistency / plot_coherence / style_fidelity / narrative_tension
✅ 输出 chapter_quality_score（0-1 浮点数）
✅ 接口约定：to_chapter_quality_signal() 供 0509 session_primary_verdicts 消费
```

**Week 6：0509 对接**

```
✅ imitation_harness preflight_draft：loom_tension check 接入
✅ _build_carry_over_json：shadow/enabled/ab 三种模式
✅ CLI：loom-status 展示张力指标
🔲 0509 operator_surface：tension_signal 字段展示（待 0509 侧接入）
🔲 0509 session_primary_verdicts：chapter_quality_score 聚合（待 0509 侧接入）
```

### 验收标准（已验证）

- ✅ 三个张力指标计算时间 < 1 秒（纯 SQL 查询）
- ✅ feature flag 关闭时，现有 preflight 逻辑完全不受影响
- ✅ LLM-as-judge heuristic fallback 在无 LLM 环境下正常工作
- 🔲 LLM-as-judge 与人工判断 Kendall's τ ≥ 0.4（需积累真实评估数据）
- 🔲 张力信号接入 0509 operator_surface（待 0509 侧实现）

---

## Phase 3 🔲：Reward Model + 生产部署

### 前提条件

1. **Alembic migration 在 PostgreSQL 生产环境运行**
   ```bash
   poetry run novel-analyzer db-upgrade
   # 或直接：
   alembic upgrade head
   ```
   migration 文件：`alembic/versions/20260509_01_loom_memory_fields.py`

2. **积累 500+ pairwise 对比数据**（从 harness 迭代产物 + manual_eval_record 提取）

3. **A/B 实验验证**：同一本书 20 章，旧路径 vs Loom enabled 路径，确认 `character_ooc` 触发率下降 ≥ 20%

### 任务清单

**P1：生产部署**

```
□ 在 PostgreSQL 生产环境运行 Alembic migration 20260509_01
□ 将 NOVEL_ANALYZER_LOOM_MEMORY_MODE 从 shadow 切换到 ab（50/50 分流）
□ 运行 A/B 实验：20 章对比，记录 character_ooc 触发率
□ 验收通过后切换到 enabled
□ 更新 carry-over-migration.md 记录实验结果
```

**P2：0509 对接**

```
✅ 0509 operator_surface 新增 Loom signal 聚合展示（writer operator surface 已暴露 `session_loom_signals`，包含 tension signal / chapter quality signal 汇总）
✅ 0509 session_primary_verdicts 已接入 chapter_quality_score 聚合（当前 writer control surface 已输出 `quality_verdict` / `average_chapter_quality_score` / `chapter_quality_signal_count`）
🔲 0509 retirement gate 接入 Loom quality gate（quality_score < 0.7 时阻止 retirement）
🔲 Consumer Migration Telemetry：记录哪些消费者已迁到 primary
```

**P3：Pairwise 数据积累 + Reward Model**

```
□ 从 manual_eval_record 提取初始 pairwise 数据（目标 50+ pairs）
□ 从 harness 迭代产物提取 pairwise 数据（同章节多版本）
□ 实现 pairwise 数据收集 CLI 命令（loom-collect-pairs）
□ 积累 500+ pairs 后：fine-tune reward model（Qwen-7B）
□ 验收：Kendall's τ ≥ 0.5（参考 EvolvR 的 0.55）
```

**P4：角色认知基（进阶）**

```
□ 每个主要角色独立的 memory + 决策逻辑（参考 BookWorld 2025）
□ 角色 agent 自主认知基（Deep Persona Alignment）
□ story-time-aware knowledge graph（参考 Living the Novel 2025）
```

### 验收标准

- [ ] PostgreSQL 生产环境 migration 运行成功，无数据丢失
- [ ] A/B 实验：`character_ooc` 触发率下降 ≥ 20%
- [ ] `loom_memory_mode=enabled` 下，carry_over_state 体积不随章节数线性增长
- [ ] pairwise reward model Kendall's τ ≥ 0.5
- [ ] 0509 operator_surface 正确展示 tension_signal

---

## 风险登记（当前状态）

| 风险 | 严重度 | 当前状态 | 缓解措施 |
|------|--------|---------|---------|
| PostgreSQL migration 未运行 | 🔴 高 | **待处理** | 运行 `alembic upgrade head` 后再切换到 enabled 模式 |
| carry_over_state 格式不兼容 | 🟢 低 | 已解决 | `_legacy_compat` 字段保持 100% 兼容，已测试 |
| 两套 verdict 语义混淆 | 🟢 低 | 已解决 | 命名严格区分：`chapter_quality_score` vs `session_primary_verdicts` |
| tension_signal 被误当作 action | 🟢 低 | 已解决 | 文档明确：tension_signal 是建议，不是指令 |
| DB 状态与 JSON 文件不一致 | 🟢 低 | 已解决 | SSOT 明确：章节记忆 → DB，session 运营 → JSON |
| pairwise 数据不足 | 🟡 中 | 待积累 | Phase 3 P3 任务 |

---

返回 [Loom 入口](./README.md) | [架构差异分析](./arch-diff-and-alignment.md)
