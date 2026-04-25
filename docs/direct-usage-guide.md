# 拆书 Agent 直接使用指南

## 适用场景
当前版本适合：
- 单本小说、串行拆书
- 章节级拆解与小批次推进
- 小说细节检索与问答
- 5 章固定窗口总结
- 事实层沉淀（entity / event / continuity）

## 基础配置
建议通过 `.env.local` 配置：

```bash
NOVEL_ANALYZER_DB_DIALECT=postgresql
NOVEL_ANALYZER_DB_HOST=127.0.0.1
NOVEL_ANALYZER_DB_PORT=5432
NOVEL_ANALYZER_DB_USER=d2
NOVEL_ANALYZER_DB_PASSWORD=...
NOVEL_ANALYZER_DB_NAME=novel_analyzer
NOVEL_ANALYZER_DB_ADMIN_NAME=postgres

NOVEL_ANALYZER_LLM_BASE_URL=https://api.vip1129.cc/v1
NOVEL_ANALYZER_LLM_MODEL_NAME=gpt-5.4
NOVEL_ANALYZER_LLM_API_KEY=...

NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=BAAI/bge-m3
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=/home/user/huggingface/bge-m3-onnx-int8
NOVEL_ANALYZER_EMBEDDING_CACHE_DIR=.cache/embeddings
```

## 一次性初始化
```bash
poetry run novel-analyzer init-db
poetry run novel-analyzer db-health
poetry run novel-analyzer test-embedding
```

## 拆书主流程
### 1. 导入小说
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title 'xxx'
```
记下：
- `novel_id`
- `manifest_id`

### 2. 创建 run / branch
```bash
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```
记下：
- `run_id`
- `branch_id`

### 3. 推进章节
#### 单章推进（推荐）
```bash
poetry run novel-analyzer analyze-next <run_id> <branch_id>
```

#### 指定区间推进
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

### 4. 查看 branch 状态
```bash
poetry run novel-analyzer show-branch <branch_id>
```

### 4.1 查看 run 总体状态
```bash
poetry run novel-analyzer show-run-status <run_id> <branch_id>
```

### 4.2 查看单章 bundle
```bash
poetry run novel-analyzer show-chapter <branch_id> <chapter_index>
```

### 4.3 查看/导出后续章节上下文
```bash
poetry run novel-analyzer show-context <branch_id> <chapter_index>
poetry run novel-analyzer export-context <branch_id> <chapter_index> ./context.json
```

### 4.4 查看/导出原始 LLM 输出
```bash
poetry run novel-analyzer show-raw-output <branch_id> <chapter_index>
poetry run novel-analyzer export-raw-output <branch_id> <chapter_index> ./raw_output.json
```

## 检索与问答
### 章节检索
```bash
poetry run novel-analyzer search-branch <branch_id> '卫图 命格 养生功'
```

### 小说细节问答
```bash
poetry run novel-analyzer ask-branch <branch_id> '卫图为什么要修养生功？'
```

问答是**保守型**：
- 有证据就答
- 证据不足就明确说不足
- 不乱编剧情

## 窗口总结
当章节推进到 5、10、15 ... 章时，会自动生成固定 5 章窗口汇总。

查看某个窗口：
```bash
poetry run novel-analyzer show-window <branch_id> 1 5
```

## Markdown 输出
当前项目支持从单章 JSON 渲染 Markdown：
- `novel_analyzer.reporting.markdown.render_chapter_markdown(...)`

后续可进一步扩展为 CLI 导出。

## 当前版本的边界
### 已经可用
- 切章
- staged 拆书 + fallback
- ONNX embedding
- PostgreSQL 中文检索
- branch 级问答
- 5 章窗口
- facts 基础层

### 仍需注意
- 外部 LLM 服务偶发 503
- 多章长跑建议小批次推进
- writer-learning 仍可继续增强
- graph 关系网络仍未完全做实

## LLM 分工建议

当前默认模型分工：
- staged 拆书链：`gpt-5.1`
- 问答：`gpt-5.2`
- monolithic fallback：`gpt-5.4`

这样可以优先使用小模型，同时保留更强 fallback。

## 多 provider 配置

当前支持多 LLM relay provider 共存：
- `vip1129`（默认）
- `vibediary`（保留兼容）

通过 `NOVEL_ANALYZER_LLM_PROVIDER_NAME` 选择当前默认 provider。
分工默认：
- stage 拆书：`gpt-5.1`
- 问答：`gpt-5.2`
- fallback：`gpt-5.4`

## 导出

```bash
poetry run novel-analyzer export-chapter-bundle <branch_id> <chapter_index> ./chapter.json
poetry run novel-analyzer export-branch-bundle <run_id> <branch_id> ./branch.json
poetry run novel-analyzer export-branch-report <run_id> <branch_id> ./branch.md
```

## 直接查看与运维命令

```bash
poetry run novel-analyzer list-chapters <branch_id>
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer validate-branch <branch_id>
poetry run novel-analyzer repair-branch <branch_id>
poetry run novel-analyzer list-failed-jobs <branch_id>
poetry run novel-analyzer clear-running-jobs <branch_id>
poetry run novel-analyzer retry-chapter <run_id> <branch_id> <chapter_index>
poetry run novel-analyzer retry-failed-jobs <run_id> <branch_id>
```

## 运行恢复与修复

```bash
poetry run novel-analyzer list-failed-jobs <branch_id>
poetry run novel-analyzer clear-running-jobs <branch_id>
poetry run novel-analyzer retry-chapter <run_id> <branch_id> <chapter_index>
poetry run novel-analyzer retry-failed-jobs <run_id> <branch_id>
poetry run novel-analyzer validate-branch <branch_id>
poetry run novel-analyzer repair-branch <branch_id>
```

## 查看与审计

```bash
poetry run novel-analyzer list-chapters <branch_id>
poetry run novel-analyzer show-facts <branch_id> --chapter-index 1
poetry run novel-analyzer search-facts <branch_id> '卫图 命格 养生功'
poetry run novel-analyzer show-graph <branch_id>
poetry run novel-analyzer summarize-graph <branch_id>
poetry run novel-analyzer show-window <branch_id> 1 5
poetry run novel-analyzer show-raw-output <branch_id> 1
```

## Package 导出

```bash
poetry run novel-analyzer export-branch-package <run_id> <branch_id> ./branch_pkg
```

整包现在包含：
- `branch_bundle.json`
- `branch_report.md`
- `chapter_index.json`
- `chapters/chapter_XXXX.json`
- `chapters/chapter_XXXX.md`
- `chapters/chapter_XXXX.raw.json`
- `chapters/chapter_XXXX.context.json`
