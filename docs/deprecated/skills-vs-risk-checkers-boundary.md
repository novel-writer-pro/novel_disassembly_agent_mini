# skills_dir 与风险检查器的职责边界

## 结论

当前仓库中的 `skills_dir/` **是系统在使用的**，但它主要服务于：

- 上游章节拆书分析
- staged prompt 渲染
- 结构化章节产物生成

而当前这套 **统一风险审查能力** 的核心执行层，主要不是 `skills_dir/`，而是系统自己的 Python 后端 checker / aggregator。

---

## 一张图看边界

```text
原文章节
  ↓
skills_dir 驱动的 staged analysis prompts
  ↓
chapter_artifact / facts / graph / windows / state summary
  ↓
risk_audit_service 中的 checker
  ↓
risk card / review candidates / clusters / audit conclusion
  ↓
bundle / report / API
```

---

## `skills_dir/` 当前负责什么

### 1. 章节拆书分析阶段

当前 `skills_dir/` 的主要职责，是给拆书 pipeline 提供 prompt 资产和 schema 资产。

典型阶段包括：

- `chapter-intake`
- `chapter-fact-extractor`
- `evidence-binder`
- `chapter-analysis-generator`
- `writer-learning-lens`
- `anti-fabrication-guard`

这些阶段会在系统里被渲染为实际 prompt，再驱动上游章节分析。

### 2. 对应代码位置

- `novel_analyzer/agent/pipeline.py`
- `novel_analyzer/skills/assets.py`
- `novel_analyzer/skills/loader.py`

也就是说：

> `skills_dir/` 主要负责“怎么拆书、怎么抽取、怎么生成章节级结构化产物”。

---

## 风险检查器当前负责什么

### 1. 下游门控与风险审查阶段

统一风险审查能力主要位于：

- `novel_analyzer/services/risk_audit_service.py`

当前 checker roster：

- `character_ooc`
- `world_rule_consistency`
- `plot_logic_consistency`
- `timeline_consistency`
- `power_scaling_consistency`

### 2. 它们依赖什么

这些 checker 当前主要依赖系统自己的运行时数据层：

- `chapter_artifact`
- `fact_record`
- `graph_nodes / graph_edges`
- `window_artifact`
- `state_summary`
- `chapter_output_summary`

也就是说：

> 风险检查器主要负责“怎么判断风险、怎么聚合风险、怎么生成审稿结论”。

---

## 为什么门控能力当前不直接做成 `skills_dir/`

原因很现实：

1. **可测试性更强**
   - checker 是 Python 逻辑，更容易写单元/集成测试
2. **聚合更容易**
   - 风险卡、候选、问题簇、结论都需要稳定聚合
3. **运行时更稳**
   - 不必把所有门控逻辑都 prompt 化
4. **系统边界更清晰**
   - 上游分析层和下游门控层不会混在一起

---

## 将来什么时候可以让风险能力部分接入 `skills_dir/`

可以，但建议是 **局部接入，而不是整体迁移**。

适合 skill-assisted 的场景：

1. 某个 checker 需要更强的 LLM 判断增强
2. 不同题材/编辑部要切换不同检查模板
3. 想做可配置的 signal extraction prompt

更合理的未来形态是：

- `skills_dir/`
  - 继续负责上游章节分析 prompt
  - 以及少量“risk signal extraction”辅助 prompt

- Python checker
  - 继续负责风险判断、聚合、排序、导出

---

## 当前产品化建议

### 运行时核心

应该强调：

- 风险检查能力是 **系统运行时能力**
- 不是 Codex skill 结果
- 也不是单纯 prompt 技巧

### 对外表述

推荐说：

> 系统基于章节拆书产物、事实层、图谱层和连续性信号层，运行统一风险审查引擎，输出风险卡、问题簇与审查结论。

不推荐说：

> 这是某个 skill 帮忙检查出来的。

---

## 一句话总结

> `skills_dir/` 当前主要服务于上游拆书分析；  
> 风险门控能力当前主要依赖系统自己的后端 checker 与聚合逻辑。  
> 它们是衔接关系，不是同一层职责。
