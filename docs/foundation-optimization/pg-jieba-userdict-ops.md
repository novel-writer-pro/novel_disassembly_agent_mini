# 领域词典接入 pg_jieba 运维指南

> 本文讲**运维侧**如何把 `DomainDictionaryService` 自动产出的 `jieba-user-dict.txt` 加载进 PostgreSQL 的 `pg_jieba` 扩展，让 FTS 分词真正受益于领域词典。
>
> 应用侧（生成两份词典文件）已在 `CL-foundation-domain-dict-jieba-01` 完成；本文只覆盖 PG 侧的安装、挂载、reload 三步。

---

## 0. 前置确认

应用层每次 materialization 后会在 `runtime_cache_dir`（默认 `.cache/novel-analyzer/`）写出两个文件：

| 文件 | 用途 | 是否稳定 |
|------|------|----------|
| `domain-dict.txt` | 纯词表，供关键词匹配 / entity-exact lane 消费 | 是 |
| `jieba-user-dict.txt` | `<term> <freq> <pos>` 格式，**运维侧需要的就是它** | 是 |

`retrieval_service.py:_fts_config_name()` 已经会自动优先选用 `jiebacfg` / `jiebaqry`（如果 PG 里装了 `pg_jieba`），所以运维动作只剩**装扩展 + 挂 userdict**。

---

## 1. 安装 pg_jieba（PostgreSQL 扩展）

### 1.1 Docker 部署（推荐）

```bash
docker run -d --name novel-pg \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=novel_analyzer \
  -v novel-pg-data:/var/lib/postgresql/data \
  wangqiru/pg_jieba:latest
```

### 1.2 源码编译（生产环境）

参考上游 `https://github.com/jaiminpan/pg_jieba`：

```bash
git clone https://github.com/jaiminpan/pg_jieba.git
cd pg_jieba && git submodule update --init
mkdir build && cd build && cmake .. && make -j && sudo make install
```

---

## 2. 启用扩展 + 创建 text search config

连接到业务库执行一次即可：

```sql
CREATE EXTENSION IF NOT EXISTS pg_jieba;

-- pg_jieba 装上后通常自带 jiebacfg / jiebaqry；若没有可手工建：
-- CREATE TEXT SEARCH CONFIGURATION jiebacfg (PARSER = jieba);
-- ALTER TEXT SEARCH CONFIGURATION jiebacfg
--   ALTER MAPPING FOR n,v,a,i,e,l,nr,ns,nt,nz WITH simple;
```

验证：

```sql
SELECT cfgname FROM pg_ts_config
WHERE cfgname IN ('jiebacfg','jiebaqry','simple');
-- 期望至少看到 jiebacfg
```

一旦 `jiebacfg` 可见，`RetrievalService` 下次查询会自动切到它（见 `retrieval_service.py:290-303`）。

---

## 3. 挂载项目生成的 userdict

`pg_jieba` 的 userdict 路径在扩展初始化时读取，**不是**运行时随便拎个文件就能热插拔。两种挂载方式：

### 3.1 启动前软链接（推荐）

把项目 runtime_cache 下的 `jieba-user-dict.txt` 软链到 pg_jieba 的 userdict 目录：

```bash
# Docker 场景：宿主机挂一个 volume 给容器
HOST_DICT=$(pwd)/.cache/novel-analyzer/jieba-user-dict.txt
docker run -d --name novel-pg \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -v "$HOST_DICT:/usr/share/postgresql/14/tsearch_data/jieba_user.dict" \
  wangqiru/pg_jieba:latest
```

> 路径里的 `14` 对应 PostgreSQL 版本；`jieba_user.dict` 是 pg_jieba 识别的默认 userdict 名称，不同发行版可能叫 `user.dict`，以镜像内实际路径为准：`docker exec novel-pg ls /usr/share/postgresql/*/tsearch_data/`。

### 3.2 重启拉起新词

每次应用层向 `jieba-user-dict.txt` 追加了新词（例如跑完新一批章节分析），都需要**让 pg_jieba 重新读 userdict**：

```bash
docker restart novel-pg
```

pg_jieba 目前**不支持**运行时热重载 userdict（上游已知限制）；重启是必要动作。如果业务对 downtime 敏感，建议：
- 用双 PG 实例蓝绿
- 或接受每天一次定时重启的运维窗口

---

## 4. 验收

### 4.1 SQL 级分词测试

```sql
SELECT to_tsvector('jiebacfg', '卫图修炼养生功');
-- 未加 userdict:  '修炼':2 '养生':3 '卫':1 '图':2 '功':4
-- 加了 userdict:  '卫图':1 '修炼':2 '养生功':3   ← 期望
```

### 4.2 BM25 召回回归

用预设的 20 条 query（含专有名词）跑 `RetrievalService.search`，对比加载 userdict 前后：

| 指标 | 目标 |
|------|------|
| 专有名词 query 召回率 | +20% 以上 |
| top-5 命中率 | +15% 以上 |
| 非专有名词 query | 不退化（容差 ±2%） |

### 4.3 失败时如何回退

`retrieval_service.py:290-303` 的逻辑：`jiebacfg` 不存在会自动回落 `simple`。因此安全回退路径 = `DROP EXTENSION pg_jieba` 或把扩展挪出 search_path，应用层**不需要改代码**。

---

## 5. 应用层与运维层的契约

| 动作 | 归属 | 触发时机 |
|------|------|----------|
| 产出 `jieba-user-dict.txt` | 应用（`DomainDictionaryService`） | 每次 `update_from_branch` / `update_from_chapter` |
| 装 pg_jieba / 建 text search config | 运维 | 环境初始化一次 |
| 重启 PG 让 userdict 生效 | 运维 | 词典文件变化后 |
| 选用 `jiebacfg` 做 BM25 查询 | 应用（`retrieval_service`） | 自动，扩展在则用 |

**关键边界**：应用层只负责写好 `<term> <freq> <pos>` 格式；是否真正加载到 PG 取决于运维动作。应用层**不会也不应该**通过 SQL 去 `load_dict`——那是扩展自身的职责。

---

## 6. 已知限制 & 未来

- **无热重载**：上游 pg_jieba 暂无 `pg_jieba.reload_userdict()` 函数；社区有 PR 但未合。
- **多租户**：若一台 PG 服务多个 branch，jieba_user.dict 是全局的，所有 branch 的词会混在一起；目前实现接受这个简化。
- **量级**：词典破万条后 PG 启动慢，建议配合 `domain-dict.txt` 人工 trim 再同步到 pg_jieba。

---

## 附：快速检查清单

- [ ] `SELECT extversion FROM pg_extension WHERE extname='pg_jieba';` 返回非空
- [ ] `SELECT cfgname FROM pg_ts_config WHERE cfgname='jiebacfg';` 返回一行
- [ ] 容器内 `ls /usr/share/postgresql/*/tsearch_data/jieba_user.dict` 文件存在且非空
- [ ] `SELECT to_tsvector('jiebacfg', '卫图修炼养生功');` 切出 `'卫图'` 一词
- [ ] 重启后以上仍然成立
