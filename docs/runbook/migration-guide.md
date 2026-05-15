# 迁移运行手册

把 ai-books 这套拆书+仿写流水线从当前机器迁到一个新环境（裸机 / 新容器 / 另一台服务器），同时保留所有已分析数据、运行中状态和模型资产。

> 当前实例规模（用于估算）
> - PG `novel_analyzer` 数据库 523 MB（27 张表，1097 chapter_artifacts，2695 chunk_embeddings）
> - 项目工作区 `/home/user/ai-books` 16 GB（其中 `.cache` 13 GB、`.venv` 746 MB）
> - BGE-M3 ONNX 模型 1.6 GB
> - TEI 模型缓存 6.4 GB（可重新下载，不必迁移）
> - `output/`（22 MB）+ `runs/`（48 MB）

---

## 1. 资源分层

| 层 | 必须迁移 | 可重建 | 路径 / 来源 |
|---|---|---|---|
| **代码** | ✅ | ❌ | `git push` 或 `tar` 整个 `/home/user/ai-books`（去掉 `.venv` `.cache` `.tmp` `node_modules`） |
| **数据库** | ✅ | ❌ | PostgreSQL `novel_analyzer`（527 MB） |
| **PG 扩展** | ✅ | ⚠️ 需要在新机重装 | `pg_trgm 1.6`、`pgvector 0.8.2`、`pg_jieba 1.1.1`、`pg_textsearch 1.1.0` |
| **小说原文** | ✅ | ❌ | `novel_sources.source_path` 指向 `/tmp/*.txt`、`/home/user/txt111/*.txt` 等绝对路径，必须全部带过去并保持路径或重映射 |
| **.env.local** | ✅ | ❌ | LLM key + DB 凭据 |
| **embedding 缓存** | 推荐 | ✅ 可重算 | `.cache/embeddings`（103 MB） |
| **BGE-M3 ONNX 模型** | ✅ | ✅ 可重下载 | `/home/user/huggingface/bge-m3-onnx-int8`（1.6 GB） |
| **TEI 模型缓存** | ❌ | ✅ 可重下载 | `.cache/tei`（6.4 GB），`make tei-prefetch` 重建 |
| **`runs/` `output/`** | 推荐 | ❌ 历史产物丢了就没了 | 工作目录 |
| **`.sisyphus/` `.omx/` `.codex/`** | 可选 | ❌ | 编辑器/agent 状态，跨机器一般不需要 |
| **Python venv** | ❌ | ✅ | 在新机 `pip install -r requirements.txt` 重建 |
| **node_modules** | ❌ | ✅ | 在新机 `npm ci` 重建 |
| **运行中的 supervisor 进程 / `/tmp/booklogs`** | ❌ | ❌ | 跑完或杀掉再迁 |

---

## 2. 源机准备 — 导出顺序

### 2.1 停止所有写入

```bash
ps -ef | grep -E "supervisor.sh|analyze-range|writer-imitate" | grep -v grep | awk '{print $2}' | xargs -r kill
ps -ef | grep -E "uvicorn|next-server" | grep -v grep | awk '{print $2}' | xargs -r kill
```

### 2.2 导出数据库(带 schema + 数据)

> ⚠️ 源机 PG 是 17.5,但系统的 `pg_dump` 可能只是 PG 15(版本不匹配会报 `aborting because of server version mismatch`)。一行命令解决:
>
> ```bash
> # 离线下载 PG17 client deb,解出来直接用,不需要 root
> mkdir -p /tmp/migrate && cd /tmp/migrate
> curl -fsSL "https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-17/postgresql-client-17_17.10-1.pgdg12+1_amd64.deb" -o pgc17.deb
> dpkg-deb -x pgc17.deb pg17-client/
> PG17=$PWD/pg17-client/usr/lib/postgresql/17/bin
> ```

```bash
mkdir -p /tmp/migrate
cd /tmp/migrate

PGPASSWORD=d2pass $PG17/pg_dump \
  -h 127.0.0.1 -p 5432 -U d2 \
  -d novel_analyzer \
  --format=custom \
  --no-owner \
  --no-privileges \
  -f novel_analyzer.dump

# 顺手导一个 plain SQL,便于 grep 排查
PGPASSWORD=d2pass $PG17/pg_dump \
  -h 127.0.0.1 -p 5432 -U d2 \
  -d novel_analyzer --format=plain --no-owner --no-privileges \
  | gzip > novel_analyzer.sql.gz
```

> `--format=custom` 可以并行 restore（`pg_restore -j N`），523 MB 在新机一两分钟搞定。

### 2.3 列出所有引用的小说原文路径，统一收集到一个目录

```bash
PGPASSWORD=d2pass psql -h 127.0.0.1 -p 5432 -U d2 -d novel_analyzer -tA -c \
  "SELECT DISTINCT source_path FROM novel_sources;" \
  > /tmp/migrate/source_paths.txt

mkdir -p /tmp/migrate/novels
while IFS= read -r p; do
  [ -f "$p" ] && cp -v "$p" /tmp/migrate/novels/
done < /tmp/migrate/source_paths.txt
```

> 迁移到新机后，要么把这些文件还原回**完全相同的绝对路径**（最省事），要么 import 后用 SQL `UPDATE novel_sources SET source_path = REPLACE(source_path, '/old/prefix', '/new/prefix')` 批量改。

### 2.4 打包代码 + 关键数据

```bash
cd /home/user
tar --exclude='ai-books/.venv' \
    --exclude='ai-books/.cache/tei' \
    --exclude='ai-books/.cache/rerank-models*' \
    --exclude='ai-books/.mypy_cache' \
    --exclude='ai-books/.ruff_cache' \
    --exclude='ai-books/.pytest_cache' \
    --exclude='ai-books/.tmp' \
    --exclude='ai-books/apps/web/node_modules' \
    --exclude='ai-books/apps/web/.next' \
    --exclude='ai-books/.git' \
    -czf /tmp/migrate/ai-books-code.tar.gz \
    ai-books/

du -sh /tmp/migrate/ai-books-code.tar.gz
```

> `.cache/embeddings`（103 MB）保留在归档里，避免新机重新跑 embedding。
>
> 如果走 git，跳过 tar，直接 `git push`。但 `.env.local`、`output/`、`runs/`、`.cache/embeddings` 通常被 gitignore，得另外打包。

### 2.5 打包 BGE-M3 ONNX 模型

```bash
tar -czf /tmp/migrate/bge-m3-onnx-int8.tar.gz \
  -C /home/user/huggingface bge-m3-onnx-int8/
```

### 2.6 校验

```bash
cd /tmp/migrate
sha256sum * > MANIFEST.sha256
ls -lh
```

期望产物：

| 文件 | 大小级 |
|---|---|
| `novel_analyzer.dump` | ~150–250 MB（custom 压缩后） |
| `novel_analyzer.sql.gz` | ~80 MB |
| `ai-books-code.tar.gz` | ~150–300 MB（含 embedding cache） |
| `bge-m3-onnx-int8.tar.gz` | ~700 MB |
| `novels/` + `source_paths.txt` | 几十 MB |
| `MANIFEST.sha256` | — |

整包 ~1.2 GB，scp / rsync 一次就到。

---

## 3. 目标机部署 — 导入顺序

> 推荐路径：直接走我们已经写好的 `docker/` 里的 compose，把 PG 一起带起来；如果你坚持裸机部署，按下面一步步来。

### 3.1 先决条件（裸机版）

- PostgreSQL 17（官方 apt 源装一下就行）
- Python 3.11
- Node.js 20+
- 用户 `d2` 在 PG 里要存在（或改成你自己的）

### 3.2 安装 PG 扩展

`pg_trgm` / `vector` / `plpgsql` 是标配,但 `pg_jieba` 和 `pg_textsearch` **不在官方 `postgres:17` 镜像里**。两条路:

**a. 用我们已经写好的 `docker/pg.Dockerfile`**(推荐):

```bash
cd ai-books/docker
MIGRATE_DIR=/tmp/migrate docker compose up -d --build postgres
```

`pg.Dockerfile` 在 `postgres:17-bookworm` 上把 `pgvector` 装上,从源码编译 `pg_jieba`,并把 `/tmp/migrate` 挂到容器里 `/migrate`,导入时直接用容器内的 `pg_restore` 即可。

**b. 裸机用 [`pgxman`](https://pgxman.com/) 一行装**:

```bash
pgxman install pg_trgm pgvector pg_jieba
```

或者:

```bash
sudo apt install postgresql-17-pgvector
git clone https://github.com/jaiminpan/pg_jieba && cd pg_jieba && make && sudo make install
```

### 3.3 还原数据库

**docker 方案**(`docker compose up postgres` 已起来):

```bash
docker exec -i novel-analyzer-pg bash -c \
  "PGPASSWORD=d2pass /usr/lib/postgresql/17/bin/psql -h 127.0.0.1 -U d2 -d novel_analyzer -c '
     CREATE EXTENSION IF NOT EXISTS pg_trgm;
     CREATE EXTENSION IF NOT EXISTS vector;
     CREATE EXTENSION IF NOT EXISTS pg_jieba;
     CREATE EXTENSION IF NOT EXISTS pg_textsearch;'"

docker exec -i novel-analyzer-pg bash -c \
  "PGPASSWORD=d2pass /usr/lib/postgresql/17/bin/pg_restore \
     -h 127.0.0.1 -U d2 -d novel_analyzer \
     --no-owner --no-privileges -j 4 /migrate/novel_analyzer.dump"
```

**裸机方案**:

```bash
sudo -u postgres createdb -O d2 novel_analyzer
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -c "
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS pg_jieba;
  CREATE EXTENSION IF NOT EXISTS pg_textsearch;"

PGPASSWORD=d2pass pg_restore \
  -h 127.0.0.1 -U d2 -d novel_analyzer \
  --no-owner --no-privileges \
  -j 4 \
  /tmp/migrate/novel_analyzer.dump
```

或者直接调用我们写好的 `docker/restore.sh`:

```bash
PGPASSWORD=d2pass docker/restore.sh /tmp/migrate/novel_analyzer.dump 127.0.0.1 5432 d2 novel_analyzer
```

> 表结构 + 索引 + 数据一次到位。`alembic_version` 也会带过去,所以 `alembic upgrade head` 在新机会立刻 no-op。

### 3.4 把代码和模型摆到位

```bash
cd /home/user
tar -xzf /tmp/migrate/ai-books-code.tar.gz
mkdir -p /home/user/huggingface
tar -xzf /tmp/migrate/bge-m3-onnx-int8.tar.gz -C /home/user/huggingface
```

### 3.5 还原小说原文

**方案 A — 路径完全一致**（最省事）：

```bash
mkdir -p /tmp /home/user/txt111
sudo cp /tmp/migrate/novels/*.txt /tmp/   # 视原路径分别 cp 到 /tmp、/home/user/txt111 等
```

**方案 B — 改路径前缀**（更干净）：

```bash
mkdir -p /home/user/ai-books/data/novels
cp /tmp/migrate/novels/*.txt /home/user/ai-books/data/novels/

PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -c "
UPDATE novel_sources SET source_path = REPLACE(source_path, '/tmp/', '/home/user/ai-books/data/novels/');
UPDATE novel_sources SET source_path = REPLACE(source_path, '/home/user/txt111/', '/home/user/ai-books/data/novels/');
UPDATE novel_sources SET source_path = REPLACE(source_path, '/home/user/download_novel/', '/home/user/ai-books/data/novels/');"
```

> `analyze-range` 会从 `source_path` 读全文做章节切分，路径错了就跑不动。**这一步必须做对再开 supervisor。**

### 3.6 配置 `.env.local`

打包带过来的 `.env.local` 已含 LLM key 和 DB 配置。检查 DB host / model path 是否与新机一致：

```bash
cd /home/user/ai-books
grep -E "DB_HOST|EMBEDDING_MODEL_PATH|LLM_BASE_URL" .env.local
```

`NOVEL_ANALYZER_EMBEDDING_MODEL_PATH` 必须指向解压后的 ONNX 目录，比如 `/home/user/huggingface/bge-m3-onnx-int8`。

### 3.7 安装运行时依赖

```bash
cd /home/user/ai-books
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
( cd apps/web && npm ci && npm run build )
```

### 3.8 验证

```bash
cd /home/user/ai-books
.venv/bin/python -m novel_analyzer.cli.app db-health
.venv/bin/python -m novel_analyzer.cli.app db-capabilities
.venv/bin/alembic current   # 应该等于 20260513_01

# 抽一个已分析章节看下能不能读
PGPASSWORD=d2pass psql -h 127.0.0.1 -U d2 -d novel_analyzer -tA -c \
  "SELECT title, COUNT(DISTINCT ca.chapter_index) FROM novel_sources n
   JOIN analysis_runs ar ON ar.novel_id=n.id
   JOIN run_branches rb ON rb.run_id=ar.id
   JOIN chapter_artifacts ca ON ca.branch_id=rb.id
   GROUP BY title HAVING COUNT(DISTINCT ca.chapter_index) > 50
   ORDER BY 2 DESC LIMIT 5;"

# 跑一章 smoke
.venv/bin/python -m novel_analyzer.cli.app analyze-range \
  <run_id> <branch_id> <next_chapter> <next_chapter>
```

四个数应该全部 > 100，且对应 `武道宗师 / 诛仙 / 雪中悍刀行 / 掌门低调点`。

### 3.9 启动

**Docker 一体化**（推荐，参考 `docker/README.md`）：

```bash
cd /home/user/ai-books/docker
BGE_M3_ONNX_PATH=/home/user/huggingface/bge-m3-onnx-int8 \
  docker compose up -d
```

**裸机**：

```bash
make api-dev   # 后端 8011
( cd apps/web && npm run start )   # 前端 4173
```

---

## 4. 恢复在途任务

源机有 4 + 1 个 `supervisor.sh` 在跑（`wudao / zhuxian / xuezhong / zhangmen / zhuxian-r2`）。在新机继续：

```bash
mkdir -p /tmp/booklogs
cp /home/user/ai-books/scripts/supervisor.sh /tmp/booklogs/   # 如果脚本已纳入仓库
# 否则从源机 /tmp/booklogs/supervisor.sh 复制过来

nohup /tmp/booklogs/supervisor.sh wudao    a8373cae-... 8af4f620-... 119 754 \
  > /tmp/booklogs/wudao-supervisor.log 2>&1 &
# ... 类推启动其他三个
```

`supervisor.sh` 内部会跳过已 `validated` 的章节，所以可以放心从原起点重启，不会重做。

> 当前进度（截到迁移前最后一次采样）：
> - 武道宗师 219 / 754 章已分析（max=308）
> - 诛仙 200 / 257（已跑完范围，等 r2 retry pass 补漏）
> - 雪中悍刀行 218 / 983（max=307）
> - 掌门低调点 158 / 317（max=307）

---

## 5. 收尾清单

- [ ] 源机 `pg_dump` 成功，新机 `pg_restore` 成功
- [ ] 新机 `alembic current` 与源机一致
- [ ] 4 个 PG 扩展全部 `CREATE EXTENSION` 成功
- [ ] `novel_sources.source_path` 在新机能读到（`test -f` 每条都 OK）
- [ ] BGE-M3 ONNX 路径在 `.env.local` 里指对
- [ ] `db-health`、`db-capabilities` 全绿
- [ ] 前端 `:4173` 能渲染至少一个 `/reader/<branch_id>` 页面
- [ ] 至少跑通一章 `analyze-range` smoke
- [ ] `chapter_artifacts` 总数与源机一致
- [ ] 4 个 supervisor 重新拉起，日志开始增长
