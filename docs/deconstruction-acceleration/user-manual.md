# 拆书加速优化用户手册

> 本手册面向“要直接使用当前拆书主线的人”，重点说明：
> 1. 当前这批改进到底已经落地了什么；
> 2. 哪些仍是后续规划；
> 3. 如何安全使用、验证，并确认**不会影响当前仿写默认行为**。

---

## 1. 当前这批改进已经落地了什么

当前已经落地并可依赖的能力：

1. **canonical quick metadata 已开始进入主链**
   - 以 `_deconstruction_profile` 的 shadow metadata 形式出现
   - 不会改名或替换 `ChapterAnalysisOutput` 既有字段

2. **默认 reader 口径已收紧**
   - 默认读取只消费 canonical / default-readable artifact
   - non-downstream companion 不会自动覆盖 canonical active artifact

3. **blocking materialization 安全性提升**
   - retrieval / fact / graph / fixed-window 仍保持 blocking
   - 若 materialization 在 artifact persist 后失败，会恢复 previous active artifact，而不是留下半成品 active state

4. **基线 benchmark 与回归保护已补齐**
   - 已补 context / chapter index / status / run service 的 reader-isolation 回归
   - 已补 canonical 默认读路径的 benchmark baseline

---

## 2. 当前还没有真正落地的部分

这点很重要，避免误用：

### 2.1 还没有完全落地的 Quick / Deep 运行时切换
虽然文档、PRD、测试和部分 metadata 已经到位，但当前仍属于：
- **安全主线 + 默认读口径 + 验证基线先落地**
- 而不是“已经有完整 quick/deep 双档 CLI 开关并大规模异步运行”

### 2.2 本轮没有开启新的默认异步写回语义
当前没有把 retrieval / fact / graph / window 这些下一章依赖的物化链异步化。

### 2.3 这轮不是“整本 100 章极限提速版本”
当前更像是：
- 先把**安全边界**和**默认行为保护**做对
- 再为后续更快的 quick/deep 主线铺路

---

## 3. 这批改进对你日常使用意味着什么

### 3.1 默认 CLI 使用方式不需要重学
你仍然主要使用：
- `ingest`
- `start-run`
- `analyze-next`
- `analyze-range`
- `show-run-status`
- `show-chapter`
- `show-context`
- `show-window`
- `search-branch`
- `ask-branch`

### 3.2 默认读路径现在更安全
如果后续有人给某一章加了 companion / manual / shadow 类产物：
- **它不会默认污染**
  - `previous_summary`
  - `chapter index`
  - `completed chapter count`
  - `fixed window summary`
  - 默认 branch/status 消费口径

### 3.3 对仿写默认行为的保护更强了
本轮的原则就是：
- **拆书链加速优化不能误伤仿写默认行为**

所以这轮的新增验证明确覆盖了：
- `tests/test_imitation_harness_service.py`
- `tests/test_whole_book_imitation_service.py`
- 相关 context/read-path 基线

---

## 4. 推荐使用流程（当前版本）

### Step 1：准备环境
按 `README.md` 的 PostgreSQL / LLM / embedding 配置来准备。

如果只是做当前主线验证，建议：
- PostgreSQL 走 README 里的本地配置
- embedding 在测试环境下可用 stub / onnx 之一
- 真实跑小说时再切到你的正式 provider 配置

### Step 2：导入小说
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title 'sample'
```

### Step 3：创建 run
```bash
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```

### Step 4：按小步推进
推荐继续用小批量推进：
```bash
poetry run novel-analyzer analyze-next <run_id> <branch_id>
```
或：
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
```

### Step 5：查看状态与上下文
```bash
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer show-chapter <branch_id> <chapter_index>
poetry run novel-analyzer show-context <branch_id> <chapter_index>
poetry run novel-analyzer show-window <branch_id> 1 5
```

### Step 6：做安全验证
建议至少检查：
- `show-run-status` 的 completed / next chapter 是否合理
- `show-context` 是否仍只读 canonical/default-readable 结果
- `show-window` 是否未被 companion 产物污染

---

## 5. 如何确认“改进后的流程能正常运行”

当前这轮最核心的验证方式，不是看 UI，而是看几类行为是否稳定：

### 5.1 run service 行为
- non-downstream artifact 不应隐藏 canonical active artifact
- previous active artifact 在 blocking materialization 失败时会恢复

### 5.2 context / chapter index / status 口径
- `previous_summary` 只读 canonical
- `chapter index` 不被 non-downstream companion summary 污染
- completed chapter count 只统计 canonical/default-readable artifact

### 5.3 imitation 默认行为
- context bundle / imitation harness / whole-book imitation 不因本轮修改而回归

### 5.4 benchmark baseline
当前已记录一个 canonical 默认读路径基线，后续 quick/deep 真正启用时，可以拿它做对照。

---

## 6. 当前已知的真实验证证据

本轮已确认通过的验证包括：

- `tests/test_run_service.py` → 5 passed
- `tests/test_context_service.py` → 2 passed
- `tests/test_chapter_index_service.py` → 2 passed
- `tests/test_status_service.py` → 2 passed
- `test_analysis_service` rollback regression → 1 passed, 19 deselected
- retrieval + fact + graph suite → 22 passed
- `tests/test_context_bundle_cli.py` + `tests/test_imitation_harness_service.py` + `tests/test_whole_book_imitation_service.py` → 17 passed

另有 benchmark baseline：
- rounds = 200
- total_ms = 5154.937
- avg_ms = 25.775

---

## 7. 使用时最重要的注意事项

### 7.1 不要误以为“当前已经有完整 async deep lane”
当前更准确的状态是：
- **reader isolation / canonical safety / blocking materialization 安全性先落地**
- 完整 quick/deep runtime 调度仍是后续工作

### 7.2 companion / manual artifact 不等于默认可读 artifact
如果你在后续调试时手工写入 artifact，请注意：
- 不要因为它是 active row，就默认认为它会成为 canonical 读结果

### 7.3 这轮的目标不是“极限提速”，而是“先把边界做对”
如果你现在就想跑真实长书：
- 可以跑
- 但应该把它视为“安全主线 + 基线观测”
- 而不是“最终版快拆 100 章流水线”

---

## 8. 推荐的实跑顺序（当前版本）

建议这样做：

1. 先用一部短文本或前 1~3 章验证 `show-run-status / show-context / show-window`
2. 再做 5 章级验证，观察 fixed window summary
3. 再用你提供的正式 provider 配置跑候补小说样例
4. 对照 benchmark baseline，观察后续 quick/deep 真实优化收益

---

## 9. 后续你最该关注的 3 个指标

1. **canonical progress 是否稳定**
2. **默认读路径有没有被 companion 污染**
3. **后续真正引入 async/deep lane 时，是否还能保持 imitation 默认行为不变**

---

## 10. 关联文档

- [architecture.md](./architecture.md)
- [development-guide.md](./development-guide.md)
- [benchmark-baseline-20260511.md](./benchmark-baseline-20260511.md)
- [critical-open-points.md](./critical-open-points.md)
- [../direct-usage-guide.md](../direct-usage-guide.md)
- [../cli-operations-manual.md](../cli-operations-manual.md)
- [../../README.md](../../README.md)
