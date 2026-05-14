#!/usr/bin/env python3
"""Bootstrap a reproducible manual-eval workspace for Weitu Loom validation."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from sqlalchemy import select

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import AnalysisRun, NovelSource, RunBranch
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.domain.schemas import StoryMappingPack
from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.whole_book_imitation_service import WholeBookImitationService


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "runs" / "manual_eval" / "_template"
TARGET_ROOT = ROOT / "runs" / "manual_eval"


def _settings(database_url: str | None = None) -> Settings:
    runtime = get_settings().model_copy(deep=True)
    if database_url:
        runtime.database_url = database_url
    return runtime


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reproducible Weitu Loom validation workspace.",
    )
    parser.add_argument("branch_id")
    parser.add_argument("workspace_slug", nargs="?", default="weitu-sample")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--project-title",
        default="卫图验证项目",
    )
    parser.add_argument(
        "--source-work-name",
        default="卫图原作",
    )
    parser.add_argument(
        "--target-work-name",
        default="卫图仿写验证",
    )
    parser.add_argument(
        "--chapter-goal",
        action="append",
        dest="chapter_goals",
        default=[],
        help="Pairs like 2:延续卫图求养生功线索",
    )
    return parser.parse_args(argv)


def _parse_chapter_goals(items: list[str]) -> list[tuple[int, str]]:
    if not items:
        return [
            (2, "延续卫图求养生功线索"),
            (3, "延续卫图得法与初练"),
        ]
    goals: list[tuple[int, str]] = []
    for item in items:
        chapter, _, goal = item.partition(":")
        goals.append((int(chapter.strip()), goal.strip()))
    return goals


def _prepare_workspace(slug: str, force: bool) -> Path:
    target = TARGET_ROOT / slug.strip().strip("/")
    if not slug or slug == "_template":
        raise SystemExit("workspace_slug must be a non-empty value other than _template")
    if not TEMPLATE_DIR.exists():
        raise SystemExit(f"template directory missing: {TEMPLATE_DIR}")
    if target.exists():
        if not force:
            raise SystemExit(f"target already exists: {target}\nUse --force to replace it.")
        shutil.rmtree(target)
    shutil.copytree(TEMPLATE_DIR, target)
    (target / "artifacts").mkdir(parents=True, exist_ok=True)
    (target / "exports").mkdir(parents=True, exist_ok=True)
    (target / "notes").mkdir(parents=True, exist_ok=True)
    return target


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = _settings(args.database_url)
    workspace = _prepare_workspace(args.workspace_slug, args.force)
    chapter_goals = _parse_chapter_goals(args.chapter_goals)
    factory = create_session_factory(settings)

    with factory() as session:
        branch = session.scalar(select(RunBranch).where(RunBranch.id == args.branch_id))
        if branch is None:
            raise SystemExit(f"branch not found: {args.branch_id}")
        run = session.scalar(select(AnalysisRun).where(AnalysisRun.id == branch.run_id))
        if run is None:
            raise SystemExit(f"run not found for branch: {args.branch_id}")
        novel = session.scalar(select(NovelSource).where(NovelSource.id == run.novel_id))
        title = novel.title if novel is not None else ""

        bundle = ExportService(session).export_branch_bundle(run.id, branch.id)
        branch_report = render_branch_report(bundle)
        mapping_pack = StoryMappingPack(
            project_title=args.project_title,
            source_work_name=args.source_work_name,
            target_work_name=args.target_work_name,
            character_mapping={"卫图": "魏拓"},
        )
        whole_book_report = WholeBookImitationService(session).run_in_sandbox(
            branch.id,
            mapping_pack=mapping_pack,
            chapter_goals=chapter_goals,
            max_rounds=1,
            use_llm=False,
        )

    artifacts_dir = workspace / "artifacts"
    exports_dir = workspace / "exports"
    notes_dir = workspace / "notes"
    bundle_path = artifacts_dir / "weitu-branch-bundle.json"
    whole_book_path = artifacts_dir / "weitu-whole-book-report.json"
    report_path = exports_dir / "weitu-branch-report.md"
    bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    whole_book_path.write_text(
        whole_book_report.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report_path.write_text(branch_report, encoding="utf-8")

    readme = """# 人工评估工作区模板

本目录是人工评估工作区的模板。
使用 `scripts/bootstrap_manual_eval_workspace.py` 从此模板创建新工作区。

```bash
python3 scripts/bootstrap_manual_eval_workspace.py <novel_slug>
```

## 目录结构

- `artifacts/` — 导出的 JSON 产物（novel-assistant、检索基准等）
- `exports/` — 分支报告与打包产物
- `notes/` — 人工审查笔记、问题追踪、后续行动

---

## 当前工作区用途：卫图样例 Loom 真实验证

- run_id: `{run_id}`
- branch_id: `{branch_id}`
- title: `{title}`

当前已导入：

- `artifacts/weitu-branch-bundle.json`
- `artifacts/weitu-whole-book-report.json`
- `exports/weitu-branch-report.md`

建议流程：

1. 先看 `notes/manual-review-notes.md`
2. 再看 `notes/problem-trace.md`
3. 人工只处理复杂 case
4. 处理后按 `notes/next-actions.md` 回到 resume / recovery 链
""".format(run_id=run.id, branch_id=branch.id, title=title)
    _write_text(workspace / "README.md", readme)

    whole_book_payload = json.loads(whole_book_report.model_dump_json())
    loom_gate = whole_book_payload.get("session_loom_gate_summary", {})
    loom_signals = whole_book_payload.get("session_loom_signals", {})
    manual_notes = """# 人工审查笔记

在此记录本次评估过程中的观察、问题和质量信号。

## 当前验证对象

- branch_id: `{branch_id}`
- run_id: `{run_id}`
- title: `{title}`

## 已导入工作区的产物

- `artifacts/weitu-branch-bundle.json`
- `artifacts/weitu-whole-book-report.json`
- `exports/weitu-branch-report.md`

## 当前 whole-book Loom 观察

- `quality_verdict={quality_verdict}`
- `gate_status={gate_status}`
- `average_chapter_quality_score={avg_quality}`
- `tension_signal_count={tension_signal_count}`

## 初步人工关注点

1. whole-book report 已出现：
   - `session_loom_signals`
   - `session_loom_gate_summary`
2. 这证明 Loom 信号已进入接近执行器的产物。
3. 但当前仍不能据此证明“比 baseline 更好”，因为尚无双臂 A/B 对照。
""".format(
        branch_id=branch.id,
        run_id=run.id,
        title=title,
        quality_verdict=loom_gate.get("quality_verdict", ""),
        gate_status=loom_gate.get("gate_status", ""),
        avg_quality=loom_signals.get("average_chapter_quality_score", ""),
        tension_signal_count=loom_gate.get("tension_signal_count", ""),
    )
    _write_text(notes_dir / "manual-review-notes.md", manual_notes)

    next_actions = """# 后续行动

在此记录本次评估会话的后续任务与决策。

## 下一步

1. 建立 baseline 产物（Loom 最小化/关闭）
2. 建立 Loom 对照产物（至少 `ab` 或 `enabled`）
3. 运行：
   - `loom-collect-pairs`
   - `loom-pairs-stats`
   - `loom-ab-compare`
4. 对复杂 case 做人工判定
5. 人工完成后回到 resume / recovery 链继续

## 恢复入口

- `writer-imitate-execution-resume.*`
- `resume-run`
- `/api/recovery`
"""
    _write_text(notes_dir / "next-actions.md", next_actions)

    problem_trace = """# 问题追踪

在此记录评估中发现的问题根因与复现步骤。

## 当前确认的问题

### 1. 真实卫图分支还没有 baseline vs loom 双臂对照

- 现状：只有一条真实卫图分支已经验证 Loom 信号存在
- 影响：无法证明 Loom 确实提升仿写能力

### 2. 当前结论仍然依赖下一轮 A/B

- 当前 whole-book loom gate 只能证明信号已接入执行器侧产物
- 不能单独证明最终仿写效果改善
"""
    _write_text(notes_dir / "problem-trace.md", problem_trace)

    print(f"manual_eval_workspace={workspace}")
    print(f"run_id={run.id}")
    print(f"branch_id={branch.id}")
    print(f"branch_title={title}")
    print(f"bundle_path={bundle_path}")
    print(f"whole_book_report_path={whole_book_path}")
    print(f"branch_report_path={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
