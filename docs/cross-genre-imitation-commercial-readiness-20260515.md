# 跨题材改写商用就绪报告 (2026-05-15)

> **结论先行**：跨题材改写产品线**技术验证完成**，可作为 B2B / API 定向商用上线，**但 SaaS 完整商用尚有 6 项 gap**。
>
> 本文档列出：(1) 已就绪的能力；(2) 待补齐的商用化基础设施；(3) 推荐上线路径。

---

## 1. 已就绪：技术指标证据

### 1.1 核心质量指标（来自 [whole-book-mapping-scale-20260514.md](./whole-book-mapping-scale-20260514.md)）

| 测试 | 章数 | 字数 | mapping items | full pass | mapping accuracy |
|---|---:|---:|---:|---|---|
| 卫图（古典仙侠）→ 太空科幻 | 102 | 227,037 | 12 | **102/102 (100%)** | 98.0% |
| 诛仙（古典仙侠）→ 太空科幻 | 59 | 151,267 | 11 | **58/59 (98.3%)** | 97.5% |
| 卫图（古典仙侠）→ 都市修真 | 10 | 21,370 | 12 | **10/10 (100%)** | 96.1% |
| **合计** | **171** | **399,674** | — | **170/171 (99.4%)** | 96-98% |

### 1.2 验证维度

- ✅ **2 套源题材**（古典仙侠 ×2 source novels：卫图 + 诛仙）
- ✅ **2 套目标题材**（太空科幻、都市修真）
- ✅ **章数尺度**：5 → 30 → 100+ 三个量级均稳定
- ✅ **mapping accuracy**：name leak rate 2-4% 可接受，scaffold-only chapter < 5%
- ✅ **service 层 auto-retry**（commit `7feb888`）：thin draft 自动重跑 3 次
- ✅ **scaffold-only in-flight 检测**（commit `4358658`）：失败章节实时拦截
- ✅ **per-chapter 增量保存**：进程被杀不丢章节

### 1.3 已具备的运维能力（[ops-debug-manual](./ops-debug-manual-20260514.md)）

- 环境自检 3 件套：LLM 通联、pg_jieba user_dict、bm25_vector attgenerated
- 5 棵故障决策树（retrieval / 章节短 / mapping 不生效 / 进程死 / docker）
- 100+ 章节后台跑批 + 不阻塞监控
- 失败恢复：仅重跑缺失章节

### 1.4 已具备的接入契约（[whole-book-imitation-docs-index](./whole-book-imitation-docs-index.md)）

- ✅ pre-v1 API contract（CLI / export / HTTP API 三入口对齐）
- ✅ 6 份 sample（成功 / 失败 / billing 错误 / readiness）
- ✅ versioning 策略（contract_version + stable_contract_version 双字段）
- ✅ provider failure recovery checklist（手动）

---

## 2. 商用 gap 清单（6 项）

### Gap 1：定价模型 ❌

**现状**：完全未定义。

**最低可上线方案**：
- 计费单位：`per-chapter`（一次成功 pass 算一个章节）
- 失败章节是否计费：建议**不计费**（保护用户体验）
- LLM 透传成本：`deepseek-v4-pro` ~$0.10/章 → 建议定价 `$0.50/章` 留 5x 毛利覆盖运维 + retry buffer
- 套餐：单本（≤120 章 = $60）/ 包年（10 本 = $400 / 8 折）/ 企业（自定义）

**实现工作量**：
- 计费表结构：1 个 model（`billing_record` per `(tenant_id, branch_id, chapter_index)`）
- Stripe 集成：~3 天
- 失败章节排除策略：在 `final_verdict != pass` 时不入库 `billing_record`，2 行代码

### Gap 2：多租户隔离 ⚠️ 部分

**现状**：`branch_id` 是事实上的 tenant 边界，但：
- ❌ 无显式 `tenant_id` 字段，跨用户的检索不会被拦截
- ❌ 无 RLS（row-level security）policy
- ❌ 无 API key → tenant 映射

**最低可上线方案**：
- 表加 `tenant_id`：`alembic revision -m "add tenant_id"`，回填默认 `system`
- API gateway 层加 token → tenant 映射
- 关键 query 加 `WHERE tenant_id = :tid` 过滤

**实现工作量**：~5 天，含数据迁移

### Gap 3：SLA + 限流 ❌

**现状**：
- ❌ 无 `requests/min` 限制
- ❌ 无章节并发限制（一个 tenant 可以同时跑 100 章）
- ❌ 无 LLM provider 队列共享
- ❌ 无 SLA 文档

**最低可上线方案**：
- 限流：每 tenant `60 chapters/hour`、`5 concurrent runs`
- SLA 草案：`99% pass rate within 2x normal time`、`<5min queue wait`、`auto-retry within provider failure`
- 实现：`fastapi-limiter` + Redis；queue 用 RQ 或 Celery

**实现工作量**：~5 天

### Gap 4：LLM provider 自动 fallback ⚠️

**现状**：[provider-recovery-checklist](./whole-book-imitation-provider-recovery-checklist.md) 是**手动 ops**：
- 主用 `nassaapi` 抖动 → 整批阻塞 → 人工切到 sealos
- circuit breaker 不存在
- provider 健康度检测：仅启动时一次

**最低可上线方案**：
- 实现 `LLMProviderRouter`：3 路 fallback（nassaapi → sealos → backup-3）
- 每 5 min 自动健康检查；连续 3 次失败 trip circuit breaker
- 单 batch 内 provider 切换：在 retry 第 2/3 次时切

**实现工作量**：~7 天

### Gap 5：内容版权 + 数据安全 ❌

**现状**：未文档化。

**最低可上线方案**：
- 用户上传内容的版权声明（必须用户拥有源作品权利）
- 生成内容的归属（建议归用户）
- LLM provider 的 data retention policy：`deepseek-v4-pro` 默认 30 天 → 文档化让用户知情
- 数据删除路径：`DELETE FROM analysis_runs WHERE tenant_id = :tid` + retrieval_chunks/embeddings 级联

**实现工作量**：~3 天（主要文档），1 天（删除 endpoint）

### Gap 6：监控 + observability ⚠️

**现状**：
- ✅ per-chapter log + per-batch log
- ❌ 无 metrics（Prometheus）
- ❌ 无 tracing（OpenTelemetry）
- ❌ 无 dashboard

**最低可上线方案**：
- key metrics：`pass_rate{tenant,batch}`、`p50/p99_chapter_time`、`llm_retry_count`、`scaffold_rejection_rate`
- 简易 dashboard：Grafana + 5 个 panel（每个对应一个 metric）

**实现工作量**：~5 天

---

## 3. 推荐上线路径

### 路径 A：Lean B2B API（最快）

适合首批 3-5 个种子客户做 PMF 验证。

**4 周 plan**：

| Week | 工作 |
|---|---|
| 1 | Gap 5（数据安全文档）+ Gap 4 之 fallback router 简版（仅 2 路） |
| 2 | Gap 1 计费 + Gap 2 多租户字段 |
| 3 | Gap 3 限流 + 内部 alpha 测试 |
| 4 | Gap 6 监控 + 第一批客户 onboard |

**SLA 承诺（Lean 版）**：
- pass-rate ≥ 95%（基于当前 99.4% 数据，留 4.4% buffer）
- 100 章交付时间 ≤ 8h（含 retry）
- 失败章节免费重跑 1 次
- 月度可用性 99.0%

**price 建议**：$50/100 章（1 半 cost、1 半 ops），早鸟 8 折。

### 路径 B：完整 SaaS（更稳）

适合面向 C 端作家的产品。

**12 周 plan**：路径 A + 前端 Dashboard + Stripe 集成 + 客户支持流程 + GDPR 合规。

不推荐立即走这条路：先用路径 A 验证 PMF，半年后再扩。

### 路径 C：白标 / OEM

把当前 CLI + API 直接给一个网文平台（如阅文、晋江），让他们 self-host。

**优势**：版权 / 隐私问题转移给 partner，monetization 直接走 license fee（$50K-200K/year）。

**工作量**：仅 ~2 周（写 deployment guide + license agreement）。

**适合时机**：手上有 1 个能 close 的 partner contact 时。

---

## 4. 不推荐立即商用的产品形态

### ❌ "AI 自动写续集" 这种 user-facing claim

**理由**：
- 当前 mapping_pack 是"题材改写"工具，不是"自动续写"
- 用户期望差距大：自动续写要求"原创 + 风格一致 + 情节合理"，远超 mapping 能力
- 法律风险：用户上传他人作品做"续集"涉及衍生作品权利
- 现有的同题材 baseline 还是 0/307（虽然已有修复，待验证）

### ❌ "文风迁移"（保留情节，仅换文风）

**理由**：
- mapping_pack 是"换名字 + 换世界设定"，不是"换文风"
- 文风维度的能力当前是 [capability-matrix](./chapter-imitation-capability-matrix.md) 标 **LOW**

### ❌ 任何宣称"原创"的内容生成

**理由**：源章节是必需输入，输出本质是"基于 X 的题材改写"。法律 + 营销层面别走这条线。

---

## 5. 适合首批商用的客户画像

### 5.1 网文平台（B2B）

**痛点**：海外发行需要"题材本地化"，把仙侠改成欧美奇幻 / 日韩异世界。

**报价**：单本 $200-500（≥100 章）。

**接入方式**：HTTP API + 异步 webhook。

### 5.2 小说工作室 / 工作组（B2B-SMB）

**痛点**：拥有热门 IP，希望同题材横向铺产品（ABC 三个版本，时代 / 角色 / 反派不同）。

**报价**：包月 $500（含 1 本 100 章 + 50 章 buffer）。

### 5.3 影视/动漫改编公司（行业上游）

**痛点**：拿到小说 IP 后做改编可行性研究，需要快速看不同题材版本的"叙事骨架"。

**报价**：单本 spike $100（仅 30 章）+ 完整 $500。

---

## 6. 不推荐的客户画像

### ❌ 个人作家（C 端）

**理由**：
- C 端用户价格敏感，$50/本 可能太贵
- C 端用户期望"AI 帮我写"而非"AI 帮我改写"
- 客服成本高（"为什么 ch37 没 pass"等问题）

### ❌ 起点 / 番茄等头部国内平台

**理由**：他们有自己的 AI 团队，更可能 build vs buy。除非你能给极强的 OEM 价（路径 C）。

### ❌ 政策敏感地区客户

**理由**：内容生成涉及多重监管，先在中性市场（东南亚、欧美 indie 出版）跑通再说。

---

## 7. 验收 checklist（开始接客户前必须完成）

### 必须项 (P0)

- [ ] Gap 1：计费表 + Stripe webhook 跑通
- [ ] Gap 2：tenant_id 字段 + RLS policy
- [ ] Gap 3：rate limiter（60 chapters/hour/tenant）
- [ ] Gap 5：数据安全文档 + 删除 endpoint
- [ ] [P0 同题材门槛验证 handoff](./baseline-imitation-quality-validation-handoff-20260515.md) Stage A 完成
- [ ] 第一份 sample 客户合同（含 SLA + 退款政策）

### 强烈建议 (P1)

- [ ] Gap 4：LLM router 自动 fallback
- [ ] Gap 6：5 个核心 metrics + dashboard
- [ ] 端到端 health check `/health`：自检 3 件套 + 1 章 dummy 仿写

### 可推迟 (P2)

- [ ] 完整前端 Dashboard
- [ ] 多语言 docs（en/ja/ko）
- [ ] webhook 自定义 retry policy
- [ ] 用户自助 retry CLI

---

## 8. 一句话商用 readiness 总结

> **跨题材改写 = 技术 ready，infra 4 周 ready，business 看你想多大。**
> 
> 路径 A（B2B API + 3-5 种子客户）建议立即启动。  
> 路径 B / C 视 PMF 反馈再扩。

---

## 9. 互补文档

- [chapter-imitation-capability-matrix.md](./chapter-imitation-capability-matrix.md) — 全能力矩阵（含未就绪能力）
- [baseline-imitation-quality-validation-handoff-20260515.md](./baseline-imitation-quality-validation-handoff-20260515.md) — 同题材修复后验证步骤
- [whole-book-mapping-scale-20260514.md](./whole-book-mapping-scale-20260514.md) — mapping 规模化数据
- [whole-book-imitation-docs-index.md](./whole-book-imitation-docs-index.md) — 接入契约总入口
- [ops-debug-manual-20260514.md](./ops-debug-manual-20260514.md) — 运维调试速查
- [whole-book-imitation-provider-recovery-checklist.md](./whole-book-imitation-provider-recovery-checklist.md) — provider failure 手动 ops（即将被 Gap 4 router 替代）
