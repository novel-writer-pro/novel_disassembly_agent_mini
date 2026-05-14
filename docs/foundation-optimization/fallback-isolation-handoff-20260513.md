# Fallback Isolation — Handoff(2026-05-13)

> 一页纸交接。如果 LLM 调用失败导致启发式 fallback 再次污染数据,这里是排查 + 修复路径。

## 1. 系统当前状态(2026-05-13 收工时)

- ✅ 568 章 chapter_artifacts 全部带 `extraction_source` tag(326 heuristic / 248 llm / 0 untagged)
- ✅ 6 个 consumer service 在读 `key_entities` 前都过 `is_heuristic_artifact` guard
- ✅ 326 章污染数据已通过非破坏性 sweep 清理(`retrieval_documents.keyword_list = []` for heuristic chapters)
- ✅ 4 个 BAD 分支 jiebacfg MRR 平均提升 +280%(单分支最高 4.6×)

## 2. 设计要点(对接手人快速建模)

```
LLM 调用失败 (e.g. 402 Insufficient Balance)
    ↓
analysis_service.py:1331 → _build_local_heuristic_analysis(chapter_index, title, content)
    ↓
key_entities = _heuristic_entities(content, limit=5)  ← 凶手:18 行 regex+stop_words
    ↓
record_chapter_artifact(payload, ...)  ← Phase 1 在这里 tag extraction_source
    ↓                                       (run_service.py:545)
chapter_artifacts.payload_json["extraction_source"] = "heuristic"
    ↓
↓ ↓ ↓ ↓ ↓ ↓ (6 个 consumer 都先调 is_heuristic_artifact)
retrieval / fact / graph / tension / risk / author_knowledge
    ↓ heuristic → return [] / set() / skip
clean retrieval_documents / fact_records / graph nodes
```

## 3. 关键代码位置

| 用途 | 文件 |
|------|------|
| 启发式 fallback 实现 | `novel_analyzer/services/analysis_service.py:573-588` (`_heuristic_entities`) |
| 触发点 | `novel_analyzer/services/analysis_service.py:1331` (`_build_local_heuristic_analysis`) |
| Write-side tagging | `novel_analyzer/services/run_service.py:545` (`record_chapter_artifact`) |
| Read-side guard | `novel_analyzer/services/_fallback_guard.py` (`is_heuristic_artifact`) |
| Backfill 工具 | `scripts/backfill_extraction_source.py` |
| 清理 sweeper | `scripts/rematerialize_heuristic_artifacts.py` |

## 4. 常用运维命令

```bash
# 查看当前 fallback 数据规模
.venv/bin/python -c "
from sqlalchemy import text
from novel_analyzer.config.settings import Settings
from novel_analyzer.database.session import create_session_factory
factory = create_session_factory(Settings())
with factory() as s:
    r = s.execute(text(\"SELECT COUNT(*) FILTER (WHERE payload_json::jsonb ->> 'extraction_source'='heuristic'), COUNT(*) FROM chapter_artifacts WHERE artifact_type='chapter_analysis'\")).fetchone()
    print(f'heuristic={r[0]} / total={r[1]}')
"

# 给新增 chapter_artifacts 补 tag(idempotent)
.venv/bin/python scripts/backfill_extraction_source.py --dry-run
.venv/bin/python scripts/backfill_extraction_source.py

# 清理污染的 retrieval_documents(非破坏性,通过 upsert)
.venv/bin/python scripts/rematerialize_heuristic_artifacts.py --dry-run
.venv/bin/python scripts/rematerialize_heuristic_artifacts.py --branch <branch_id> --commit-every 20
```

## 5. 核心文档索引

| 文档 | 用途 |
|------|------|
| [`entity-extraction-noise-diagnosis-20260513.md`](./entity-extraction-noise-diagnosis-20260513.md) §1-§14 | 诊断全流程 + 修复实施记录 |
| [`fallback-isolation-plan-20260513.md`](./fallback-isolation-plan-20260513.md) | 历史设计草稿(已被实际实现覆盖) |
| [`p0-quickstart-and-handoff.md`](./p0-quickstart-and-handoff.md) | 并行 BM25 P0 工作的 handoff(不同议题) |

## 6. 测试

- `tests/test_fallback_guard.py`(7 单元测试)
- `tests/test_fallback_guard_consumers.py`(8 集成测试)
- `tests/test_run_service.py`(3 个新增 tag 测试)

## 7. 已知未做(留给下一轮)

- **§14.6** graph_nodes/edges 中由 fallback 派生的脏 entity 节点未清理(跨章共享,等下次完整 LLM 重跑)
- **§14.7** LLM provider 告警:`fallback='local-heuristic'` 触发时未 emit WARN log;quota 耗尽再次发生时仍会静默污染(下一个 commit 的目标)
- **整合**:`scripts/rematerialize_heuristic_artifacts.py` 与并行 session 的 `omx rematerialize-retrieval` CLI 可考虑合并

## 8. 紧急排查清单

如果发现某分支检索质量退化:

1. 跑 `retrieval-benchmark <branch_id> --configs simple,jiebacfg` 看 MRR 数
2. 查 `SELECT COUNT(*) FILTER (...) FROM chapter_artifacts WHERE branch_id=...` 看 heuristic 比例
3. 比例高 → 查最近 LLM 调用历史(`chapter_raw_outputs.parsed_json` 含 `stage_error`)
4. 修 LLM provider 后,跑 `rematerialize_heuristic_artifacts.py --branch ...` 清理
