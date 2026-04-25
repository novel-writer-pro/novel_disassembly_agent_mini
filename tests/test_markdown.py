from novel_analyzer.reporting.markdown import render_chapter_markdown


def test_render_chapter_markdown() -> None:
    markdown = render_chapter_markdown(
        {
            'chapter_index': 1,
            'normalized_title': '大器晚成',
            'chapter_summary': '概要',
            'key_events': ['事件A'],
            'continuity_notes': ['说明A'],
            'state_transition_notes': ['推进A'],
            'evidence_backed_resolutions': ['解决A'],
            'unresolved_threads': ['未解A'],
            'state_summary': {
                'new_foreshadowing': ['伏笔A'],
                'paid_off_foreshadowing': ['回收A'],
                'new_conflicts': ['冲突A'],
                'escalated_conflicts': ['升级A'],
                'evolved_relations': ['关系A'],
                'constraining_world_rules': ['规则A'],
            },
            'dimensions': [
                {'dimension': 'chapter_summary', 'summary': '维度概要', 'evidence': ['证据1']}
            ],
        }
    )
    assert '# 第1章 大器晚成' in markdown
    assert '## Key Events' in markdown
    assert '## State Transition Notes' in markdown
    assert '推进A' in markdown
    assert '## State Summary' in markdown
    assert '伏笔A' in markdown
    assert '证据1' in markdown
