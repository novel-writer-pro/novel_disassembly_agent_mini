# 雪中悍刀行 问题追踪

> 用于把审查发现的问题转化为 cluster review 写回。

## 已知问题（来自系统）

- verdict 全部 needs_revision（与卫图/诛仙/雪中悍刀行三本完全一致 → 是 gate 阈值问题，非本书特性）
- manifest 共 983 章，仅完成前 113 章；本次仿写覆盖 ch1-103，后续若要全本仿写还需继续 batch

## 审查发现

| chapter | 问题类型 | 描述 | 严重度 | 处置 |
|---|---|---|---|---|
|   |   |   |   |   |

问题类型候选：
- `style_drift` — 风格漂移
- `dialogue_voice` — 对话辨识度低
- `rhythm_flat` — 节奏平淡
- `env_thin` — 环境描写薄
- `psyche_thin` — 人物心理薄
- `ooc` — 角色脱离设定
- `world_rule` — 世界规则违和
- `hook_weak` — 钩子无力

## 写回模板

```bash
.venv/bin/python -m novel_analyzer.cli.app set-cluster-status 2cd9c1ff-aba2-4d92-a42e-b2e373baaab7 <cluster_key> resolved \
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
- **数量**：本书 19/102 章 = 18%
- **scaffold-only 章节列表**：[3, 7, 8, 9, 11, 24, 25, 28, 30, 52, 64, 70, 72, 79, 87, 91, 93, 100, 102]
- **机制**：当 LLM 调用失败/超时/降级，harness fallback 输出结构化骨架（`【章节目标】场景1...场景2...`）而非 prose
- **后果**：FULL md 里夹着没有真正正文的"占位章节"

### 已应用的修复
- `scripts/clean_imitation_drafts.py` — 离线清洗工具（regex 剥离 actq + 标记 scaffold-only）
- `output/whole-book-xuezhong-FULL/雪中悍刀行-imitation-fullbook-clean.md` — 清洗后 FULL（**实际可用**）
- `output/whole-book-xuezhong-FULL/contamination-report.json` — 完整污染清单
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
