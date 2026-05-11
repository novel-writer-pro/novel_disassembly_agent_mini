# Funded Provider 真实 Benchmark Runbook

> 目的：当 provider 余额/配额恢复后，直接执行一次新的 20 章真实 candidate run，并与既有卫图旧基线做严格对照。

## 1. 前提

- baseline artifact 已固定：
  - `docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json`
- benchmark 工具链已就位：
  - `scripts/benchmark_deconstruction_run.py`
  - `scripts/compare_deconstruction_benchmarks.py`
  - `scripts/export_deconstruction_benchmark_bundle.py`
  - `scripts/run_and_export_deconstruction_benchmark_bundle.py`
- 目标输入：
  - `/.tmp/weitu_first20.txt` 或新的卫图 20 章输入文件

## 2. 推荐执行命令

```bash
export NOVEL_ANALYZER_LLM_PROVIDER_NAME='deepseek'
export NOVEL_ANALYZER_LLM_BASE_URL='https://api.deepseek.com/v1'
export NOVEL_ANALYZER_LLM_API_KEY='<FUNDED_KEY>'
export NOVEL_ANALYZER_LLM_MODEL_NAME='deepseek-v4-flash'
export NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME='deepseek-v4-flash'
export NOVEL_ANALYZER_LLM_QA_MODEL_NAME='deepseek-v4-flash'
export NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME='deepseek-v4-flash'
export NOVEL_ANALYZER_EMBEDDING_BACKEND='onnx'
export NOVEL_ANALYZER_EMBEDDING_MODEL_NAME='BAAI/bge-m3'

python3 scripts/run_and_export_deconstruction_benchmark_bundle.py \
  /home/user/ai-books/.tmp/weitu_first20.txt \
  --title 'weitu-funded-benchmark' \
  --database-url 'postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer_weitu_funded_benchmark' \
  --baseline-json docs/deconstruction-acceleration/benchmarks/weitu-baseline-20260511.json \
  --output-dir runs/benchmark/weitu-funded-benchmark \
  --end-chapter 20 \
  --ensure-db
```

## 3. 必看结果

查看：
- `runs/benchmark/weitu-funded-benchmark/candidate.json`
- `runs/benchmark/weitu-funded-benchmark/compare.json`
- `runs/benchmark/weitu-funded-benchmark/summary.md`

## 4. 严格可比性判定

只有在下面条件都满足时，才把结果当成严格性能结论：
- `compare.comparability.is_strictly_comparable == true`
- `compare.comparability.chapter_count_match == true`
- `compare.comparability.provider_purity_match == true`
- `candidate.fallback_chapter_count == 0`
- `candidate.failed_jobs == 0`

否则该 run 只能作为：
- smoke 证据
- fallback 稳定性证据
- 工具链可用性证据

## 5. 最终需要汇报的指标

至少报告：
- baseline / candidate `elapsed_seconds`
- baseline / candidate `avg_seconds_per_completed_chapter`
- `failed_jobs.delta`
- `prompt_char_totals.*.delta_pct`
- `is_strictly_comparable`
- 是否出现 fallback 章节

## 6. 建议结论模板

```md
- baseline elapsed_seconds: ...
- candidate elapsed_seconds: ...
- elapsed delta pct: ...
- baseline avg/chapter: ...
- candidate avg/chapter: ...
- failed_jobs delta: ...
- strict comparable: true|false
- fallback chapter count: ...
- conclusion: [是否能把这次结果当成优化后的真实性能结论]
```
