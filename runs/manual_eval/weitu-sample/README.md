# 人工评估工作区模板

本目录是人工评估工作区的模板。
使用 `scripts/bootstrap_manual_eval_workspace.py` 从此模板创建新工作区。

```bash
python3 scripts/bootstrap_manual_eval_workspace.py <novel_slug>
```

## 目录结构

- `artifacts/` — 导出的 JSON 产物（novel-assistant、检索基准等）
- `exports/` — 分支报告与打包产物
- `notes/` — 人工审查笔记、问题追踪、后续行动

---

## 当前工作区用途：卫图样例 Loom 真实验证

- run_id: `ac9449b9-7326-474f-bb72-4416375a7491`
- branch_id: `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- title: `示例小说-fresh10-db-v2`

当前已导入：

- `artifacts/weitu-branch-bundle.json`
- `artifacts/weitu-whole-book-report.json`
- `exports/weitu-branch-report.md`

建议流程：

1. 先看 `notes/manual-review-notes.md`
2. 再看 `notes/problem-trace.md`
3. 人工只处理复杂 case
4. 处理后按 `notes/next-actions.md` 回到 resume / recovery 链
