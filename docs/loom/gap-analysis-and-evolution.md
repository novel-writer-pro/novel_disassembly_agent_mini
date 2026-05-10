# 商业水准差距分析与演进规划 / Gap Analysis & Evolution

> 最后更新：2026-05-10
>
> 本文回答三个问题：
> 1. 当前仿写能力距离商业水准的 SOTA 还有多少距离？
> 2. 差距在哪里，怎么缩短？
> 3. Loom Phase 4/5 应该做什么？

---

## 1. 商业水准的定义

"商业水准"不是学术 benchmark，而是读者愿意付费的标准：

| 维度 | 商业水准要求 | 当前系统状态 |
|------|------------|------------|
| **角色一致性** | 100 章内角色行为、语气、动机不漂移 | 🟡 有 OOC checker，但无主动记忆代谢 |
| **情节连贯性** | 伏笔有回收，支线有收束，节奏有起伏 | 🟡 有 unresolved threads，但无节奏调度器 |
| **文风稳定性** | 全书风格统一，不因章节切换而漂移 | 🔴 只有 style axes 描述，无量化校准 |
| **对话质量** | 角色说话有辨识度，对话推进情节 | 🔴 几乎无独立对话设计能力 |
| **爽点密度** | 每章有钩子，读者不弃书 | 🟡 有 hook_score，但无爽点密度模型 |
| **世界观自洽** | 规则不矛盾，设定不穿帮 | ✅ risk_checker + graph 已较强 |
| **长书稳定性** | 50 章后质量不下滑 | 🔴 carry_over 线性增长，Loom Phase 1 正在解决 |

**结论**：当前系统在"不写崩"（风控/一致性）上已接近商业水准，但在"写得好"（文风/节奏/对话/爽点）上仍有明显差距。

---

## 2. 与商业 SOTA 的完整差距矩阵

### 2.1 已缩短的差距（Phase 1-3 成果）

| 维度 | Phase 前状态 | Phase 1-3 后状态 | 缩短程度 |
|------|------------|----------------|---------|
| 长书记忆退化 | carry_over 线性追加，无代谢 | 三层记忆 + 冲突代谢（shadow 模式运行） | 🟢 架构已就绪，待生产验证 |
| 评估维度固化 | 9 个固定 checker，无学习 | LLM-as-judge pairwise + 数据收集 CLI | 🟡 工具就绪，待数据积累 |
| 情节张力无量化 | 完全依赖人工 steering | 三个张力指标（pgvector + GraphEdge） | 🟢 指标已实现，待 A/B 验证 |
| 评估数据孤岛 | manual_eval 无法转化为训练数据 | loom-collect-pairs-from-manual 等 4 个 CLI | 🟢 数据管道已就绪 |

### 2.2 仍存在的核心差距

#### 差距 A：文风量化与校准（🔴 高优先级）

**现状**：
- 只有 `style_axes`（文字描述的风格轴）
- 没有风格向量，无法量化"当前章节与目标风格的距离"
- 没有风格漂移检测，100 章后风格可能已悄悄偏移

**SOTA 参考**：
- StyleRPA（2024）：风格向量 + 相似度评估，可量化风格一致性
- Living the Novel（2025）：角色/风格专用 SFT，风格可学习

**商业影响**：读者对风格漂移极敏感，这是弃书的主要原因之一。

**Loom 方案（Phase 4）**：
```
style_vector = embedding(chapter_text)
style_drift = cosine_distance(style_vector, reference_style_vector)
→ 接入 preflight_imitation 作为 style_drift_score
→ 超过阈值时触发 style_recalibration 建议
```

---

#### 差距 B：节奏分析与爽点密度（🔴 高优先级）

**现状**：
- 有 `hook_score`（章末钩子评分）
- 有 `scene_beats`（场景节拍）
- 缺：爽点密度模型、节奏类型识别、高潮点检测

**SOTA 参考**：
- 网文商业实践：每 3000 字一个小高潮，每章末必有钩子
- 学术：Narrative Arc Detection（2024），情节弧线自动识别

**商业影响**：爽点密度直接决定读者留存率，是网文商业化的核心指标。

**Loom 方案（Phase 4）**：
```
rhythm_signal = {
    "hook_density": hooks_per_1000_chars,
    "climax_position": peak_tension_chapter_ratio,
    "pacing_type": "slow_burn | action_heavy | balanced",
    "satisfaction_score": reader_sim_score
}
→ 接入 tension 层，与 plot_similarity_score 联动
```

---

#### 差距 C：对话设计能力（🟡 中优先级）

**现状**：
- 只能从 `fact_records` 抽取 dialogue candidates
- 没有角色说话风格控制
- 没有对话信息效率检查（对话是否推进情节）

**SOTA 参考**：
- CharacterBench（2024）：角色对话一致性评估
- DialogueRPG（2025）：角色专属对话风格建模

**商业影响**：对话质量是读者评价"角色有没有灵魂"的核心感知点。

**Loom 方案（Phase 4）**：
```
dialogue_signal = {
    "character_voice_consistency": per_character_style_score,
    "dialogue_efficiency": plot_advancement_per_dialogue_line,
    "conflict_dialogue_density": confrontation_lines_ratio
}
→ 接入 reward 层，作为 pairwise 评估的第五个维度
```

---

#### 差距 D：读者模拟评审（🟡 中优先级）

**现状**：
- 只有系统级 review（risk/gate/harness self-check）
- 没有读者视角的质量评估

**SOTA 参考**：
- HANNA benchmark（2023）：人工读者评估框架
- EvolvR（2025）：多维度读者偏好学习

**商业影响**：系统认为"通过"的章节，读者可能觉得"无聊"。需要读者视角的补充。

**Loom 方案（Phase 5）**：
```
reader_sim_panels = [
    "casual_reader",      # 小白读者：是否看得懂、是否有趣
    "genre_veteran",      # 老书虫：是否符合题材惯例
    "satisfaction_reader", # 爽文读者：爽点是否到位
    "editor_view"         # 编辑视角：结构是否合理
]
→ 每个 panel 输出 0-1 分 + 具体反馈
→ 接入 session_primary_verdicts 作为 reader_satisfaction_score
```

---

#### 差距 E：角色认知基（🟡 中优先级，Phase 3 P4 已规划）

**现状**：
- 角色状态是 snapshot，不是持续演化的认知基
- OOC checker 是规则检测，不是角色自主判断

**SOTA 参考**：
- BookWorld（2025）：角色 agent 自主认知基，每个角色有独立 memory + 决策逻辑
- Deep Persona Alignment（2025）：角色价值观/动机的持续对齐

**Loom 方案（Phase 3 P4 → Phase 4 深化）**：
```
character_agent = {
    "character_id": "张三",
    "memory": episodic_memory_slice,      # 从 Loom memory 层切片
    "persona": {
        "values": [...],
        "goals": [...],
        "fears": [...],
        "speech_style": style_vector
    },
    "consistency_score": pairwise_eval_score
}
```

---

#### 差距 F：多线叙事调度（🟢 低优先级）

**现状**：
- 有 `unresolved_threads`，但只是列表，没有优先级调度
- 没有支线平衡器，支线可能长期悬空

**Loom 方案（Phase 5）**：
```
thread_scheduler = {
    "active_threads": [...],
    "dormant_threads": [...],
    "overdue_threads": [...],   # 超过 N 章未推进的线索
    "recommended_activation": thread_id  # 建议本章激活哪条线
}
```

---

## 3. 距离商业水准的综合评估

```
当前系统商业水准评分（满分 10）：

风控/一致性（不写崩）：  ████████░░  8/10  ← 已接近商业水准
情节连贯性：             ██████░░░░  6/10  ← Loom Phase 1-2 正在提升
文风稳定性：             ████░░░░░░  4/10  ← Phase 4 重点
节奏/爽点：              ████░░░░░░  4/10  ← Phase 4 重点
对话质量：               ███░░░░░░░  3/10  ← Phase 4 中期
读者体验：               ███░░░░░░░  3/10  ← Phase 5 目标
长书稳定性（50章+）：    ████░░░░░░  4/10  ← Loom Phase 1 解决中

综合：约 5/10，距离商业水准（7/10）还有明显差距。
主要差距集中在：文风量化、节奏/爽点、对话设计。
```

---

## 4. Phase 4 规划：文风 + 节奏 + 对话

**目标**：把综合评分从 5/10 提升到 7/10，达到商业可用水准。

**前提**：Phase 3 A/B 实验验证通过（character_ooc 下降 ≥20%）。

### P1：风格向量化与漂移检测

```
新增服务：style_calibration_service.py
  - compute_style_vector(chapter_text) → embedding（复用现有 ChunkEmbedding）
  - compute_style_drift(branch_id, chapter_index) → float（与参考章节的 cosine 距离）
  - suggest_style_recalibration(drift_score) → StyleRecalibrationSignal

接入点：
  - preflight_imitation：新增 style_drift 检查（feature flag loom_style_enabled）
  - loom-status：展示 style_drift_score
  - session_loom_signals：新增 style_signal 字段

验收：style_drift_score 与人工风格评分 Pearson r ≥ 0.5
```

### P2：节奏分析器

```
新增服务：rhythm_analysis_service.py
  - compute_hook_density(chapter_text) → float（每千字钩子数）
  - detect_climax_position(branch_id) → list[int]（高潮章节索引）
  - classify_pacing_type(branch_id, chapter_index) → str（slow_burn/action_heavy/balanced）

接入点：
  - tension 层：rhythm_signal 与 tension_signal 联动
  - preflight_imitation：节奏偏差警告
  - loom-status：展示 rhythm_signal

验收：hook_density 与读者留存率正相关（需真实数据验证）
```

### P3：对话质量信号

```
新增字段：ChapterImitationHarnessReport.dialogue_signal
  - character_voice_consistency: dict[str, float]  # 每个角色的说话风格一致性
  - dialogue_efficiency: float                      # 对话推进情节的效率
  - conflict_dialogue_density: float                # 冲突对话占比

接入点：
  - pairwise 评估：新增第五个维度 dialogue_quality
  - reward 层：dialogue_signal 进入 chapter_quality_score 计算

验收：dialogue_signal 与人工对话评分 Kendall's τ ≥ 0.4
```

### P4：角色认知基（深化 Phase 3 P4）

```
新增服务：character_agent_service.py
  - build_character_persona(branch_id, character_name) → CharacterPersona
    - 从 Loom memory 层切片该角色的 episodic_anchors
    - 从 graph_nodes 提取该角色的关系网络
    - 从 fact_records 提取该角色的行为模式
  - check_character_consistency(persona, draft_text) → ConsistencySignal

接入点：
  - preflight_imitation：角色认知基一致性检查
  - 替代/补充现有 OOC checker

验收：character_ooc 触发率进一步下降 ≥10%（在 Phase 3 基础上）
```

---

## 5. Phase 5 规划：读者模拟 + 多线调度 + 自适应编排

**目标**：把综合评分从 7/10 提升到 8.5/10，达到头部网文水准。

**前提**：Phase 4 风格/节奏/对话信号稳定运行，reward model 已 fine-tune。

### P1：读者模拟评审面板

```
新增服务：reader_simulation_service.py
  - simulate_reader_panel(chapter_text, panel_type) → ReaderSimSignal
    panel_type: "casual" | "veteran" | "satisfaction" | "editor"
  - aggregate_reader_scores(signals) → ReaderSatisfactionScore

接入点：
  - session_primary_verdicts：新增 reader_satisfaction_score
  - retirement gate：reader_satisfaction_score < 0.6 时标记 reader-blocked
  - operator surface：展示各 panel 的具体反馈

验收：reader_satisfaction_score 与真实读者评分 Pearson r ≥ 0.6
```

### P2：多线叙事调度器

```
新增服务：thread_scheduler_service.py
  - analyze_thread_status(branch_id) → ThreadStatusReport
    - active_threads: 当前活跃线索
    - dormant_threads: 超过 5 章未推进的线索
    - overdue_threads: 超过 15 章未推进的线索（建议激活或收束）
  - suggest_thread_activation(branch_id, chapter_index) → ThreadActivationSignal

接入点：
  - preflight_imitation：线索调度建议
  - tension 层：overdue_threads 触发 obstacle injection

验收：支线收束率（overdue_threads 比例）下降 ≥30%
```

### P3：长书自适应编排

```
目标：50 章后质量不下滑，100 章后仍可控

核心机制：
  - 自动检测质量下滑信号（chapter_quality_score 连续 3 章下降）
  - 触发 carry_over 重组（Working Memory 强制压缩 + Semantic Memory 重建）
  - 自动建议 steering pack 更新（当前 steering 是否还适合当前阶段）

接入点：
  - loom-status：展示 long_book_health_score
  - operator surface：长书健康度仪表盘

验收：100 章仿写的 chapter_quality_score 标准差 < 0.15
```

### P4：外部知识 RAG 接入

```
目标：让仿写不只依赖书内知识，能接入外部题材/世界观/读者预期

数据来源：
  - 题材 trope 库（已有 steering_library_service 基础）
  - 世界观 dossier（已有 worldview_capsule 基础）
  - 读者预期 pack（新增，从读者评论/书评提炼）

接入点：
  - constraint_pack：外部知识作为软约束
  - steering_pack：自动从 RAG 库检索相关 steering

验收：使用外部 RAG 的章节，reader_satisfaction_score 提升 ≥10%
```

---

## 6. 演进路线总览

```
Phase 1 ✅ 已完成：分层记忆基础设施（解决长书记忆退化）
Phase 2 ✅ 已完成：张力自动调节 + Pairwise 评估（情节质量可量化）
Phase 3 🔄 进行中：Reward Model + 角色认知基 + 生产部署
  前提：A/B 实验验证 + 500+ pairwise 数据积累

Phase 4 🔲 规划中：文风 + 节奏 + 对话（从 5/10 → 7/10）
  P1: 风格向量化与漂移检测（style_calibration_service）
  P2: 节奏分析器（rhythm_analysis_service）
  P3: 对话质量信号（dialogue_signal）
  P4: 角色认知基深化（character_agent_service）
  前提：Phase 3 A/B 验证通过

Phase 5 🔲 规划中：读者模拟 + 多线调度 + 自适应编排（从 7/10 → 8.5/10）
  P1: 读者模拟评审面板（reader_simulation_service）
  P2: 多线叙事调度器（thread_scheduler_service）
  P3: 长书自适应编排（100 章质量稳定）
  P4: 外部知识 RAG 接入
  前提：Phase 4 风格/节奏/对话信号稳定
```

---

## 7. 最快缩短差距的路径

如果只能做一件事，优先级如下：

1. **完成 Phase 3 A/B 实验**（生产验证 Loom memory 效果）
   - 这是所有后续 Phase 的前提
   - 验证通过后，长书稳定性从 4/10 → 7/10

2. **实现风格向量化**（Phase 4 P1）
   - 复用现有 ChunkEmbedding，开发成本低
   - 直接解决"文风漂移"这个高频弃书原因

3. **实现节奏分析器**（Phase 4 P2）
   - 爽点密度是网文商业化的核心指标
   - 与现有 tension 层天然联动

4. **积累 pairwise 数据 → fine-tune reward model**（Phase 3 P3）
   - 数据飞轮一旦启动，评估质量持续提升
   - 是所有后续 Phase 的质量保障

---

## 8. 与 capability-matrix 的映射

| capability-matrix 能力 | 对应 Loom Phase | 当前状态 |
|----------------------|----------------|---------|
| 文风修辞 | Phase 4 P1 | 🔲 规划中 |
| 节奏分析 | Phase 4 P2 | 🔲 规划中 |
| 对话设计 | Phase 4 P3 | 🔲 规划中 |
| 模拟读者评审 | Phase 5 P1 | 🔲 规划中 |
| 多线叙事 | Phase 5 P2 | 🔲 规划中 |
| 故事架构（书级） | Phase 5 P3 | 🔲 规划中 |
| 资料研究 | Phase 5 P4 | 🔲 规划中 |
| 角色认知基 | Phase 3 P4 → Phase 4 P4 | 🔄 进行中 |
| 记忆代谢 | Phase 1 ✅ | ✅ 完成 |
| 张力量化 | Phase 2 ✅ | ✅ 完成 |
| 评估自进化 | Phase 2-3 | 🔄 进行中 |

---

返回 [Loom 入口](./README.md) | [路线图](./roadmap.md) | [架构全景](./overview.md)
