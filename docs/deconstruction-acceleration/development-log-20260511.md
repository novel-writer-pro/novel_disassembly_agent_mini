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

- 卫图链路实测表明：在 stall timeout 提升到 600 后，前 6 章可连续完成，当前未见 failed_jobs，说明稳定性已较上一轮万相验证明显改善。
- 但真实吞吐仍偏慢：前 5 章约 31 分钟，折算约 6.2 min/章，距离“100章 5min”目标仍有数量级差距。
- 现阶段性能瓶颈更接近 `fact_extractor / evidence_binder / analysis_generator` 的串行模型耗时，而不是 artifact materialization 或恢复逻辑。

- 卫图第 6 章实测中，`small_model_pipeline` 曾出现 JSON 解析失败，但 `monolithic_fallback` 接管后仍完成整章，说明当前链路不仅更稳，而且确实具备真实运行中的故障吸收能力。
- 这也意味着后续性能优化不能误伤 fallback 可用性；在追求极限吞吐时，需要保住当前这层“慢但能兜住”的安全网。

- 性能优化第 1 刀已落地：将 `writer_learning_lens` 从 quick 同步主链中移出，改为 deferred stub，从而直接减少一次串行 LLM 调用。
- 契约保持不变：`writer_learning_notes` 仍保留为空数组，`_deconstruction_profile.writer_lens_status` 标记为 `deferred`，consumer 无需改读路径。
- 这是一种“先削 stage 数，再谈 prompt 缩短”的低风险提速策略，适合作为真实瓶颈优化的第一步。

- 性能优化第 2 刀已落地：将 `risk_aggregation` 从 quick 同步尾部移出，改为 deferred non-blocking event，避免章节完成后仍在主请求里继续做 risk card 聚合。
- 卫图真实样例基线已完整跑到 20 章且 0 failed_jobs，说明在当前稳定性修复基础上，后续性能优化已经可以围绕完整链路做对照，而不是只看 5 章 / 9 章的中途样本。

- 性能优化第 3 刀已落地：针对 `analysis_generator` / `anti_fabrication_guard` 输入做 token 缩减，不改输出 schema，只减少同步 stage 看到的大 JSON 上下文。
- 具体策略：去掉完整 graph context，state summary 压缩到关键状态列表；优先保留对 continuity/guard 判断最关键的前情状态，而不是全量图谱信息。
- 这是典型的“缩 prompt 体积而不改 contract”的中低风险优化，适合作为前两刀 stage deferral 之后的第三步。

- 性能优化第 4 刀已落地：继续缩减同步事实链路的 prompt 输入体积。
- 具体包括：
  - `fact_extractor` 去掉完整图谱上下文，仅保留 compact state summary；
  - `evidence_binder` 回到最小必要输入（`cleaned_text + fact_json`），不再额外消费 graph/state/window。
- 这是当前最符合 prompt 资产定义的瘦身动作，因为 evidence-binder 的技能说明本来就只依赖章节正文与事实 JSON。

- 性能优化第 5 刀已落地：继续压缩 `prior_context_json`，把前情事实输入从全量 JSON 缩为 compact 版，只保留 chapter_index / fact_type / label / confidence 等小字段。
- 这一步进一步降低了 `fact_extractor` / `analysis_generator` / `anti_fabrication_guard` 的同步 prompt 体积，并且量化结果显示 `fact_extractor` 已从约 26k 字符降到约 2.5k 字符量级。

- 已把当前 prompt 缩减成果固化为测试护栏：后续如果有人把 quick 主链 prompt 重新撑大，将直接在 `tests/test_analysis_service.py` 里暴露回退。
- 这比单纯写文档更有价值，因为它把“提速成果”变成了可执行约束，而不是口头约定。

- 性能优化第 6 刀已落地：统一压缩 `previous_summary`，避免上一章摘要在多个同步 stage prompt 中重复占据大量上下文。
- 这是一个全局性小优化：虽然单点收益不如 graph/prior_context 缩减那么大，但它会作用到每个需要 previous_summary 的同步 stage。

- 已补 prompt 体积观测埋点：在 `invocation_metadata` 中记录每个同步 stage 的 prompt 字符数与总和。
- 这一步不是直接提速，而是为下一步 funded-provider 真实 benchmark 铺测量基础，使后续对照不只看 wall-clock，也能看 prompt 成本变化是否兑现到真实耗时。
