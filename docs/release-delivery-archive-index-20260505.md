# Release Delivery Archive Index — 2026-05-05

这份索引用于快速找到当前 AI 小说助手在“候选稿 -> 发布前治理 -> 归档”链路上的关键交付件。

## 1. 候选稿与发布前治理主样例
- [`./examples/sample-branch-novel-assistant-20260505.sample.json`](./examples/sample-branch-novel-assistant-20260505.sample.json)
- [`./examples/sample-branch-final-release-archive-20260505.sample.json`](./examples/sample-branch-final-release-archive-20260505.sample.json)

## 2. 治理导出面
- [`./examples/sample-branch-governance-dashboard-20260505.sample.json`](./examples/sample-branch-governance-dashboard-20260505.sample.json)
- [`./examples/sample-branch-governance-report-brief-20260505.sample.md`](./examples/sample-branch-governance-report-brief-20260505.sample.md)
- [`./examples/sample-branch-release-review-note-20260505.sample.md`](./examples/sample-branch-release-review-note-20260505.sample.md)
- [`./examples/sample-branch-approval-decision-memo-20260505.sample.md`](./examples/sample-branch-approval-decision-memo-20260505.sample.md)
- [`./examples/sample-branch-external-report-bundle-20260505.sample.json`](./examples/sample-branch-external-report-bundle-20260505.sample.json)
- [`./examples/sample-branch-external-report-bundle-20260505.sample.md`](./examples/sample-branch-external-report-bundle-20260505.sample.md)

## 3. 反馈与评测样例
- [`./examples/sample-reader-feedback-summary-20260505.sample.json`](./examples/sample-reader-feedback-summary-20260505.sample.json)
- [`./examples/sample-reader-feedback-summary-live-20260505.sample.json`](./examples/sample-reader-feedback-summary-live-20260505.sample.json)
- [`./examples/sample-branch-retrieval-benchmark-20260505.sample.json`](./examples/sample-branch-retrieval-benchmark-20260505.sample.json)

## 4. whole-book 一致性与生成主样例
- [`./examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json`](./examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json)
- [`./examples/whole-book-imitation-run.provider-success-20260504.sample.json`](./examples/whole-book-imitation-run.provider-success-20260504.sample.json)

## 5. 典型使用顺序
1. 先看 `sample-branch-novel-assistant-20260505.sample.json`
2. 再看 `sample-branch-final-release-archive-20260505.sample.json`
3. 对外沟通时优先发 `governance-report-brief` / `release-review-note` / `approval-decision-memo`
4. 做治理/归档汇总时直接用 `external-report-bundle` 与本索引

## 6. Archive navigation metadata
- final archive 现已提供 archive manifest / retention / integrity / index / navigation metadata。
- 导航时优先看 archive_key、indexed_sections、navigation_sections。

## 7. Archive navigation metadata
- final release archive now includes `archive_navigation_metadata_pack`.
- Use `archive_key` and `navigation_sections` for quick archive lookup.
