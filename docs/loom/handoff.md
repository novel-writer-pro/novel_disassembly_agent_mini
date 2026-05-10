# Loom 开发交接文档 / Handoff

> 最后更新: 2026-05-09
>
> 本文件供下次打开项目时**不重新理解上下文**，直接按步骤继续开发。
>
> ⚠️ 本文件不包含任何敏感凭据（API key、SK、密码等）。环境变量配置见 `.env.local`（已 gitignore）。

---

## 1. 当前架构定位

Loom 是 novel-analyzer 的 **跨章节仿写记忆与质量基础设施**，叠加在现有系统之上，不替换任何已有组件。

### 核心能力

| 层 | 能力 | 状态 |
|---|------|------|
| **memory/** | 三层记忆（Working/Episodic/Semantic）+ 冲突代谢 | ✅ Phase 1+2 完成 |
| **tension/** | 叙事张力指标（plot_similarity / conflict_density / surprise_index） | ✅ Phase 1+2 完成 |
| **reward/** | 学习型 pairwise 评估 | 🔲 Phase 3 规划 |

### 与 0509 控制层的关系

```
0509 session_state  →  carry_over_state 的 "运行时容器"（不变）
Loom memory 层      →  carry_over_state 的 "组装器"（新增）
```

两者不冲突。详见 [`docs/loom/arch-diff-and-alignment.md`](./arch-diff-and-alignment.md)。

### 架构全景

参见 [`docs/loom/overview.md`](./overview.md)（含完整 mermaid 架构图 + SOTA 对比表）。

---

## 2. 当前工作状态

### 2.1 已完成的提交历史

| Commit | 描述 |
|--------|------|
| `edf1237` | feat(loom): Loom Phase 1+2 代码与测试（38 tests） |
| `9a793a4` | docs+migration: 文档体系 + Alembic migration + roadmap/manual/checklist |
| `0131636` | fix(loom): CLI 命令注册顺序（loom-status/loom-consolidate/loom-assemble） |
| `bee4d89` | ops: DeepSeek + PostgreSQL 端到端验证通过 |
| `54a7fbd` | fix(loom): node/edge type 查询对齐真实生产数据 |

### 2.2 核心文件清单

#### 服务层（3 个核心服务）

| 文件 | 职责 | 最后修改 |
|------|------|---------|
| `novel_analyzer/services/tension_service.py` | 张力指标计算（plot_similarity / conflict_density / surprise_index） | 已对齐真实 edge/node 类型 |
| `novel_analyzer/services/memory_assembler_service.py` | 三层记忆组装（Working/Episodic/Semantic）→ carry_over_state | 已对齐 `entity/world_rule` |
| `novel_analyzer/services/memory_consolidation_service.py` | 冲突代谢 + 重要性衰减 + 分类（evolution/contradiction/ambiguity） | 已修复 `is_active` bug + CONFLICT_EDGE_TYPES |

#### CLI 入口

| 文件 | 职责 |
|------|------|
| `novel_analyzer/cli/app.py` | Loom CLI 命令注册（loom-status / loom-consolidate / loom-assemble）+ writer operator surface Loom signal 聚合 |

#### 数据模型

| 文件 | 职责 |
|------|------|
| `novel_analyzer/database/models.py` | GraphNode / GraphEdge / FactRecord Loom 字段（conflict_status, loom_version, superseded_by_node_id, decay_factor, episodic_status） |
| `alembic/versions/20260509_01_loom_memory_fields.py` | 生产 migration（已在 PG 成功执行） |

#### 测试

| 文件 | 数量 | 状态 |
|------|------|------|
| `tests/test_loom_phase1.py` | 23 tests | ✅ 全部通过 |
| `tests/test_loom_phase2.py` | 15 tests | ✅ 全部通过 |

#### 文档

| 文档 | 说明 |
|------|------|
| `docs/loom/overview.md` | 架构全景 + SOTA 对比 |
| `docs/loom/roadmap.md` | Phase 状态与后续任务 |
| `docs/loom/arch-diff-and-alignment.md` | Loom vs 0509 对比 |
| `docs/loom/memory/carry-over-migration.md` | 迁移路径与实验记录 |
| `docs/loom/tension/README.md` | 张力指标设计 |
| `docs/loom/reward/README.md` | Reward 模型规划 |
| `docs/cli-operations-manual.md` | CLI 手册（第 12 节 Loom） |
| `docs/real-run-checklist.md` | 试跑清单（第 8 节 Loom） |
| `CHANGELOG.md` | 变更记录 |

### 2.3 生产环境真实数据（PostgreSQL）

#### 真实 Edge Types

| edge_type | 数量 | 说明 |
|-----------|------|------|
| `carries_forward` | 85,301 | 事件/实体延续 |
| `participates_in` | 7,201 | 实体参与事件 |
| `contextualizes` | 6,304 | 上下文关联 |
| `hints_at` | 4,833 | 伏笔提示 |
| `advances_to` | 4,011 | 事件推进 |
| `pays_off_as` | 3,900 | 伏笔兑现 |
| `conflict_centers_on` | 3,456 | 冲突核心 |
| `co_occurs` | 3,287 | 共现关系 |
| `persists_into` | 1,954 | 持续关系 |
| `constrains` | 1,273 | 约束关系 |
| `follows` | 856 | 时间跟随 |
| `evolves_to` | 351 | 演进关系 |
| `escalates_to` | 213 | 升级关系 |
| `relates_to` | 206 | 关联关系 |
| `conflict_involves` | 108 | 冲突涉及 |
| `pressured_by` | 108 | 冲突压力 |

#### 真实 Node Types

| node_type | 数量 | 说明 |
|-----------|------|------|
| `event` | 920 | 事件节点 |
| `continuity` | 725 | 连续性节点 |
| `entity` | 548 | 实体（角色等） |
| `world_rule` | 144 | 世界规则 |
| `relation` | 81 | 关系节点 |
| `foreshadow` | 63 | 伏笔节点 |
| `conflict` | 49 | 冲突节点 |

**关键结论**：
- `graph_service` 不产出 `"character"` 类型的 node — 角色是 `entity`
- `graph_service` 不产出 `"rule"` 类型的 node — 世界规则是 `world_rule`
- `graph_service` 不产出 `"relationship"` 类型的 edge — 关系是 `relates_to`
- GraphNode **没有** `is_active` 列（该列仅存在于 GraphEdge）

### 2.4 已验证的端到端链路

```
Ingest → DeepSeek analyze → fact_records + graph_nodes + graph_edges
  → Consolidation triggered (loom_consolidation_complete event)
    → loom-status shows tension metrics
      → loom-assemble outputs carry_over_state with episodic decay
```

#### 关键运行标识

| 项目 | ID |
|------|----|
| 大分支（115章） | `72da24e9-e65c-45a9-836d-957c4ae783ec` |
| fresh 分支 | `62e636f0-c901-4167-aa1c-aff3da9c83ef` |
| 实测 run | `da1ca7d4-28ab-434b-bdbb-489f703e1f1d` |
| 实测 branch | `bd9c6d9d-4f83-4989-b092-001c74be7281` |
| 测试小说（3章） | `loom-test-deepseek` |

---

## 3. 关键架构决策记录

### 决策 1：Loom 非侵入式叠加
- **原则**：不替换任何现有组件，仅在现有 `carry_over_state` / FactRecord / GraphNode / GraphEdge 之上叠加 Loom 字段
- **理由**：现有 0509 链路已生产运行，Loom 故障不应阻塞主链路
- **实现**：`loom_memory_mode=shadow`（记录事件但不阻塞）

### 决策 2：无 `is_active` 在 GraphNode
- **问题**：`_mark_evolution` 尝试设置 `old_node.is_active = False`，但 GraphNode 模型无此列
- **解决**：移除该赋值。GraphNode 通过 `superseded_by_node_id` 追踪演进历史
- **教训**：`is_active` 仅存在于 GraphEdge；GraphNode 用 `conflict_status` + `superseded_by_node_id` 替代

### 决策 3：node_type 实际值对齐
- **问题**：服务代码假设 node_type 为 `"character"`/`"rule"`，但实际 graph_service 产出 `"entity"`/`"world_rule"`
- **解决**：使用 `in_(["entity", "character"])` 保持前向兼容
- **教训**：未来新增 node_type 时需同步更新 `CONFLICT_EDGE_TYPES` 和 `in_()` 列表

### 决策 4：CLI 命令注册顺序
- **问题**：`@app.command()` 定义在 `if __name__ == "__main__": app()` 之后，导致命令不可见
- **解决**：将 Loom 命令移至 `app()` 调用之前
- **教训**：`typer` 的 `@app.command()` 必须在 `app()` 前执行

---

## 4. 剩余工作与下一步

### 4.0 最近新增交付（2026-05-10）

- `writer-imitate-session-state.json` / `writer-imitate-operator-surface.json` 新增 `session_loom_signals` 聚合段。
- 当前聚合源来自 `writer-imitate-ch*.json` 章节产物，已汇总 tension signal 与可选 chapter quality signal。
- operator surface markdown 也新增 `Loom Signals` 小节，便于 operator 直接查看章节级 tension/quality 摘要。
- 第一轮交付先补稳定消费合同；随后已把 `chapter_quality_score` 聚合接入 `session_primary_verdicts`，当前 control surface 可直接输出 `quality_verdict` / `average_chapter_quality_score` / `chapter_quality_signal_count`。

### 4.1 当前未完成的 Phase 3 规划

参见 [`docs/loom/roadmap.md`](./roadmap.md) 完整清单。

| 优先级 | 任务 | 说明 | 前置条件 |
|--------|------|------|---------|
| 🔴 P0 | A/B 实验：Loom on vs off | 用 20 章数据对比 character_ooc 下降指标 | 需积累足够人工评估数据 |
| 🟡 P0 | 0509 operator_surface 深化对接 | 当前 writer operator surface 已聚合展示 `session_loom_signals`，且 `session_primary_verdicts` 已吸收 quality 聚合；下一步是让更多 0509 消费者直接依赖该稳定合同 | 需 Loom 稳定运行 |
| 🟡 P1 | Pairwise 数据积累 | 产出足够多的 LLM-as-judge 评估对 | 需生产运行积累 |
| 🟡 P1 | 角色认知基（Phase 3） | 角色级 agent 自主认知基 | 需 A/B 实验验证通过 |
| 🟢 P2 | Fine-tuned reward model | 替代 LLM-as-judge | 需 pairwise 数据量充足 |

### 4.2 下次继续开发时的标准启动步骤

```bash
# 1. 激活环境
source .venv/bin/activate

# 2. 验证数据库连通
pg_isready -h 127.0.0.1 -p 5432 -U d2

# 3. 验证 LLM 连通（DeepSeek / vLLM 或其他 provider）
#    注意：API key 在 .env.local 中，不在文档里
# python3 -c "import httpx; r=httpx.post('${NOVEL_ANALYZER_LLM_BASE_URL}/chat/completions', ...)"

# 4. 运行 migration（如有新变更）
alembic upgrade head

# 5. 运行 Loom 测试
python3 -m pytest tests/test_loom_phase1.py tests/test_loom_phase2.py -v

# 6. 验证 CLI 命令
python3 -m novel_analyzer --help  # 确认 loom-status / loom-consolidate / loom-assemble 可见

# 7. 真实分支验证
python3 -m novel_analyzer loom-status --branch-id <branch-id>
```

### 4.3 需关注的风险点

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| node_type 新增 | graph_service 新增 node_type 时 Loom 查询可能遗漏 | 注册时同步更新所有 `in_()` 列表 |
| metadata_json 结构变化 | graph_service 输出 metadata 格式变化 → 冲突分类逻辑失效 | 由 consolidation_service 的 `_classify()` 统一处理 |
| 性能 | 115 章分支已产生 85K edges，查询延迟可能升高 | 当前查询有 `branch_id` 索引，必要时加 composite index |
| 新 provider 切换 | 切换 LLM provider 后 embedding 维度/质量变化 | `_plot_similarity()` 有 keyword fallback |

---

## 5. 文档索引（快速跳转）

### 架构与设计
- [`docs/loom/overview.md`](./overview.md) — 架构全景 + SOTA 对比 + 资产盘点
- [`docs/loom/arch-diff-and-alignment.md`](./arch-diff-and-alignment.md) — Loom vs 0509 对比
- [`docs/loom/roadmap.md`](./roadmap.md) — Phase 计划与任务清单
- [`docs/loom/tension/README.md`](./tension/README.md) — 张力指标设计文档
- [`docs/loom/reward/README.md`](./reward/README.md) — Reward 模型规划

### 记忆层
- [`docs/loom/memory/carry-over-migration.md`](./memory/carry-over-migration.md) — 三阶段迁移路径

### 操作与验证
- [`docs/cli-operations-manual.md`](../cli-operations-manual.md) — CLI 手册（第 12 节 Loom）
- [`docs/real-run-checklist.md`](../real-run-checklist.md) — 试跑清单（第 8 节 Loom）

### 变更记录
- [`CHANGELOG.md`](../../CHANGELOG.md) — 完整变更历史

### 主文档入口
- [`docs/README.md`](../README.md) — 按角色分流入口

---

## 6. 代码诊断速查

### CMD
- 测试 Loom Phase 1+2: `python3 -m pytest tests/test_loom_phase1.py tests/test_loom_phase2.py -v`
- 全部测试: `python3 -m pytest tests/ -v`
- Migration: `alembic upgrade head`
- Loom CLI: `python3 -m novel_analyzer loom-status --branch-id <id>`
- Loom Consolidate: `python3 -m novel_analyzer loom-consolidate --branch-id <id>`
- Loom Assemble: `python3 -m novel_analyzer loom-assemble --branch-id <id>`
- DB direct: `PGPASSWORD=*** psql -h 127.0.0.1 -p 5432 -U d2 -d novel_analyzer -c "SELECT..."`

### 变量速查
- 环境配置位置: `.env.local`（已 gitignore）
- PG host/port/user/db: 见 `.env.local` 或 history
- Alembic: `alembic/versions/20260509_01_loom_memory_fields.py`
