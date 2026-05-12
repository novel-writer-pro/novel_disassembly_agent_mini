# Application Seams / 共享编排层契约

本文件定义 **Phase 1 已实现的共享编排层**，以及后续 Web/API 的收口方向。

## 1. 边界
- `novel_analyzer/application/*`：唯一对 CLI / API 暴露的公开编排层
- `novel_analyzer/services/*`：原子能力层，仅供 application 组合
- `novel_analyzer/workflows/*`：内部执行引擎/实验骨架，不直接给 CLI / API 使用

## 2. 目标
把当前 CLI 中手工拼接的流程（导入、建 run、推进、恢复、导出）变成稳定的产品级 use cases。

## 3. 首期事务结论（已定）
**首期不承诺跨 `IngestService` + `RunService` 的强原子 rollback。**

原因：
- 现有 `IngestService.ingest_text_file()` 与 `RunService.create_run()` 都在 service 内部 `commit()`；
- 为了满足“尽量少动既有逻辑目录”的约束，首期不强制先改造成无 commit/UoW 风格。

因此首期采用：
- **application façade + compensating cleanup（补偿式清理）**
- 若 ingest 成功但 run 创建失败：
  - 在 `NovelSource.metadata_json` 写入 `setup_status=setup_incomplete`
  - 同时记录失败摘要 `setup_error`
  - 不启动 pipeline
  - 在 UI/API 中暴露为可诊断失败，而不是伪装为原子回滚
- Phase 2 以后再评估是否把 service 提交边界收口到 UoW 模式

## 4. Use Cases

### 4.1 ingest_and_start
**输入（Phase 1 实际）**
- `path: str`
- `title: str | None`
- `branch_name: str`
- `pipeline_profile: manual | auto-lite | auto-full`
- `max_chapters: int`
- `database_url: str | None`

**输出（Phase 1 实际）**
- `novel_id`
- `manifest_id`
- `run_id | null`
- `branch_id | null`
- `pipeline_profile`
- `pipeline_state`
- `existing: bool`
- `setup_status`

**Phase 1 语义**
- 先 ingest
- 再 create run/branch
- 若 run 创建失败，不做伪原子 rollback，而进入可诊断失败状态
- CLI `auto-run` 当前会直接同步调用后续推进
- 真正的后台 launcher 交接留给后续 `apps/api`

### 4.2 advance_pipeline
**输入**
- `run_id`
- `branch_id`
- `max_chapters`
- `database_url`
- `settings`

**输出**
- `(processed_chapters, next_chapter, pipeline_state)`

**事务边界**
- 以“章”为最小提交边界
- 单章成功后提交；章内失败可重试

### 4.3 get_run_snapshot
**输入**
- `run_id`
- `branch_id`

**输出**
- `RunSnapshot`
- `pipeline_state`
- `allowed_actions`

### 4.4 export_workbench_bundle
**输入**
- `run_id`
- `branch_id`

**输出**
- `branch_bundle_path`
- `branch_qa_context_path`
- `branch_report_path`

### 4.5 recover_branch
**输入**
- `action: retry-chapter | retry-failed | clear-running | repair`
- `run_id`
- `branch_id`
- `chapter_index?`

**输出**
- `accepted_action`
- `pipeline_state`
- `message`

### 4.6 start_pipeline
**输入**
- `run_id`
- `branch_id`
- `pipeline_profile`
- `max_chapters`
- `database_url`
- `settings`

**输出**
- `(processed_chapters, next_chapter, pipeline_state)`

**用途**
- 供 `manual` profile 在 `ready` 状态下显式启动后续推进

## 5. Error taxonomy
- `ConfigurationError`
- `IngestError`
- `ValidationError`
- `RunCreationError`
- `PipelineLaunchError`
- `AnalysisExecutionError`
- `RecoveryActionError`
- `ExportError`

## 6. Session / Unit-of-Work policy
- application 层负责 session 生命周期
- service 层逐步朝“无自主 commit”的方向收敛
- 首期允许旧 service 保持内部 commit；因此 setup 流程以补偿式清理/可诊断状态为准，而非跨服务原子事务

## 7. Phase 1 vs Future launcher ownership
- **Phase 1（当前实现）**：CLI `auto-run` 同步调用 `advance_pipeline(...)`
- **Future API target**：`apps/api` 接手 launcher，API 只做接受请求 + 轮询状态
- 后续若引入 worker/queue，只替换 launcher 实现，不改 use case 契约

## 8. Pipeline state source & precedence（已定）
首期 **不新增专门持久化字段**，统一采用聚合推导，但判定优先级必须固定：
1. `setup_incomplete` -> `failed_terminal`
2. 配置类/不可恢复错误 -> `failed_terminal`
3. 存在失败 job / 僵死 running job -> `needs_recovery`
4. 用户显式暂停标记 -> `paused`
5. 存在运行中 chapter -> `auto_running`
6. 已有 run/branch 但尚未启动推进 -> `ready`
7. 全部目标章节完成且无失败 -> `completed`

说明：
- `accepted` / `ingesting` 是 **未来 API target state**，Phase 1 CLI 实现暂不产出；
- `completed` 必须在更高优先级状态都不命中后才能判定；
- 若后续聚合逻辑过脆弱，再补显式持久化字段。

## 9. Architecture rule
- `novel_analyzer/application/*` 是新的高层编排入口
- 旧 CLI 命令仍有部分直接调用 `services/*`，它们属于后续迁移目标
- 允许 CLI / API 直接调用纯读取型导出/展示 helper，仅在它们已由 application façade 封装时
