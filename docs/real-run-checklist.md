# 真实小说首轮试跑清单

这份清单用于把当前拆书 agent 从“阶段性交付完成”推进到“真实文本首轮验证”。

---

## 1. 试跑前准备

### 环境确认
- 已完成 `poetry install`
- 已完成 `poetry run novel-analyzer init-db`
- 已完成 `poetry run novel-analyzer db-health`
- 已完成 `poetry run novel-analyzer test-embedding`
- `.env.local` 已配置：
  - 数据库
  - LLM provider / model
  - embedding path

### 文本准备
- 文本编码统一为 UTF-8
- 章节标题格式尽量稳定
- 尽量避免正文中夹杂大量目录、番外、作者感言

---

## 2. 推荐试跑策略

### 第 1 轮：只跑前 1~3 章
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title '真实试跑'
poetry run novel-analyzer start-run <novel_id> <manifest_id>
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

重点观察：
- 章节切分是否正确
- chapter summary 是否贴文本
- facts 是否明显漏抓/乱抓
- graph 是否形成合理主线
- state summary 是否符合章节推进

### 第 2 轮：问答验证
```bash
poetry run novel-analyzer ask-branch <branch_id> '主角前几章的核心推进是什么？'
poetry run novel-analyzer export-branch-qa-context <run_id> <branch_id> ./branch-qa.json
```

重点观察：
- answer 是否保守且有信息量
- evidence 是否指向正确章节
- reasoning_path / graph_signal 是否合理
- thematic_contexts 是否能形成专题入口

### 第 3 轮：导出验证
```bash
poetry run novel-analyzer export-branch-report <run_id> <branch_id> ./branch.md
poetry run novel-analyzer export-branch-package <run_id> <branch_id> ./branch_pkg
```

重点观察：
- branch report 是否可读
- chapter markdown 是否有参考价值
- QA context 是否适合下游工具消费
- thematic contexts 是否结构完整

---

## 3. 必查项

### A. 不能接受的问题
- 伪造剧情
- 把未发生事件写成已发生
- 把弱暗示写成确定结论
- 错误声称伏笔已回收
- 错误声称冲突已解决

### B. 可接受但需记录的问题
- 细枝末节漏抓
- writer_learning_notes 偏弱
- thematic 字段较稀疏
- 推荐问题不够有针对性

---

## 4. 推荐审查顺序

### 对单章看
1. `show-chapter`
2. `show-context`
3. `show-raw-output`
4. `export-chapter-qa-context`

### 对整体看
1. `show-run-status`
2. `summarize-graph`
3. `export-branch-report`
4. `export-branch-qa-context`
5. `export-branch-package`

---

## 5. 若试跑出现问题

### 切分不对
先看：
```bash
poetry run novel-analyzer inspect-novel /path/to/novel.txt
```

### 某章失败
```bash
poetry run novel-analyzer list-failed-jobs <branch_id>
poetry run novel-analyzer retry-chapter <run_id> <branch_id> <chapter_index>
```

### 派生层不全
```bash
poetry run novel-analyzer validate-branch <branch_id>
poetry run novel-analyzer repair-branch <branch_id>
```

### 想保留前面章节、后面重拆
```bash
poetry run novel-analyzer fork-branch <branch_id> <keep_through>
```

---

## 6. 首轮试跑建议输出

建议你至少保留这些文件：
- `branch.md`
- `branch_pkg/branch_bundle.json`
- `branch_pkg/branch_qa_context.json`
- `branch_pkg/chapters/chapter_0001.md`
- `branch_pkg/chapters/chapter_0001.qa-context.json`

---

## 7. 首轮试跑完成后建议复盘的问题

- 哪些章节 summary 最不稳定？
- facts 的漏抓主要发生在哪类文本？
- reasoning graph 哪种边最有用？
- state summary 是否足够帮助后续章节？
- QA 的保守程度是否合适？
- thematic contexts 哪个主题最有价值？

---

## 8. Loom 记忆层检查（Phase 1+2 已上线）

Loom 默认以 `shadow` 模式运行，不影响主链路。试跑完成后可用以下命令检查 Loom 状态。

### 8.1 查看记忆与张力状态

```bash
poetry run novel-analyzer loom-status <branch_id>
```

重点观察：
- `contradiction_nodes` > 0：有角色/规则矛盾，建议人工确认
- `tension_score` < 0.3：情节偏平淡，可考虑引入新元素
- `plot_similarity` > 0.85：当前章节与前几章高度重复

### 8.2 手动运行冲突代谢

```bash
poetry run novel-analyzer loom-consolidate <branch_id> <chapter_index>
```

### 8.3 查看记忆组装内容

```bash
poetry run novel-analyzer loom-assemble <branch_id> <next_chapter_index>
```

### 8.4 PostgreSQL 生产环境首次启用 Loom

**必须先运行 migration：**

```bash
poetry run novel-analyzer db-upgrade
```

然后在 `.env.local` 中设置：

```bash
NOVEL_ANALYZER_LOOM_MEMORY_MODE=shadow   # 先用 shadow 观察
# 验证无问题后切换到：
NOVEL_ANALYZER_LOOM_MEMORY_MODE=enabled
```

详细说明见 [CLI 操作手册第 12 节](./cli-operations-manual.md#12-loom-记忆与张力命令phase-12)。
