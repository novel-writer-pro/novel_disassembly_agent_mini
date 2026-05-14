# Auto Pipeline Profiles

## Profiles

### manual
- 只完成 ingest + run/branch 创建
- 不自动推进
- 适合保守 CLI 用户

### auto-lite
- ingest 后自动推进安全小批次
- Phase 1 CLI 默认 `--max-chapters=1`
- Future Web/API 可提升到 1~3 章默认窗口
- 首个失败即停
- 首期 Web 默认值

### auto-full
- ingest 后持续推进
- Phase 1 若未显式传 `--max-chapters`，默认尝试推进到当前 manifest 末尾
- 默认先以“全书完成”为目标
- 受预算上限、用户暂停、首个失败影响
- 失败进入 `needs_recovery`
