from langchain_core.messages import AIMessage

from novel_analyzer.services.analysis_service import AnalysisService


def test_extract_json_payload_accepts_fenced_json() -> None:
    message = AIMessage(
        content='```json\n{"chapter_index":1,"normalized_title":"X"}\n```'
    )
    assert AnalysisService._extract_json_payload(message) == {
        "chapter_index": 1,
        "normalized_title": "X",
    }
