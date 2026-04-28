# Storage Lifecycle / 上传与导出生命周期

## 1. 目标
为 Web 场景补齐上传、导出、清理、审计语义，同时尽量少动现有核心逻辑。

## 2. Upload lifecycle
- 当前上传文件进入受管目录：`.cache/novel-analyzer/uploads/<uuid>-<filename>.txt`
- 数据模型演进：
  - 继续保留现有 `NovelSource.source_path` 以兼容 CLI
  - 新增（计划）
    - `source_kind: local_path | upload`
    - `source_ref: str`（受管路径或本地路径）
  - 迁移期间：
    - CLI: `source_kind=local_path`, `source_ref=source_path`
    - Web: `source_kind=upload`, `source_ref=受管路径`
    - **兼容桥（已定）**：首期 Web upload 必须把受管路径同步写入 `source_path`，直到分析链统一切到 `source_ref`
- 审计仍以 `source_hash` 为主

## 3. Export lifecycle
- branch package 当前输出到：`.cache/novel-analyzer/runtime-exports/<run_id>/<branch_id>/`
- **返回策略已定：首期统一返回 `{download_ref, content_type}`，不做 inline / 下载双态**
- API 下载通过受管引用获取实际文件
- 首期不强制流式生成；优先“受管目录 + 下载引用”

## 4. Cleanup policy
- 上传与导出文件都应有 TTL
- 仍被 run/branch 引用的文件不得删除
- 清理任务只处理：
  - 已完成且超过 TTL 的导出目录
  - 无引用的上传暂存文件

## 5. Failure handling
- 上传落盘成功但 ingest 失败：保留上传文件与 source_hash，便于重试/审计
- 导出生成失败：保留失败状态，不暴露不完整下载链接

## 6. Compatibility strategy
- 不立即移除 `source_path`
- 首期通过新增字段兼容 CLI 与 Web 双来源
- 先以“同步回写 `source_path`”作为兼容桥
- 等 Web/CLI 都切到 `source_kind + source_ref` 后，再考虑淡化 `source_path`
- 对历史 `.omx/uploads/` 与 `.omx/runtime-exports/` 路径保留兼容读取，并在后端启动时自动迁移到 `.cache/novel-analyzer/`
