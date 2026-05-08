# Batch Innovation Experiment Workflow / 批量创新导向实验流程

## 目标

不是单章小修，而是：

- 给一批章节统一注入新的世界观底座
- 给一批章节统一注入套路轴
- 验证这组创新导向是否提升可读性、商业感和差异化

---

## 当前入口

新增 CLI：

```bash
./.venv/bin/novel-analyzer writer-innovation-experiment <branch_id> <experiment_name> \
  '24:压住成绩爽点，但拉高阶层跃迁冲击' \
  '25:强化回乡情绪与身份落差' \
  --worldview-note "灵气衰败时代，资源与身份强绑定" \
  --trope-axis "底层逆袭" \
  --trope-axis "账本修仙" \
  --innovation-directive "把修炼收益折算为社会信用与家族博弈" \
  --taboo-innovation "不要突然引入无代价系统外挂" \
  --knowledge-ref "男频修仙读者期待先压后扬、收益可见" \
  --output-dir output
```

输出：
- `writer-innovation-experiment-<name>.json`
- `writer-innovation-experiment-<name>.md`

现在同一份 experiment 里也会附带：
- `baseline_items`
- `delta_visual_summary`
- `experiment_meta.baseline_vs_steering_report`

其中建议重点看：
- `steering_pack`
- `steering_retrieval_meta`
- `steering_retrieval_meta.selected_doc_summaries`
- `delta_visual_summary`
- `experiment_meta.baseline_vs_steering_report`
- `experiment_meta.innovation_delta_summary`
- `experiment_meta.risk_delta_summary`

---

## 推荐实验步骤

1. 先定实验主题
   - 例如“账本修仙化”
   - 例如“宗门税制化世界观”

2. 再定一组 steering pack
   - worldview
   - trope
   - innovation
   - taboo
   - knowledge refs

3. 选 2~5 个连续章节
   - 最好是一段完整小弧线

4. 统一跑 experiment

5. 对比：
   - 是否更有底座感
   - 是否更有内涵创新
   - 是否破坏 continuity
   - 是否提高 reader-sim / hook / novelty 感
   - 命中的 trope/worldview/audience 文档是否合理
   - 命中文档摘要是否真的解释了本轮 steering 在借什么底座
   - innovation/risk delta 是否在预期范围

---

## 推荐记录字段

每次 experiment 建议记录：
- experiment_name
- chapter_range
- steering_pack
- steering_retrieval_meta
- innovation_delta_summary
- risk_delta_summary
- 最满意章节
- 最失真章节
- continuity 风险
- reader-sim 变化
- 是否值得推广到更长区间

---

## 当前最适合的实验主题

### A. 资源账本化成长
- 把每次收益写成可见账本

### B. 制度化修仙
- 把修炼与家族/宗门/王朝信用绑定

### C. 阶层跃迁型男频
- 每次进步都要带社会位置变化

---

## 风险提醒

批量创新实验最常见的问题：
- 创新过头，人物连续性崩
- 世界观一下变太大
- 套路轴太强，导致章节都长得像说明书

所以实验时必须保留：
- taboo list
- continuity memory
- risk gate
- reader sim
