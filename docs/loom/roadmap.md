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

Phase 3 🔄 进行中：Reward Model + 角色认知基 + 生产部署
  目标：评估自进化，角色一致性进一步提升，PostgreSQL 生产启用
  前提：积累 500+ pairwise 对比数据；Alembic migration 在生产 PG 上运行

Phase 4 🔄 进行中：文风 + 节奏 + 对话（5/10 → 7/10 商业可用）
  目标：文风量化校准、节奏/爽点分析、对话质量信号、角色认知基深化
  前提：Phase 3 A/B 实验验证通过
  当前：P1（style_calibration_service）✅ P2（rhythm_analysis_service）✅

Phase 5 🔲 规划中：读者模拟 + 多线调度 + 自适应编排（7/10 → 8.5/10 头部水准）
  目标：读者模拟评审、多线叙事调度、长书自适应编排、外部知识 RAG
  前提：Phase 4 风格/节奏/对话信号稳定运行
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
✅ 运行 A/B 实验工具：loom-ab-compare（character_ooc 触发率对比，目标下降 ≥ 20%）
□ 验收通过后切换到 enabled
□ 更新 carry-over-migration.md 记录实验结果
```

**P2：0509 对接**

```
✅ 0509 operator_surface 新增 Loom signal 聚合展示（writer operator surface 已暴露 `session_loom_signals`，包含 tension signal / chapter quality signal 汇总）
✅ 0509 session_primary_verdicts 已接入 chapter_quality_score 聚合（当前 writer control surface 已输出 `quality_verdict` / `average_chapter_quality_score` / `chapter_quality_signal_count`）
✅ 0509 retirement gate 已接入最小 Loom quality gate（当前 writer retirement readiness/preview 在 `quality_score < 0.7` 时标记 `quality-blocked`）
✅ Consumer Migration Telemetry：当前 writer control surfaces、execution resume、live/runtime readiness 与 external runtime simulation bridge 已输出 `session_consumer_migration_telemetry`，标明 primary-ready 与 legacy-remaining 消费方
```

**P3：Pairwise 数据积累 + Reward Model**

```
✅ 从 manual_eval_record 提取初始 pairwise 数据（loom-collect-pairs-from-manual，扫描 runs/manual_eval/ 工作区）
   - 跳过 _template 目录，pair_source=manual_eval_workspace
   - 8 个单元测试，全部通过
✅ 从 harness 迭代产物提取 pairwise 数据（同章节多版本）
✅ 实现 pairwise 数据收集 CLI 命令（loom-collect-pairs + loom-pairs-stats + loom-ab-compare + loom-collect-pairs-from-db）
   - loom-collect-pairs: 单目录（round-0 vs final）+ 跨目录（baseline vs steering）两种模式
   - loom-pairs-stats: 显示采集进度、质量分布、距 500 目标的剩余量
   - loom-ab-compare: A/B 实验报告，character_ooc 触发率对比
   - loom-collect-pairs-from-db: 跨两个 DB 分支提取 pairwise 对
   - 20 个单元测试，全部通过
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

## Phase 4 🔲：文风 + 节奏 + 对话（商业可用）

### 前提条件

1. Phase 3 A/B 实验验证通过（`character_ooc` 触发率下降 ≥ 20%）
2. `loom_memory_mode=enabled` 在生产环境稳定运行
3. pairwise reward model 已 fine-tune（Kendall's τ ≥ 0.5）

### 任务清单

**P1：风格向量化与漂移检测**

```
✅ 新增 style_calibration_service.py
   - compute_style_drift(branch_id, chapter_index) → StyleDriftResult（cosine 距离）
   - to_style_signal() 输出供 operator surface 消费
   - 阈值：warn ≥ 0.15，critical ≥ 0.30
✅ loom-status 展示 style_drift_score（loom_style_enabled=True 时）
□ preflight_imitation 接入 style_drift 检查（feature flag loom_style_enabled）
□ session_loom_signals 新增 style_signal 字段
□ 验收：style_drift_score 与人工风格评分 Pearson r ≥ 0.5
```

**P2：节奏分析器**

```
✅ 新增 rhythm_analysis_service.py
   - compute(branch_id, chapter_index) → RhythmSignal
   - hook_density: HOOK_FACT_TYPES 事件数 / 千字
   - pacing_type: slow_burn | action_heavy | balanced | episodic
   - climax_score: hook 事件占比
✅ loom-status 展示 rhythm_signal（loom_style_enabled=True 时）
□ tension 层：rhythm_signal 与 tension_signal 联动
□ preflight_imitation：节奏偏差警告
□ 验收：hook_density 与读者留存率正相关（需真实数据）
```

**P3：对话质量信号**

```
□ ChapterImitationHarnessReport 新增 dialogue_signal 字段
   - character_voice_consistency: dict[str, float]
   - dialogue_efficiency: float
   - conflict_dialogue_density: float
□ pairwise 评估新增第五个维度 dialogue_quality
□ reward 层：dialogue_signal 进入 chapter_quality_score 计算
□ 验收：dialogue_signal 与人工对话评分 Kendall's τ ≥ 0.4
```

**P4：角色认知基深化**

```
□ 新增 character_agent_service.py
   - build_character_persona(branch_id, character_name) → CharacterPersona
     （从 Loom memory 层切片 + graph_nodes 关系网络 + fact_records 行为模式）
   - check_character_consistency(persona, draft_text) → ConsistencySignal
□ preflight_imitation：角色认知基一致性检查（补充/替代现有 OOC checker）
□ 验收：character_ooc 触发率在 Phase 3 基础上再下降 ≥10%
```

### 验收标准

- [ ] style_drift_score 与人工风格评分 Pearson r ≥ 0.5
- [ ] hook_density 指标与读者留存率正相关（真实数据验证）
- [ ] dialogue_signal 与人工对话评分 Kendall's τ ≥ 0.4
- [ ] character_ooc 触发率累计下降 ≥ 30%（Phase 3 + Phase 4 合计）
- [ ] 综合仿写质量评分从 5/10 提升到 7/10

---

## Phase 5 🔲：读者模拟 + 多线调度 + 自适应编排（头部水准）

### 前提条件

1. Phase 4 风格/节奏/对话信号稳定运行
2. reward model 多维度版本（风格/张力/一致性/对话分离）已就绪
3. 积累足够的读者反馈数据（reader_feedback_comments）

### 任务清单

**P1：读者模拟评审面板**

```
□ 新增 reader_simulation_service.py
   - simulate_reader_panel(chapter_text, panel_type) → ReaderSimSignal
     panel_type: "casual" | "veteran" | "satisfaction" | "editor"
   - aggregate_reader_scores(signals) → ReaderSatisfactionScore
□ session_primary_verdicts 新增 reader_satisfaction_score
□ retirement gate：reader_satisfaction_score < 0.6 时标记 reader-blocked
□ operator surface：展示各 panel 的具体反馈
□ 验收：reader_satisfaction_score 与真实读者评分 Pearson r ≥ 0.6
```

**P2：多线叙事调度器**

```
□ 新增 thread_scheduler_service.py
   - analyze_thread_status(branch_id) → ThreadStatusReport
     （active / dormant / overdue 三类线索分类）
   - suggest_thread_activation(branch_id, chapter_index) → ThreadActivationSignal
□ preflight_imitation：线索调度建议
□ tension 层：overdue_threads 触发 obstacle injection
□ 验收：overdue_threads 比例下降 ≥ 30%
```

**P3：长书自适应编排**

```
□ 自动检测质量下滑信号（chapter_quality_score 连续 3 章下降）
□ 触发 carry_over 重组（Working Memory 强制压缩 + Semantic Memory 重建）
□ 自动建议 steering pack 更新
□ loom-status 展示 long_book_health_score
□ operator surface：长书健康度仪表盘
□ 验收：100 章仿写的 chapter_quality_score 标准差 < 0.15
```

**P4：外部知识 RAG 接入**

```
□ 读者预期 pack（从读者评论/书评提炼，新增）
□ 题材 trope 库自动检索（复用 steering_library_service）
□ 世界观 dossier 自动检索（复用 worldview_capsule）
□ constraint_pack：外部知识作为软约束
□ steering_pack：自动从 RAG 库检索相关 steering
□ 验收：使用外部 RAG 的章节，reader_satisfaction_score 提升 ≥ 10%
```

### 验收标准

- [ ] reader_satisfaction_score 与真实读者评分 Pearson r ≥ 0.6
- [ ] overdue_threads 比例下降 ≥ 30%
- [ ] 100 章仿写质量标准差 < 0.15
- [ ] 综合仿写质量评分从 7/10 提升到 8.5/10

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
| Phase 4 风格向量与现有 embedding 不兼容 | 🟡 中 | 待验证 | 优先复用 ChunkEmbedding，不新建 embedding 调用 |
| Phase 5 读者模拟评审成本过高 | 🟡 中 | 待评估 | 先用 LLM-as-judge 模拟，积累数据后 fine-tune |

---

返回 [Loom 入口](./README.md) | [架构差异分析](./arch-diff-and-alignment.md) | [差距分析与演进](./gap-analysis-and-evolution.md)
