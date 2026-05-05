# Risk Semantic Checkout — 2026-05-04

## 1. 本轮范围
- 能力线：risk semantic / signal store / link / cluster / review workflow
- 关联样例：sample branch `62e636f0-c901-4167-aa1c-aff3da9c83ef`
- 目标用户：编辑、审校、平台运营、风险维护者

## 2. 当前已完成
- semantic signal store / link / cluster 主链已形成。
- canonical key / evidence reason / candidate reason 已落地。
- review workflow 已有 DB-backed 主路径与 legacy schema 读兼容。
- 已补真实 PG migration + self-check + branch report 再验证。

## 3. 当前未完成
- 更长窗口 linking / clustering 质量证据仍不足。
- 自动 adjudication 仍应保持保守，不宜过早黑盒化。
- risk 文档仍有历史层与 current canonical 层并存。

## 4. 预期效果
- 风险判断保持可解释。
- review workflow 不受老旧 DB schema 拖累。
- sample branch / release handoff 都能给出稳定风险结论。

## 5. 解决的问题
- 之前：真实 PG 的 cluster-review 旧 schema 会阻断 branch report 导出。
- 现在：已有 migration + self-check + fallback read path。

## 6. 测试 / 评估状态
- `tests/test_risk_signal_store_service.py` 通过
- `tests/test_export_risk_card.py::legacy schema` 通过
- `db-capabilities` 与 `export-branch-report` 在真库复验成功

## 7. 下一步闭环
### 必做
1. 长窗口 linking quality benchmark
2. cluster质量与误报率证据
3. 更细的 review workflow 消费指引

### 快速可补
1. 运营复核 FAQ
2. review workflow 场景图

## 8. 结论
risk semantic 线已经具备“真实环境可用 + 可迁移 + 可自检”的运营基础。
