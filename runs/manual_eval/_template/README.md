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
