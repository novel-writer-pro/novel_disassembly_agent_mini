from novel_analyzer.domain.schemas import ChapterAnalysisOutput
from novel_analyzer.services.quality_gate_service import QualityGateService


def test_quality_gate_sets_hook_score_and_notes() -> None:
    result = ChapterAnalysisOutput(
        chapter_index=1,
        normalized_title='大器晚成',
        chapter_summary='卫图决定明天先去找二姑。',
        key_entities=['卫图'],
        key_events=['卫图决定明天先去找二姑'],
        continuity_notes=['后续将去找二姑。'],
    )
    report = QualityGateService.evaluate('明天先去找二姑，看看黄宅有没有养生功。', result)
    assert report.hook_score >= 4.5
    assert report.notes
