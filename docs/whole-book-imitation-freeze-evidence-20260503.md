# Whole-Book Imitation Freeze Evidence - 2026-05-03

## 1. 本轮目标

对 whole-book imitation 的 pre-v1 合同，补一轮 **真实 provider-backed freeze evidence**。

目标不是继续补结构文档，而是验证：
- 当前本地配置是否可实际发起 whole-book sandbox execute
- 当前 CLI/export/API 合同之外，是否存在外部阻断条件
- 当前 freeze readiness 中“provider-backed 回归不足”是否仍然成立

---

## 2. 本轮环境结论

### 数据库侧
- 本地 PostgreSQL 可连接
- `d2` 库结构存在但无作品数据
- `novel_analyzer` 库存在真实拆书数据
- 本轮选择 branch：`62e636f0-c901-4167-aa1c-aff3da9c83ef`
- 该 branch 具备：
  - `chapter_analysis` 产物 11 章
  - `fact_records` 232 条

### LLM/provider 侧
- 当前 settings 已解析到：
  - `llm_provider_name = vip1129`
  - `llm_model_name = gpt-5.4-mini`
  - `llm_api_key_present = true`
- 当前历史 provider health 文件已记录：
  - 最近状态曾为 `degraded`
  - 最近已知错误包含 `502 Bad Gateway`

这说明：
- 本地并非“没配 key / 没配 provider”
- 当前已具备发起真实 provider 回归的最低条件

---

## 3. 本轮真实执行

执行命令（provider-backed whole-book sandbox execute）：

```bash
./.venv/bin/python -m novel_analyzer.cli.app export-whole-book-imitation-run \
  62e636f0-c901-4167-aa1c-aff3da9c83ef \
  "freeze-evidence" \
  "示例小说-fresh10-db-v2" \
  "示例小说-fresh10-db-v2-仿写评估" \
  /tmp/whole-book-provider-run.json \
  "2:延续前文资源铺垫与关系推进" \
  "3:延续主角获得功法后的行动线并保持克制成长节奏" \
  --execute \
  --max-rounds 1 \
  --use-llm \
  --database-url "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer"
```

---

## 4. 实际结果

本轮没有暴露出 contract 层错误；阻断点来自 provider：

- HTTP status: `403 Forbidden`
- provider error type: `billing_error`
- provider error message: `daily usage limit exceeded`

也就是说：
- whole-book imitation 主链已经走到真实 provider 请求
- 失败原因不是本地 CLI / export / API contract 不一致
- 失败原因也不是 schema / payload 结构错误
- 当前外部阻断是 **上游配额/计费限制**

---

## 5. freeze/readiness 影响判断

这轮证据非常关键，因为它把“还没 fully freeze”的原因进一步具体化为：

### 已被证明没问题的部分
- contract_version / stable_contract_version 已贯通
- CLI export 路径可跑到真实 provider 请求阶段
- whole-book sandbox execute 主链可进入真实 LLM 调用阶段
- 数据库与 branch 读取路径正常

### 仍然不足的部分
- 缺少成功完成的 provider-backed whole-book execute 样本
- 缺少真实 provider 正常返回后的 freeze evidence
- 缺少跨多轮/多 branch 的 provider 稳定性统计

### 当前阻断类型
> **外部运行条件阻断，而不是主链代码阻断。**

这意味着当前 freeze readiness 的剩余条件，应更明确表述为：
- 需要补充 provider 配额/计费可用条件
- 需要补至少一轮成功的 provider-backed whole-book run 证据

---

## 6. 当前建议口径

当前最准确的口径是：

> whole-book imitation 已达到 **system-contract-ready / pre-v1**，
> 且本地主链已能触达真实 provider；
> 但由于上游配额限制，尚未拿到成功完成的 provider-backed freeze evidence。

---

## 7. 下一步最小闭环

当 provider 可用后，建议只补一轮最小闭环：

1. 用同一 branch 再跑一次 provider-backed whole-book execute
2. 保留成功输出 JSON
3. 记录：
   - 章节数
   - stop_reason
   - overall_score
   - next_stage_focus
   - book_handoff_summary
4. 再判断是否可把 freeze readiness 提升为更接近 stable v1

---

## 8. 一句话总结

> 本轮真实回归已经证明：当前 whole-book imitation 主链不是“文档稳定、运行未证”，而是“运行可达真实 provider，但被外部 billing 限制阻断”。
