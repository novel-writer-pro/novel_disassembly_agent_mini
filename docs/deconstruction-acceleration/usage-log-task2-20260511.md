# 拆书加速使用日志（Task 2 / 2026-05-11）

## 本次执行命令

1. 读取 worker inbox / task / mailbox 状态
2. 检查：
   - `novel_analyzer/domain/schemas.py`
   - `novel_analyzer/services/analysis_service.py`
   - `tests/test_analysis_service.py`
   - `tests/test_run_service.py`
3. 验证：
   - `/home/user/ai-books/.venv/bin/pytest tests/test_analysis_service.py tests/test_analysis_fallback.py -q`
   - `/home/user/ai-books/.venv/bin/python` 内直接 `model_validate + model_dump(mode='json')` 检查 `ChapterAnalysisOutput` 输出键

## 观察

- 当前输出键仍是 canonical contract：
  - `chapter_summary`
  - `key_entities`
  - `key_events`
  - `continuity_notes`
  - `writer_learning_notes`
  - `unsupported_inferences`
  - `ambiguous_points`
  - `quality_gate_notes`
- `_deconstruction_profile` 仅追加 metadata，不会改写主输出 contract
