# 同题材仿写质量门槛 — 长跑验证交接 (2026-05-15)

> **目的**：自动诊断 + 修复已上线（commit `9704127`）。本文档给出在新环境**人工验证**修复是否生效的完整步骤。
>
> **预期工时**：5-章 spike ~10 min；30-章对比 ~60-90 min；100-章重跑 ~3-5 h（取决于 LLM 速度）。
>
> **互补文档**：
> - [ops-debug-manual-20260514.md](./ops-debug-manual-20260514.md) — 环境自检 + 命令速查
> - [chapter-imitation-capability-matrix.md](./chapter-imitation-capability-matrix.md) — 能力总表
> - [whole-book-mapping-scale-20260514.md](./whole-book-mapping-scale-20260514.md) — 跨题材验证基线

---

## 1. 背景：诊断结论一句话

跨题材 mapping 路径达到 99.4% pass / 同题材 baseline 路径 0/307 pass。**经过逐章对比 `policy_summary`，发现唯一的有效差别是 prompt 里的"二次检查"指令。** 同题材 baseline prompt 没有这个 self-verification pass，导致 LLM 在 rhythm/dialogue/motivation/relationship 几个 lane 持续触发 priority-1 medium-severity action，进而 `final_verdict=needs_revision`。

**修复（已上线）**：commit `9704127` 在 baseline prompt 加入了 5 项 self-check（节奏、对话、动机、关系、营销冗余），保留 mapping prompt 的额外二次检查。

**验证假设**：修复后同题材 baseline pass-rate 应从 0% 提升到 ≥50%（保守）/ ≥80%（理想）。

---

## 2. 验证前置：环境自检

```bash
cd /home/user/ai-books
set -a && source .env.local && set +a

# 三件套自检（详见 ops-debug-manual §1）
.venv/bin/python -c "
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from sqlalchemy import text
factory = create_session_factory(Settings())
with factory() as s:
    cfg = s.execute(text(\"SHOW pg_jieba.user_dict\")).scalar()
    print('user_dict:', cfg)  # 应含 novel_analyzer
"

curl -s -m 15 -X POST "$NOVEL_ANALYZER_LLM_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $NOVEL_ANALYZER_LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"'$NOVEL_ANALYZER_LLM_MODEL_NAME'","messages":[{"role":"user","content":"ok"}],"max_tokens":10}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('LLM ok:', d['choices'][0]['message']['content'][:30])"
```

如果上面任一步报错，进 [ops-debug-manual §4](./ops-debug-manual-20260514.md#4-故障定位决策树) 故障定位。

---

## 3. Stage A：5-章 spike（最快验证，~10 min）

**目的**：最低成本确认修复有方向性效果。`pass-rate ≥ 1/5` 即说明 prompt 修复生效；`= 0/5` 说明修复无效，需重诊断。

```bash
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "2:延续资源" "3:功法起点" "4:家族压力" "5:婚事" "6:外界变局" \
  --output-dir /tmp/baseline-spike-after-fix \
  --use-llm --max-rounds 2

# 预期：每章 1500-3000 字，时间 50-180s/章
```

### 验证脚本

```bash
python3 <<'PY'
import json, glob
files = sorted(glob.glob('/tmp/baseline-spike-after-fix/writer-imitate-ch*.json'))
passes = 0
for f in files:
    d = json.load(open(f))
    fd = d['final_draft']
    v = d['final_verdict']
    s = d['policy_summary'].get('overall_score', '?')
    sev = d['policy_summary'].get('highest_action_severity', '?')
    crit = d['policy_summary'].get('highest_action_priority', '?')
    print(f"ch{d['source_chapter_index']:>3}: chars={len(fd['draft_text']):>5} verdict={v:<15} score={s} crit={crit}/{sev}")
    if v == "pass": passes += 1
print(f"\nPASS RATE: {passes}/{len(files)} = {100*passes/len(files):.0f}%")
PY
```

### 判定标准

| pass-rate | 判定 | 下一步 |
|---|---|---|
| ≥ 4/5 | ✅ 修复极强 | 跳到 Stage C 全本验证 |
| 2-3/5 | ✅ 修复生效 | 进 Stage B 30-章对比 |
| 1/5 | ⚠️ 修复部分生效 | 看 stop_reason 分布，可能要再加 self-check 项 |
| 0/5 | ❌ 修复无效 | **STOP**，进 §6 调试路径 |

---

## 4. Stage B：30-章对比（中等强度，~90 min）

**目的**：跟历史 baseline batch (`whole-book-weitu-30ch`) 1:1 对比，区分"运气波动"和"真改善"。

```bash
nohup bash -c '
set -a && source .env.local && set +a
timeout 9000 .venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "31:下山初行" "32:首次试炼" "33:门派交锋" "34:命格觉醒" "35:旧识重逢" \
  "36:暗流涌动" "37:风波再起" "38:抉择关头" "39:身份揭露" "40:阵营选择" \
  "41:绝境突破" "42:同伴相助" "43:重要邂逅" "44:意外收获" "45:旧账清算" \
  "46:阶段总结" "47:新格局" "48:对手再现" "49:关键证据" "50:转折点" \
  "51:实力跃迁" "52:危机解除" "53:格局变动" "54:新旧交替" "55:暗中布局" \
  "56:意外发现" "57:暂时安稳" "58:反派显形" "59:正面交锋" "60:阶段终结" \
  --output-dir output/baseline-after-fix-31-60 \
  --use-llm --max-rounds 2 \
  > /tmp/baseline-after-fix-31-60.log 2>&1
' > /tmp/baseline-after-fix-launch.log 2>&1 &
disown
```

### 监控

```bash
# 进度
ps -o pid,etime,cmd -p $(pgrep -f "writer-imitate-range" | head -1)
tail -3 /tmp/baseline-after-fix-31-60.log
ls output/baseline-after-fix-31-60/writer-imitate-ch*.json 2>/dev/null | wc -l

# 自动恢复次数
grep -c "recovered on attempt" /tmp/baseline-after-fix-31-60.log
grep -c "rejected.*scaffold_only\|rejected.*action_queue" /tmp/baseline-after-fix-31-60.log
```

### 对比验证

```bash
python3 <<'PY'
import json, glob
def stats(d):
    files = sorted(glob.glob(f'{d}/writer-imitate-ch*.json'))
    if not files: return None
    items = [json.load(open(f)) for f in files]
    passes = sum(1 for c in items if c['final_verdict'] == 'pass')
    avg_score = sum(c['policy_summary'].get('overall_score',0) for c in items) / len(items)
    avg_chars = sum(len(c['final_draft']['draft_text']) for c in items) / len(items)
    return {'n': len(items), 'pass': passes, 'avg_score': avg_score, 'avg_chars': avg_chars}

before = stats('output/whole-book-weitu-30ch')  # 历史 baseline (修复前)
after = stats('output/baseline-after-fix-31-60')

print(f"BEFORE (无 self-check prompt):  n={before['n']:>3}  pass={before['pass']:>3}/{before['n']:<3}  avg_score={before['avg_score']:.1f}  avg_chars={before['avg_chars']:.0f}")
print(f"AFTER  (有 self-check prompt):  n={after['n']:>3}  pass={after['pass']:>3}/{after['n']:<3}  avg_score={after['avg_score']:.1f}  avg_chars={after['avg_chars']:.0f}")
print(f"\n  pass-rate delta: {100*(after['pass']/after['n'] - before['pass']/before['n']):+.1f}%")
print(f"  avg score delta: {after['avg_score'] - before['avg_score']:+.1f}")
PY
```

### 判定标准

| pass-rate delta | 判定 |
|---|---|
| +50% 以上 | ✅ 修复显著生效，可宣布 P0 解除阻塞 |
| +20% ~ +49% | ✅ 修复生效，但 gate 仍偏严，写下一轮 prompt 改进点 |
| +5% ~ +19% | ⚠️ 修复部分生效，与 mapping 路径仍有 gap，需配合 harness 调整 |
| < +5% | ❌ 修复无效，重新诊断（§6） |

---

## 5. Stage C：100-章全本重跑（终极验证，~3-5 h）

**目的**：确认修复在长程稳定。**只在 Stage B 显示 ≥+30% delta 时执行**，否则浪费 LLM 调用额度。

```bash
nohup bash -c '
set -a && source .env.local && set +a
timeout 28800 .venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "2:延续资源" "3:功法起点" ... "103:终章" \
  --output-dir output/whole-book-weitu-FULL-after-fix \
  --use-llm --max-rounds 2 \
  > /tmp/weitu-full-after-fix.log 2>&1
' > /tmp/weitu-full-after-fix-launch.log 2>&1 &
disown
```

> **章节目标列表**：从 `output/whole-book-weitu-43ch/writer-imitate-range-61-103.json` + 前批的 chapter_spec 拼出完整 102 章列表。  
> 或者直接从 DB 读：
> ```sql
> SELECT chapter_index, normalized_title FROM chapter_artifacts
> WHERE branch_id='72da24e9-...' AND chapter_index BETWEEN 2 AND 103
> ORDER BY chapter_index;
> ```

### 验证标准

```bash
python3 <<'PY'
import json, glob
files = sorted(glob.glob('output/whole-book-weitu-FULL-after-fix/writer-imitate-ch*.json'))
items = [json.load(open(f)) for f in files]
passes = sum(1 for c in items if c['final_verdict'] == 'pass')
total = len(items)
needs_rev = sum(1 for c in items if c['final_verdict'] == 'needs_revision')

# stop_reason 分布
from collections import Counter
stops = Counter(c['stop_reason'] for c in items)

# scaffold/short 章节
shorts = [c for c in items if len(c['final_draft']['draft_text']) < 500]
scaffolds = [c for c in items if any('scaffold_only' in n for n in c['final_draft'].get('comparison_notes',[]))]

print(f"100-ch baseline AFTER fix:")
print(f"  total: {total}")
print(f"  pass: {passes} ({100*passes/total:.1f}%)")
print(f"  needs_revision: {needs_rev}")
print(f"  short (<500 chars): {len(shorts)}")
print(f"  scaffold-only flagged: {len(scaffolds)}")
print(f"  stop_reason distribution:")
for r, n in stops.most_common():
    print(f"    {r:<40} {n:>3}")
PY
```

### 商用 release 门槛

| 指标 | release-ready 阈值 |
|---|---|
| pass-rate | ≥ 70% |
| short chapter rate | < 5% |
| scaffold-only rate | < 2% |
| 单章成本 | < 200s |

任一指标不达标，写 `release-blockers.md` 列出需要的下轮改进，回到 prompt/harness 调优。

---

## 6. 如果修复无效：重诊断路径

### 6.1 检查 prompt 是否真生效

```bash
# 把当前 prompt 渲染出来看
.venv/bin/python -c "
from novel_analyzer.llm.prompts import build_chapter_imitation_prompt
p = build_chapter_imitation_prompt(
    source_chapter_index=2,
    source_title='二姑卫荭',
    source_excerpt='测试',
    target_goal='测试目标',
    style_axes=['第三人称'],
    scene_beats=['拜访'],
    hard_constraints=['不违背设定'],
    soft_constraints=['连贯'],
)
print(p)
" | grep -A 10 "已通过自检"
```

应该看到节奏/对话/动机/关系/营销 5 项检查。如果看不到 → git log 检查 commit `9704127` 是否真的在你环境里。

### 6.2 检查 harness verdict 阈值

`novel_analyzer/services/imitation_harness_helpers.py` `aggregate_stop_reason()` 第 105-127 行定义 pass/needs_revision 边界。如果 prompt 无效且分数已经 84+，可能门槛设置过严：

| stop_reason 分布 | 含义 |
|---|---|
| 主要 `critical_action_required` | priority-1 + severity high 的 action 触发，prompt 应该减少这些 |
| 主要 `quality_iteration_required` | score < 80 或 gate.needs_human_review，可能要降低 score 门槛 |
| 主要 `risk_revision_required` | risk_overall_level != low，与 prompt 关系不大，可能是源章节固有 |

### 6.3 抽样查看具体 critical action

```bash
python3 <<'PY'
import json
d = json.load(open('output/baseline-after-fix-31-60/writer-imitate-ch31.json'))
print("verdict:", d['final_verdict'])
print("stop:", d['stop_reason'])
print("policy_summary:", d['policy_summary'])
# 注意：单章 ch json 里没有 rounds 字段；要看完整 round/action，必须查 range json
PY

# 完整 round/action 在 range json 里
python3 <<'PY'
import json
d = json.load(open('output/baseline-after-fix-31-60/writer-imitate-range-31-60.json'))
items = d['items']
fail = next((c for c in items if c['final_verdict'] == 'needs_revision'), None)
if fail:
    print("ch", fail['source_chapter_index'])
    # range json 也没有 rounds，只在 final_verdict 顶层
    print("policy_summary:", fail['policy_summary'])
PY
```

> ⚠️ writer-imitate-range JSON **不存 rounds/actions 详情**（被剥离以减小体积）。如需完整 trace，需要单章用 `iterate-imitation` 或 `review-imitation` 跑一次（输出含完整 rounds）。

---

## 7. 验证完成后该做什么

### 如果 pass-rate ≥ 70%（修复成功）

1. 更新 [chapter-imitation-capability-matrix.md](./chapter-imitation-capability-matrix.md) 的"已较强利用的能力"，把"同题材仿写"加入。
2. 更新 [ops-debug-manual-20260514.md §6 锁定基线](./ops-debug-manual-20260514.md#6-锁定的回归基线) baseline 数字。
3. CHANGELOG 加入：`feat(imitation): 同题材 baseline pass-rate 突破到 N%（N/100）`。
4. 移除 [whole-book-mapping-scale-20260514.md] 里"baseline 0/307 不能商用"的注释。
5. 准备公关物料："同题材 AI 仿写"已具备生产级质量。

### 如果 pass-rate 在 50%-69%（修复部分生效）

1. 不要宣布"已解决"，写 `imitation-baseline-improvements-roadmap.md` 列下一轮改进点：
   - dialogue 检查太弱 → 加具体角色台词风格
   - rhythm 检查太抽象 → 加节奏锚点示例
   - motivation 检查不够细 → 显式要求"前情对应行 N"
2. 跨题材产品线可以先商用，同题材产品线标"alpha"。

### 如果 pass-rate < 50%（修复无效或微弱）

1. **revert** commit `9704127`：`git revert 9704127`
2. 重新诊断：可能不是 prompt 而是 harness gate 设计问题。
3. 路径 A：调整 `_aggregate_stop_reason` 软边界（score≥75 即 pass，已经是这样）。
4. 路径 B：开发 prose-polish post-pass（生成完后用更小模型润色，类似 mapping 的 second-pass）。
5. 路径 C：把 baseline 视为不可解，永久建议用户用 mapping_pack 模式（即使是同题材）。

---

## 8. LLM 资源预估

按 `deepseek-v4-pro` via nassaapi 当前价目：

| 阶段 | 章数 | 估时 | 估token | 估成本 |
|---|---:|---:|---:|---:|
| Stage A spike | 5 | 10 min | ~50K | ~$0.5 |
| Stage B 对比 | 30 | 90 min | ~300K | ~$3 |
| Stage C 全本 | 100 | 5 h | ~1M | ~$10 |
| **总计（最坏路径）** | **135** | **~7 h** | **~1.35M** | **~$13.5** |

如果 Stage A 即明确无效，可以早停在 ~$0.5。

---

## 9. 已知 risk + mitigation

| Risk | Mitigation |
|---|---|
| LLM provider 抖动卡住整批 | `nassaapi` 切到 `https://ykhelsrdmyua.usw-1.sealos.app/v1` + `claude-haiku-4.5`（见 [ops-debug §8](./ops-debug-manual-20260514.md#8-llm-endpoints当前可用--已知失效)） |
| Stage C 过半时 LLM 鉴权过期 | 写 cron-style 监控：每 30 min 看 progress 是否前进 |
| scaffold contamination 漏网 | 现已在 service 层 in-flight 检测（commit `4358658`），只在 LLM 一直返回劣化输出时才会持续 fallback |
| 修复 + scaffold 检测共同导致更多 retry → 整体变慢 | 接受。retry 次数应 <10%，详见日志 `recovered on attempt` 计数 |

---

## 10. 历史对照（修复前的真相）

来自 [chapter-imitation-capability-matrix.md](./chapter-imitation-capability-matrix.md) 当前数据：

| 测试 | 章数 | full pass | 修复前 prompt |
|---|---:|---:|---|
| 卫图 baseline | 102 | **0/102** | 无 self-check |
| 诛仙 baseline | 102 | **0/102** | 无 self-check |
| 雪中悍刀行 baseline | 103 | **0/103** | 无 self-check |
| 卫图→科幻 (mapping) | 102 | 102/102 | 含 mapping 二次检查 |
| 诛仙→科幻 (mapping) | 59 | 58/59 | 含 mapping 二次检查 |

**307 章 baseline 0% pass + 161 章 mapping 99.4% pass + score 几乎相同 → prompt 是唯一变量假设的核心证据**。

---

## 11. 完成后请回报这些数字

- Stage A 5-章 pass-rate：__ / 5
- Stage B 30-章 pass-rate：__ / 30 (对比 0/30)
- Stage C 100-章 pass-rate：__ / 100 (对比 0/102)
- 平均生成时间/章（秒）：__
- 平均 score：__（对比 83.7）
- short-chapter rate：__%
- scaffold-only rate：__%
- 异常事件（LLM 抖动、auto-retry 触发次数）：

把这一段填好回到 PR 描述或 git commit message，方便回溯。
