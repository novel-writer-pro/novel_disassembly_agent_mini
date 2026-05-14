# 诛仙 问题追踪

> 用于把审查发现的问题转化为 cluster review 写回。

## 已知问题（来自系统）

- verdict 全部 needs_revision（与卫图/诛仙/雪中悍刀行三本完全一致 → 是 gate 阈值问题，非本书特性）
- branch-report 显示 1 个 failed_jobs，需要先排查（不影响仿写但影响后续分支扩展）

## 审查发现

| chapter | 问题类型 | 描述 | 严重度 | 处置 |
|---|---|---|---|---|
| ch2 | `scaffold_only` | LLM 报 JSONDecodeError;尝试输出"玄火坛""黑巫族"——属诛仙后期设定,context 串了 | **high** | 重跑;查 helicone trace |
| ch3 | `psyche_thin` | 普智内心独白整段平铺,缺与外景(雨势)呼吸交替 | medium | reader-sim 应捕到 |
| ch3 | `style_drift` | "他心中忽地一紧""他苦笑一声"等套语在一章内重复 4 次 | low | style-calibrator |
| ch4 | `mapping_inconsistency` | method_notes 说"对应张小凡",draft 用"李尘",risk_gate_notes 出现"鬼厉" | **high** | mapping_pack 没注入 |
| ch4 | `world_rule` | 横幅"善"被改成"剑",宗派改成"天剑宗"(与 ch5"青云"冲突) | medium | LLM 越界 |
| ch5 | `dialogue_voice` | 道玄/普智/徐长青共用"温润威严"声纹,无辨识度 | **high** | dialogue-designer 接 reward |
| ch5 | `psyche_thin` | 林枫(=张小凡)反应被叙述压缩,缺真实痛感 | medium | reader-sim |
| ch5 | `style_drift` | 章尾"阳光洒在青石路上,云雾缭绕的巍峨山门"——程式化 | medium | style-calibrator |
| 跨章 | `world_rule` | 宗派名 ch4=天剑宗 vs ch5=青云,长程一致性破裂 | **high** | Loom memory 应解决 |
| 跨章 | `template_residue` | 所有章 method_notes 拖 12-15 行 "1:draft_body, 2:rhythm..." | medium | **已修(commit f60827d)** |

## 写回模板

```bash
.venv/bin/python -m novel_analyzer.cli.app set-cluster-status e5becabd-e2f3-4045-9249-fa91f382dc9a <cluster_key> resolved \
  --review-notes "..." \
  --review-owner "<reviewer>" \
  --review-actor "review-bot" \
  --review-result "<confirmed-issue|confirmed-benign|needs-escalation|deferred>"
```


## 2026-05-14 系统级污染发现（已修复 FULL 产物）

### 发现 1: Harness Action Queue 调试尾巴泄漏到 prose
- **范围**：本书 102/102 章 ALL 受影响（卫图/雪中悍刀行同样 100% 中招）
- **机制**：`HarnessControllerService._apply_actions_to_draft` (imitation_harness_service.py:241-257) 把 action queue 拼接到 `draft.draft_text` 末尾作为 telemetry，但 writer-imitate-range 直接把 `draft_text` 当成最终产物落盘
- **CLI 显示侧**已经 split 屏蔽（cli/app.py:3149/3195/3279 都做了 `.split("【Harness Action Queue】", 1)[0]`），但 JSON 落盘和 FULL 聚合没做相同处理
- **后果**：本书 fullbook 共含 1127 处 `[P|...]` 标记 + 调试尾巴

### 发现 2: scaffold-only 章节
- **数量**：本书 23/102 章 = 22%
- **scaffold-only 章节列表**：[2, 15, 21, 25, 27, 34, 37, 42, 51, 58, 67, 68, 69, 78, 80, 81, 82, 83, 84, 85, 87, 93, 96]
- **机制**：当 LLM 调用失败/超时/降级，harness fallback 输出结构化骨架（`【章节目标】场景1...场景2...`）而非 prose
- **后果**：FULL md 里夹着没有真正正文的"占位章节"

### 已应用的修复
- `scripts/clean_imitation_drafts.py` — 离线清洗工具（regex 剥离 actq + 标记 scaffold-only）
- `output/whole-book-zhuxian-FULL/诛仙-imitation-fullbook-clean.md` — 清洗后 FULL（**实际可用**）
- `output/whole-book-zhuxian-FULL/contamination-report.json` — 完整污染清单
- 本工作区 ch2-5 .md 已用 --clean 重新渲染

### 修复评估
- 离线清洗：已就绪，本次 review 可直接使用
- **根因修复（待办）**：
  - [ ] writer-imitate-range 落盘前 strip `【Harness Action Queue】` 之后的内容
  - [ ] `whole-book-imitation-export` / `_write_writer_imitation_outputs` 同步处理
  - [ ] scaffold-only fallback：harness 应该 mark 出来而不是当作 final_draft 落盘

### 影响范围估算
- 三本完本共 297 章，**47 章 scaffold-only（16%）+ 297 章全部含 actq 尾巴（100%）**
- 之前所有"avg 1700-2200 字/章"统计被高估了 **40% 左右**（含尾巴）
- 真实有效 prose：约 **37.7 万字 / 250 章 = 1508 字/章**（不是之前报告的 ~2000）
