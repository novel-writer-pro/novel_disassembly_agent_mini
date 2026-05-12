# 拆书引擎 SOTA 优化 — 完整交付与后续开发 Handoff

## 交付概述

本轮优化将拆书引擎从"固定窗口 + 逐 stage 串行"架构升级为"自适应检索 + 合并 stage + 多层记忆 + 质量自检 + 自动修复"的 SOTA 级架构。

**核心指标**:
- 单章耗时：330.4s → 170.2s（**-48%**）
- LLM 调用次数：5 → 3 次/章
- 新增 10 个独立 service，零额外 LLM 成本
- 门控从"检测型"升级为"检测+修复型"
- 文档从 90 份平铺精简为 4 层深度管理

---

## 交付物清单

### 新增 Service (10 个)

| 文件 | 功能 | LLM 成本 |
|------|------|----------|
| `novel_analyzer/services/foreshadowing_service.py` | 伏笔生命周期 planted/reinforced/paid_off | 零 |
| `novel_analyzer/services/entity_resolution_service.py` | 实体指代消解 (Jaccard 聚类) | 零 |
| `novel_analyzer/services/arc_memory_service.py` | 三层弧记忆 (recent/midrange/distant) | 零 |
| `novel_analyzer/services/causal_graph_service.py` | 因果图提取 + 逻辑断裂检测 | 零 |
| `novel_analyzer/services/confidence_calibration_service.py` | 四因子置信度校准 | 零 |
| `novel_analyzer/services/self_evaluation_service.py` | 5 项确定性自评估 | 零 |
| `novel_analyzer/services/claim_grounding_service.py` | 声称级原文锚定验证 | 零 |
| `novel_analyzer/services/auto_repair_service.py` | 4 类确定性自动修复 | 零 |
| `novel_analyzer/services/confidence_gated_activation_service.py` | 动态 checker 激活/severity 调整 | 零 |
| `skills_dir/chapter-intake-and-facts/prompts/main.md` | 合并 intake+facts prompt | - |
| `skills_dir/evidence-and-analysis/prompts/main.md` | 合并 evidence+analysis prompt | - |

### 修改文件

| 文件 | 变更 |
|------|------|
| `novel_analyzer/services/context_service.py` | 自适应三策略检索 + 实体消解 + 弧记忆 + 伏笔注入 |
| `novel_analyzer/services/analysis_service.py` | 合并 stage + 复杂度路由 + 全部后处理集成 + 风控 |
| `novel_analyzer/services/qa_service.py` | 别名扩展检索 + 伏笔/因果上下文注入 |
| `novel_analyzer/services/export_service.py` | 伏笔表 + 因果链导出 |
| `novel_analyzer/services/risk_audit_service.py` | confidence-gated checker 激活 |
| `novel_analyzer/agent/pipeline.py` | 合并 stage 映射 |
| `novel_analyzer/config/settings.py` | `use_merged_stages` 配置 |
| `novel_analyzer/application/pipeline_async.py` | 批量章节处理 |
| `apps/api/app/main.py` | quality-dashboard API 端点 |
| `.env.example` | 推荐 deepseek-v4-flash 配置 |

---

## 架构全景

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Chapter Analysis Pipeline                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Stage 1: intake + fact_extractor (merged, 1 LLM call)        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │                                                              │
│       ├── complexity_score → model routing (small/large)             │
│       ├── entity_resolution → alias expansion                        │
│       ├── adaptive_fact_context (relevance + recency + foreshadow)  │
│       ├── adaptive_graph_context (relevance-ranked nodes)            │
│       ├── arc_memory (3-tier: recent/midrange/distant)              │
│       ├── open_foreshadowing_threads (lifecycle-managed)            │
│       │                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Stage 2: evidence_binder + analysis_generator (1 LLM call)   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Stage 3: anti_fabrication_guard (1 LLM call)                 │   │
│  │ + state_summary_guard (deterministic)                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│       │                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ Post-processing (all deterministic, zero LLM cost)           │   │
│  │                                                               │   │
│  │  self_evaluation (5 checks)                                   │   │
│  │  → claim_grounding (source text anchoring)                    │   │
│  │  → auto_repair (overclaim/dedup/backfill/summary)             │   │
│  │  → quality_gate (hook score, meta-narrative detection)        │   │
│  │  → artifact persist                                           │   │
│  │  → materialization (retrieval/fact/graph/window)              │   │
│  │  → foreshadowing lifecycle update                             │   │
│  │  → entity resolution (alias map rebuild)                      │   │
│  │  → causal graph extraction + logic-break detection            │   │
│  │  → confidence calibration (4-factor weighted)                 │   │
│  │  → loom memory consolidation                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                    Risk Audit (9 checkers, confidence-gated)          │
│  character_ooc | world_rule | relationship | foreshadow_payoff      │
│  setting_scope | thread_closure | plot_logic | timeline | power     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Benchmark 数据

| 配置 | 单章耗时 | vs 基线 | LLM 调用 |
|------|---------|---------|----------|
| 原始基线 | 330.4s | - | 5 |
| Phase 1 (merged only) | 254.0s | -23% | 3 |
| Phase 3 (entity + arc) | 136.0s | -59% | 5 |
| Phase 4 non-merged | 241.3s | -27% | 5 |
| **Phase 4 merged (推荐)** | **170.2s** | **-48%** | **3** |

Provider: deepseek-v4-flash @ https://api.deepseek.com/v1
Novel: 775 chapters, ~5.2MB

---

## 推荐生产配置

```bash
NOVEL_ANALYZER_LLM_PROVIDER_NAME=deepseek
NOVEL_ANALYZER_LLM_BASE_URL=https://api.deepseek.com/v1
NOVEL_ANALYZER_LLM_API_KEY=your-key
NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_USE_MERGED_STAGES=true
```

---

## 后续开发 Roadmap

### 短期 (1-2 周) — 验证与调参

| 任务 | 优先级 | 预期工作量 | 说明 |
|------|--------|-----------|------|
| 跑 30 章连续分析 | P0 | 1 天 | 验证全栈稳定性，收集 grounding_ratio/repair_count/risk_density 数据 |
| 调整 complexity threshold | P1 | 2h | 根据 30 章数据调整 0.7 阈值 |
| 调整 entity similarity threshold | P1 | 2h | 根据实际别名聚类结果调整 0.6 阈值 |
| 前端接入 quality-dashboard API | P1 | 1 天 | `/api/quality-dashboard` 已就绪，前端做可视化 |
| 清理 provider_health 文件 | P2 | 30min | 当前 degraded_events 累积过高，需重置 |

### 中期 (2-4 周) — 能力增强

| 任务 | 优先级 | 预期工作量 | 说明 |
|------|--------|-----------|------|
| LLM-based Coreference | P1 | 2 天 | 在 fact_extractor prompt 中增加"同一人物不同称呼"指令 |
| Arc Auto-segmentation | P2 | 2 天 | 基于 continuity_notes 变化幅度检测弧边界 |
| Streaming Early Abort | P2 | 1 天 | 前 200 token 检测格式错误，立即 abort 重试 |
| Quality Dashboard 前端 | P1 | 3 天 | 置信度分布图、伏笔甘特图、risk 热力图 |
| 导出 Mermaid 因果图 | P2 | 1 天 | 从 causal_chains 生成 mermaid 可视化 |

### 长期 (1-2 月) — 架构演进

| 任务 | 优先级 | 预期工作量 | 说明 |
|------|--------|-----------|------|
| True Pipeline Pipelining | P3 | 3 天 | N+1 intake 与 N materialization 并行 |
| Adaptive Context Budget | P3 | 1 天 | 根据模型 context window 动态调整 |
| Multi-language Causal Markers | P3 | 2h | 英文/日文因果关键词 |
| Hard Circuit Breaker | P3 | 1 天 | degraded_events >= 10 自动切换 provider |
| Confidence Calibration N+1 优化 | P3 | 1 天 | 批量查询替代逐 fact 查询 |

---

## 接手开发者快速起手指南

### 1. 环境准备

```bash
cd /home/user/ai-books
cp .env.example .env.local  # 填入 API key
.venv/bin/python -m pytest tests/test_analysis_service.py -q  # 验证 32 pass
```

### 2. 理解代码结构

```
novel_analyzer/
├── services/
│   ├── analysis_service.py      ← 主 pipeline (入口: analyze_range)
│   ├── context_service.py       ← 自适应上下文组装
│   ├── foreshadowing_service.py ← 伏笔生命周期
│   ├── entity_resolution_service.py ← 实体消解
│   ├── arc_memory_service.py    ← 三层弧记忆
│   ├── causal_graph_service.py  ← 因果图
│   ├── confidence_calibration_service.py ← 置信度校准
│   ├── self_evaluation_service.py ← 自评估
│   ├── claim_grounding_service.py ← 声称锚定
│   ├── auto_repair_service.py   ← 自动修复
│   ├── confidence_gated_activation_service.py ← 动态门控
│   ├── qa_service.py            ← QA (已集成新能力)
│   ├── export_service.py        ← 导出 (已集成新能力)
│   └── risk_audit_service.py    ← 风险审计 (已集成 confidence gate)
├── agent/pipeline.py            ← stage 映射
├── config/settings.py           ← 配置
└── application/pipeline_async.py ← 异步 pipeline runner
```

### 3. 关键入口

- **跑一章分析**: `AnalysisService(session, settings).analyze_range(run_id, branch_id, 1, 1)`
- **跑 pipeline**: `start_pipeline_run_async(run_id=..., branch_id=..., concurrency=2)`
- **QA 问答**: `BranchQAService(session, settings).answer_question(branch_id, "问题")`
- **导出**: `ExportService(session).export_chapter_bundle(branch_id, chapter_index)`
- **质量仪表盘**: `GET /api/quality-dashboard?branch_id=...`

### 4. 调参指南

| 参数 | 位置 | 当前值 | 调整建议 |
|------|------|--------|---------|
| `ADAPTIVE_FACT_LIMIT` | ContextService | 30 | 长篇可增至 50 |
| `ADAPTIVE_RELEVANT_LIMIT` | ContextService | 16 | 检索精度不够时增加 |
| `SIMILARITY_THRESHOLD` | EntityResolutionService | 0.6 | 误合并多时提高到 0.7 |
| Complexity threshold | AnalysisService | 0.7 | 模型切换太频繁时提高 |
| `ARC_COMPRESSION_RATIO` | ArcMemoryService | 3 | distant tier 太粗时降到 2 |
| `GROUNDING_CONFIDENCE_BOOST` | ClaimGroundingService | 0.1 | grounding 太严时降低 |
| `MAX_OVERCLAIM_DEMOTIONS` | AutoRepairService | 5 | 修复太激进时降低 |

### 5. 新增功能开发模式

所有新增 service 遵循相同模式：
1. 创建 `novel_analyzer/services/xxx_service.py`
2. 在 `AnalysisService.__init__` 中实例化
3. 在 `analyze_range` 的 post-processing 区域调用（try/except 包裹）
4. 如需注入 context，在 `ContextService.adaptive_fact_context_json` 中添加字段
5. 如需导出，在 `ExportService.export_chapter_bundle` 中添加字段

---

## 已知限制

1. **实体消解**: Jaccard 无法处理语义级别名（"那个少年"≠"卫图"）
2. **因果提取**: 基于关键词匹配，隐含因果可能遗漏
3. **弧记忆**: 固定窗口分层，不感知故事弧自然边界
4. **置信度校准**: 首章数据不足时校准效果有限
5. **自评估**: 纯确定性检查，无法发现语义层面逻辑错误
6. **Claim Grounding**: 中文分词边界可能影响关键词匹配精度
7. **Auto-repair**: 保守策略，只降级/去重/回填，不会创造新内容
8. **Provider Health**: 当前仅观察模式，不自动熔断

---

## 回滚方案

```bash
# 回退到非合并模式
NOVEL_ANALYZER_USE_MERGED_STAGES=false

# 所有新增 service 均为 additive，不修改原有数据结构
# 回退无数据风险
```

---

## 文档入口

| 文档 | 说明 |
|------|------|
| [docs/README.md](../../docs/README.md) | 文档主入口 (4 层深度管理) |
| [roadmap-sota-optimization.md](./roadmap-sota-optimization.md) | 完整 roadmap + benchmark + 风险矩阵 |
| [architecture.md](./architecture.md) | Quick/Deep 双档架构设计 |
| [user-manual.md](./user-manual.md) | 用户使用说明 |
