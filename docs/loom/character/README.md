# Character 层入口 / 角色认知基

> Character 层解决的核心问题：**角色状态是 snapshot，不是持续演化的认知基**。
> 现有 OOC checker 是规则检测，不能感知角色的内在动机、价值观演变和说话风格。

---

## 与 0509 控制层的关系

```
0509 operator_surface（展示角色一致性信号，不变）
        ↑
        │ 接收 character_consistency_signal（新信号）
        │
Loom character 层（角色认知基构建 + 一致性检测，新增）
        │ 从 Loom memory 层切片该角色的 episodic_anchors
        │ 从 graph_nodes 提取该角色的关系网络
        ↓
FactRecord（行为模式）+ GraphNode（关系网络）+ EpisodicMemory（关键事件）
```

Character 层是 OOC checker 的**深化补充**，不是替换。
OOC checker 检测"是否违规"，Character 层检测"是否符合角色认知基"。

---

## 核心概念：CharacterPersona

```json
{
  "character_id": "张三",
  "branch_id": "...",
  "built_at_chapter": 42,
  "persona": {
    "values": ["忠义", "家族优先", "不信任外人"],
    "goals": ["保护家族", "积累修为", "复仇"],
    "fears": ["失去家人", "被背叛"],
    "speech_style": {
      "formality": 0.7,
      "verbosity": 0.4,
      "emotional_intensity": 0.6,
      "style_vector": [...]
    }
  },
  "episodic_anchors": [
    {"chapter": 5, "event": "第一次背叛经历", "impact": "high"},
    {"chapter": 18, "event": "家族危机", "impact": "critical"}
  ],
  "relationship_network": {
    "李四": {"type": "ally", "trust_level": 0.8},
    "王五": {"type": "rival", "trust_level": 0.2}
  },
  "consistency_score": 0.85
}
```

---

## 与 Loom 其他层的关系

```
Character 层 → Memory 层：
  - CharacterPersona 从 Loom memory 层的 episodic_anchors 切片构建
  - 角色关键事件自动进入 episodic_anchors（高 importance_score）

Character 层 → Style 层：
  - speech_style.style_vector 与 Style 层的 character_voice_consistency 共享
  - 角色说话风格向量存入 CharacterPersona，供 Style 层对比

Character 层 → Reward 层：
  - character_consistency_signal 作为 pairwise 评估 character_consistency 维度的增强
  - CharacterPersona 的 consistency_score 进入 chapter_quality_score 计算
```

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [character-persona-design.md](./character-persona-design.md) | CharacterPersona 构建与一致性检测设计 |

---

## 接入点

| 接入层 | 接入方式 | feature flag |
|--------|---------|-------------|
| `preflight_imitation` | 角色认知基一致性检查（补充 OOC checker） | `loom_character_enabled` |
| `loom-status` | 展示主要角色的 consistency_score | 同上 |
| `ChapterImitationHarnessReport` | 新增 character_consistency_signal 字段 | 同上 |

---

返回 [Loom 入口](../README.md) | [差距分析与演进](../gap-analysis-and-evolution.md)
