# P0 底座维护清单（领域词典 → pg_jieba → bm25_vector）

> 本文档是 **P0 链路的运维 checklist**，用于：
> - 新章节分析后的字典刷新
> - 新小说接入后的 baseline 验证
> - 周期性的健康检查
> - 出问题时的快速定位
>
> 配套读物：[`p0-quickstart-and-handoff.md`](./p0-quickstart-and-handoff.md)（操作手册）、[`pg-jieba-userdict-ops.md`](./pg-jieba-userdict-ops.md)（运维细节）、[`p0-final-benchmark-20260513.md`](./p0-final-benchmark-20260513.md)（基准数据）。

---

## 1. 日常字典刷新（每次新一批章节分析完成后）

每次有 ≥30 个新章节通过分析进 DB 后，执行：

```bash
cd /home/user/ai-books && set -a && source .env.local && set +a

# 1. 重建词典文件
python -m novel_analyzer.cli.app domain-dict-rebuild
```

- [ ] 输出 `total new=N dict_size=M` 中 N > 0（说明新章节带入了新词条）
- [ ] M 不超过 10000（超过需评估 PG 启动时间影响）

```bash
# 2. 同步到 PG 容器挂载目录（含 quality filter）
python <<'PY'
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
```

- [ ] 输出 `wrote N terms`，N 应略小于 dict_size（过滤掉了长句/标点词条）

```bash
# 3. 重启 PG 容器
sudo docker restart d2-pg17 && sleep 15
sudo docker ps | grep d2-pg17
```

- [ ] 容器状态显示 `Up <N> seconds (healthy)`

```bash
# 4. 重建 bm25_vector 列（必须新连接，CLI 自动开新连接）
python -m novel_analyzer.cli.app bm25-reindex --confirm
```

- [ ] 输出包含 `tokenizer check: '养生功':2 '路朝歌':1 '龟息养气功':3`（三个测试词都被识别为单 lexeme）
- [ ] 输出 `done. N rows reindexed.`，N 等于 retrieval_documents 总数

```bash
# 5. 验证
python -m novel_analyzer.cli.app retrieval-benchmark <branch_id> \
  --output-file /tmp/post-bench.json
```

- [ ] simple Recall@5 > 0.4（任何分支都该达到，否则字典或 reindex 出问题）

---

## 2. 新小说接入 baseline

每次导入一部新小说并完成 ≥40 章分析后，跑一次 baseline：

- [ ] `domain-dict-rebuild` 在新分支上 +N >= 50 新词条
- [ ] 同步 + 重启 + reindex 走完
- [ ] `retrieval-benchmark <new_branch_id>` 输出：
  - simple Recall@5 落在 [0.4, 1.0] 区间（典型范围）
  - 如果 < 0.4，先检查 `keyword_list` 是否被噪声污染（参考 `entity-extraction-noise-diagnosis-20260513.md`）
- [ ] 如果通过 baseline，把数字归档进 `p0-final-benchmark-20260513.md` 的 §1 表格

---

## 3. 健康检查（建议每周）

```bash
cd /home/user/ai-books && set -a && source .env.local && set +a
```

### 3.1 数据完整性

```bash
python -m novel_analyzer.cli.app rematerialize-retrieval
```

- [ ] dry-run 输出 `docs missing chunks: 0`；如果非 0，加 `--confirm` 修复

### 3.2 字典 / pg_jieba 状态

```bash
python -c "
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from sqlalchemy import text
s = Settings()
factory = create_session_factory(s)
with factory() as session:
    cfg = session.execute(text(\"SHOW pg_jieba.user_dict\")).scalar()
    print('user_dict:', cfg)
    v = session.execute(text(\"SELECT to_tsvector('jiebacfg', '路朝歌养生功')::text\")).scalar()
    print('tokenizer:', v)
"
```

- [ ] `user_dict` 包含 `novel_analyzer`
- [ ] 测试串切出 `'养生功':2 '路朝歌':1`（不是 `'路' '朝歌' '养生' '功'`）

### 3.3 bm25_vector 列状态

```bash
python -c "
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
from sqlalchemy import text
s = Settings()
factory = create_session_factory(s)
with factory() as session:
    row = session.execute(text('''
        SELECT attname, attgenerated FROM pg_attribute
        JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
        WHERE pg_class.relname='retrieval_documents' AND attname='bm25_vector'
    ''')).first()
    print('attgenerated:', repr(row[1]))
"
```

- [ ] 输出 `attgenerated: 's'`（stored generated column，不是空字符串）
- [ ] 如果是 `''`（regular column），说明被某次诊断脚本破坏了，需要 `bm25-reindex --confirm` 恢复

### 3.4 主分支基准回归

```bash
python -m novel_analyzer.cli.app retrieval-benchmark \
  72da24e9-e65c-45a9-836d-957c4ae783ec \
  --output-file /tmp/health-check.json
```

- [ ] simple MRR > 0.4 （基准分支锁定值是 0.68）
- [ ] simple Recall@5 > 0.6 （基准分支锁定值是 0.81）
- [ ] 如果数字大幅下降（>20%），先检查字典文件大小、pg_jieba 配置、bm25_vector 状态

---

## 4. 故障定位决策树

```
症状：retrieval-benchmark 分数突然变差
   │
   ├── attgenerated ≠ 's'？
   │     └── 是 → 跑 bm25-reindex --confirm（修复列定义）
   │
   ├── pg_jieba.user_dict 不含 novel_analyzer？
   │     └── 是 → 检查 docker-compose env, 重启容器
   │
   ├── tokenizer 测试串切不出单词？
   │     └── 是 → 检查 /opt/postgresql/share/tsearch_data/novel_analyzer.dict
   │             文件存在性 + 重启容器
   │
   ├── 词典文件 < 1000 词？
   │     └── 是 → 跑 domain-dict-rebuild（可能 DB 被清空了）
   │
   ├── docs/chunks/embeddings 不一致？
   │     └── 是 → 跑 rematerialize-retrieval --confirm
   │
   └── 全部正常但分数还是差
         └── 看 entity-extraction-noise-diagnosis-20260513.md
```

---

## 5. 不要做的事（教训汇总）

- ❌ **直接 `DELETE FROM retrieval_chunks`** — 会留下孤儿 retrieval_documents（已收割教训，工具 `rematerialize-retrieval` 是为此而生）
- ❌ **试图 UPDATE bm25_vector** — 它是 generated column，UPDATE 静默失败
- ❌ **在重启 PG 之前的连接里跑 bm25-reindex** — backend 还有旧 tokenizer 缓存，重建出来的列还是旧分词
- ❌ **把 jieba-user-dict.txt 直接当 novel_analyzer.dict 用** — 包含长句（"卫图三更喂马并完成夜间劳作"），会污染 jieba 内部 trie
- ❌ **手工 `pg_jieba.user_dict = '...'` 改成只有 novel_analyzer** — 会丢掉 d2_core/items/skills 三本游戏字典（虽然不影响小说，但破坏环境对称性）

---

## 6. 锁定的基准（作为回归参照）

2026-05-13 锁定值，环境：5 本小说 587 docs，4869 词字典：

| 分支 | 角色 | simple R@5 | simple MRR |
|---|---|---|---|
| 72da24e9 | 卫图（参照） | 0.8061 | 0.6815 |
| e5becabd | 诛仙 | 0.9412 | 0.7975 |
| 2cd9c1ff | 雪中悍刀行 | 0.7333 | 0.7111 |

如果上述任一指标下降 >20%，启动故障定位决策树（§4）。
