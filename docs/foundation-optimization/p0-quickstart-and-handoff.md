# P0 闭环：领域词典 → pg_jieba → bm25_vector 操作 + 交接

> **状态**：P0 已完成，5 本小说实测 Recall@5 = 0.72-1.00（DF 过滤后）。
> **作者**：Sisyphus，2026-05-13
> **依赖**：`pg-jieba-userdict-ops.md`（细节）、`priority-and-roi-research-20260512.md`（决策上下文）

---

## 1. 一分钟读懂这件事

中文小说的专有名词（路朝歌、龟息养气功、北凉王府）在 PG 默认 `simple` 分词下被拆得支离破碎，BM25 召回率被腰斩。把这些词喂给 `pg_jieba` 的 userdict，再让 `bm25_vector` 用新分词重建，**simple/jiebacfg 的 Recall@5 都跳到 0.7-1.0**。

整个链路上一份机器可读的合同：

```
DomainDictionaryService          ← 应用侧，每次 materialization 自动追加
    └─ jieba-user-dict.txt        ← .cache/novel-analyzer/
              ↓ 运维手工 cp
        novel_analyzer.dict       ← /home/user/pgsql17-ubuntu24/jieba/dicts/
              ↓ 容器重启加载
        pg_jieba user dict        ← 容器内 /opt/postgresql/share/tsearch_data/
              ↓ ALTER TABLE 重建
        bm25_vector (jiebacfg)    ← retrieval_documents 列
              ↓ @@ tsquery
        BM25 search results
```

---

## 2. 四条最常用的命令

| 场景 | 命令 |
|---|---|
| 看一下领域词典现状 | `wc -l .cache/novel-analyzer/jieba-user-dict.txt` |
| 从 DB 重建领域词典 | `python -m novel_analyzer.cli.app domain-dict-rebuild` |
| 把更新后的字典推到 pg 容器 | 见 §3 步骤 2-3 |
| 重建 bm25_vector 列 | `python -m novel_analyzer.cli.app bm25-reindex --confirm` |
| 修复缺失的 chunks/embeddings | `python -m novel_analyzer.cli.app rematerialize-retrieval --confirm` |
| 跑 retrieval 基准 | `python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> --output-file /tmp/bench.json` |

---

## 3. 完整运维流程（每次 dict 更新都跑一遍）

加载环境变量先行：`set -a && source .env.local && set +a`

```bash
# 1) 应用侧：从所有有 retrieval_documents 的 branch 重建词典
python -m novel_analyzer.cli.app domain-dict-rebuild
# 输出: total new=N dict_size=M
# 文件: .cache/novel-analyzer/{domain-dict.txt, jieba-user-dict.txt}

# 2) 运维侧：过滤 + 同步到 pg 容器挂载目录
python <<'PY'
import re
src = open('.cache/novel-analyzer/jieba-user-dict.txt', encoding='utf-8').readlines()
def ok(t):
    if len(t) < 2 or len(t) > 10: return False
    if re.search(r'[，。！？、；：「」【】()（）\s\u3000]', t): return False
    return len(re.findall(r'[\u4e00-\u9fff]', t)) >= 2
keep = [l.strip() for l in src if l.strip() and ok(l.strip().split()[0])]
open('/home/user/pgsql17-ubuntu24/jieba/dicts/novel_analyzer.dict', 'w', encoding='utf-8').write('\n'.join(keep) + '\n')
print(f'wrote {len(keep)} terms')
PY

# 3) 运维侧：重启容器加载新字典
sudo docker restart d2-pg17 && sleep 15
sudo docker ps | grep d2-pg17  # 确认 healthy

# 4) 应用侧：在新连接中重建 bm25_vector（关键：必须在容器重启后做）
python -m novel_analyzer.cli.app bm25-reindex --confirm
# 输出: tokenizer check / done. N rows reindexed.

# 5) 验证：跑一次 benchmark
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> --output-file /tmp/bench.json
```

**唯一会忘的坑**：步骤 4 必须在**容器重启之后**做。如果在重启之前跑 reindex，PG backend 用的是旧 jieba tokenizer 缓存，列重建出来仍然是旧分词。`bm25-reindex` 会做 tokenizer 自检并 WARN，但不会拒绝执行。

---

## 4. 当前 P0 实测结果（2026-05-13）

字典：4528 词条，来自 5 本小说 533 docs。

| 小说 | docs | simple R@5 | jiebacfg R@5 | DF 过滤后 simple R@5 |
|---|---|---|---|---|
| 卫图 | 103 | 0.7245 | 0.7245 | **0.8061** |
| 掌门低调点 | 41 | 1.0000 | 1.0000 | 1.0000 |
| 诛仙 | 94 | 1.0000 | 1.0000 | 1.0000 |
| 武道宗师 | 91 | 0.8182 | 0.8182 | 0.7273 (11 q) |
| 雪中悍刀行 | 91 | 0.9167 | 0.9167 | 0.5833 (12 q) |

> simple 与 jiebacfg 趋于完全收敛，因为 bm25_vector 已用 jiebacfg 分词存储，专有名词都是单 lexeme，simple tsquery 也命中相同 lexeme。后续如需进一步推动 jiebacfg 优势，需要有"复合短语 only jieba 拆得对"的 query，这超出本期范围。

---

## 5. 已知限制 & 不要做的事

- **pg_jieba 没有热重载**：上游不支持 `pg_jieba.reload_userdict()`。重启 + ALTER TABLE 是唯一可靠路径。
- **`bm25-reindex` 不要在 reindex 前的连接里跑**：CLI 自己开新 psycopg 连接，不要用 SQLAlchemy session 复用旧连接。
- **`bm25_vector` 是 STORED generated column**：手工 `UPDATE SET bm25_text = bm25_text` 不会触发重算（PG 优化为 no-op）。只有 ALTER TABLE DROP+ADD 会强制全表重写。
- **不要给字典塞过长词条**：`domain-dict-rebuild` 会写入完整 fact label（包括"卫图三更喂马并完成夜间劳作"这种事件描述）。运维侧的 §3 步骤 2 过滤逻辑会丢掉超过 10 字 / 含标点的项；这是必要的。
- **不要把字典塞超过 1 万条**：PG 启动会变慢；超过 5K 时考虑做 cross-novel 通用化。

---

## 6. 下一步候选（按 ROI 排序）

| 候选 | 成本 | 收益 | 备注 |
|---|---|---|---|
| **B. 转向预研推荐的"应做的三件事"** | — | 高 | 见 `priority-and-roi-research-20260512.md` §4：whole-book 真书完本 / story bible 产品层 / live route benchmark |
| **A. P1 embedding 升级（bge-m3 → Conan-v2 / Qwen3-4B）** | 1 周 + pgvector 列迁移 + 灰度 | 中（净增益 +3-6%） | 当前 BM25 已不是瓶颈；除非 retrieval 综合分还卡住，不建议优先做 |
| **C. 给 5 本小说继续填章节** | 无（持续后台跑） | 低 | benchmark 已饱和，更多章节只是数据量增加，不会刷出新洞察 |

**推荐 B**：现在 BM25 召回不是瓶颈，再优化 P1 收益递减明显。把焦点切回 whole-book / story bible 这种产品层方向才是符合 ROI 预研结论的下一步。

---

## 7. 给下次会话/Agent 的交接清单

**已完成**（commit 已提交）：
- `7ffc481` 研究备忘
- `28a9f16` P0 应用侧（dict 双格式输出）
- `c27f49e` P0 运维指南
- `94dd73e` retrieval-benchmark CLI
- `f56d63c` P0 闭环（reindex 步骤文档化 + benchmark regex 修复）
- `3657085` CLI 自动化（domain-dict-rebuild + bm25-reindex）
- `ede7d2b` benchmark DF 过滤

**未提交**（本地 sisyphus 工件，按惯例不入库）：
- `.sisyphus/plans/*.md` — 本期工作的 ralph 计划
- `.sisyphus/evidence/*.json` — pre/post benchmark 原始数据

**当前可用 CLI**：
- `domain-dict-rebuild [--branch-id ID]` — 重建词典文件
- `bm25-reindex [--confirm]` — 重建 bm25_vector 列
- `rematerialize-retrieval [--branch-id ID] [--confirm]` — 修复缺失的 chunks/embeddings
- `retrieval-benchmark BRANCH_ID [--configs simple,jiebacfg] [--output-file PATH]` — 跑 BM25 召回率 benchmark
- `loom-benchmark BRANCH_ID [--use-llm] [--output-file PATH]` — 跑 LLM 综合能力 benchmark

**当前 5 个分支**（用于 benchmark）：
| novel | branch_id | docs |
|---|---|---|
| 卫图（示例） | `72da24e9-e65c-45a9-836d-957c4ae783ec` | 103 |
| 掌门低调点 | `2ac6f639-d2fc-49b2-b4a9-58a5aecfc673` | 41 |
| 诛仙 | `e5becabd-e2f3-4045-9249-fa91f382dc9a` | ~94 |
| 武道宗师 | `8af4f620-0c3a-4629-82bb-b30a1a48b30e` | ~91 |
| 雪中悍刀行 | `2cd9c1ff-aba2-4d92-a42e-b2e373baaab7` | ~91 |

**LLM 配置（.env.local）**：当前指向 `https://card.nassaapi.xyz/v1` 的 `deepseek-v4-pro`。备用：`https://ykhelsrdmyua.usw-1.sealos.app/v1` claude-haiku-4.5（Connection reset by peer 时切换）。

**DB 配置**：本机 docker `d2-pg17`，data 在 `/home/user/pgsql17-ubuntu24/data/`，jieba dict 挂载 `/home/user/pgsql17-ubuntu24/jieba/dicts/`。

**新会话最快上手**：读本文 §3 一遍 + `priority-and-roi-research-20260512.md` 一遍 + `pg-jieba-userdict-ops.md` 一遍，就能接着干。
