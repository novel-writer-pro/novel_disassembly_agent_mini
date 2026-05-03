# Whole-Book Imitation Handoff Brief

## 1. 当前状态

whole-book imitation 线当前已经完成：
- CLI run
- CLI export
- API run
- API readiness
- request / success / error / readiness samples
- request / success / error / readiness executable regressions
- contract version fields
- stability / versioning / freeze / evidence docs
- quickstart / docs index / provider recovery checklist

当前内部判断：
> **内部合同与系统接入面已基本收口完成。**

---

## 2. 当前唯一关键阻断

真实 provider-backed whole-book execute 已经尝试过，且主链能触达上游 provider。

当前阻断不是本地代码，而是外部 provider：
- `403 Forbidden`
- `billing_error`
- `daily usage limit exceeded`

所以当前最大的未完成项是：
> 等 provider 条件恢复后，补一轮成功的 provider-backed freeze evidence。

---

## 3. 恢复后下一步

按这个顺序执行：

1. 先跑 readiness
   - `show-whole-book-imitation-readiness`
   - 或 `GET /api/whole-book-imitation-readiness`
2. 再跑 whole-book execute
3. 保存成功 JSON
4. 更新 freeze evidence / freeze readiness 文档
5. 判断是否把 `stable_contract_version` 从 pre-v1 往 stable 提升

参考文档：
- `docs/whole-book-imitation-provider-recovery-checklist.md`
- `docs/whole-book-imitation-freeze-evidence-20260503.md`

---

## 4. 最短接手路径

新的维护者 / 接入方建议顺序：

1. `apps/api/README.md`
2. `docs/whole-book-imitation-integration-quickstart.md`
3. `docs/whole-book-imitation-docs-index.md`
4. `docs/whole-book-imitation-provider-recovery-checklist.md`

---

## 5. 一句话总结

> 这条线现在不是“还没做完”，而是“内部已基本完成，等外部 provider 恢复后做最后一轮成功验证”。
