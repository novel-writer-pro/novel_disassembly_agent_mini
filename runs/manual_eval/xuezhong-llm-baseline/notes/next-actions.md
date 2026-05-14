# 雪中悍刀行 后续行动

## 已完成(2026-05-14)
- [x] 审 ch2-5 → 填 manual-review-notes.md(本批最佳本,综合 6.2/10)
- [x] 把发现的问题写进 problem-trace.md(8 条 chapter-level + 1 条跨章)
- [x] **新发现 prompt-bleed bug**(ch4 prose 末尾自带"目标明确/阻力浮现/主角回应/章尾钩子"4 行 method 标签)

## 立即(下一会话)
- [ ] 写回至少一条 cluster status 验证 mailbox 通路(`set-cluster-status`)
- [ ] 重跑 ch3(scaffold-only failed)+ ch4(LLM 越界改写章节标题/情节)→ 看 prompt-bleed 是否系统性发生
- [ ] 把 ch5"我要去东海"作为 P1 reference,扔进 pairwise eval 当 winner 候选

## 短期(本周)
- [ ] 扩样到 ch10/30/60/100(覆盖前/中/后期,验证长程稳定性)
- [ ] 跑 `loom-collect-pairs-from-manual` 把上述评分转化为 pairwise 数据
- [ ] 跨本对比:雪中(6.2) vs 诛仙(5.8) vs 卫图(待审)→ 烽火戏诸侯文风对模型更友好这个 hypothesis 是否站住

## 已被这轮 review 触发的根因修复(代码层)
- [x] **commit f6b3bab** P0-1 action_queue 不污染 draft_text
- [x] **commit f6b3bab** P0-2 scaffold-only 显式标记
- [x] **commit f6b3bab** P1-3 verdict 阈值松绑(P1+medium 不再一票否决)
- [x] **commit 99e6abe** workspace bootstrap + 离线清洗工具
- [x] **commit f60827d** action_queue 也不再 echo 进 method_notes
- [ ] **新发现** prose 中 LLM 自带"目标明确/阻力浮现"4 行结构标签 → prompt 层修复
- [ ] **新发现** ch3/诛仙ch2 LLM context 串章问题 → 查 helicone trace + batch isolation

## 中期(Phase 4 推进)
- [ ] 对照 [docs/loom/gap-analysis-and-evolution.md](../../../docs/loom/gap-analysis-and-evolution.md) Phase 4 计划
- [x] 验证 style/rhythm/dialogue skill 信号是否进入 harness ✅ Phase-4 flag 已开,LLM 实测 dialogue_signal/chapter_quality_signal 各 8 字段
- [ ] 把人工评分与 Loom signal 做相关性分析(baseline 第一轮)
- [ ] 重跑 ch1-103(开 flag 后),拿到接线后真基线
