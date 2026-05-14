# 卫图 后续行动

## 已完成(2026-05-14)
- [x] 审 ch2-5 → 填 manual-review-notes.md(综合 6.2/10)
- [x] 把发现的问题写进 problem-trace.md(8 条)
- [x] 三本横评:雪中(6.2)≈ 卫图(6.2)> 诛仙(5.8)

## 立即(下一会话)
- [ ] 写回至少一条 cluster status 验证 mailbox 通路
- [ ] 把 ch3"养生功法"作为 P1 reference candidate 入 pairwise eval
- [ ] 重跑 ch2-5(P0+P1+method_notes 修复后)拿干净基线

## 短期(本周)
- [ ] 扩样到 ch10/30/60/90 验证长程稳定性
- [ ] 跑 `loom-collect-pairs-from-manual` 把上述评分转化为 pairwise 数据
- [ ] 跨本对比:卫图(原创 IP)vs 雪中(名家作品)的 style/rhythm 信号差异

## prose-bleed 修复(高优先级,跨本系统问题)
- [ ] 跨本观察:xuezhong ch4(4 行 method 标签)+ weitu ch4-5("章末钩子：..."+"（本章完）")
- [ ] 修 prompt template:在 `build_chapter_imitation_prompt`(novel_analyzer/llm/prompts.py:96-209)加 explicit 禁令
  - "draft_text 中不要出现"目标明确：""阻力浮现：""主角回应：""章尾钩子："这些 method 标签"
  - "draft_text 中不要出现"（本章完）""（章末钩子：）"这类元描述"
- [ ] 加 prompt 层单元测试,避免回归

## Phase 4 推进
- [x] commit f6b3bab P0/P1 三件套
- [x] commit 99e6abe workspace bootstrap + 离线清洗工具
- [x] commit f60827d method_notes 不再 echo action_queue
- [x] commit 09be55c 三本人工 review 落盘
- [ ] dialogue-designer 接 reward 闭环 → 解决三本共同的"长辈级角色无声纹差异"问题
- [ ] reader-sim 4 视角接 session 报告 → 捕获"内心戏过单调"等心理薄弱问题
