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
