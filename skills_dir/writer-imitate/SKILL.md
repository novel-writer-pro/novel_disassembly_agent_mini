---
name: writer-imitate
description: 写手一站式仿写工作流 — 拆书→仿写→风险控制→续写笔记
---

# Writer Imitate — 拆书→仿写 一站式工作流

面向写手的完整仿写能力：从已拆解的小说中抽取源章骨架，生成约束包，产出仿写草稿，通过六维质量检查（节奏/读者/对话/风格/自检/研究），进行风险审查，最后输出结构化的续写笔记。

## 使用方式

### CLI 单章仿写（推荐入门）

```bash
novel-analyzer writer-imitate <branch_id> <source_chapter_index> "<target_goal>"
```

示例：

```bash
novel-analyzer writer-imitate abc123 3 "延续主角获得功法后的克制成长"
```

### CLI 多章连续仿写（自动传递续写笔记）

```bash
novel-analyzer writer-imitate-range <branch_id> "3:延续资源铺垫" "4:延续成长线"
```

### 使用 LLM 生成正文

```bash
novel-analyzer writer-imitate <branch_id> 3 "延续主角获得功法后的克制成长" --use-llm --max-rounds 2
```

## 输出说明

### 写手友好概要（CLI stdout）

```
═══════════════════════════════════════════════════════════
  仿写报告 — 第3章 → 第4章
═══════════════════════════════════════════════════════════
  源章节: 第3章 养生功法
  仿写目标: 延续主角获得功法后的克制成长
  综合评分: 78/100
  风险等级: low
  最终判定: needs_revision
  停止原因: quality_iteration_required
───────────────────────────────────────────────────────────
  【仿写草稿】
  标题: 第3章 养生功法
  正文预览: ...

  【阻塞问题】
  ✗ draft_too_short_for_gate

  【建议修复】
  → 补足中段阻力、行动转向与章尾钩子之间的承接。

  【续写笔记 — 下一章注意事项】
  章尾钩子: 卫图决定从明天开始正式修炼...
  活跃人物: 卫图, 二姑, 黄宅管事
  关系状态: 二姑的态度仍保持距离
  未解线程: 命格的潜力尚未完全揭示
  世界规则: 养生功修炼需要时间积累
  硬约束: 不要无铺垫升级战力
  禁止动作: 不要直接抄原文句式
  风险关注: 补足中段阻力与章尾钩子
  写作建议: 下次仿写时优先补足中段阻力
───────────────────────────────────────────────────────────
```

### JSON 完整报告（--output）

包含：
- `draft_text` — 仿写正文
- `rhythm` — 节奏分析（速度、张力曲线、钩子强度）
- `reader_engagement` — 读者模拟反馈（参与度、困惑点）
- `dialogue_quality` — 对话设计诊断
- `style_calibration` — 风格校准结果
- `risk_level` / `top_risks` — 风险审查
- `blocking_issues` / `recommended_actions` — 阻塞与修复
- `continuation_notes` — 结构化续写笔记
- `harness_report` — 完整 harness 原始数据

### 续写笔记（ContinuationNotes）结构

| 字段 | 说明 |
|------|------|
| `ending_hook` | 当前章尾钩子，下一章应承接 |
| `active_characters` | 当前活跃人物 |
| `relationship_state` | 关系状态快照 |
| `unresolved_threads` | 未解伏笔/线程 |
| `world_rules` | 当前生效的世界规则 |
| `hard_constraints` | 不可违反的硬约束 |
| `soft_constraints` | 建议遵守的软约束 |
| `forbidden_moves` | 明确禁止的动作 |
| `risk_focus` | 下一章需重点关注的 risk |
| `continuity_risks` | 连续性风险点 |
| `quality_reminders` | 质量提醒 |

## 工作流

```
源章 (已拆书)  ──→ 提取骨架/事实/关系
                         │
                    ┌─────▼──────┐
                    │ 约束包生成  │  imitation-constraint-pack
                    └─────┬──────┘
                          │
                    ┌─────▼──────┐
                    │  草稿生成   │  skeleton draft / LLM draft
                    └─────┬──────┘
                          │
          ┌───────┬───────┼───────┬───────┬───────┐
          ▼       ▼       ▼       ▼       ▼       ▼
       节奏    读者模拟  对话设计  风格校准  自检    研究
     analyzer  sim     designer calib  self-check  research
          │       │       │       │       │       │
          └───────┴───────┴───┬───┴───────┴───────┘
                              │
                        ┌─────▼──────┐
                        │  Preflight  │  确定性预检
                        └─────┬──────┘
                              │
                        ┌─────▼──────┐
                        │ Gate/Risk   │  门控+风险审查
                        └─────┬──────┘
                              │
                    ┌─────────▼──────────┐
                    │  写手报告 + 续写笔记  │
                    └────────────────────┘
```

## 相关能力

- **风格指纹**: `novel-analyzer writer-style-fingerprint <branch_id>`
- **跨书对比**: `novel-analyzer writer-compare-novels <src_branch> <ref_branch>`
- **Harness 调试**: `novel-analyzer harness-imitation <branch_id> <idx> "<goal>"`
- **LLM 生成**: 添加 `--use-llm` 参数使用 LLM 生成正文而非骨架草案

## 前置条件

1. 已完成小说的导入和拆书（`ingest` + `start-run` + `analyze-range`）
2. 至少完成了目标源章的拆书分析
3. 数据库可连接

## 注意事项

- 默认生成 skeleton draft（结构草案），需要 `--use-llm` 才会调用 LLM 生成正文
- 续写笔记是结构化的，可以直接作为下一章的输入
- 风格指纹需要至少 2 章已拆书数据才能产出有意义的结果
- 跨书对比需要两部小说都已完成拆书
