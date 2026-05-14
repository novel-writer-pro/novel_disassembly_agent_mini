# Whole-Book 仿写流水线 quickstart

> 2026-05-14 验证：在卫图分支（72da24e9）上，`writer-imitate-range` 5 章测试通过，单章 ~1k 字真实中文正文 + 多轮 refinement。
>
> 这是 **whole-book 真书完本** 工作流程的最小可工作版本（MVP）。

---

## 1. 一分钟读懂

整本仿写不是单一命令，而是 4 层 CLI 的级联：

| 层 | 命令 | 作用 |
|---|---|---|
| 章节级 dry-run | `imitate-chapter <branch> <ch> <goal> --use-llm` | 单章 LLM 生成 + 推理注释，~1k 字 |
| 章节级 sandbox | `run-whole-book-imitation --execute --use-llm` | 多章 sandbox 队列 + carry-over，但只产出 240-char 摘要 |
| 章节级落盘 | `imitate-chapter-writer <branch> <ch> <goal> --use-llm` | 真正写盘到 `output/writer-imitate-ch{N}.json` + `.md` |
| **批量落盘** | **`writer-imitate-range <branch> "ch:goal" ... --use-llm`** | **多章 + 多轮 refinement，写盘** |

**只用最后一个就够**——`writer-imitate-range` 是真正的 whole-book 入口。前三个是骨架/单元入口，留作调试。

---

## 2. 最小工作流程（5 章实测）

```bash
cd /home/user/ai-books && set -a && source .env.local && set +a

mkdir -p output/whole-book-{novel}-{n}ch

python -m novel_analyzer.cli.app writer-imitate-range \
  <branch_id> \
  "2:延续资源铺垫与人物互动" \
  "3:主角获得功法后的修炼起点" \
  "4:主角面对家族压力的反应" \
  "5:婚事与小家庭建立" \
  "6:面对外界变局的初次决断" \
  --output-dir output/whole-book-{novel}-{n}ch \
  --use-llm --max-rounds 2
```

输出：
- `output/.../writer-imitate-range-2-6.json`（结构化结果，含 method_notes / risk_gate_notes / 多轮 refinement 历史）
- `output/.../writer-imitate-range-2-6.md`（markdown 渲染版，正文 + 章节元数据）

时间成本：5 章 × max_rounds=2 ≈ 10 分钟（取决于 LLM 延迟）。

---

## 3. 实测数据（卫图分支，2026-05-14）

| ch | title | 字数 | verdict | stop_reason |
|---|---|---|---|---|
| 2 | 二姑卫荭 | 1007 | needs_revision | critical_action_required |
| 3 | 养生功法 | 951 | needs_revision | critical_action_required |
| 4 | 珍惜眼下 | 978 | needs_revision | critical_action_required |
| 5 | 婚事敲定 | 1950 | needs_revision | critical_action_required |
| 6 | 郑国官兵 | 2007 | needs_revision | critical_action_required |
| **总计** | | **6893** | | |

LLM 配置：`https://card.nassaapi.xyz/v1` + `deepseek-v4-pro`。

**质量评估**（人工抽样）：
- 文体一致：保持原作的第三人称有限视角 + 中等节奏 ✓
- 人物动机连贯：卫图的"务实、隐忍"性格在 5 章中稳定 ✓
- 章间连续性：ch5→ch6 婚后家庭→外界变局过渡自然 ✓
- 设定替换：world-map / character-map 在 LLM 提示里生效（但实测使用了原命名"卫图"而非映射后的"陈默"，需要 mapping 强制传入）⚠

---

## 4. 已知限制

1. **`final_verdict=needs_revision`**：max_rounds=2 不足以触发 `quality-pass`。生产建议 max_rounds=4-6。每多一轮成本翻倍。
2. **`stop_reason=critical_action_required`**：harness 仍然挂在某个 critical action（rhythm / ending_hook / character_motivation 等）上。需要：
   - 增加 max_rounds
   - 或调整 quality gate 阈值
   - 或 manual_eval 介入（见 `loom/handoff.md` mailbox 流程）
3. ~~**mapping_pack 似乎不生效**~~：**已修复**（commit `584758f`）。`writer-imitate-range` 现在接 `--world-map` / `--character-map` / `--faction-map` / `--power-map` / `--rule-override` / `--forbidden-transformation`，会注入到 LLM prompt。
   - 5 章实测：跨题材映射（仙侠→科幻）在 15K 字中 0 leak / 20 mapped hits，并且 LLM 整体翻译语境（非字面替换）。
   - 详见 `whole-book-progress-20260514.md` §"验证：mapping_pack 注入修复"。
4. **LLM 成本**：deepseek-v4-pro 是 thinking 模型，单章 token 消耗 ~5k input + ~3k output（含 reasoning_tokens）。100 章 ≈ 80 万 token / 次完整 run。

---

## 5. 下一步候选（按 ROI 排序）

| 候选 | 价值 | 成本 |
|---|---|---|
| **A. 在卫图上跑完 100 章 + 落盘** | 第一份 whole-book 完本样例，可对照原书做人工评估 | 长（~3 小时持续 LLM 调用） |
| B. 跑诛仙/雪中悍刀行 5 章批量 | 验证不同题材的 prompt 鲁棒性 | 中（~30 min/小说） |
| C. 修 mapping_pack 不生效的 bug | 让 character_map 真正影响生成 | 小（半天 + LLM 测试） |
| D. 调高 max_rounds 看 verdict 变化曲线 | 知道多少轮才能到 quality-pass | 小（试 max_rounds=4 跑 1 章） |
| E. 接 loom 的 mailbox 人工评估流程 | 让 `needs_revision` 章节进入人工 review | 中（需理解 `bootstrap_weitu_validation_workspace`） |

**推荐 D → A**：先用最小代价（1 章 × max_rounds=4）验证质量曲线，再决定是否值得跑完 100 章。

---

## 6. 给下一会话的 handoff

**已验证**：
- `writer-imitate-range` 端到端工作（5 章卫图测试）
- LLM 配置：`https://card.nassaapi.xyz/v1` + `deepseek-v4-pro` + `sk-zUMzSU0gxTVtyHr9Gr4T6poyCmifP84bOhhwW1B7JIVHn9st`
- 输出位置：`output/whole-book-{novel}-{n}ch/`（gitignored）

**未验证**：
- 100 章长程稳定性（LLM 中断 / token 上限 / 多轮 refinement 累积）
- 跨小说的 prompt 鲁棒性（只测了卫图）
- 跨章节连续性如何在 verdict=needs_revision 下劣化

**5 个分支可选**（来自 `p0-quickstart-and-handoff.md`）：

| novel | branch_id | docs |
|---|---|---|
| 卫图（示例） | `72da24e9-e65c-45a9-836d-957c4ae783ec` | 103 |
| 掌门低调点 | `2ac6f639-d2fc-49b2-b4a9-58a5aecfc673` | 41 |
| 诛仙 | `e5becabd-e2f3-4045-9249-fa91f382dc9a` | 115 |
| 武道宗师 | `8af4f620-0c3a-4629-82bb-b30a1a48b30e` | 112 |
| 雪中悍刀行 | `2cd9c1ff-aba2-4d92-a42e-b2e373baaab7` | 113 |

**入口文档**：本文 + `loom/handoff.md` + `chapter-imitation-method.md` §10。
