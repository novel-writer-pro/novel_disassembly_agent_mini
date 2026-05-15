# Session Handoff — 2026-05-14 — Kernel Assessment & External Integration Planning

> **Branch**:`v0.2.4`(主线)+ `futures/enbed`(v5 cutover 留档)
> **Last commit**:`7536dd9 fix(prompts): forbid method-label and scaffold-marker bleed in draft_text`
> **Working tree**:有未 commit 的 router 改动(import_recovery / risk_review)+ 4 份新文档 + 1 份本 handoff。

---

## 1. 本次会话的上下文(给下一棒的人 60 秒看完)

**用户在 v5 FastAPI cutover 完成、v5.1 broken-test cleanup 进行到一半的时候,主动喊停**,要求:

> "你看我们的内核上还有哪些优化空间,距离 sota,我想的是还是需要先把核心做扎实,再考虑外部对接,所以外部的对接可以先做 roadmap + checklist + 架构图的思路规划等,后续再展开"

也就是说:**v5 测试清理 deferred,v5.1 工作暂停,优先把内核与外部对接的 4 份规划文档落下来**。

本次会话围绕这个交付。

---

## 2. 本次会话产出物

### 2.1 新增文档(已落盘,**未 commit**)

| 路径 | 行数 | 状态 |
|---|---|---|
| [docs/strategy/kernel-sota-gap-assessment-20260514.md](file:///home/user/ai-books/docs/strategy/kernel-sota-gap-assessment-20260514.md) | ~340 | ✅ 完成 |
| [docs/strategy/external-integration-roadmap-20260514.md](file:///home/user/ai-books/docs/strategy/external-integration-roadmap-20260514.md) | ~310 | ✅ 完成 |
| [docs/strategy/external-integration-checklist-20260514.md](file:///home/user/ai-books/docs/strategy/external-integration-checklist-20260514.md) | ~330 | ✅ 完成 |
| [docs/architecture/external-integration-architecture-20260514.md](file:///home/user/ai-books/docs/architecture/external-integration-architecture-20260514.md) | ~370 | ✅ 完成 |
| [docs/session-handoff-20260514-kernel-and-integration.md](file:///home/user/ai-books/docs/session-handoff-20260514-kernel-and-integration.md) | 本文档 | ✅ 完成 |

### 2.2 4 份核心规划文档的串联关系

```
            kernel-sota-gap-assessment-20260514.md
                          ▲
                          │ (内核基线 / 阻塞拆分前置)
                          │
            external-integration-roadmap-20260514.md
                    │            │
       (决策依据)   ▼            ▼  (架构视图)
   external-integration-checklist  external-integration-architecture
```

阅读顺序建议:**kernel-sota → roadmap → architecture → checklist**。
执行顺序建议:**先内核 6 周冲刺 Week 1-2 → 再开 Stage 1 外部对接**。

### 2.3 4 份文档各自的核心结论(摘要)

| 文档 | 一句话结论 |
|---|---|
| **kernel-sota** | 内核不是"差很多",而是"差关键的最后一档";阻塞集中在 4 个大文件未拆 + Loom shadow 没真跑过 + 词典生成未消费 + 风险触发器没升 LLM-judge |
| **roadmap** | 4 个 🟡 系统(Dify/n8n/Helicone/Langfuse)立即推到 ✅;Letta 唯一值得 Stage 2 PoC;UI shell 暂不动 |
| **checklist** | Stage 1 共 5 大块 17 条 atomic 任务,每条 ≤ 2h 可验证;DoD = 4 个系统都有真流量 |
| **architecture** | 5 层(UI / 编排 / 接入 / 内核 / 推理基础设施)+ 旁路 2 层(观测 / 记忆);3 张时序图(Writer Copilot / Imitation 主流量 / Reader QA 防剧透) |

---

## 3. 下一棒应该做的事

### 3.1 立即可做(无需等待)

```
[ ] 1. Commit 4 份新文档 + 本 handoff
       建议拆 2 commit:
       (a) docs(strategy): kernel sota gap assessment + external integration plan
       (b) docs(handoff): 2026-05-14 kernel & integration handoff
       Lore Constraint/Rejected/Directive trailers 见 §6 模板

[ ] 2. 用户确认 4 份文档方向无误
       (本会话已完成内容,但用户没看到最终版,只看到了"我在写"的状态)
```

### 3.2 用户认可方向后(下次会话起)

按 kernel-sota §10 的"6 周内核冲刺"启动:

```
Week 1-2 (内核阻塞拆分 + 观测启用)
  T1: jieba 词典激活 (1d, P0-1, ROI 最高)
  T2: Helicone proxy 启用 (0.5d, 直接验观测面)
  T3: risk_audit_service 拆 4 子文件 (3d, 阻塞拆分)
  T4: imitation_harness 拆 5 Registry (4d, 阻塞拆分)

Week 3-4 (Loom 闭环 + Contextual Retrieval)
  T5: Loom carry-over enabled 跑 20 章对照 (3d)
  T6: Contextual chunk prefix + 召回回归 (3d)
  T7: FActScore-lite + qa_factscore 信号 (4d)
  T8: Persona 相关性回归报告 (1d)

Week 5-6 (Reward + 风险升级)
  T9:  pairwise → DPO 0.5B reward model (2w)
  T10: LLM-judge 统一风险语义触发器 (5d, 并行)
  T11: 6 周总结 + capability scorecard 升级 (1d)
```

并行启动外部对接 Stage 1(看 checklist S1.1-S1.5):

```
[ ] S1.1 Helicone Proxy 启用 (与 T2 重合,合并做)
[ ] S1.2 Langfuse self-host
[ ] S1.3 Dify Writer Copilot 真上线
[ ] S1.4 n8n daily-eval-report 真跑
[ ] S1.5 n8n pipeline-complete-notify
```

### 3.3 deferred(本次会话不动)

```
[deferred] v5.1 broken tests cleanup (~30 个 in tests/test_api_main.py)
           原因:用户主动 redirect 到内核评估
           恢复条件:用户明确说继续 v5.1
           入口:apps/api/app/routers/{import_recovery,risk_review}.py
                + tests/test_api_main.py 当前未 commit 改动

[deferred] 22 FastAPI-only endpoints audit
[deferred] /api/review-batch-execute 最后一个 dispatch 路径完全 inline
[deferred] main.py 1585 → 进一步收缩
```

---

## 4. 关键 context 链(下一棒必须扫一遍)

### 4.1 内核现状

- 60 个 service file in `novel_analyzer/services/`
- 5 个超 1500 行的大文件(risk_audit 2156 / imitation_harness 1851 / novel_assistant 1639 / analysis 1567 / whole_book_imitation 1339 / export 2539)→ **核心阻塞**
- Loom Phase 1-5 服务全部存在,**default shadow mode**
- Foundation Phase 1-4 全部存在
- DomainDictionaryService 生成词典 → BM25 没消费 → **白捡的 ROI**
- risk_audit 内一部分语义触发器还是规则 → **可升 LLM-judge**

### 4.2 外部生态现状

| 系统 | 状态 |
|---|---|
| Dify | 🟡 docker-compose + writer-copilot DSL + iframe 都备好,无真流量 |
| n8n | 🟡 docker-compose + workflow JSON + runtime/notify.py 都备好,N8N_WEBHOOK_PIPELINE_COMPLETE_URL 默认未设 |
| Helicone | 🟡 docker-compose + llm_base_url_override 字段都备好,env 注释中未启用 |
| Langfuse | 🟡 docker-compose + Dify 集成开关都备好,未启用 |
| TEI | ✅ 真用 |
| ONNX bge-m3 + reranker | ✅ 真用 |
| pg_jieba | ✅ 装了,但词典未喂 |

### 4.3 历史决策(已论证不重做)

| 决策 | 文档 |
|---|---|
| Dify 主选,FastGPT 不切 | `docs/research/fastgpt-vs-dify.md` |
| Helicone + Langfuse 组合方案 | `docs/observability/helicone-vs-langfuse.md` |
| 不接商业 embedding,不微调 | `.sisyphus/plans/foundation-optimization-priority-research-20260512.md` |
| TEI 切换教训 | `docs/foundation-optimization/tei-integration-postmortem-20260512.md` |

### 4.4 v5 cutover 已完成事实

- 11 个 router 全部注册在 `apps/api/app/fastapi_app.py`(loom / writer / quality / library / chapters / risk_review / pipeline / import_recovery / whole_book / steering_character / meta / whole_book_imitation / reader)
- IdentityMiddleware 已 wired(v3 PR9 模块,v5 T8 真启用)
- `make api-dev` = uvicorn,`make api-wsgi-legacy` = 回滚
- main.py 2774 → 1585 行,37 → 1 dispatch 路径
- 83/83 in-scope backend tests pass at v5 commit time
- F1/F2/F3 verifications APPROVED

### 4.5 v5.1 paused state

- `apps/api/app/routers/risk_review.py`:`/api/review-batch-execute` 已 inline(249 行)
- `apps/api/app/routers/import_recovery.py`:`/api/import` 已 rewrite 接受 JSON+multipart
- `tests/test_api_main.py`:30 个 broken tests,`_call` helper 已迁到 TestClient,但调 `application()` 直连的 case 仍 404

---

## 5. 配套资源(无变化,仅参考)

### 5.1 当前可跑的命令

```bash
# 后端
make api-dev              # uvicorn :8011 (default)
make api-wsgi-legacy      # WSGI fallback (rollback)

# 前端
cd apps/web && pnpm dev   # :4173

# 测试
pytest tests/contract/test_main_fastapi_contract.py        # canonical contract
pytest tests/contract/test_dual_parity.py                   # 1-endpoint parity
pytest -k "owner_scoping or anti_spoiler"                   # core e2e

# 内核 CLI(已有)
python -m novel_analyzer.cli loom-status
python -m novel_analyzer.cli loom-consolidate
python -m novel_analyzer.cli loom-collect-pairs
```

### 5.2 关键 env

```bash
# 当前 .env.local 里有的(都已存在但部分注释掉)
NOVEL_ANALYZER_LLM_PROVIDER_NAME=deepseek
NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
NOVEL_ANALYZER_USE_MERGED_STAGES=true
NOVEL_ANALYZER_EMBEDDING_BACKEND=onnx
NOVEL_ANALYZER_RERANK_BACKEND=onnx

# Stage 1 启用时要加的(目前注释掉或未设)
NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/<target>  # Helicone
N8N_WEBHOOK_PIPELINE_COMPLETE_URL=http://localhost:5678/webhook/pipeline-complete
NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

### 5.3 当前 boulder / plan 状态

`.sisyphus/boulder.json` 可能仍指向 `v5-fastapi-cutover` plan;实际该 plan 已 13/13 完成。下次会话开新 plan 时建议:

- 内核冲刺 plan = `.sisyphus/plans/kernel-6week-sprint-20260515.md`
- 外部对接 Stage 1 plan = `.sisyphus/plans/external-integration-stage1-20260515.md`

---

## 6. 提交建议(Lore Commit Protocol)

### 6.1 拆分两个 commit

**Commit A:**

```
docs(strategy): kernel SOTA gap assessment + external integration plan

Produce 4 forward-looking planning artifacts that frame the next 6
weeks of work: a kernel vs SOTA gap matrix across 6 internal
domains, an external-integration roadmap covering 5 categories
(orchestration / observability / memory / inference infra / UI),
its ATOMIC checklist with verify+rollback per task, and a layered
mermaid architecture diagram showing current GA / wired / planned
state per system.

Constraint: User explicitly redirected mid-cutover to require
"core solidified first, external integration as planning artifacts
only" — no implementation in this turn.
Constraint: Background sub-agents kept falling through model
fallback chains; produced via direct tool inspection of code +
existing docs (Foundation roadmap, Loom roadmap, Helicone vs
Langfuse, FastGPT vs Dify, TEI postmortem).
Rejected: A single mega-document | violates the user's explicit
"roadmap + checklist + 架构图" three-artifact split.
Rejected: Implementing Stage 1 in this turn | user's redirect
explicitly defers external integration to "后续再展开".
Rejected: Adding new external systems beyond what's already wired |
must respect 5-question gate in roadmap §2.2 first.
Confidence: high
Scope-risk: narrow (docs only)
Reversibility: clean
Directive: Before starting Stage 1 of external integration, the
6-week kernel sprint Week 1-2 (jieba activation + Helicone enable +
risk_audit/imitation_harness split) MUST be done — these unblock
all downstream optimization work.
Tested: Documents read end-to-end for cross-references
Not-tested: Stage 1 落地命令 (Helicone curl, Langfuse compose) —
deferred to Stage 1 execution turn
```

**Commit B:**

```
docs(handoff): 2026-05-14 kernel & integration session

Capture the redirect from v5.1 cleanup to kernel-vs-SOTA assessment +
integration planning, what's deferred (v5.1 broken tests,
22 FastAPI-only endpoints audit), and the recommended next-session
sequence (kernel 6-week sprint Week 1-2 + external integration
Stage 1 in parallel).

Constraint: v5.1 paused mid-test-cleanup; ~30 broken tests in
tests/test_api_main.py remain.
Confidence: high
Scope-risk: narrow
Directive: tests/test_api_main.py + apps/api/app/routers/
{import_recovery,risk_review}.py have uncommitted local changes
from v5.1 — DO NOT discard them; they are the v5.1 resumption
point.
```

### 6.2 不要 commit 的文件

- `.sisyphus/run-continuation/ses_*.json`(运行时状态,gitignored 应该)
- `tests/test_api_main.py`(v5.1 进行中,留作恢复点)
- `apps/api/app/routers/{import_recovery,risk_review}.py`(同上)

---

## 7. 给下一棒的 1 行建议

> **先让用户看一眼这 4 份新文档**,确认方向无误,**再 commit**;然后按 kernel-sota §10 启动内核 6 周冲刺 + checklist Stage 1 并行。**不要回去碰 v5.1 broken tests,除非用户明确要求。**

---

## 8. Week 1-2 + T6 sprint outcomes (2026-05-14 → 05-15)

After the 4 planning artifacts landed, work resumed on the kernel sprint. The
following commits ship internal-state changes (not just docs):

| Commit | T# | Surface |
|---|---|---|
| `ae16931` | T1 | jieba domain dictionary validator + cleaned userdict (7000+ → 2627 valid terms) + `docs/runbook/bm25-jieba-reindex.md` |
| `26952d0` | T2 | `scripts/dev/helicone-doctor.py` + `docs/runbook/helicone-enable.md` for proxy-trace activation |
| `80971ee` | T3 | `risk_audit_service.py` 2156 → 365 + `risk_audit_checkers.py` 1854 (9 GateChecker classes split out) |
| `03daf85` | T4 | `imitation_harness_helpers.py` 238 lines (8 pure helpers extracted; class shrank by 35 net lines) |
| `77670c4` | T6 | `RetrievalService._embedding_inputs_for_chunks()` contextual-prefix wiring, flag-gated, default off |

**5 commits pushed to `origin/v0.2.4`. All in-scope tests pass:**
- `test_domain_dictionary_service.py` 4/4
- `tests/e2e/test_llm_base_url_override.py` 4/4
- `test_risk_audit_service.py` 40/40 + `test_export_risk_card.py` 11/11 + `test_export_report.py` 18/18
- `test_imitation_harness_service.py` 32/32 + `test_loom_phase2.py` 4/4 + `test_chapter_imitation_service.py` 9/9
- `test_retrieval_service.py` 21/21 (incl. 3 new contextual-prefix tests)

### 8.1 Deferred (operator/data-side, NOT lost)

| Task | Why deferred this turn | Resumption signal |
|---|---|---|
| T1.5 `bm25-reindex` | `ALTER TABLE DROP COLUMN bm25_vector` requires `AccessExclusiveLock`; PID 7235 `writer-imitate-range` (started 06:41, still running 1h+ later) holds `AccessShareLock`. My ALTER queued and would have read-locked the entire table for the duration. **Cancelled to keep user's job alive.** | Wait for PID 7235 to finish or coordinate maintenance window, then run `python -m novel_analyzer.cli.app bm25-reindex --confirm` per `docs/runbook/bm25-jieba-reindex.md` |
| T2.5 Helicone container up | No docker-socket access from this user; container start is operator step | Run `cd infra/helicone/upstream && docker compose up -d`, then `python scripts/dev/helicone-doctor.py` — exits 0 when trace is live |
| T5 Loom carry-over 20-章 A/B | DB locked by T1.5 blocker + needs 20 real LLM imitation runs | After T1.5 complete; needs LLM budget + ~3 days runtime |
| T7 FActScore-lite QA grounding | Requires new LLM prompt in `prompts.py`. The v5 cutover constraint **explicitly forbids** modifying `prompts.py`. Implementing as a deterministic ngram-overlap stub would ship a misleading signal. | Either lift the v5 prompt-freeze, or accept stubbed signal with strict warning labels |
| T8 Persona real-vs-simulated correlation | Needs accumulated reader_feedback rows + reader_simulation history; current branches don't have enough data points | After at least 3 branches have ≥30 reader_feedback entries each |

### 8.2 Honest reality check on kernel-sota §10 timeline

The 6-week sprint plan I wrote in `kernel-sota-gap-assessment-20260514.md` overestimated what's achievable as pure code-side work. **Half of Week 3-4 + Week 5-6 tasks need either a clear DB maintenance window, accumulated runtime data, or a relaxation of the v5 prompts.py freeze.** The plan is still directionally right, but the order should be:

1. **Operator first**: open a maintenance window, complete T1.5 + T2.5
2. **Data first**: kick off Loom shadow runs to generate the data T5/T8 need
3. **Decision first**: get explicit OK to edit `prompts.py` for T7, OR redefine T7 as ngram-only with a clear caveat
4. **Then code**: T9 (reward model), T10 (LLM-judge unification) can be staged in parallel once 1-3 are unblocked

### 8.3 Things in this branch that should NOT be discarded

```
M apps/api/app/routers/import_recovery.py   # v5.1 paused
M apps/api/app/routers/risk_review.py       # v5.1 paused
M tests/test_api_main.py                    # v5.1 paused — 30 broken tests
```

These are v5.1 in-progress edits flagged in §6 Directive of commit `80a46f6`. Do not `git checkout` them.

---

## 9. 修订记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-05-14 | 初版 |
| 1.1 | 2026-05-15 | Week 1-2 + T6 sprint outcomes — 5 commits shipped (T1/T2/T3/T4/T6); T1.5/T2.5/T5/T7/T8 deferred with explicit resumption signals |
| 1.2 | 2026-05-15 | Borrow items B1/B4/B5 shipped (3 of 5 from competing-novel-ai-projects-20260515.md); B2/B3 deferred — see §10 |
| 1.3 | 2026-05-15 | Validation surfaced B1 inverted + scaffold cascade bug; 4 corrective commits + ch49 follow-through — see §11 |

---

## 10. Borrow items from competing project research (2026-05-15 后续)

(unchanged from §10 in v1.2 — B1/B4/B5 shipped, B2/B3 deferred, wiring deferred)

---

## 11. Validation cycle and follow-through (2026-05-15 v1.3)

After §10 shipped 3 standalone scoring helpers, a validation pass against
the real 507-draft corpus produced a finding that **invalidated the
"diagnostic → quality gate" promotion path** for B1, and incidentally
surfaced a real cascade bug. Shipped 6 corrective commits:

| Commit | Surface | Why |
|---|---|---|
| `3eeecda` | Real-data threshold calibration + reusable benchmark script | Original docstring thresholds (0.55/0.45) were unit-test-derived and caught 0/507 real drafts |
| `8f24346` | Validation finding doc | B1 ai_trace correlates BACKWARDS with harness verdict (pass mean 0.201 > needs_revision mean 0.184). The dominant ngram_repetition component tracks narrative density, not "AI flavor". B4 effect size below noise floor |
| `1d6cbae` | B1/B4 docstring demotion to "diagnostic only, NOT a gate" | Prevent future re-promotion based on stale claims |
| `db2a179` | Loom signal extractor early-returns None for `is_scaffold_only=True` drafts | Defense-in-depth — current "no signal" gate at line 3363 catches ch49 by accident |
| `a7d43a3` | Block scaffold-only `draft_text` from `previous_excerpt` + `generated_summary` carry-over | **Real cascade bug** — scaffold outline text was leaking into next chapter's prompt context augmentation |
| `d29d771` | `is_scaffold_only` exposed on `/api/writer/imitate` response | Closes the audit chain so frontend can render scaffold banner |

### 11.1 Cascade bug discovery — the real win of validation

The benchmark surfaced `output/whole-book-zhuxian-scifi-59ch/writer-imitate-ch49.json`:
502 chars of pure outline scaffold (`【章节目标】斗败老怪 / 场景1：承接上一章 / ...`)
persisted as `final_draft.draft_text` with `is_scaffold_only=True` and
`final_verdict=needs_revision`. The harness correctly knew it had failed.
Audit of 5 downstream consumers found **2 of them silently fed scaffold text
into next-chapter prompt context**:

- `chapter_imitation_service.build_multi_chapter_consistency:589/603` → scaffold
  excerpt entered `MultiChapterImitationStep.final_draft_excerpt`, then 120 chars
  of it became the next chapter's `previous_excerpt`, telling the LLM to
  "continue from this scene" when there was no scene at all.
- `whole_book_imitation_service:818` → `WholeBookCarryOverState.generated_summary`
  (220 chars of scaffold) flowed into the next chapter's `target_goal`
  augmentation: `承接上一生成状态：【章节目标】斗败老怪 场景1：...`.
  Meta-prompt language bleeding into prose generation.

Fixed by checking `is_scaffold_only` before extracting context; scaffold
contributes empty string to carry-over and a sentinel string
(`"[scaffold-only fallback; not user-facing prose]"`) to viewer excerpts.

### 11.2 Lessons for future borrow items

1. **Threshold calibration ≠ signal validation.** Always run a correlation
   against the **outcome variable** (here: harness `final_verdict`) before
   claiming a heuristic is a quality signal.
2. **"Inspired by N-star repo X" doesn't transfer.** The inkos 33-dim audit
   lives inside a different harness; their dimensions might not be redundant
   with their main pipeline. Ours are.
3. **Pure-function helpers cost nothing as diagnostics**, but **wiring claims
   are expensive** — they would have produced false alerts in production
   reviewer queues.
4. **Always audit downstream cascades** when adding a new produce/consume
   contract. The scaffold flag existed for a year before anyone checked
   whether all consumers honored it.
5. **Validation can find bugs you weren't looking for.** The cascade bug
   was a surprise; running B1 was the only reason we discovered it.

### 11.3 Audit chain status

| Site | Status |
|---|---|
| `_extract_writer_output_loom_signal` (cli/app.py) | ✅ guarded |
| `MultiChapterImitationStep.final_draft_excerpt` (chapter_imitation) | ✅ guarded |
| `WholeBookCarryOverState.generated_summary` (whole_book_imitation) | ✅ guarded |
| `WholeBookImitationExecutedStep.draft_excerpt` (whole_book_imitation) | ✅ sentinel-replaced |
| `MultiChapterImitationConsistencyReport.previous_excerpt` (chapter_imitation) | ✅ empty when scaffold |
| `/api/writer/imitate` response | ✅ field exposed |
| `clean_imitation_drafts.py` | ✅ already detects via regex |
| `render_workspace_chapter_md.py` | ✅ already shows banner with --clean |
| `cli/app.py` markdown render paths (lines 3149/3195/3279) | ⚠️ render scaffold prose without banner — cosmetic, not safety; deferred |

### 11.4 Outstanding work after this cycle

- B5 Elo wiring into `pairwise_eval_service` — still ready, still needs DB
  schema decision
- B2 (relationship dim in retrieval) — needs live retrieval testing
- B3 (arc-rolling planning) — multi-day integration, should be its own plan
- T1.5 bm25-reindex — still blocked by long-running graph_edges INSERT
  transactions; check `pg_stat_activity` before next attempt
- cli/app.py markdown render paths — could add scaffold banner; cosmetic only

### 11.5 Things still NOT to discard from working tree

```
M apps/api/app/routers/import_recovery.py   # v5.1 paused
M apps/api/app/routers/risk_review.py       # v5.1 paused
M tests/test_api_main.py                    # v5.1 paused — 30 broken tests
```

(Same as §8.3 + §10.3, restated.)

---

## 10. Borrow items from competing project research (2026-05-15 后续)

After [docs/research/competing-novel-ai-projects-20260515.md](research/competing-novel-ai-projects-20260515.md) identified 5 borrow candidates, 3 were shipped as standalone scoring helpers (no DB, no LLM, no integration risk):

| Commit | Borrow | Surface |
|---|---|---|
| `0dc7232` | **B1** AI-trace heuristic | `novel_analyzer/services/ai_trace_signal_service.py` — ngram repetition + sentence uniformity + hedge density. 8/8 tests. |
| `a868b32` | **B4** Mechanical slop scorer | `novel_analyzer/services/slop_scorer_service.py` — cliché density + show-don't-tell + adverb stacking. 8/8 tests. Verified orthogonal to B1. |
| `837e346` | **B5** Elo tournament | `novel_analyzer/services/elo_tournament_service.py` — pure math aggregation over pairwise outcomes. 11/11 tests. |

### 10.1 B2/B3 deferred

| Borrow | Why deferred | Resumption shape |
|---|---|---|
| **B2** Relationship dim in retrieval | Pure-function helper feasible, but the actual value is wiring it as the 4th dimension in `ContextService.adaptive_fact_context_json`. Live retrieval modifications are too risky while writer-imitate-range processes are still inserting graph_edges. | Add `_relationship_route()` method to `ContextService` mirroring `_foreshadow_route`/`_relevance_route`. Reads `GraphEdge` table where `edge_type IN ('relationship', 'alliance', 'enmity')`. Test against a real branch with active relationship subgraph. |
| **B3** Arc-rolling planning | Multi-day integration: needs `next_chapter_planner_service` rework + new `BranchArc` table or jsonb field on `RunBranch` + Architect agent stage in imitation harness. | Treat as a separate `kernel-7week-arc-rolling.md` plan. Cannot fit into the 6-week kernel sprint window without expanding scope. |

### 10.2 Wiring B1/B4/B5 into the orchestrator (also deferred)

All three shipped helpers are **standalone scoring functions**, not yet called by `RiskAuditService` or `pairwise_eval_service`. The wiring is intentionally postponed:

- B1/B4 → should land as new GateChecker classes in `risk_audit_checkers.py` taking `ChapterImitationDraft.draft_text` as input. The current GateChecker contract takes `(artifact_payload, facts)` not draft text — needs a new dispatch path.
- B5 → should write Elo deltas back to `loom_pairwise_evaluations` (or a sibling table) on each new pair. Needs DB write surface.

Both wirings need a clean DB maintenance window AND a live integration test path. Defer to the same window as T1.5/T2.5.

### 10.3 Things in this branch that still should NOT be discarded

```
M apps/api/app/routers/import_recovery.py   # v5.1 paused
M apps/api/app/routers/risk_review.py       # v5.1 paused
M tests/test_api_main.py                    # v5.1 paused — 30 broken tests
```

(Same as §8.3, restated.)
