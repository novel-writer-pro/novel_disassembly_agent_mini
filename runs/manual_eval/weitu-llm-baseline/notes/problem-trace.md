# 卫图 问题追踪

> 用于把审查发现的问题转化为 cluster review 写回。

## 已知问题(来自系统)

- verdict 全部 needs_revision(三本完本一致 → gate 阈值问题,已通过 commit f6b3bab P1-3 修复)

## 审查发现

| chapter | 问题类型 | 描述 | 严重度 | 处置 |
|---|---|---|---|---|
| ch2 | `dialogue_voice` | 杏/卫图对话依赖叙述者复述,缺少人物自己说话 | low | dialogue-designer 接 reward |
| ch3 | `style_drift` | 赵伯"慢悠悠""沉吟半晌"等动作套语 | low | style-calibrator |
| ch4 | `prose_template_bleed` | 章末"（章末钩子：...）" 显式标签泄露到 prose | **high** | prompt 层修复 |
| ch4 | `prose_template_bleed` | "（本章完）"出现在正文 | medium | 同上 prompt 层修复 |
| ch5 | `prose_template_bleed` | "（本章完）"再次出现 — 系统性而非偶发 | **high** | 同上 |
| ch5 | `mapping_inconsistency` | LLM 改写了原章标题"婚事敲定"→"婚后筹谋" | medium | prompt 加约束 |
| ch5 | `world_rule` | 时间线断裂:ch4 是 2.5 两赎身;ch5 突然变成"减月例"+"府城采买药材"差事,前后不连贯 | medium | Loom memory shadow 应解决 |
| 跨章 | `template_residue` | method_notes/comparison_notes 末尾累积 "1:rhythm, 2:ending_hook..." 噪声 | medium | **已修(commit f60827d)** |

## prose-bleed 模式总结

跨三本观察:
- xuezhong ch4: 4 行 method 标签("目标明确：...""阻力浮现：...""主角回应：...""章尾钩子：...")
- weitu ch4-5: "（章末钩子：...）"+"（本章完）"
- zhuxian: 未观察到此类(原作风格压制了 LLM 的元描述倾向)

→ **prompt 层 bug**,不是 harness 后处理 bug。需要 prompt template 加 explicit 禁令。

## 写回模板

```bash
.venv/bin/python -m novel_analyzer.cli.app set-cluster-status 72da24e9-e65c-45a9-836d-957c4ae783ec <cluster_key> resolved \
  --review-notes "..." \
  --review-owner "<reviewer>" \
  --review-actor "review-bot" \
  --review-result "<confirmed-issue|confirmed-benign|needs-escalation|deferred>"
```
