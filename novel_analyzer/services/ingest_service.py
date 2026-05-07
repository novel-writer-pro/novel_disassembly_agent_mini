"""Novel ingest and manifest creation."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.database.models import ChapterManifest, ChapterSegment, NovelSource
from novel_analyzer.preprocessing.chapter_splitter import inspect_text, split_text_into_chapters
from novel_analyzer.runtime.storage import runtime_cache_root


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

    @staticmethod
    def _chapter_heading(item: dict[str, object], index: int) -> str:
        raw_heading = str(item.get("raw_heading") or "").strip()
        if raw_heading:
            return raw_heading

        title = str(
            item.get("title")
            or item.get("chapter_title")
            or item.get("normalized_title")
            or ""
        ).strip()
        if title.startswith("第") and ("章" in title or "节" in title):
            return title
        return f"第{index}章 {title}".strip()

    @staticmethod
    def _chapter_content(item: dict[str, object]) -> str:
        return str(
            item.get("content")
            or item.get("text")
            or item.get("body")
            or ""
        ).strip()

    def persist_chapter_list_file(
        self,
        chapters: list[dict[str, object]],
        *,
        source_name: str = "chapter-list-import",
    ) -> str:
        normalized_blocks: list[str] = []
        for index, item in enumerate(chapters, start=1):
            heading = self._chapter_heading(item, index)
            content = self._chapter_content(item)
            if not content:
                continue
            normalized_blocks.append(f"{heading}\n{content}".strip())

        if not normalized_blocks:
            raise ValueError("chapter list import requires at least one non-empty chapter content item")

        target_dir = runtime_cache_root(self.settings) / "uploads"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid4().hex}-{source_name}.txt"
        target_path.write_text("\n\n".join(normalized_blocks).strip() + "\n", encoding="utf-8")
        return str(target_path)

    def ingest_chapter_list(
        self,
        chapters: list[dict[str, object]],
        *,
        title: str | None = None,
        source_name: str = "chapter-list-import",
    ) -> tuple[NovelSource, ChapterManifest]:
        path = self.persist_chapter_list_file(chapters, source_name=source_name)
        return self.ingest_text_file(path, title)
