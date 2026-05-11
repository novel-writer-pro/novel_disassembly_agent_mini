# 分层记忆设计 / Layered Memory Design

---

## 1. 问题陈述

### 当前 carry_over_state 的问题

```python
# 当前实现（伪代码）
carry_over_state = {
    "characters": [...],          # 追加，不去重，不排序
    "relationships": [...],       # 追加，冲突不消解
    "rules": [...],               # 追加，矛盾不检测
    "unresolved_threads": [...],  # 追加，已解决的不清理
    "previous_summary": "..."     # 全量，不压缩
}
# 第 50 章时，这个 JSON 可能有 10000+ tokens
# 模型处理效率下降，冲突信息干扰生成
```

### 目标

```python
# Loom memory 层输出（伪代码）
carry_over_state = {
    "working_memory": {           # 当前章节最相关的 ~2000 tokens
        "active_characters": [...],
        "active_threads": [...],
        "recent_events": [...]
    },
    "episodic_anchors": [...],    # 重要事件锚点，按 importance_score 排序，最多 20 条
    "semantic_snapshot": {        # 从 PostgreSQL 实时查询，不存在 JSON 里
        "character_states": [...],
        "active_rules": [...],
        "relationship_map": [...]
    }
}
# 无论第几章，Working Memory 始终 ~2000 tokens
```

---

## 2. 三层记忆定义

### 2.1 Working Memory（工作记忆）

**职责**：给当前章节生成提供最直接的上下文，控制在 ~2000 tokens。

**内容**：
- 当前活跃角色（本章出现概率 > 0.5 的角色）
- 当前活跃线程（未解决且最近 5 章内有更新的线程）
- 最近 3 章的事件摘要（压缩版）
- 当前章节目标和约束

**现有 DB 映射**：
- `window_artifacts`（最近窗口摘要，直接复用）
- `chapter_artifacts[chapter_index-1].payload_json.state_summary`（上章状态）

**更新时机**：每章生成前，由 `memory_assembler` 动态组装，不持久化（每次重新生成）。

---

### 2.2 Episodic Memory（情节记忆）

**职责**：保存重要事件的有序序列，按重要性排序，支持"最近发生了什么重要的事"的查询。

**内容**：
- 关键事件（角色死亡、关系转折、规则建立/打破、伏笔埋设/兑现）
- 每个事件有 `importance_score`、`chapter_index`、`decay_factor`

**现有 DB 映射**：扩展 `fact_records` 表，新增字段：

```sql
-- 在现有 fact_records 表新增（Alembic migration）
ALTER TABLE fact_records ADD COLUMN importance_score FLOAT DEFAULT 0.5;
ALTER TABLE fact_records ADD COLUMN decay_factor FLOAT DEFAULT 1.0;
ALTER TABLE fact_records ADD COLUMN episodic_status VARCHAR(32) DEFAULT 'active';
-- episodic_status: active | decayed | superseded
```

**更新时机**：每章分析完成后，`memory_consolidation_service` 运行：
1. 新章节的 facts 按重要性打分（用现有 `confidence` 字段 + 新的 `importance_score`）
2. 旧 facts 的 `decay_factor` 按时间衰减（每章 × 0.95，重要事件衰减更慢）
3. 被新事件"覆盖"的旧事件标记为 `superseded`

---

### 2.3 Semantic Memory（语义记忆）

**职责**：持久化知识图谱，支持跨章节的角色/关系/规则查询，是最稳定的记忆层。

**内容**：
- 角色节点（`node_type=character`）及其当前状态
- 关系边（`edge_type=relationship`）及其演进历史
- 规则节点（`node_type=rule`）及其有效范围
- 世界观节点（`node_type=world_element`）

**现有 DB 映射**：扩展 `graph_nodes` 和 `graph_edges` 表，新增字段：

```sql
-- 在现有 graph_nodes 表新增
ALTER TABLE graph_nodes ADD COLUMN conflict_status VARCHAR(32) DEFAULT 'clean';
-- conflict_status: clean | contradiction | evolution | ambiguity | resolved
ALTER TABLE graph_nodes ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE graph_nodes ADD COLUMN superseded_by_node_id VARCHAR(36) NULL;
ALTER TABLE graph_nodes ADD COLUMN importance_score FLOAT DEFAULT 0.5;

-- 在现有 graph_edges 表新增
ALTER TABLE graph_edges ADD COLUMN conflict_status VARCHAR(32) DEFAULT 'clean';
ALTER TABLE graph_edges ADD COLUMN version INTEGER DEFAULT 1;
ALTER TABLE graph_edges ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
```

**更新时机**：每章分析完成后，`memory_consolidation_service` 运行冲突检测（见 conflict-metabolism.md）。

---

## 3. 动态组装器接口

### 3.1 `MemoryAssembler` 服务

```python
# novel_analyzer/services/memory_assembler_service.py（新增）

class MemoryAssemblerService:
    """
    从三层记忆动态组装 carry_over_state。
    输出格式与现有 carry_over_state 兼容，内容质量更高。
    """

    def assemble(
        self,
        branch_id: str,
        target_chapter_index: int,
        budget_tokens: int = 2000,
    ) -> dict:
        """
        返回标准 carry_over_state dict，可直接被 0509 session_state 消费。

        组装逻辑：
        1. 从 Semantic Memory 查询活跃角色/关系/规则（PostgreSQL）
        2. 从 Episodic Memory 查询重要事件（按 importance_score 排序，取 top-K）
        3. 从 Working Memory 查询最近窗口摘要（window_artifacts）
        4. 按 budget_tokens 裁剪，优先保留高 importance_score 内容
        """
        ...

    def get_active_characters(self, branch_id: str, chapter_index: int) -> list[dict]:
        """从 graph_nodes 查询 conflict_status != 'contradiction' 的活跃角色"""
        ...

    def get_important_events(
        self, branch_id: str, chapter_index: int, top_k: int = 20
    ) -> list[dict]:
        """从 fact_records 查询 importance_score 最高的 top_k 事件"""
        ...

    def get_active_rules(self, branch_id: str) -> list[dict]:
        """从 graph_nodes 查询 node_type=rule 且 is_active=True 的规则"""
        ...
```

### 3.2 输出格式（与现有 carry_over_state 兼容）

```json
{
  "loom_version": "1.0",
  "assembled_at_chapter": 42,
  "working_memory": {
    "active_characters": [
      {"name": "张三", "current_state": "...", "importance_score": 0.9}
    ],
    "active_threads": [
      {"thread_id": "...", "description": "...", "last_seen_chapter": 40}
    ],
    "recent_summary": "第40-41章：..."
  },
  "episodic_anchors": [
    {"event": "...", "chapter": 15, "importance_score": 0.95, "decay_factor": 0.8}
  ],
  "semantic_snapshot": {
    "character_count": 12,
    "active_rules": ["规则A", "规则B"],
    "key_relationships": [...]
  },
  "_legacy_compat": {
    "characters": [...],
    "relationships": [...],
    "rules": [...],
    "unresolved_threads": [...]
  }
}
```

> `_legacy_compat` 字段保持与现有 carry_over_state 格式完全兼容，
> 0509 session_state 可以继续读取旧字段，也可以逐步迁移到新字段。

---

## 4. DB 扩展方案（Alembic Migration）

### 需要新增的字段

```python
# alembic/versions/xxxx_loom_memory_fields.py

def upgrade():
    # fact_records 扩展
    op.add_column('fact_records', sa.Column('importance_score', sa.Float(), default=0.5))
    op.add_column('fact_records', sa.Column('decay_factor', sa.Float(), default=1.0))
    op.add_column('fact_records', sa.Column('episodic_status', sa.String(32), default='active'))

    # graph_nodes 扩展
    op.add_column('graph_nodes', sa.Column('conflict_status', sa.String(32), default='clean'))
    op.add_column('graph_nodes', sa.Column('version', sa.Integer(), default=1))
    op.add_column('graph_nodes', sa.Column('superseded_by_node_id', sa.String(36), nullable=True))
    op.add_column('graph_nodes', sa.Column('importance_score', sa.Float(), default=0.5))

    # graph_edges 扩展
    op.add_column('graph_edges', sa.Column('conflict_status', sa.String(32), default='clean'))
    op.add_column('graph_edges', sa.Column('version', sa.Integer(), default=1))
    op.add_column('graph_edges', sa.Column('is_active', sa.Boolean(), default=True))
```

### 不需要新建的表

所有扩展都在现有表上加字段，**不新建表**，**不破坏现有查询**。

---

## 5. 与现有服务的关系

| 现有服务 | 关系 | 变更 |
|---------|------|------|
| `graph_service.py` | Semantic Memory 的写入方 | 新增写入 `conflict_status`/`version` 字段 |
| `fact_service.py` | Episodic Memory 的写入方 | 新增写入 `importance_score`/`decay_factor` 字段 |
| `chapter_imitation_service.py` | carry_over_state 的消费方 | 可选：切换到 `MemoryAssemblerService` 输出 |
| `whole_book_imitation_service.py` | carry_over_state 的消费方 | 可选：切换到 `MemoryAssemblerService` 输出 |
| `risk_semantic_signal_service.py` | 冲突检测的信号来源 | 不变，冲突代谢读取其输出 |

---

## 6. 验收标准

- [ ] `MemoryAssemblerService.assemble()` 输出的 `_legacy_compat` 字段与现有 carry_over_state 格式 100% 兼容
- [ ] 连续 20 章仿写，Working Memory 始终 ≤ 2000 tokens（不随章节数增长）
- [ ] `character_ooc` checker 触发率相比旧链路下降 ≥ 20%（同一本书对比实验）
- [ ] 所有新增字段有默认值，不影响现有数据

---

返回 [Memory 层入口](./README.md) | [冲突代谢](./conflict-metabolism.md)
