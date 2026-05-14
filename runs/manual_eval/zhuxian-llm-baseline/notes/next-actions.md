# 诛仙 后续行动

## 已完成(2026-05-14)
- [x] 审 ch2-5 → 填 manual-review-notes.md(综合 5.8/10)
- [x] 把发现的问题写进 problem-trace.md(10 条问题)
- [x] **确认 mapping_pack 没注入**:steering_pack 全空,人物 mapping 不一致

## 立即(下一会话)
- [ ] 写回至少一条 cluster status 验证 mailbox 通路
- [ ] 重跑 ch2(LLM 报 JSONDecodeError)→ 这是 batch 隔离问题还是 prompt 太长?
- [ ] **重跑整本** + 显式注入 `--worldview-doc` `--character-map` 等 steering 参数
- [ ] 把 ch3"宏愿"作为 P1 reference 候选(萧鼎"雷电斗法"风格保真度最高)

## 短期(本周)
- [ ] 扩样到 ch10/30/60/100,看 mapping 不一致问题是否会全本恶化
- [ ] 跑 `loom-collect-pairs-from-manual` 把上述评分转化为 pairwise 数据
- [ ] 与 weitu-llm-baseline 对比:跨题材共性 vs 本书特有

## 已被这轮 review 触发的代码修复
- [x] **commit f6b3bab** P0/P1 三件套
- [x] **commit 99e6abe** workspace bootstrap
- [x] **commit f60827d** method_notes 不再 echo action_queue
- [ ] **新发现** mapping_pack 在 writer-imitate-range 路径没生效 → 查 cli/app.py mapping_pack_dict 注入路径
- [ ] **新发现** dialogue_voice 完全无差异 → dialogue-designer 接 reward 闭环优先级提高

## 中期(Phase 4 推进)
- [ ] 对照 [docs/loom/gap-analysis-and-evolution.md](../../../docs/loom/gap-analysis-and-evolution.md) Phase 4 计划
- [x] 验证 style/rhythm/dialogue skill 信号是否进入 harness ✅ flag 已开,signals 实际产出
- [ ] dialogue_signal 与人工"声纹辨识度"评分相关性
