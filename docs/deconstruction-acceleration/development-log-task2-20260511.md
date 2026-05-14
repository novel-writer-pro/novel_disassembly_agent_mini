# 拆书加速开发日志（Task 2 / 2026-05-11）

## 本次目标

- 验证 `ChapterAnalysisOutput` 在引入 `_deconstruction_profile` 后没有重命名既有输出键
- 保持 `chapter_summary`、`key_entities`、`key_events`、`continuity_notes`
- 保持 `writer_learning_notes`、`unsupported_inferences`、`ambiguous_points`、`quality_gate_notes`

## 本次结论

1. `novel_analyzer/domain/schemas.py` 中 `ChapterAnalysisOutput` 仍直接声明 canonical 字段名，没有 alias / serialization_alias / alias_generator 改写。
2. `novel_analyzer/services/analysis_service.py` 仍通过 `ChapterAnalysisOutput.model_validate(...)` 和 `result.model_dump(mode='json')` 走标准序列化路径。
3. `_deconstruction_profile` 仅作为附加 metadata 键写入 payload，不会替换或重命名既有 `ChapterAnalysisOutput` 键。
4. 既有回归测试已经覆盖：
   - `test_build_deconstruction_profile_marks_deferred_writer_without_schema_rename`
   - `test_record_chapter_artifact_backfills_deconstruction_profile_metadata`

## 风险控制

- 本次不改 schema 键名
- 不新增 alias 兼容层
- 不改 `ChapterAnalysisOutput` 下游消费字段名

## 后续约束

- 若未来继续扩展 quick/deep metadata，只能新增 shadow metadata（如 `_deconstruction_profile`），不能重命名 `ChapterAnalysisOutput` 既有 contract keys
