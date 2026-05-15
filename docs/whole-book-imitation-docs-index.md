# Whole-Book Imitation Docs Index

## 1. 最短阅读路径

如果你只想最快完成 system 接入，建议顺序：

1. `apps/api/README.md`
2. `docs/whole-book-imitation-integration-quickstart.md`
3. `docs/interface-manifest.md`
4. `docs/examples/whole-book-imitation-run.request.sample.json`
5. `docs/examples/whole-book-imitation-run.sample.json`
6. `docs/examples/whole-book-imitation-run.error.provider-billing.sample.json`
7. `docs/examples/whole-book-imitation-readiness.sample.json`

如果你想最快了解**业务/质量层面**：

1. `docs/cross-genre-imitation-commercial-readiness-20260515.md` — 商用就绪决策
2. `docs/whole-book-mapping-scale-20260514.md` — 规模化数据
3. `docs/chapter-imitation-capability-matrix.md` — 能力矩阵
4. `docs/baseline-imitation-quality-validation-handoff-20260515.md` — 同题材修复验证

如果你是**运维 / 调试**：

1. `docs/ops-debug-manual-20260514.md` — 故障决策树速查

---

## 2. 契约类文档

- `docs/interface-manifest.md`
- `docs/api-current-surface.md`
- `docs/whole-book-imitation-api-stability-summary.md`
- `docs/whole-book-imitation-api-versioning.md`
- `docs/whole-book-imitation-api-freeze-readiness.md`

---

## 3. 样例类文档

- `docs/examples/whole-book-imitation-run.request.sample.json`
- `docs/examples/whole-book-imitation-run.sample.json`
- `docs/examples/whole-book-imitation-run.provider-success-20260504.sample.json`
- `docs/examples/whole-book-imitation-run.provider-success-20260505.deepseek.sample.json`
- `docs/examples/whole-book-imitation-run.error.provider-billing.sample.json`
- `docs/examples/whole-book-imitation-readiness.sample.json`
- `docs/whole-book-imitation-sample-coverage-matrix.md`

---

## 4. 证据类文档

- `docs/whole-book-imitation-freeze-evidence-20260503.md`
- `docs/whole-book-imitation-provider-recovery-checklist.md`
- `docs/whole-book-imitation-handoff-brief.md`
- `docs/whole-book-mapping-scale-20260514.md` — **mapping_pack 5/30/100+ 章规模化数据，170/171 pass**
- `docs/whole-book-weitu-scifi-fullbook-20260514.md` — 卫图→科幻 102/102 完本里程碑
- `docs/whole-book-zhuxian-scifi-fullbook-20260514.md` — 诛仙→科幻 跨原作复现
- `docs/whole-book-weitu-urban-spike-20260514.md` — 卫图→都市修真 spike + auto-retry 验证

---

## 5. 方法/架构类文档

- `docs/chapter-imitation-method.md`
- `docs/architecture/chapter-imitation-harness-architecture.md`
- `docs/chapter-imitation-capability-matrix.md`
- `docs/whole-book-imitation-integration-quickstart.md`

---

## 6. 商用 / 运维 / 验证（2026-05-15 新增）

- `docs/cross-genre-imitation-commercial-readiness-20260515.md` — 6 项 SLA gap + 3 条上线路径 + 客户画像匹配
- `docs/baseline-imitation-quality-validation-handoff-20260515.md` — 同题材 prompt 修复后 Stage A/B/C 长跑验证步骤
- `docs/ops-debug-manual-20260514.md` — 环境自检 / 常见操作 / 故障决策树 / 反模式

---

## 7. 一句话说明

> 接入方先看 quickstart + samples；维护者看 stability / versioning / freeze evidence；业务 / PM 看 commercial-readiness + mapping-scale；下一棒接手看 baseline-validation-handoff + ops-debug-manual。
