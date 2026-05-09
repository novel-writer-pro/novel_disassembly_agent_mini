# carry_over_state 迁移方案 / Carry-Over Migration

---

## 1. 迁移原则

> **渐进式迁移，不破坏现有链路。**
> 现有 `carry_over_state` 继续工作，Loom 作为可选的新组装路径，
> 通过 feature flag 控制，任何时候都可以回滚。

---

## 2. 现有 carry_over_state 的结构

```json
{
  "characters": [
    {"name": "张三", "status": "...", "motivation": "..."}
  ],
  "relationships": [
    {"from": "张三", "to": "李四", "type": "敌对", "notes": "..."}
  ],
  "rules": ["规则A", "规则B"],
  "unresolved_threads": ["线索1", "线索2"],
  "previous_chapter_summary": "第N章：...",
  "carry_over_inputs": {...}
}
```

**问题**：
- 所有字段都是追加的，没有重要性排序
- 没有冲突标记，矛盾信息混在一起
- 随章节数线性增长，第 50 章可能超过 8000 tokens

---

## 3. 迁移路径（三阶段）

### 阶段 0：现状（不变）

```
chapter_imitation_service
    → 直接读取 chapter_artifacts 拼装 carry_over_state
    → 传给 draft_writer
```

### 阶段 1：并行运行（feature flag = loom_memory_shadow）

```
chapter_imitation_service
    → 旧路径：直接拼装 carry_over_state（继续使用）
    → 新路径（shadow）：MemoryAssemblerService.assemble() 同时运行，结果记录但不使用
    → 对比两个结果，验证新路径的输出质量
```

**目的**：在不影响生产的情况下，验证 Loom memory 层的输出是否更好。

### 阶段 2：A/B 测试（feature flag = loom_memory_ab）

```
chapter_imitation_service
    → 50% 请求：使用旧路径
    → 50% 请求：使用 MemoryAssemblerService 输出
    → 对比 character_ooc 触发率、人工评分
```

**验收条件**：新路径的 `character_ooc` 触发率 < 旧路径 × 80%，且人工评分不下降。

### 阶段 3：全量切换（feature flag = loom_memory_enabled）

```
chapter_imitation_service
    → 全量使用 MemoryAssemblerService 输出
    → 旧拼装逻辑保留但不调用（保留 30 天后删除）
```

---

## 4. 与 0509 session_state 的兼容

### 关键约定

0509 的 `session_state` 通过 `carry_over_inputs` 字段消费 carry_over_state：

```json
// writer-imitate-session-state.json 中
{
  "carry_over_inputs": {
    // 这里的内容由 chapter_imitation_service 提供
    // Loom 迁移后，这里的内容由 MemoryAssemblerService 提供
    // 格式不变，内容质量更好
  }
}
```

**Loom 的承诺**：
- `_legacy_compat` 字段保持与现有格式 100% 兼容
- 0509 session_state 无需任何修改即可消费 Loom 输出
- 新字段（`working_memory`、`episodic_anchors`、`semantic_snapshot`）是可选的增量

---

## 5. 回滚方案

```python
# 任何时候都可以通过 feature flag 回滚

# settings.py
LOOM_MEMORY_MODE = os.getenv("LOOM_MEMORY_MODE", "disabled")
# disabled: 完全使用旧路径
# shadow: 新路径并行运行但不使用
# ab: A/B 测试
# enabled: 全量使用新路径

# chapter_imitation_service.py
if settings.LOOM_MEMORY_MODE == "enabled":
    carry_over = memory_assembler.assemble(branch_id, chapter_index)
else:
    carry_over = self._legacy_assemble(branch_id, chapter_index)
```

---

## 6. 数据迁移

### 现有数据不需要迁移

- 现有 `graph_nodes`、`fact_records` 继续存在
- 新增字段（`importance_score`、`conflict_status` 等）有默认值
- `memory_consolidation_service` 只处理新章节，不回填历史数据

### 历史数据的处理

如果需要对历史章节也启用 Loom memory：
```bash
# 可选的历史数据回填命令（后续实现）
poetry run novel-analyzer loom-backfill <branch_id> --from-chapter 1 --to-chapter 50
```

---

返回 [Memory 层入口](./README.md) | [三层记忆设计](./layered-memory-design.md)
