# 运维调试手册（novel-analyzer）— 2026-05-14

> 给运维 / 接手 agent 的**速查手册**。每个场景 1-3 条命令直接给答案，不绕弯。
>
> 互补文档：
> - `cli-operations-manual.md` — CLI 完整说明（深度）
> - `foundation-optimization/p0-quickstart-and-handoff.md` — P0 入门
> - `foundation-optimization/p0-maintenance-checklist.md` — 健康检查节奏
> - `session-handoff-20260514.md` — 当前会话状态与 next moves

---

## 1. 环境准备（每次 session 开始）

```bash
cd /home/user/ai-books
set -a && source .env.local && set +a
```

**自检 3 件事**（如果某项失败立刻定位）：

```bash
# (1) LLM 通联
curl -s -m 15 -X POST "$NOVEL_ANALYZER_LLM_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $NOVEL_ANALYZER_LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"'$NOVEL_ANALYZER_LLM_MODEL_NAME'","messages":[{"role":"user","content":"ok"}],"max_tokens":10}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('LLM:',d['choices'][0]['message']['content'][:30])"

# (2) PG + pg_jieba
.venv/bin/python -c "
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from sqlalchemy import text
factory = create_session_factory(Settings())
with factory() as s:
    cfg = s.execute(text(\"SHOW pg_jieba.user_dict\")).scalar()
    v = s.execute(text(\"SELECT to_tsvector('jiebacfg', '路朝歌养生功')::text\")).scalar()
    print('user_dict:', cfg)
    print('tokenize:', v)
"

# (3) bm25_vector 列状态
.venv/bin/python -c "
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from sqlalchemy import text
factory = create_session_factory(Settings())
with factory() as s:
    row = s.execute(text(\"\"\"
        SELECT attgenerated FROM pg_attribute
        JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
        WHERE pg_class.relname='retrieval_documents' AND attname='bm25_vector'
    \"\"\")).first()
    print('attgenerated:', repr(row[0]))
"
```

**期望输出**：
- LLM: 非空响应
- user_dict 包含 `novel_analyzer`
- tokenize 切出 `'养生功':2 '路朝歌':1`（不是分散的字符）
- attgenerated: `'s'`（stored generated column）

---

## 2. 常见操作场景

### 2.1 跑 retrieval benchmark（验证 P0 仍生效）

```bash
.venv/bin/python -m novel_analyzer.cli.app retrieval-benchmark \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  --configs simple,jiebacfg \
  --output-file /tmp/bench.json
```

**期望**：simple R@5 ≥ 0.6，jieba R@5 ≥ 0.7。低于此值进 §4 故障定位。

### 2.2 跑 whole-book 仿写（5-章 spike）

```bash
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "2:延续资源" "3:功法起点" "4:家族压力" "5:婚事" "6:外界变局" \
  --output-dir /tmp/spike \
  --use-llm --max-rounds 2
```

**期望**：每章生成 1500-3000 字 / verdict=pass。每章完成后立即看到 `[N/5] chN done in Xs chars=Y verdict=Z`。

### 2.3 跑跨题材仿写（mapping_pack）

```bash
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "2:延续资源" "3:功法起点" \
  --output-dir /tmp/scifi-spike \
  --use-llm --max-rounds 2 \
  --world-map "郑国=星际联邦" --world-map "庆丰府=星辰城" \
  --character-map "卫图=魏拓" \
  --power-map "养生功=星能调息术" \
  --rule-override "封建奴籍体系替换为合同义务工制度"
```

**期望**：100% verdict=pass（mapping_pack 提升质量），生成的正文用映射后的名称（魏拓/星际联邦/星能调息术）。

### 2.4 把 range 输出拆成 per-chapter

```bash
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range-split \
  /tmp/spike/writer-imitate-range-2-6.json
# 默认输出到同目录，每章一个 writer-imitate-ch{N}.json
```

### 2.5 LLM 失败后恢复缺失章节（per-chapter 增量保存的好处）

writer-imitate-range 已经把每章在完成后立刻写入 `output_dir/writer-imitate-ch{N}.json`，所以进程被杀也不丢已完成章节。**只需重启时跳过已存在的 ch**：

```bash
# 查已完成
ls /tmp/spike/writer-imitate-ch*.json | sed 's|.*ch\([0-9]*\)\.json|\1|' | sort -n
# 续跑：只把未完成的 ch 写进 chapter_spec
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-... \
  "8:私塾考量" "10:外出冒险" \
  --output-dir /tmp/spike --use-llm --max-rounds 2
```

### 2.6 P0 字典刷新完整流程（每次 ≥30 章新分析后跑一遍）

```bash
# 1) DB → dict 文件
.venv/bin/python -m novel_analyzer.cli.app domain-dict-rebuild

# 2) 同步到 PG 容器（含质量过滤）
python3 <<'PY'
import re
src = open('.cache/novel-analyzer/jieba-user-dict.txt', encoding='utf-8').readlines()
def ok(t):
    if len(t) < 2 or len(t) > 10: return False
    if re.search(r'[，。！？、；：「」【】()（）\s\u3000]', t): return False
    return len(re.findall(r'[\u4e00-\u9fff]', t)) >= 2
keep = [l.strip() for l in src if l.strip() and ok(l.strip().split()[0])]
open('/home/user/pgsql17-ubuntu24/jieba/dicts/novel_analyzer.dict','w',encoding='utf-8').write('\n'.join(keep)+'\n')
print(f'wrote {len(keep)} terms')
PY

# 3) 重启 PG 容器
sudo docker restart d2-pg17 && sleep 15 && sudo docker ps | grep d2-pg17

# 4) 重建 bm25_vector（必须新连接）
.venv/bin/python -m novel_analyzer.cli.app bm25-reindex --confirm

# 5) 验证
.venv/bin/python -m novel_analyzer.cli.app retrieval-benchmark \
  72da24e9-e65c-45a9-836d-957c4ae783ec --output-file /tmp/post.json
```

### 2.7 修复缺失的 retrieval_chunks/embeddings

```bash
# Dry-run 看影响范围
.venv/bin/python -m novel_analyzer.cli.app rematerialize-retrieval

# 真修复（重跑 ONNX embedding，每章 1-2s）
.venv/bin/python -m novel_analyzer.cli.app rematerialize-retrieval --confirm

# 只修某 branch
.venv/bin/python -m novel_analyzer.cli.app rematerialize-retrieval \
  --branch-id 72da24e9-... --confirm
```

---

## 3. 后台长任务管理

### 3.1 启动后台 whole-book 跑批（脱钩 shell，断网安全）

```bash
nohup bash -c '
set -a && source .env.local && set +a
timeout 9000 .venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  <branch_id> \
  "2:目标A" "3:目标B" ... \
  --output-dir output/run-name \
  --use-llm --max-rounds 2 \
  > /tmp/run-name.log 2>&1
' > /tmp/run-name-launch.log 2>&1 &
disown
```

### 3.2 监控进度（不阻塞）

```bash
# 看进程状态 + elapsed time
ps -o pid,etime,cmd -p $(pgrep -f "writer-imitate-range" | head -1)

# 看最近一行进度（每章一行）
tail -3 /tmp/run-name.log

# 数已完成章节
ls output/run-name/writer-imitate-ch*.json 2>/dev/null | wc -l

# 数自动恢复的章节（auto-retry）
grep -c "recovered on attempt" /tmp/run-name.log
```

### 3.3 杀掉跑飞的进程

```bash
pgrep -af "writer-imitate-range" | grep -v grep | awk '{print $1}' | xargs -r kill
sleep 3
pgrep -af "writer-imitate-range"  # 应该空
```

### 3.4 已知 LLM 输出的速度参考

| LLM provider | 每章耗时 | 100 章预估 |
|---|---|---|
| deepseek-v4-pro via nassaapi (高峰) | ~120s | ~3.5h |
| deepseek-v4-pro via nassaapi (空闲) | ~50s | ~80 min |
| deepseek-v4-flash via deepseek-direct | ~120s | ~3.5h |

如果 etime > 180s/章 仍没有 progress 输出，进 §4 故障定位。

---

## 4. 故障定位决策树

### 4.1 retrieval-benchmark 分数突然变差

```
症状：simple R@5 < 0.6 或 jiebacfg R@5 < 0.7
   │
   ├── 跑 §1 自检的 (3) 看 attgenerated
   │     └── 不是 's' → bm25-reindex --confirm
   │
   ├── 跑 §1 自检的 (2) 看 user_dict
   │     └── 不含 novel_analyzer → 检查 docker-compose env，sudo docker restart d2-pg17
   │
   ├── 跑 §1 自检的 (2) 看 tokenize
   │     └── 切出多个零碎字符 → /opt/postgresql/share/tsearch_data/novel_analyzer.dict 缺失
   │         → 跑 §2.6 step 2 + 3
   │
   ├── 词典文件 < 1000 词
   │     └── 跑 domain-dict-rebuild（DB 可能被清空）
   │
   ├── docs/chunks/embeddings 数量不一致
   │     └── 跑 rematerialize-retrieval --confirm
   │
   └── 全部正常但分数还是差
         └── 看 entity-extraction-noise-diagnosis-20260513.md（上游 entity 噪声）
```

### 4.2 writer-imitate-range 章节字数都很短（<500）

```
症状：每章 chars=375-470 / verdict=needs_revision
   │
   ├── LLM endpoint 不通
   │     └── 跑 §1 自检的 (1)
   │     └── 切到 backup endpoint（见 .env.local）
   │
   ├── auto-retry 但 3 次都失败（comparison_notes 含 "after 3 attempts"）
   │     └── 单独重跑那几章，--max-rounds 4 或 5
   │     └── 命令模板：
   │         python -m novel_analyzer.cli.app writer-imitate-range <branch> \
   │           "<ch>:<goal>" \
   │           --output-dir <same-output-dir> --use-llm --max-rounds 5 [mappings...]
   │
   ├── LLM 返回 HTML 错误页面
   │     └── 上游 proxy 抖动，sleep 60 后重跑
   │
   └── chars <500 + verdict=pass
         └── 这是 short skeleton fallback，不是真 pass。同上重跑
```

### 4.3 mapping_pack 不生效（生成的正文里还有原名）

```
症状：character_map "卫图=魏拓" 但 draft_text 里还出现"卫图"
   │
   ├── 用的是 writer-imitate / writer-imitate-range？
   │     └── 是 → 检查 mapping flag 是否真的传了（dry-run 一次看 mapping_pack 字段）
   │
   ├── 用的是 run-whole-book-imitation？
   │     └── 那个命令只产出 240-char skeleton，不真生成正文
   │     └── 切换到 writer-imitate-range
   │
   ├── 用的是 imitate-chapter？
   │     └── 该 CLI 还未接 --world-map / --character-map（设计 gap）
   │     └── 用 writer-imitate-range 单章模式 + mapping
   │
   └── 都对但 leak 仍 > 5%
         └── source 章节信息密度高，触发 prompt second-pass 后仍有残留
         └── 把那一章单独 rerun --max-rounds 4
```

### 4.4 进程已死但 output 没有 final 文件

```
症状：output 目录有 writer-imitate-ch{N}.json 但没有 writer-imitate-range-{lo}-{hi}.json
   │
   └── per-chapter 增量保存生效，所有完成的章节都在
       → 拿已完成章节 list，把缺失的章节写进新 chapter_spec rerun
       → 命令模板：
         ls output/<dir>/writer-imitate-ch*.json | sed 's|.*ch\([0-9]*\)\.json|\1|' | sort -n
       → 列出哪些 ch 缺失，rerun 那些
```

### 4.5 docker 没起来 / 5432 端口连不上

```
症状：psycopg.OperationalError: connection refused
   │
   ├── 容器没启动
   │     └── sudo docker ps -a | grep d2-pg17
   │     └── 没启动 → sudo docker start d2-pg17 && sleep 15
   │
   ├── 容器启动但 unhealthy
   │     └── sudo docker logs --tail 50 d2-pg17
   │     └── 看启动日志（pg_jieba 加载失败 / 端口被占用 / userdict 找不到）
   │
   └── 进程在但端口被占
         └── sudo lsof -i:5432
         └── 看有没有别的 PG 在跑
```

---

## 5. 不要做的事（教训）

| ❌ 操作 | 原因 |
|---|---|
| `DELETE FROM retrieval_chunks` | 留下孤儿 retrieval_documents；用 `rematerialize-retrieval` |
| `UPDATE retrieval_documents SET bm25_vector = ...` | 是 generated column，UPDATE 静默失败 |
| `UPDATE retrieval_documents SET bm25_text = bm25_text` 期待重算 | PG 检测无变化跳过 generated 列重算 |
| 在重启 PG 之前的连接里跑 `bm25-reindex` | 旧 backend 还有旧 jieba tokenizer 缓存 |
| 直接把 jieba-user-dict.txt 当 novel_analyzer.dict 用 | 会塞入长句（事件描述），污染 jieba trie |
| `pg_jieba.user_dict` 改成只有 `novel_analyzer` | 丢掉 d2_core/items/skills，破坏环境对称性 |
| 在 thin draft 后立刻 rerun 整批 | 已经 per-chapter 增量保存，只 rerun 缺失章节 |
| `docker restart d2-pg17` 后立即 query | 等 15s 再操作（健康检查需时间） |
| 用 imitate-chapter --world-map | 该命令不接 mapping flag；用 writer-imitate-range |
| `localhost:4000/v1` 当 LLM 端点 | 那个 proxy 已知不工作（返回 HTML 错误） |

---

## 6. 锁定的回归基线

### P0 retrieval（卫图分支 72da24e9）

| 指标 | 锁定值 | 容差 |
|---|---|---|
| simple R@5 | 0.81 | ±20% |
| jieba R@5 | 0.84 | ±20% |
| simple MRR | 0.68 | ±20% |
| jieba MRR | 0.70 | ±20% |

### Whole-book 仿写（截至 2026-05-14）

| 测试 | 章数 | full-pass | mapping accuracy |
|---|---|---|---|
| 卫图 baseline | 102 | 0/102 | n/a |
| 卫图 → 科幻 | 102 | 102/102 | 98.0% |
| 诛仙 → 科幻 | 59 | 58/59 | 97.5% |
| 卫图 → 都市 (spike) | 10 | 10/10 | 96.1% |

回归告警门槛：**任一指标下降 > 20% 启动 §4 故障定位**。

---

## 7. 5 个分析过的 branch（即用即查）

| novel | branch_id | docs |
|---|---|---|
| 卫图（参照） | `72da24e9-e65c-45a9-836d-957c4ae783ec` | 103 |
| 掌门低调点 | `2ac6f639-d2fc-49b2-b4a9-58a5aecfc673` | 41 |
| 诛仙 | `e5becabd-e2f3-4045-9249-fa91f382dc9a` | 115 |
| 武道宗师 | `8af4f620-0c3a-4629-82bb-b30a1a48b30e` | 112 |
| 雪中悍刀行 | `2cd9c1ff-aba2-4d92-a42e-b2e373baaab7` | 113 |

---

## 8. LLM endpoints（当前可用 / 已知失效）

```
当前主用（.env.local）：
  base: https://card.nassaapi.xyz/v1
  model: deepseek-v4-pro
  key: 见 .env.local

备用：
  base: https://ykhelsrdmyua.usw-1.sealos.app/v1
  model: claude-haiku-4.5
  注意：可能"用户已被封禁"，要求重激活

已知失效：
  http://localhost:4000/v1 — 返回 HTML 错误页
  https://ai.sixthsense-llm.com/v1 — completion_tokens=0 空响应
```

切换 LLM 的最快方式：编辑 `.env.local` 三行（base / key / model），重新 source。

---

## 9. session 完整命令一图流

```bash
# 启动
cd /home/user/ai-books && set -a && source .env.local && set +a

# 健康检查
.venv/bin/python -m novel_analyzer.cli.app retrieval-benchmark \
  72da24e9-e65c-45a9-836d-957c4ae783ec --output-file /tmp/health.json

# 5 章 spike（验证 LLM 通联 + 整套 prompt）
.venv/bin/python -m novel_analyzer.cli.app writer-imitate-range \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  "2:目标A" "3:目标B" "4:目标C" "5:目标D" "6:目标E" \
  --output-dir /tmp/health-spike --use-llm --max-rounds 2

# 跑完后看：
python3 -c "
import json, glob
for f in sorted(glob.glob('/tmp/health-spike/writer-imitate-ch*.json')):
    d = json.load(open(f))
    fd = d['final_draft']
    print(f\"{d['source_chapter_index']:>3}: {fd['draft_title']!r:>20} chars={len(fd['draft_text']):>5} verdict={d['final_verdict']}\")
"
```

如果上面三步都跑过且符合预期，说明系统从 LLM → P0 → 仿写 pipeline 全链路正常。可以放心进入新一轮迭代。
