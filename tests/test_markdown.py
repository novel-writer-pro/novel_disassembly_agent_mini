from novel_analyzer.reporting.markdown import render_chapter_markdown


def test_render_chapter_markdown() -> None:
    markdown = render_chapter_markdown(
        {
            'chapter_index': 1,
            'normalized_title': '大器晚成',
            'chapter_summary': '概要',
            'key_events': ['事件A'],
            'continuity_notes': ['说明A'],
            'dimensions': [
                {'dimension': 'chapter_summary', 'summary': '维度概要', 'evidence': ['证据1']}
            ],
        }
    )
    assert '# 第1章 大器晚成' in markdown
    assert '## Key Events' in markdown
    assert '证据1' in markdown
