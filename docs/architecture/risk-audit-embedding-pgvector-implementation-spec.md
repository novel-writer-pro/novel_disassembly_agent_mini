# 风险审查：ONNX Embedding + pgvector 实施规格

## 1. 目的

这份文档把“最终推荐方案”从架构原则进一步收口为更接近开发落地的规格。

目标不是立刻把全部实现写完，而是明确：

- 哪些对象需要入库
- 哪些 checker 优先消费 embedding 结果
- 哪些地方必须保持规则化判定
- 哪些地方适合引入目标式 LLM 复核

---

## 2. 最终方案概览

推荐方案：

1. **ONNX embedding**
   - 负责稳定、本地、低漂移的向量化
2. **PostgreSQL + pgvector**
   - 负责 signal 存储、ANN 检索、跨章候选 linking
3. **Semantic Signal Builder**
   - 负责 canonicalization / linking / grouping
4. **Risk Checkers**
   - 负责最终 advisory-only 风险判定
5. **Targeted LLM Adjudication**
   - 只用于疑难候选 / 高价值复核，不做全量同步判定

---

## 3. 建议新增的数据对象

## A. `risk_semantic_signals`

建议作为主表，存语义信号节点。

### 建议字段

- `id`
- `branch_id`
- `chapter_index`
- `signal_type`
  - `character`
  - `relationship`
  - `foreshadow`
  - `rule_scope`
  - `authority_boundary`
  - `resource_constraint`
  - `conflict_thread`
  - `timeline_anchor`
  - `power_state`
- `source_field`
  - `unsupported_inferences`
  - `state_transition_notes`
  - `evidence_backed_resolutions`
  - `unresolved_threads`
  - `state_summary.*`
  - `fact_record`
- `raw_text`
- `canonical_label`
- `canonical_group`
- `confidence`
- `metadata_json`
- `embedding vector(<dim>)`
- `created_at`

### 作用

- 把“文本级 signal”变成“可检索的结构化语义节点”
- 让后续 checker 不再每次从 artifact 文本重新做弱归并

---

## B. `risk_signal_links`

建议作为候选对齐表，存 signal 与 signal 之间的关系。

### 建议字段

- `id`
- `branch_id`
- `from_signal_id`
- `to_signal_id`
- `link_type`
  - `semantic_duplicate`
  - `payoff_of`
  - `rule_variant_of`
  - `relationship_variant_of`
  - `thread_continuation`
  - `possible_conflict_with`
- `score`
- `evidence_json`
- `created_at`

### 作用

- 支持伏笔与兑现对齐
- 支持规则表述归一
- 支持关系表达归一
- 支持线程跨章延续判断

---

## C. `risk_signal_clusters`（可选后续）

如果后续要进一步收口 review workflow，可加 signal cluster 层。

当前阶段不是必须，但长远有利于：

- 把跨章语义候选先聚成稳定簇
- checker 直接消费 cluster，而不是散 signal

---

## 4. 各 checker 与 embedding 的优先接入顺序

## 第一优先级

### 1. `foreshadow_payoff_consistency`

最适合先吃 embedding。

原因：
- 前文伏笔与当前兑现常常不是同字面表达
- 最需要跨章语义 linking

embedding 用途：
- 找“可能是同一条伏笔线”的历史 signal
- 建 payoff candidate set

checker 保持：
- `payoff_without_setup`
- `resolved_thread_reopened_without_reason`
- `important_thread_long_unmentioned`

---

### 2. `relationship_consistency`

原因：
- 关系缓和/恶化的表述高度多样
- “停战 / 和解 / 缓和 / 冰释前嫌”适合语义归一

embedding 用途：
- 关系状态表述归一
- 候选关系簇构建

checker 保持：
- `relationship_shift_without_bridge`
- `trust_state_conflict`
- `hostility_resolution_too_fast`

---

## 第二优先级

### 3. `setting_scope_consistency`

原因：
- 规则边界、权限边界、资源限制经常存在不同说法

embedding 用途：
- 边界规则 canonicalization
- scope expansion 候选 linking

checker 保持：
- `constraint_scope_expansion`
- `resource_limit_missing`
- `authority_boundary_conflict`

---

### 4. `thread_closure_consistency`

原因：
- 冲突线程跨章延续需要更强“是否仍是同一线程”的判断

embedding 用途：
- conflict thread continuation matching
- resolution-thread rejoin

checker 保持：
- `thread_dropped_after_escalation`
- `closure_without_resolution_basis`
- `ending_stability_candidate`

---

## 第三优先级

### 5. `character_ooc`
### 6. `world_rule_consistency`
### 7. `plot_logic_consistency`
### 8. `timeline_consistency`
### 9. `power_scaling_consistency`

这些不是不能吃 embedding，而是当前收益不如前四项直接。

---

## 5. Semantic Signal Builder 的职责边界

signal builder 应负责：

1. 文本 signal 标准化
2. embedding 向量生成
3. ANN 候选召回
4. canonical group 生成
5. link proposal 生成

signal builder 不负责：

- 最终风险成立判断
- 最终 severity 裁决
- review workflow 状态流转

这些仍由 checker / aggregator / review workflow 负责。

---

## 6. LLM 在最终方案中的位置

LLM 不是主判定引擎，而是：

## Targeted Adjudication Layer

只在这些情况调用：

1. embedding 候选相似度接近，但规则判定不够稳
2. 候选同时有强 supporting / strong counter evidence
3. review priority 高
4. 人工复核前需要更强 evidence pack

### 不建议

- 每章全量跑 LLM adjudication
- 每个 checker 同步跑 LLM 二判

---

## 7. 与当前代码结构的映射

当前已有：

- `novel_analyzer/services/risk_semantic_signal_service.py`
- `novel_analyzer/services/risk_audit_service.py`

建议后续新增：

- `novel_analyzer/services/risk_signal_store_service.py`
- `novel_analyzer/services/risk_signal_link_service.py`
- `novel_analyzer/services/risk_adjudication_service.py`

### 推荐职责

#### `risk_signal_store_service.py`
- 写入 / 查询 `risk_semantic_signals`
- 执行 pgvector ANN 检索

#### `risk_signal_link_service.py`
- 生成 link proposals
- payoff linking / rule variant linking / thread continuation linking

#### `risk_adjudication_service.py`
- 在少量目标 case 上调用 LLM
- 输出 adjudication note
- 不直接替代 checker verdict

---

## 8. 推荐实施阶段

## Phase 1
- 定义 signal store schema
- 写入最小 `risk_semantic_signals`
- 接入 `foreshadow` / `relationship`

## Phase 2
- 加 `risk_signal_links`
- 接入 `setting_scope` / `thread_closure`

## Phase 3
- 加目标式 LLM adjudication
- review workflow 消费 adjudication note

## Phase 4
- signal cluster 化
- batch review / human review evidence pack 优化

---

## 9. 一句话结论

> 如果要把风险审查推进到真正靠近生产的能力架构，最应该做的不是让 checker 直接全量连 LLM，而是把 **ONNX embedding + pgvector** 落到语义信号层，先把跨章 signal 的归一、链接、检索能力做稳，再让 checker 在这个底座上做可解释判定。
