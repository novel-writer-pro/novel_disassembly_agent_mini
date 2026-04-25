# novel-analyzer

CLI-first scaffold for a chapter-progressive 小说拆书系统.

## Current scope
- 文本导入与章节规范化
- PostgreSQL / SQLite 双模式配置
- Alembic 迁移驱动的数据库演进
- 运行 / 分支 / checkpoint / chapter_job / raw_output 数据模型
- 逻辑隐藏式回退分支
- 手工产物保留但默认不参与下游上下文
- LangGraph 工作流骨架
- `skills_dir/` + SkillKit(`skillkit[langchain]`) 技能加载
- JSON-first chapter analysis -> PostgreSQL -> Markdown pipeline
- PostgreSQL 内 BM25 / trigram / vector 扩展探测与启用

## Environment

### SQLite default
No extra setup is required; the app falls back to:

```bash
sqlite:///./novel_analyzer.db
```

### PostgreSQL example
```bash
export NOVEL_ANALYZER_DB_DIALECT=postgresql
export NOVEL_ANALYZER_DB_HOST=127.0.0.1
export NOVEL_ANALYZER_DB_PORT=5432
export NOVEL_ANALYZER_DB_USER=d2
export NOVEL_ANALYZER_DB_PASSWORD=d2pass
export NOVEL_ANALYZER_DB_NAME=novel_analyzer
export NOVEL_ANALYZER_DB_ADMIN_NAME=postgres
```

### LLM example
```bash
export NOVEL_ANALYZER_LLM_API_KEY='your-key'
export NOVEL_ANALYZER_LLM_BASE_URL='https://api.vip1129.cc/v1'
export NOVEL_ANALYZER_LLM_MODEL_NAME='gpt-5.4'

# or copy .env.example -> .env.local and fill the secrets locally
```

### Embedding backend example
```bash
export NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
export NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3
export NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=
export NOVEL_ANALYZER_EMBEDDING_CACHE_DIR=.cache/embeddings
```

See `docs/agent-skills-and-embedding.md` for the internal staged agent pipeline and ONNX embedding details.

## Quick start
```bash
poetry install
poetry run novel-analyzer init-db
poetry run novel-analyzer db-health
poetry run novel-analyzer list-skills
poetry run novel-analyzer test-embedding
poetry run novel-analyzer inspect-novel /path/to/novel.txt
poetry run novel-analyzer ingest /path/to/novel.txt --title 'sample'
poetry run novel-analyzer start-run <novel_id> <manifest_id>
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

## Skills
Project-local skills live under:

```bash
skills_dir/
```

The current loader uses SkillKit with:
- `project_skill_dir=./skills_dir`
- `anthropic_config_dir=""`
- no plugin dirs

This keeps skill discovery scoped to repo-local skills only.

## Important semantics
- 章节是最小提交单元。
- 当前章成功后，才能继续下一章。
- 回退后续进展采用**逻辑隐藏**，默认只读 active branch。
- 手工结果允许保留，但默认 `participates_in_downstream = false`。
- JSON 是标准中间产物；后续从 JSON 入库并渲染 Markdown。
- 中文检索优先 PostgreSQL 扩展 / 原生能力；当前已启用 `pg_textsearch`、`pg_trgm`、`vector`。

## Live ONNX note

If the environment cannot reach `huggingface.co`, the ONNX backend will now fail with an actionable error telling you to either:
- provide `NOVEL_ANALYZER_EMBEDDING_MODEL_PATH`, or
- enable outbound access to Hugging Face.

## More docs

- `docs/direct-usage-guide.md`：直接使用拆书 agent 的操作指南
- `docs/agent-skills-and-embedding.md`：内部 staged agent 与 ONNX embedding 说明
