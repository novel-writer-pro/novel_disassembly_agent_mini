# Style 层入口 / 文风 + 节奏 + 对话质量

> Style 层解决的核心问题：**文风漂移无检测、节奏平淡无量化、对话质量无信号**。
> 当前系统在"不写崩"上已接近商业水准，但在"写得好"上仍有明显差距。

---

## 与 0509 控制层的关系

```
0509 operator_surface（展示 style/rhythm/dialogue 信号，不变）
        ↑
        │ 接收 style_signal + rhythm_signal + dialogue_signal（新信号）
        │
Loom style 层（三类信号计算 + 输出，新增）
        │ 复用现有 ChunkEmbedding（风格向量）
        │ 复用现有 FactRecord（对话候选）
        ↓
ChunkEmbedding（pgvector）+ FactRecord（对话）+ WindowArtifact（节奏）
```

Style 层是 0509 operator_surface 的**信号提供者**，不直接写入 action_queue。
operator 看到风格漂移/节奏警告后自行决定是否创建 style_intervention ticket。

---

## 三类信号

| 信号 | 服务 | 核心指标 | 数据来源 |
|------|------|---------|---------|
| `style_signal` | `style_calibration_service` | `style_drift_score`（风格漂移距离） | `chunk_embeddings`（pgvector） |
| `rhythm_signal` | `rhythm_analysis_service` | `hook_density`、`pacing_type`、`climax_position` | `window_artifacts` + `fact_records` |
| `dialogue_signal` | 内嵌于 harness report | `character_voice_consistency`、`dialogue_efficiency` | `fact_records`（对话候选） |

**关键优势**：三类信号全部复用现有数据，**不需要新的 LLM 调用**。

---

## 与 Loom 其他层的关系

```
Style 层 → Tension 层：rhythm_signal 与 tension_signal 联动
  - hook_density 低 + conflict_density 低 → 双重平淡警告
  - 触发更强的 obstacle injection 建议

Style 层 → Reward 层：dialogue_signal 进入 pairwise 评估第五维度
  - character_voice_consistency 作为 character_consistency 的补充
  - dialogue_efficiency 作为 plot_coherence 的补充

Style 层 → Memory 层：style_vector 作为 Semantic Memory 的风格锚点
  - 参考章节的 style_vector 存入 semantic_snapshot
  - 后续章节与锚点对比，检测漂移
```

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [style-vector-design.md](./style-vector-design.md) | 风格向量化与漂移检测设计 |
| [rhythm-analysis-design.md](./rhythm-analysis-design.md) | 节奏分析器设计 |
| [dialogue-signal-design.md](./dialogue-signal-design.md) | 对话质量信号设计 |

---

## 接入点

| 接入层 | 接入方式 | feature flag |
|--------|---------|-------------|
| `preflight_imitation` | style_drift 检查（warn 级别，非阻塞） | `loom_style_enabled` |
| `loom-status` | 展示 style_drift_score + rhythm_signal | 同上 |
| `session_loom_signals` | 新增 style_signal 字段 | 同上 |
| `ChapterImitationHarnessReport` | 新增 dialogue_signal 字段 | `loom_pairwise_enabled` |

---

返回 [Loom 入口](../README.md) | [差距分析与演进](../gap-analysis-and-evolution.md)
