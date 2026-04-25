"""Export a complete branch package for downstream use."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterArtifact
from novel_analyzer.reporting.branch_report import render_branch_report
from novel_analyzer.reporting.markdown import render_chapter_markdown
from novel_analyzer.services.chapter_index_service import ChapterIndexService
from novel_analyzer.services.context_service import ContextService
from novel_analyzer.services.export_service import ExportService
from novel_analyzer.services.raw_output_service import RawOutputService


class PackageService:
    """Build an export package containing branch- and chapter-level artifacts."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.export_service = ExportService(session)
        self.chapter_index_service = ChapterIndexService(session)
        self.context_service = ContextService(session)
        self.raw_output_service = RawOutputService(session)

    def export_branch_package(self, run_id: str, branch_id: str, output_dir: Path) -> Path:
        """Export a branch package into a directory tree."""

        output_dir.mkdir(parents=True, exist_ok=True)
        bundle = self.export_service.export_branch_bundle(run_id, branch_id)
        (output_dir / 'branch_bundle.json').write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        chapter_index_rows = [
            {key: getattr(row, key) for key in row.__dataclass_fields__}
            for row in self.chapter_index_service.list_rows(branch_id)
        ]
        (output_dir / 'chapter_index.json').write_text(
            json.dumps(chapter_index_rows, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        (output_dir / 'branch_report.md').write_text(
            render_branch_report(bundle),
            encoding='utf-8',
        )
        branch_qa_context = self.export_service.export_branch_qa_context(run_id, branch_id)
        (output_dir / 'branch_qa_context.json').write_text(
            json.dumps(branch_qa_context, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        chapters_dir = output_dir / 'chapters'
        chapters_dir.mkdir(exist_ok=True)
        artifacts = self.session.scalars(
            select(ChapterArtifact)
            .where(ChapterArtifact.branch_id == branch_id)
            .where(ChapterArtifact.visibility == 'active')
            .order_by(ChapterArtifact.chapter_index)
        ).all()
        for artifact in artifacts:
            chapter_bundle = self.export_service.export_chapter_bundle(
                branch_id,
                artifact.chapter_index,
            )
            json_path = chapters_dir / f'chapter_{artifact.chapter_index:04d}.json'
            md_path = chapters_dir / f'chapter_{artifact.chapter_index:04d}.md'
            raw_path = chapters_dir / f'chapter_{artifact.chapter_index:04d}.raw.json'
            context_path = chapters_dir / f'chapter_{artifact.chapter_index:04d}.context.json'
            qa_context_path = chapters_dir / f'chapter_{artifact.chapter_index:04d}.qa-context.json'
            json_path.write_text(
                json.dumps(chapter_bundle, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            artifact_payload = cast(dict[str, Any], chapter_bundle['artifact'])
            md_path.write_text(
                render_chapter_markdown(artifact_payload),
                encoding='utf-8',
            )
            raw_record = self.raw_output_service.latest_for_chapter(
                branch_id,
                artifact.chapter_index,
            )
            raw_payload = None
            if raw_record is not None:
                raw_payload = {
                    'chapter_index': raw_record.chapter_index,
                    'job_attempt': raw_record.job_attempt,
                    'parse_status': raw_record.parse_status,
                    'parse_error': raw_record.parse_error,
                    'invocation_metadata': raw_record.invocation_metadata,
                    'parsed_json': raw_record.parsed_json,
                    'raw_response_text': raw_record.raw_response_text,
                }
            raw_path.write_text(
                json.dumps(raw_payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            context_payload = self.context_service.context_bundle(
                branch_id,
                artifact.chapter_index + 1,
            )
            context_path.write_text(
                json.dumps(context_payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            qa_context_payload = self.export_service.export_chapter_qa_context(
                branch_id,
                artifact.chapter_index,
            )
            qa_context_path.write_text(
                json.dumps(qa_context_payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        return output_dir
