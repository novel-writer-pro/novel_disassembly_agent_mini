from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from novel_analyzer.config.settings import Settings
from novel_analyzer.domain.schemas import BranchQAResult
from novel_analyzer.services.fact_service import FactService
from novel_analyzer.services.graph_service import GraphService
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.qa_service import BranchQAService
from novel_analyzer.services.run_service import RunService


class _DummyQAService(BranchQAService):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Settings(llm_api_key='test-key'))

    def answer_question(
        self,
        branch_id: str,
        question: str,
        limit: int = 5,
    ) -> BranchQAResult:
        hits = self.retrieval_service.search_branch(branch_id, question, limit)
        if not hits:
            return super().answer_question(branch_id, question, limit)
        return BranchQAResult(
            answer=(
                f"根据第{hits[0].chapter_index}章，可直接确认：{hits[0].summary_text}"
                '。若追问更深层动机，还需要更多章节证据。'
            ),
            used_chapters=[hit.chapter_index for hit in hits],
            evidence=[f"第{hit.chapter_index}章：{hit.summary_text}" for hit in hits],
            reasoning_paths=['卫图觉醒命格 -[advances_to]-> 卫图决定先修养生功'],
            graph_signals=['活跃冲突: 卫图受限于出身'],
            confidence=0.7,
            insufficient_context=False,
        )


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    from novel_analyzer.database.session import create_schema
    create_schema(engine)
    return Session(engine)


def test_branch_qa_requires_postgresql_retrieval_runtime(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 命格初现\n卫图觉醒命格，并决定先修养生功。\n', encoding='utf-8')

    with _session() as session:
        settings = Settings()
        novel, manifest = IngestService(session, settings).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session, settings).create_run(novel.id, manifest.id)
        artifact = RunService(session, settings).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格，并决定先修养生功。',
                'key_entities': ['卫图', '命格', '养生功'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['主线进入修行筹备阶段。'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'dimensions': [],
            },
        )
        from novel_analyzer.services.retrieval_service import RetrievalService
        RetrievalService(session, settings).materialize_for_artifact(artifact.id)
        with pytest.raises(RuntimeError, match='Only PostgreSQL is supported'):
            _DummyQAService(session).answer_question(branch.id, '卫图为什么要修养生功？')


def test_branch_qa_window_context_is_available(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        settings = Settings()
        novel, manifest = IngestService(session, settings).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session, settings).create_run(novel.id, manifest.id)
        fact_service = FactService(session)
        from novel_analyzer.services.retrieval_service import RetrievalService
        retrieval_service = RetrievalService(session, settings)
        for idx in range(1, 6):
            artifact = RunService(session, settings).record_chapter_artifact(
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
                    'dimensions': [],
                },
            )
            retrieval_service.materialize_for_artifact(artifact.id)
            fact_service.materialize_for_artifact(artifact.id)
            fact_service.materialize_window_if_ready(branch.id, idx, 5)
        service = BranchQAService(session, settings)
        lines = service._window_context(branch.id, [3])
        assert lines
        assert '窗口 1-5' in lines[0]


def test_branch_qa_graph_reasoning_snapshot_is_available(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        settings = Settings()
        novel, manifest = IngestService(session, settings).ingest_text_file(str(novel_path), '样例')
        run, branch = RunService(session, settings).create_run(novel.id, manifest.id)
        artifact1 = RunService(session, settings).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格。',
                'key_entities': ['卫图', '命格'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['命格线开启'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'dimensions': [],
            },
        )
        artifact2 = RunService(session, settings).record_chapter_artifact(
            branch.id,
            2,
            {
                'chapter_index': 2,
                'normalized_title': '命格兑现',
                'chapter_summary': '卫图因命格得到机缘。',
                'key_entities': ['卫图', '命格'],
                'key_events': ['卫图因命格得到机缘'],
                'continuity_notes': ['命格开始兑现'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'dimensions': [],
            },
        )
        RunService(session, settings).record_raw_output(
            run.id,
            branch.id,
            1,
            1,
            '{"facts":{"characters":[{"label":"卫图"}],"events":[{"label":"卫图觉醒命格"}],"relations":[{"label":"卫图与命格建立联系"}],"conflicts":[{"label":"卫图受限于出身"}],"foreshadowing":[{"label":"命格后续将改变命运"}],"worldbuilding_facts":[{"label":"命格决定成长路径"}]},"analysis":{"continuity_notes":["命格线开启"]}}',
            parsed_json={'ok': True},
            parse_status='parsed',
            parse_error=None,
            invocation_metadata={'pipeline': 'test'},
        )
        RunService(session, settings).record_raw_output(
            run.id,
            branch.id,
            2,
            1,
            '{"facts":{"characters":[{"label":"卫图"}],"events":[{"label":"卫图因命格得到机缘"}],"relations":[{"label":"卫图借命格翻身"}],"conflicts":[{"label":"卫图仍受家境掣肘"}],"foreshadowing":[],"worldbuilding_facts":[{"label":"命格会影响机缘分配"}]},"analysis":{"continuity_notes":["命格开始兑现"]}}',
            parsed_json={'ok': True},
            parse_status='parsed',
            parse_error=None,
            invocation_metadata={'pipeline': 'test'},
        )
        GraphService(session).materialize_for_artifact(artifact1.id)
        GraphService(session).materialize_for_artifact(artifact2.id)
        service = BranchQAService(session, settings)
        reasoning_paths, graph_signals = service._graph_reasoning_snapshot(branch.id, [1, 2])
        assert reasoning_paths
        assert any('advances_to' in item for item in reasoning_paths)
        assert graph_signals
        assert any(item.startswith('活跃冲突:') for item in graph_signals)


def test_branch_qa_falls_back_when_llm_temporarily_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 命格初现\n卫图觉醒命格，并决定先修养生功。\n', encoding='utf-8')

    with _session() as session:
        settings = Settings(llm_api_key='test-key')
        novel, manifest = IngestService(session, settings).ingest_text_file(str(novel_path), '样例')
        _, branch = RunService(session, settings).create_run(novel.id, manifest.id)
        artifact = RunService(session, settings).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图觉醒命格，并决定先修养生功。',
                'key_entities': ['卫图', '命格', '养生功'],
                'key_events': ['卫图觉醒命格'],
                'continuity_notes': ['主线进入修行筹备阶段。'],
                'writer_learning_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'dimensions': [],
            },
        )
        service = BranchQAService(session, settings)

        monkeypatch.setattr(
            service.retrieval_service,
            'search_branch',
            lambda branch_id, question, limit: [
                type(
                    'Hit',
                    (),
                    {
                        'chapter_index': 1,
                        'title': '命格初现',
                        'summary_text': '卫图觉醒命格，并决定先修养生功。',
                        'score': 1.0,
                        'keyword_list': ['卫图', '命格', '养生功'],
                    },
                )()
            ],
        )
        monkeypatch.setattr(service, '_window_context', lambda branch_id, chapters: ['[窗口 1-1] 卫图开始筹备修行。'])
        monkeypatch.setattr(service, '_graph_context', lambda branch_id, chapters: ['[图推理] 卫图觉醒命格 -> 决定修行'])
        monkeypatch.setattr(
            service,
            '_graph_reasoning_snapshot',
            lambda branch_id, chapters: (['卫图觉醒命格 -[advances_to]-> 卫图决定先修养生功'], ['活跃冲突: 卫图受限于出身']),
        )

        class _BoomModel:
            def invoke(self, _prompt: str):
                raise RuntimeError('503 Service temporarily unavailable')

        monkeypatch.setattr('novel_analyzer.services.qa_service.build_chat_model', lambda *args, **kwargs: _BoomModel())

        result = service.answer_question(branch.id, '卫图为什么要修养生功？')
        assert result.insufficient_context is True
        assert result.used_chapters == [1]
        assert '当前问答模型暂时不可用' in result.answer
        assert any(item.startswith('服务降级:') for item in result.graph_signals)
