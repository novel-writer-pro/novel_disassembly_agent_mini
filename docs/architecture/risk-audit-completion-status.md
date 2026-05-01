# 风险审查技术完成度与使用说明

## 1. 当前技术上是否已完成

结论：

> **风险审查主链第一阶段已完成。**

这里的“完成”是指：

1. 已形成稳定的 risk audit checker 主链
2. 已形成 semantic middle layer（signal / latest / link / cluster / exact context）
3. 已形成 multi-source evidence pack
4. 已形成 risk card / review summary / report 导出链
5. 已形成文档入口与验证报告链
6. 已有持续的 fresh verification evidence

### 当前已完成的 9 个 checker

1. `character_ooc`
2. `world_rule_consistency`
3. `relationship_consistency`
4. `foreshadow_payoff_consistency`
5. `setting_scope_consistency`
6. `thread_closure_consistency`
7. `plot_logic_consistency`
8. `timeline_consistency`
9. `power_scaling_consistency`

### 当前已完成的语义中间层

- `RiskSemanticSignalService`
- `RiskSignalStoreService`
- `RiskSignalLinkService`
- `RiskSignalClusterService`
- `RiskExactContextService`
- `RiskLatestObjectService`
- `RiskEvidencePackService`

### 当前已完成的增强门控线

以下 6 条关键门控线已开始真实消费历史 evidence：

- relationship
- foreshadow
- setting_scope
- thread_closure
- timeline
- power

---

## 2. 什么还不算“最终完成”

以下内容属于下一阶段，而不是当前第一阶段完成定义的一部分：

1. **PostgreSQL / pgvector 真环境验证**
   - 代码路径已准备，但当前未在真实 PostgreSQL 环境里完成最终打通验证
2. **entity latest state 的更完整对象层**
3. **targeted LLM adjudication**
4. **多路融合器进一步精细化**

因此更准确的说法是：

> 已完成 **第一阶段的可运行、可验证、可交接的风险审查主链**；
> 未完成“所有后续增强路线的最终生产化收尾”。

---

## 3. 当前如何使用

### 3.1 运行 risk audit 主链

当前主链会在章节分析后运行：

- 生成 checker results
- 生成 semantic signals
- 生成 signal links
- 生成 signal clusters
- 聚合 chapter risk card
- 导出 branch risk/review/report

如果你通过现有分析流程推进章节，risk audit 会自动参与主链。

### 3.2 关键中间层的职责

#### `RiskSemanticSignalService`
- 生成结构化 signal

#### `RiskSignalStoreService`
- signal 落库
- 向量写入
- semantic retrieval
- latest signal retrieval

#### `RiskSignalLinkService`
- signal link proposal 落库

#### `RiskSignalClusterService`
- signal cluster 落库
- latest cluster retrieval

#### `RiskExactContextService`
- 历史 fact 的最新精确命中

#### `RiskLatestObjectService`
- relationship / rule_scope / conflict_thread 的对象级 latest snapshot

#### `RiskEvidencePackService`
当前 evidence pack 字段：
- `semantic_hits`
- `latest_signals`
- `clusters`
- `link_types`
- `support_texts`
- `graph_paths`
- `state_summaries`
- `exact_hints`
- `exact_contexts`
- `latest_objects`

---

## 4. 当前如何验证

### 4.1 推荐验证命令

#### 主链 + 中间层 + 导出链联合回归
```bash
./.venv/bin/python -m pytest \
  tests/test_risk_latest_object_service.py \
  tests/test_risk_evidence_pack_service.py \
  tests/test_risk_signal_store_service.py \
  tests/test_risk_signal_cluster_service.py \
  tests/test_risk_audit_service.py \
  tests/test_export_risk_card.py \
  tests/test_export_report.py -q
```

#### 当前最近一次结果
- `111 passed`

### 4.2 轻量验证命令

#### risk audit 主链
```bash
./.venv/bin/python -m pytest tests/test_risk_audit_service.py -q
```

#### evidence pack
```bash
./.venv/bin/python -m pytest tests/test_risk_evidence_pack_service.py -q
```

#### exact/latest 层
```bash
./.venv/bin/python -m pytest \
  tests/test_risk_exact_context_service.py \
  tests/test_risk_latest_object_service.py -q
```

#### export/report
```bash
./.venv/bin/python -m pytest \
  tests/test_export_risk_card.py \
  tests/test_export_report.py -q
```

---

## 5. 当前验证报告在哪里

主链验证报告：

- `.omx/reports/risk-audit-mainline-verification-20260430.md`

这份报告当前包含：
- checker roster
- semantic middle layer 列表
- evidence pack 内容
- retrieval-enhanced checker paths
- fresh evidence 摘要
- known warning
- outcome

---

## 6. 当前已知 warning

当前唯一已知 warning 是：

- `apps/api/app/main.py:142`
- `cgi` deprecation warning

它不阻塞当前风险审查主链。

---

## 7. 一句话结论

> 当前风险审查技术已经完成第一阶段：具备可运行、可验证、可交接的多源 evidence pack 门控主链；后续主要工作是 PostgreSQL/pgvector 真环境验证与下一阶段增强，而不是再补齐主链骨架。
