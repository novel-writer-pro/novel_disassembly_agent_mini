# Whole-Book Imitation API 稳定性说明

## 1. 当前定位

当前 whole-book imitation 系列接口建议按：

> **pre-v1 / system-contract-ready**

管理。

含义：
- 已经可以给系统/agentOS/调度器直接消费
- CLI / export / API 三个入口已经对齐同一份 report contract
- 但暂不宣称为完全冻结的 v1，因为后续仍可能继续补 orchestration 语义与版本字段

---

## 2. 当前入口

### CLI 运行
- `run-whole-book-imitation`

### CLI 导出
- `export-whole-book-imitation-run`

### API
- `POST /api/whole-book-imitation-run`

推荐原则：
- 人工调试优先 CLI
- 系统集成优先 API / export
- 不建议依赖 stdout 抓取做正式系统接入

---

## 3. 当前建议稳定字段

## 3.1 顶层稳定字段

- `branch_id`
- `project_title`
- `queue`
- `carry_over_notes`
- `execution_mode`
- `executed_steps`
- `final_carry_over_state`
- `policy_summary`
- `dashboard_summary`
- `run_notes`

## 3.2 dry-run 稳定字段

- `queue[*].order`
- `queue[*].source_chapter_index`
- `queue[*].target_goal`
- `queue[*].prerequisites`
- `queue[*].carry_over_inputs`
- `queue[*].risk_focus`
- `queue[*].scheduling_priority`
- `queue[*].scheduling_reason`
- `policy_summary.queue_length`
- `policy_summary.highest_queue_priority`
- `policy_summary.priority_reason_histogram`
- `dashboard_summary.queue_priority_preview`
- `dashboard_summary.top_queue_priority_chapters`
- `dashboard_summary.queue_cluster_buckets`
- `dashboard_summary.queue_next_actions`

## 3.3 sandbox 稳定字段

- `executed_steps[*].source_chapter_index`
- `executed_steps[*].overall_score`
- `executed_steps[*].overall_risk_level`
- `executed_steps[*].stop_reason`
- `executed_steps[*].scheduling_priority`
- `executed_steps[*].scheduling_reason`
- `executed_steps[*].strategy_input`
- `executed_steps[*].policy_summary`
- `executed_steps[*].carry_over_state`
- `executed_steps[*].action_queue`
- `executed_steps[*].revise_payload`
- `policy_summary.executed_step_count`
- `policy_summary.chapter_ranking`
- `policy_summary.book_priority_ranking`
- `policy_summary.severity_histogram`
- `policy_summary.risk_bucket_histogram`
- `policy_summary.next_stage_focus`
- `dashboard_summary.highest_priority_chapters`
- `dashboard_summary.top_risk_chapters`
- `dashboard_summary.strategy_targets`
- `dashboard_summary.top_priority_summary`
- `dashboard_summary.top_risk_summary`
- `dashboard_summary.chapter_flags`
- `dashboard_summary.book_handoff_summary`

---

## 4. 当前更偏增强/实验字段

这些字段当前可用，但下游不建议强绑定过深：

- `executed_steps[*].draft_excerpt` 的文本细节
- `executed_steps[*].revise_payload.recommended_actions` 的自然语言内容
- `executed_steps[*].strategy_input.recommended_actions` 的自然语言内容
- `dashboard_summary.issue_family_ranking`
- `dashboard_summary.weak_lane_priority_ranking`
- `dashboard_summary.weak_lane_top_actions`
- `dashboard_summary.weak_lane_dominance`
- `dashboard_summary.top_priority_summary` 内更细粒度统计的排序细节
- `dashboard_summary.top_risk_summary` 内更细粒度统计的排序细节

原则：
- 结构字段可以用
- 文案字段、排序细节、提示文本应宽松消费

---

## 5. 最小调用约定

推荐最小请求：

```json
{
  "branch_id": "branch-xxx",
  "project_title": "测试项目",
  "source_work_name": "示例小说",
  "target_work_name": "新世界版示例小说",
  "chapter_specs": [
    {"source_chapter_index": 2, "target_goal": "延续资源铺垫"},
    {"source_chapter_index": 3, "target_goal": "延续主角获得功法后的行动线"}
  ]
}
```

如果系统只想拿编排层，不跑执行：
- 不传 `execute`
- 或显式 `"execute": false`

如果系统要拿 sandbox report：
- `"execute": true`
- 可再传 `max_rounds / use_llm / model_name`

---

## 6. 进入 v1 的建议条件

建议至少满足：

1. 增加显式的 `contract_version / stable_contract_version`
2. whole-book report 的稳定字段集合冻结
3. API / CLI / export 三路 contract regression 长期稳定
4. orchestration handoff 语义不再频繁变化
5. provider-backed sandbox run 完成更多真实回归

---

## 7. 一句话总结

> 当前 whole-book imitation 已经达到 **系统可接入的 pre-v1 稳定状态**：
> 可正式消费结构字段，但对自然语言提示与细粒度排序信号应保持宽松绑定。
