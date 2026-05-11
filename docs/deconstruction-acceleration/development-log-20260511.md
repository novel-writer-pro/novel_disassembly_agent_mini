# 拆书加速开发日志（2026-05-11）

## 本次目标

- 领取 regression / benchmark / docs lane
- 不改变 current imitation functionality default behavior
- 补当前 canonical 默认读路径的回归保护、benchmark 基线、文档同步与变更记录

## 本次修改

1. 新增 `tests/test_context_service.py` 回归测试：
   - inactive/shadow companion artifact 不应改变 `previous_summary`
   - newer shadow window artifact 不应改变 `window_summary`
2. 新增 `docs/deconstruction-acceleration/benchmark-baseline-20260511.md`
   - 固定当前 canonical `context_bundle()` 读路径基线
3. 更新专题入口与总文档入口，补 benchmark/log evidence 导航
4. 更新 `CHANGELOG.md`

## 风险控制

- 不新增运行时开关
- 不修改 `ContextService`、仿写 service、whole-book imitation service 逻辑
- 所有交付以“锁定现状、防止回归、补证据”为边界

## 待后续实现方继续

- `_deconstruction_profile` 真实 schema/写入/读隔离
- canonical vs enrichment 计量拆分
- 10章/100章真实 benchmark

- 新增 `user-manual.md`，把当前已落地能力、未落地能力、推荐实跑顺序、默认 reader 口径和验证方式整理成用户手册。

- 真实试跑发现：新库+真实模型可跑通前 3 章，但第 4 章在 `fact_extractor` 阶段出现 `job stalled for more than 180 seconds`，说明当前版本仍存在真实运行稳定性问题。

- 长跑继续推进到第 8 章后，第 9 章再次失败，错误同样是 `job stalled for more than 180 seconds`，但这次卡在 `evidence_binder @ 30%`，说明稳定性问题不只出现在 `fact_extractor`。

- 为真实 DeepSeek 长跑补最小稳定性修复：将 `chapter_job_stall_timeout_seconds` 默认值从 180 提高到 600，并新增 run_service 单测覆盖，减少长阶段调用被过早判定为 stalled 的风险。

- 为避免已完成章节被重复 `retry-chapter` 拉起并造成 job/artifact 进度错位，新增 `RunService.ensure_chapter_retryable()`，并让 CLI / recovery 在发现 active canonical artifact 时直接拒绝 retry。

- 将 `chapter_job_stall_timeout_seconds` 默认值从 180 调高到 600，并补了 run_service 对应回归，降低真实长阶段调用被过早判定 stalled 的概率。

- QA answer path 新增 question-type 分类、检索 rerank、章节/窗口/图证据分层字段，以及薄证据问题的保守降级策略。
- recovery / retry bulk path 补 completed-chapter guard，避免已完成章节被 retry-failed / retry_failed_jobs 再次重跑。
- 已完成定向验证：QA 6/6，retry/stall guard 子集 3/3。
