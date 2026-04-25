from novel_analyzer.preprocessing.chapter_splitter import inspect_text, split_text_into_chapters

SAMPLE = """第1章 大器晚成
第1章 大器晚成
正文A
第65章 65.第65章 临终安排
第65章 临终安排
正文B
"""


def test_inspect_preview_counts_duplicate_titles() -> None:
    preview = inspect_text(SAMPLE)
    assert preview.raw_heading_count == 4
    assert preview.duplicate_heading_count == 2
    assert preview.normalized_chapter_count == 2


def test_split_text_collapses_duplicate_headings_to_latest_boundary() -> None:
    chapters = split_text_into_chapters(SAMPLE)
    assert [chapter.chapter_index for chapter in chapters] == [1, 2]
    assert chapters[0].normalized_chapter_no == 1
    assert chapters[0].content.startswith('第1章 大器晚成\n正文A')
    assert chapters[0].content.endswith('正文A')
    assert '第65章' not in chapters[0].content
    assert chapters[1].normalized_chapter_no == 65
    assert chapters[1].normalized_title == '临终安排'
    assert chapters[1].content.startswith('第65章 临终安排\n正文B')
