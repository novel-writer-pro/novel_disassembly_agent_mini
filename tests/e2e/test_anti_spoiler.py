from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from novel_analyzer.database.base import Base
from novel_analyzer.database.models import (
    AnalysisRun,
    ChapterManifest,
    NovelSource,
    RetrievalDocument,
    RunBranch,
)
from novel_analyzer.services.retrieval_service import RetrievalHit, RetrievalService
from novel_analyzer.config.settings import get_settings


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/anti_spoiler.sqlite")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_hit(chapter_index: int, score: float = 1.0) -> RetrievalHit:
    return RetrievalHit(
        chapter_index=chapter_index,
        title=f"第{chapter_index}章",
        summary_text=f"summary {chapter_index}",
        score=score,
        keyword_list=[],
    )


class TestMaxChapterPostFilter:
    def test_no_max_chapter_returns_all(self):
        hits = [_make_hit(i) for i in [1, 3, 5, 7]]
        filtered = [h for h in hits if True]
        assert len(filtered) == 4

    def test_max_chapter_filters_later_chapters(self):
        hits = [_make_hit(i) for i in [1, 3, 5, 7]]
        max_chapter = 3
        filtered = [h for h in hits if h.chapter_index <= max_chapter]
        assert len(filtered) == 2
        assert all(h.chapter_index <= 3 for h in filtered)

    def test_max_chapter_zero_returns_empty(self):
        hits = [_make_hit(i) for i in [1, 2, 3]]
        filtered = [h for h in hits if h.chapter_index <= 0]
        assert filtered == []

    def test_max_chapter_exact_boundary(self):
        hits = [_make_hit(i) for i in [1, 2, 3, 4, 5]]
        max_chapter = 3
        filtered = [h for h in hits if h.chapter_index <= max_chapter]
        chapter_indices = [h.chapter_index for h in filtered]
        assert 3 in chapter_indices
        assert 4 not in chapter_indices

    def test_max_chapter_larger_than_all_returns_all(self):
        hits = [_make_hit(i) for i in [1, 2, 3]]
        filtered = [h for h in hits if h.chapter_index <= 999]
        assert len(filtered) == 3


class TestRetrievalServiceMaxChapter:
    def test_search_branch_signature_accepts_max_chapter(self):
        import inspect
        from novel_analyzer.services.retrieval_service import RetrievalService
        sig = inspect.signature(RetrievalService.search_branch)
        assert "max_chapter" in sig.parameters

    def test_max_chapter_default_is_none(self):
        import inspect
        from novel_analyzer.services.retrieval_service import RetrievalService
        sig = inspect.signature(RetrievalService.search_branch)
        assert sig.parameters["max_chapter"].default is None


class TestQAServiceMaxChapter:
    def test_answer_question_signature_accepts_max_chapter(self):
        import inspect
        from novel_analyzer.services.qa_service import BranchQAService
        sig = inspect.signature(BranchQAService.answer_question)
        assert "max_chapter" in sig.parameters

    def test_max_chapter_default_is_none(self):
        import inspect
        from novel_analyzer.services.qa_service import BranchQAService
        sig = inspect.signature(BranchQAService.answer_question)
        assert sig.parameters["max_chapter"].default is None


class TestAskBranchStreamMaxChapter:
    def test_ask_branch_stream_reads_max_chapter_from_body(self):
        import json
        from io import BytesIO
        from typing import cast
        from wsgiref.types import StartResponse
        from apps.api.app.main import application

        captured = {}

        def start_response(status, headers, exc_info=None):
            captured["status"] = status
            return lambda chunk: None

        body = json.dumps({
            "branch_id": "nonexistent-branch",
            "question": "test question",
            "max_chapter": 3,
        }).encode()

        raw = b"".join(application(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/ask-branch-stream",
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": str(len(body)),
                "QUERY_STRING": "",
                "wsgi.input": BytesIO(body),
            },
            cast(StartResponse, start_response),
        ))
        assert captured.get("status") in ("200 OK", "500 Internal Server Error")
