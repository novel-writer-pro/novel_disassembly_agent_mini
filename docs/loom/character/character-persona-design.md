# CharacterPersona 构建与一致性检测 / Character Persona Design

---

## 1. 问题定位

**现状**：
- 角色状态是 `carry_over_state` 中的 snapshot，随章节追加，无演化逻辑
- OOC checker 是规则检测（角色是否违反已知规则），不能感知角色内在动机
- 没有角色说话风格的量化模型

**解法**：从 Loom memory 层切片构建 `CharacterPersona`，包含价值观、目标、恐惧、说话风格向量，
并在每次仿写前检测当前草案是否符合角色认知基。

---

## 2. CharacterPersona 构建

```python
def build_character_persona(
    branch_id: str,
    character_name: str,
    as_of_chapter: int,
) -> CharacterPersona:
    """
    从现有数据构建角色认知基。
    数据来源：
    1. FactRecord：该角色的行为模式（动词/决策/情感反应）
    2. GraphNode：该角色的关系网络（allies/rivals/neutral）
    3. EpisodicMemory：该角色的关键事件锚点（高 importance_score）
    4. ChunkEmbedding：该角色的对话风格向量
    """
    # 1. 从 fact_records 提取行为模式
    behavior_facts = session.execute(
        select(FactRecord)
        .where(FactRecord.branch_id == branch_id)
        .where(FactRecord.entity_label == character_name)
        .where(FactRecord.chapter_index <= as_of_chapter)
        .where(FactRecord.episodic_status == "active")
        .order_by(FactRecord.importance_score.desc())
        .limit(20)
    ).scalars().all()

    # 2. 从 graph_nodes 提取关系网络
    character_node = session.execute(
        select(GraphNode)
        .where(GraphNode.branch_id == branch_id)
        .where(GraphNode.label == character_name)
        .where(GraphNode.node_type == "entity")
    ).scalar_one_or_none()

    relationships = {}
    if character_node:
        edges = session.execute(
            select(GraphEdge)
            .where(GraphEdge.branch_id == branch_id)
            .where(
                (GraphEdge.source_node_id == character_node.id) |
                (GraphEdge.target_node_id == character_node.id)
            )
            .where(GraphEdge.is_active == True)
        ).scalars().all()
        relationships = _extract_relationships(character_node, edges)

    # 3. 从 episodic_anchors 提取关键事件
    episodic_anchors = _get_character_episodic_anchors(
        branch_id, character_name, as_of_chapter
    )

    # 4. 从 chunk_embeddings 提取说话风格向量
    speech_style_vector = _compute_character_speech_vector(
        branch_id, character_name, as_of_chapter
    )

    return CharacterPersona(
        character_id=character_name,
        branch_id=branch_id,
        built_at_chapter=as_of_chapter,
        values=_infer_values(behavior_facts),
        goals=_infer_goals(behavior_facts),
        fears=_infer_fears(behavior_facts),
        speech_style_vector=speech_style_vector,
        episodic_anchors=episodic_anchors,
        relationship_network=relationships,
    )
```

---

## 3. 一致性检测

```python
def check_character_consistency(
    persona: CharacterPersona,
    draft_text: str,
    character_name: str,
) -> CharacterConsistencySignal:
    """
    检测草案中该角色的行为是否符合认知基。
    三个检测维度：
    1. 说话风格一致性（embedding 对比）
    2. 行为模式一致性（与 values/goals 的语义对比）
    3. 关系态度一致性（对 allies/rivals 的态度是否符合关系网络）
    """
    # 1. 说话风格一致性
    draft_dialogues = extract_character_dialogues(draft_text, character_name)
    if draft_dialogues:
        draft_speech_vector = mean_embedding(draft_dialogues)
        speech_consistency = 1.0 - cosine_distance(
            draft_speech_vector, persona.speech_style_vector
        )
    else:
        speech_consistency = 1.0

    # 2. 行为模式一致性（heuristic：检测是否有明显违反 values 的行为）
    behavior_consistency = _check_behavior_consistency(
        draft_text, character_name, persona.values, persona.goals
    )

    # 3. 关系态度一致性
    relationship_consistency = _check_relationship_consistency(
        draft_text, character_name, persona.relationship_network
    )

    overall_score = (
        speech_consistency * 0.4
        + behavior_consistency * 0.35
        + relationship_consistency * 0.25
    )

    return CharacterConsistencySignal(
        character_id=character_name,
        overall_consistency_score=round(overall_score, 4),
        speech_consistency=round(speech_consistency, 4),
        behavior_consistency=round(behavior_consistency, 4),
        relationship_consistency=round(relationship_consistency, 4),
        alert_level=_classify_consistency(overall_score),
        suggestion=_generate_suggestion(overall_score, persona),
    )
```

---

## 4. 与现有 OOC Checker 的关系

```
现有 OOC checker（保持不变）：
  检测"是否违反已知规则"（规则化，可解释）
  例：角色 A 不会使用技能 X → 草案中使用了 → OOC 触发

Character 层（新增，补充）：
  检测"是否符合角色认知基"（学习型，可进化）
  例：角色 A 一贯冷静 → 草案中突然情绪失控 → consistency_score 下降

两者串联：
  OOC checker 先过滤规则违规 → Character 层再检测认知基一致性
  不互相替代，各司其职
```

---

## 5. 接入点

```python
# preflight_imitation 接入（feature flag: loom_character_enabled）
if settings.loom_character_enabled:
    main_characters = get_main_characters(branch_id, chapter_index)
    for char_name in main_characters[:3]:  # 只检测前3个主要角色
        persona = character_agent_service.build_character_persona(
            branch_id=branch_id,
            character_name=char_name,
            as_of_chapter=chapter_index - 1,
        )
        consistency = character_agent_service.check_character_consistency(
            persona=persona,
            draft_text=draft_text,
            character_name=char_name,
        )
        if consistency.alert_level in ("warn", "critical"):
            preflight_notes.append(PrefligtNote(
                level=consistency.alert_level,
                checker="loom_character_consistency",
                message=f"{char_name} 角色一致性偏低（{consistency.overall_consistency_score:.2f}）：{consistency.suggestion}",
            ))
```

---

## 6. 渐进式演进路径

```
阶段 1（Phase 4 P4，当前规划）：
  - 基于现有数据构建 CharacterPersona（无 LLM）
  - heuristic 一致性检测（embedding 对比）
  - 接入 preflight_imitation 作为补充检查

阶段 2（Phase 5 后续）：
  - LLM 辅助推断 values/goals/fears（更准确）
  - 角色认知基随章节自动更新（动态演化）
  - 多角色关系网络的联动检测

阶段 3（长期）：
  - 角色 agent 自主决策（参考 BookWorld 2025）
  - story-time-aware knowledge graph（参考 Living the Novel 2025）
```

---

## 7. 验收标准

- `character_consistency_signal` 与人工角色评分 Kendall's τ ≥ 0.4
- `character_ooc` 触发率在 Phase 3 基础上再下降 ≥ 10%
- 构建 CharacterPersona 时间 < 1s（纯 DB 查询）
- feature flag 关闭时，现有链路完全不受影响

---

返回 [Character 层入口](./README.md) | [Loom 入口](../README.md)
