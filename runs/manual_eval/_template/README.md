# Manual Eval Workspace Template

这个目录用于每本新小说的一次完整人工评估。

建议复制为：

```bash
cp -R runs/manual_eval/_template runs/manual_eval/<novel_slug>
```

或：

```bash
mkdir -p runs/manual_eval/<novel_slug>/{artifacts,exports,notes}
cp docs/manual-eval-record-template.md runs/manual_eval/<novel_slug>/notes/manual-review-notes.md
```

---

## 目录说明
- `artifacts/`：JSON/结构化导出
- `exports/`：Markdown/对外阅读友好导出
- `notes/`：人工记录、问题追踪、结论

## 建议保存文件

### artifacts/
- `novel-assistant.json`
- `author-knowledge.json`
- `retrieval-benchmark.json`
- `search-diagnostics-*.json`
- `reader-feedback-summary.json`
- `whole-book-readiness.json`
- `whole-book-run.json`
- `governance-dashboard.json`
- `final-release-archive.json`

### exports/
- `branch-report.md`
- `governance-report-brief.md`
- `release-review-note.md`
- `approval-decision-memo.md`

### notes/
- `manual-review-notes.md`
- `problem-trace.md`
- `next-actions.md`

## 推荐启动步骤
1. 复制本模板目录
2. 拷贝 `docs/manual-eval-record-template.md` 到 `notes/manual-review-notes.md`
3. 按 `docs/novel-assistant-manual-eval-handbook-20260505.md` 执行测试
4. 每完成一条能力线，就更新 notes 中的结论与薄弱点
