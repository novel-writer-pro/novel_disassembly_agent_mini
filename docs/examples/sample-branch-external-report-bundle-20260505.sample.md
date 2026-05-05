# External Report Bundle

## Dashboard
release_ready=False | criteria_ready=False | decision=no_go | approval_status=pending | runbook_status=blocked | closure_status=recovery_pending

## Governance Brief
# Governance Report Brief

- dashboard_status: guarded
- governance_status: guarded
- summary_card: release_ready=False | criteria_ready=False | decision=no_go | approval_status=pending | runbook_status=blocked | closure_status=recovery_pending
- operator_brief: decision=no_go | freeze_reason=release_gate_or_sample_criteria_not_ready | sample_count_ready=True | retrieval_benchmark_ready=True | release_gate_ready=False
- whole_book_release_impact: whole_book_consistency_blocks_release

## Release Review Note
# Release Review Note

- candidate_review_ready: False
- whole_book_ready: True
- ready_for_release: False
- criteria_ready: False
- governance_brief: release_ready=False | criteria_ready=False | decision=no_go | approval_status=pending | runbook_status=blocked | closure_status=recovery_pending
- whole_book_consistency_release_impact: whole_book_consistency_blocks_release

## Approval Memo
# Approval Decision Memo

- verdict: REJECT
- decision: no_go
- freeze_reason: release_gate_or_sample_criteria_not_ready
- review_note: release_ready=False | criteria_ready=False | decision=no_go | approval_status=pending | runbook_status=blocked | closure_status=recovery_pending
- whole_book_release_impact: whole_book_consistency_blocks_release

## Runbook
- 检查 operator brief 与 freeze_artifact 是否一致。
- 确认 release gate / sample criteria / risk evidence 的最新快照。
- 若 decision=no_go，则生成阻断清单并停止发布动作。
- 若 decision=go，则进入人工 approval 与 release review。

## Rollback
- 停止当前发布/扩散动作。
- 回退到上一版候选稿或安全版本。
- 重新收集 risk / review / release gate 快照。
- 完成问题修复后重新进入 freeze review。

## Governance Summary
release_ready=False | criteria_ready=False | decision=no_go | approval_status=pending | runbook_status=blocked | closure_status=recovery_pending
