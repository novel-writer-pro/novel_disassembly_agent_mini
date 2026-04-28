# Session Handoff Manual / 续跑交接手册

这份文档用于你下次重新打开项目时，能够**不重新理解上下文**，直接按步骤继续：
- 继续真实试跑
- 做校验
- 看结果
- 做优化

---

## 1. 当前交接状态

### 1.1 当前真实试跑对象
- 小说路径：`/home/user/txt111/novel.txt`
- run_id：`34545dc4-9db4-4619-86b4-d91e2153c575`
- branch_id：`e321854a-8f3f-4af4-9244-c86338ca62ad`

### 1.2 当前模型配置
- base_url：`https://api-inference.modelscope.cn/v1`
- model：`Qwen/Qwen3.5-122B-A10B`

### 1.3 当前结论
- 前 12 章已经形成可评估结果（详见 [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)）
- 当前模型：
  - 适合做**质量验证 / 人工盯跑**
  - 不适合做**长程无人值守生产跑批**

---

## 2. 下次启动后先做什么

### 第一步：确认环境
```bash
poetry run novel-analyzer db-health
poetry run novel-analyzer test-embedding
```

### 第二步：确认当前模型仍生效
```bash
python - <<'PY'
from novel_analyzer.config.settings import Settings
s = Settings()
print(s.resolved_llm_base_url)
print(s.llm_model_name)
PY
```

### 第三步：确认当前 run / branch 状态
```bash
RUN_ID=34545dc4-9db4-4619-86b4-d91e2153c575
BRANCH_ID=e321854a-8f3f-4af4-9244-c86338ca62ad

poetry run novel-analyzer show-run-status $RUN_ID $BRANCH_ID
poetry run novel-analyzer list-chapters $BRANCH_ID | sed -n '1,30p'
poetry run novel-analyzer list-failed-jobs $BRANCH_ID
```

---

## 3. 如果你要继续真实试跑

### 3.1 小批次推进（推荐）
```bash
poetry run novel-analyzer analyze-range $RUN_ID $BRANCH_ID 13 15
```

不建议直接继续超大区间无人值守长跑。

### 3.2 如果失败，先看失败章
```bash
poetry run novel-analyzer list-failed-jobs $BRANCH_ID
```

### 3.3 重试失败章
```bash
poetry run novel-analyzer retry-chapter $RUN_ID $BRANCH_ID <chapter_index>
```

### 3.4 批量重试失败章
```bash
poetry run novel-analyzer retry-failed-jobs $RUN_ID $BRANCH_ID
```

---

## 4. 如果你要检查某一章的细节

假设要看第 12 章：
```bash
CH=12
poetry run novel-analyzer show-context $BRANCH_ID $CH
poetry run novel-analyzer show-raw-output $BRANCH_ID $CH
poetry run novel-analyzer show-chapter $BRANCH_ID $CH
poetry run novel-analyzer show-facts $BRANCH_ID --chapter-index $CH
```

如果想落盘：
```bash
mkdir -p ./debug-ch$CH
poetry run novel-analyzer export-context $BRANCH_ID $CH ./debug-ch$CH/context.json
poetry run novel-analyzer export-raw-output $BRANCH_ID $CH ./debug-ch$CH/raw.json
poetry run novel-analyzer export-chapter-bundle $BRANCH_ID $CH ./debug-ch$CH/chapter.json
poetry run novel-analyzer export-markdown $BRANCH_ID $CH ./debug-ch$CH/chapter.md
poetry run novel-analyzer export-chapter-qa-context $BRANCH_ID $CH ./debug-ch$CH/chapter-qa.json
```

---

## 5. 如果你要看窗口级总结

### 第一个窗口
```bash
poetry run novel-analyzer show-window $BRANCH_ID 1 5
```

### 第二个窗口
```bash
poetry run novel-analyzer show-window $BRANCH_ID 6 10
```

### 后续窗口
```bash
poetry run novel-analyzer show-window $BRANCH_ID 11 15
```

前提是 해당窗口章节都已完成。

---

## 6. 如果你要做整体导出

```bash
poetry run novel-analyzer export-branch-report $RUN_ID $BRANCH_ID ./branch.md
poetry run novel-analyzer export-branch-bundle $RUN_ID $BRANCH_ID ./branch.json
poetry run novel-analyzer export-branch-qa-context $RUN_ID $BRANCH_ID ./branch-qa.json
poetry run novel-analyzer export-branch-package $RUN_ID $BRANCH_ID ./branch_pkg
```

---

## 7. 当前最重要的优化优先级

### P1（优先做）
1. writer-learning 增强（已做第一轮，但真实产出仍偏弱）
2. summary 压缩（已做第一轮）
3. JSON 稳定性增强（已做第一轮修复）

### 当前最值得继续观察的点
- 第 12 章以后，JSON 修复后的失败率是否下降
- writer-learning 在真实章节里是否开始非空
- 第二、第三个窗口是否继续有结构价值

---

## 8. 当前模型判断（重要）

当前模型：`Qwen/Qwen3.5-122B-A10B`

### 适合
- 小批次试跑
- 质量验证
- 人工盯跑
- 结构能力评估

### 不适合
- 100 章无人值守长跑
- 高稳定性生产跑批

如果后续要换模型，请使用：
- [`./model-eval-template.md`](./model-eval-template.md)

---

## 9. 建议阅读顺序

### 如果你要继续试跑
1. [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)
2. [`./real-run-checklist.md`](./real-run-checklist.md)
3. [`./review-template.md`](./review-template.md)
4. 本文档

### 如果你要继续开发
1. [`./final-handoff.md`](./final-handoff.md)
2. [`./interface-manifest.md`](./interface-manifest.md)
3. [`./cli-operations-manual.md`](./cli-operations-manual.md)
4. 本文档

---

## 10. 下次回来最小操作清单

```bash
# 1) 确认环境
poetry run novel-analyzer db-health
poetry run novel-analyzer test-embedding

# 2) 看当前 run 状态
RUN_ID=34545dc4-9db4-4619-86b4-d91e2153c575
BRANCH_ID=e321854a-8f3f-4af4-9244-c86338ca62ad
poetry run novel-analyzer show-run-status $RUN_ID $BRANCH_ID
poetry run novel-analyzer list-failed-jobs $BRANCH_ID

# 3) 决定是继续跑还是先复盘
poetry run novel-analyzer analyze-range $RUN_ID $BRANCH_ID 13 15
# 或者
poetry run novel-analyzer export-branch-report $RUN_ID $BRANCH_ID ./branch.md
```

---

## 11. 当前续做优先级（面向下一位继续开发者）

### 第一优先级：稳定性
1. 检查跨小说跳转链路是否还存在 `run_id / branch_id` 丢失
2. 验证 `/control` 内 tab 化后的 pipeline 入口是否在所有小说下都指向正确上下文
3. 验证 stalled 检测不会误伤正常长章节

### 第二优先级：任务台可读性
4. 给 pipeline 增加“只看当前 run”聚焦模式
5. 给章节任务表增加更清晰的排序
6. 给单章详情补结构化错误摘要

### 第三优先级：后续演进
7. 在当前轮询稳定后再考虑 SSE
8. 等控制面稳定后再继续拆 scheduler / worker
