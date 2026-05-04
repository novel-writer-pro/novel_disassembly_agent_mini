# Imitation / Generation Checkout — 2026-05-04

## 1. 本轮范围
- 能力线：chapter imitation / harness / whole-book orchestration
- 关联样例：whole-book provider-backed rerun 2026-05-04
- 目标用户：仿写系统接入方、作者工作流、后续生成链维护者

## 2. 当前已完成
- harness + repair lanes + long-book consistency diagnostics 已成形。
- whole-book sample / readiness / request / error / provider-success 样例已齐备。
- 真实 provider-backed rerun 成功，说明 whole-book 主链已可打通。

## 3. 当前未完成
- 多轮 / 长书级成功样例密度仍偏少。
- 仍是 sandbox-oriented，尚未提升到受控 live artifact lane。
- whole-book 文件有风格债，尚未做大规模整理。

## 4. 预期效果
- 生成链从“能跑”升级为“可控、可解释、可交接”。
- 仿写系统更适合长篇连续性与平台级接入。

## 5. 解决的问题
- 之前：whole-book 更像结构设计和 dry-run contract。
- 现在：provider-backed success sample 已证明主链可实跑。

## 6. 测试 / 评估状态
- `tests/test_whole_book_imitation_service.py` 通过
- `tests/test_imitation_harness_service.py` 通过
- provider rerun 成功，输出已入仓库样例

## 7. 下一步闭环
### 必做
1. 更多 provider-backed 成功样例
2. 更长章节窗口 consistency evidence
3. sandbox -> live artifact 受控升级路径

### 快速可补
1. style-calibrator / story bible 结合说明
2. 作者侧使用说明 / 成功案例文档

## 8. 结论
imitation 线目前最大的变化是：它已经不是“未来能力”，而是“已可跑、可验证、可交接的系统能力”。
