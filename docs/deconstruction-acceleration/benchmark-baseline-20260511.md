# 拆书加速基线 benchmark（2026-05-11）

> 目的：在 Quick / Deep 双档尚未真正落地前，先固定**当前 canonical 默认读路径**的基线证据，避免后续优化误伤仿写默认行为。

## 范围

- 不改当前 imitation / context 默认行为
- 只测当前 `ContextService.context_bundle()` 的 canonical 读路径基线
- 这份文档不是 Quick/Deep 性能宣称，只是后续对比的零点

## 基线命令

```bash
python - <<'PY'
from pathlib import Path
from time import perf_counter
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.database.session import create_schema
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.run_service import RunService

engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
create_schema(engine)

with Session(engine) as session, TemporaryDirectory() as td:
    novel_path = Path(td) / 'novel.txt'
    novel_path.write_text('第1章 一\\n正文\\n', encoding='utf-8')
    novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
    _, branch = RunService(session).create_run(novel.id, manifest.id)
    fact_service = FactService(session)
    graph_service = GraphService(session)
    run_service = RunService(session)
    for idx in range(1, 6):
        artifact = run_service.record_chapter_artifact(
            branch.id,
            idx,
            {
                'chapter_index': idx,
                'normalized_title': f'第{idx}章',
                'chapter_summary': f'第{idx}章摘要',
                'key_entities': ['卫图', '养生功'],
                'key_events': [f'第{idx}章事件'],
                'continuity_notes': [f'第{idx}章衔接'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'hook_score': 4.5,
                'dimensions': [],
            },
        )
        fact_service.materialize_for_artifact(artifact.id)
        graph_service.materialize_for_artifact(artifact.id)
        fact_service.materialize_window_if_ready(branch.id, idx, 5)
    service = ContextService(session)
    rounds = 200
    started = perf_counter()
    for _ in range(rounds):
        bundle = service.context_bundle(branch.id, 6)
        assert bundle['previous_summary'] == '第5章摘要'
    elapsed_ms = (perf_counter() - started) * 1000
    print(f'rounds={rounds}')
    print(f'total_ms={elapsed_ms:.3f}')
    print(f'avg_ms={elapsed_ms / rounds:.3f}')
PY
```

## 本次实测

- 测试日期：2026-05-11
- 环境：本地 SQLite 内存库
- 目标：5 章 canonical artifact + window materialization 后读取第 6 章 context bundle

| 指标 | 结果 |
|---|---:|
| rounds | 200 |
| total_ms | 5154.937 |
| avg_ms | 25.775 |

## 解释边界

- 这是**默认 canonical 读路径**的本地基线，不代表真实 LLM / pipeline / async lane 的整体吞吐。
- 它只能回答：后续引入 shadow metadata、enrichment companion、Quick / Deep lane 后，默认 context 读取是否被明显拖慢。
- 后续真正实现 `_deconstruction_profile`、reader isolation、stale guard 后，应补：
  - 10 章 baseline vs quick
  - canonical commit latency vs enrichment latency
  - concurrency=1 vs post-commit enrichment lane 对照

## 真实 run benchmark（funded-provider 恢复后复跑入口）

当真实 provider 可用时，推荐直接用下面脚本汇总一次完整拆书 run 的耗时与 prompt 成本：

```bash
python3 scripts/benchmark_deconstruction_run.py <run_id> <branch_id> --database-url <dburl> --json
```

建议至少记录：
- `completed_chapters`
- `failed_jobs`
- `elapsed_seconds`
- `avg_seconds_per_completed_chapter`
- `prompt_char_totals.*`
- `per_chapter[*].total_prompt_chars`

这样后续就能同时对比：
- 优化前后 wall-clock
- 优化前后 prompt 体积
- prompt 缩减是否真实兑现成耗时下降

## 当前卫图真实 run 基线（旧 run，无 prompt metrics）
已汇总：
- run: `754b205f-22fc-4eeb-962d-6d6800c4052d`
- branch: `03c657c8-5389-4e42-9234-b14137c04125`
- `completed_chapters=20`
- `failed_jobs=0`
- `elapsed_seconds=4728.32721`
- `avg_seconds_per_completed_chapter=236.4163605`

说明：
- 这份 run 完成于 prompt-metrics 埋点落地之前；
- 所以它可作为 wall-clock 基线，但不能提供 prompt_char_totals；
- 下一次 funded-provider 重跑将作为“带 prompt metrics 的新基线”。

## 对照命令（新 funded run 完成后）
先分别导出两份 benchmark JSON：
```bash
python3 scripts/benchmark_deconstruction_run.py <baseline_run_id> <baseline_branch_id> --database-url <dburl> --json > baseline.json
python3 scripts/benchmark_deconstruction_run.py <candidate_run_id> <candidate_branch_id> --database-url <dburl> --json > candidate.json
```

再运行：
```bash
python3 scripts/compare_deconstruction_benchmarks.py baseline.json candidate.json --json
```

重点关注：
- `elapsed_seconds.delta_pct`
- `avg_seconds_per_completed_chapter.delta_pct`
- `failed_jobs.delta`
- `prompt_char_totals.*.delta_pct`

## 一键执行入口（新对照 run）
```bash
python3 scripts/run_deconstruction_benchmark.py /path/to/novel.txt   --title 'benchmark'   --database-url <dburl>   --end-chapter 20   --ensure-db   --json > candidate.json
```

再与旧基线对比：
```bash
python3 scripts/compare_deconstruction_benchmarks.py baseline.json candidate.json --json
```

## 固定旧基线 artifact
- JSON: `docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json`
- Markdown: `docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.md`

## runner + compare smoke 证据
已验证：
- candidate smoke run: `38fc4606-eedd-495c-9370-9ff09ee4bf19`
- candidate smoke branch: `6b4239db-875b-4862-8f2e-d628421023ad`
- `completed_chapters=1`
- `failed_jobs=0`
- `elapsed_seconds=14.360999`

说明：
- 这是工具链执行面 smoke，不是正式 20 章 funded-provider 对照结果；
- 但它证明 runner + summarize + compare 三段式已经可以在真实数据库上闭环使用。

## fallback-aware 对照原则
后续对照时，优先使用：
- `is_pure_primary_provider_run=true`
- `fallback_chapter_count=0`

若 candidate run 混入 fallback/heuristic，则应把它标记为：
- 工具链可用性证据 / 兜底稳定性证据
- 而不是纯粹的 primary provider 性能证据

## 完整交付包导出命令
```bash
python3 scripts/export_deconstruction_benchmark_bundle.py baseline.json candidate.json out_dir
```

输出：
- `out_dir/baseline.json`
- `out_dir/candidate.json`
- `out_dir/compare.json`
- `out_dir/summary.md`

## compare 结果解读原则
当 `compare.json` 里：
- `comparability.is_strictly_comparable=true`

才适合把该对照当成严格性能结论。

若为 `false`，则应优先把结果解释为：
- smoke / 可用性证据
- fallback 稳定性证据
- 或非等价样本对照

## 最终一键对照入口
```bash
python3 scripts/run_and_export_deconstruction_benchmark_bundle.py /path/to/novel.txt   --title 'benchmark'   --database-url <dburl>   --baseline-json docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json   --output-dir out_dir   --end-chapter 20   --ensure-db
```

## 最终链路 smoke 证据
已验证：
- candidate smoke run: `76acab25-c731-43a4-a479-5a66032c096b`
- bundle dir: `/tmp/deconstruction-bundle-smoke`
- compare 结果：
  - `chapter_count_match=false`
  - `provider_purity_match=false`
  - `is_strictly_comparable=false`

说明：
- 最终一键交付链已真实可执行；
- 但这只是工具链 smoke，不是正式 funded-provider 20 章对照结论。

## 交付前校验命令
```bash
python3 scripts/check_deconstruction_benchmark_bundle.py out_dir --json
```

建议：
- 只有在 validator 返回 `ok=true` 时，才把该 bundle 当作正式交付物发送。

