"""Novel ingest and manifest creation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterManifest, ChapterSegment, NovelSource
from novel_analyzer.preprocessing.chapter_splitter import inspect_text, split_text_into_chapters


class IngestService:
    """Handles source import and chapter manifest generation."""

    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def ingest_text_file(
        self,
        path: str,
        title: str | None = None,
    ) -> tuple[NovelSource, ChapterManifest]:
        """Import a novel text file and derive a new chapter manifest."""

        source_path = Path(path)
        text = source_path.read_text(encoding="utf-8")
        text_hash = sha256(text.encode("utf-8")).hexdigest()
        preview = inspect_text(text)
        chapters = split_text_into_chapters(text)

        novel = NovelSource(
            title=title or source_path.stem,
            source_path=str(source_path),
            source_hash=text_hash,
            metadata_json={
                "raw_heading_count": preview.raw_heading_count,
                "duplicate_heading_count": preview.duplicate_heading_count,
            },
        )
        self.session.add(novel)
        self.session.flush()

        next_version = self.session.scalar(
            select(func.coalesce(func.max(ChapterManifest.version), 0) + 1).where(
                ChapterManifest.novel_id == novel.id
            )
        )
        manifest = ChapterManifest(
            novel_id=novel.id,
            version=int(next_version or 1),
            splitter_version=self.settings.chapter_splitter_version,
            chapter_count=len(chapters),
            notes={
                "first_headings": preview.first_headings,
                "raw_heading_count": preview.raw_heading_count,
                "normalized_chapter_count": preview.normalized_chapter_count,
            },
        )
        self.session.add(manifest)
        self.session.flush()

        for chapter in chapters:
            self.session.add(
                ChapterSegment(
                    manifest_id=manifest.id,
                    chapter_index=chapter.chapter_index,
                    raw_heading=chapter.raw_heading,
                    normalized_chapter_no=chapter.normalized_chapter_no,
                    normalized_title=chapter.normalized_title,
                    start_offset=chapter.start_offset,
                    end_offset=chapter.end_offset,
                    content_hash=chapter.content_hash,
                )
            )

        self.session.commit()
        self.session.refresh(novel)
        self.session.refresh(manifest)
        return novel, manifest
