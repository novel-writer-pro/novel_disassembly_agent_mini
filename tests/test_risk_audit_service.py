from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from novel_analyzer.database.models import ChapterRiskCardRecord, GateCheckerResultRecord
from novel_analyzer.database.session import create_schema
from novel_analyzer.domain.schemas import ChapterRiskCard, CheckerResult, GateRiskItem
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.services.risk_audit_service import RiskAuditService
from novel_analyzer.services.run_service import RunService


def _session() -> Session:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    create_schema(engine)
    return Session(engine)


def test_risk_card_schema_counts() -> None:
    risk = GateRiskItem(
        checker_name='character_ooc',
        risk_domain='character',
        risk_type='motivation_shift',
        severity='medium',
        confidence=0.72,
        summary='动机出现可疑偏移。',
        supporting_evidence=['第10章：突然改变决定。'],
        counter_evidence=['也可能是新信息触发。'],
        related_entities=['卫图'],
        related_chapters=[10],
        risk_key='branch|10|character_ooc|卫图|motivation_shift',
    )
    result = CheckerResult(checker_name='character_ooc', chapter_index=10, risks=[risk])
    card = ChapterRiskCard(
        branch_id='branch',
        chapter_index=10,
        top_risks=[risk],
        risk_counts_by_domain={'character': 1},
        risk_counts_by_severity={'medium': 1},
        checker_statuses={'character_ooc': 'ready'},
    )
    assert result.status == 'ready'
    assert card.risk_counts_by_domain['character'] == 1
    assert card.top_risks[0].risk_type == 'motivation_shift'


def test_generate_for_chapter_persists_checker_results_and_risk_card(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'world_rule_signals': ['命格限制'],
                'world_rule_issues': [
                    {
                        'rule_key': '命格限制',
                        'risk_type': 'rule_consistency',
                        'severity': 'medium',
                        'summary': '本章对命格限制的描述与前文存在冲突候选。',
                        'supporting_evidence': ['前文强调命格有限制', '本章描述限制突然消失'],
                        'counter_evidence': ['也可能是例外条件首次触发'],
                    }
                ],
                'plot_logic_issues': [
                    {
                        'risk_type': 'causality_break',
                        'severity': 'medium',
                        'summary': '本章关键决策的因果链条不完整。',
                        'supporting_evidence': ['前文未铺垫该资源来源', '本章直接进入结果态'],
                        'counter_evidence': ['也可能是中间过程被省略但未违背设定'],
                    }
                ],
                'timeline_issues': [
                    {
                        'risk_type': 'timeline_conflict',
                        'severity': 'low',
                        'summary': '本章事件先后顺序存在可疑重叠。',
                        'supporting_evidence': ['同一日内出现互斥地点切换'],
                        'counter_evidence': ['也可能是叙事压缩导致的表述误差'],
                    }
                ],
                'power_scaling_issues': [
                    {
                        'risk_type': 'capability_shift',
                        'severity': 'medium',
                        'summary': '角色能力上限在无充分解释下突然提升。',
                        'supporting_evidence': ['前文只能防守', '本章直接跨级压制'],
                        'counter_evidence': ['也可能是一次性增益首次公开'],
                    }
                ],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'high',
                        'summary': '卫图在无铺垫下突然改换目标。',
                        'supporting_evidence': ['前文目标A', '本章突然选择B'],
                        'counter_evidence': ['可能存在未展示的新信息'],
                    }
                ],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'hook_score': 4.0,
                'dimensions': [],
                'timeline_signals': ['三日后回城', '当夜再次出手'],
                'power_signals': ['越阶压制', '突然掌握新招式'],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        assert card.overall_risk_level in {'high', 'medium'}
        assert len(card.top_risks) == 5

        records = session.scalars(
            select(GateCheckerResultRecord).where(GateCheckerResultRecord.branch_id == branch.id)
        ).all()
        assert {record.checker_name for record in records} == {
            'character_ooc',
            'world_rule_consistency',
            'plot_logic_consistency',
            'timeline_consistency',
            'power_scaling_consistency',
        }

        risk_card_record = session.scalar(
            select(ChapterRiskCardRecord)
            .where(ChapterRiskCardRecord.branch_id == branch.id)
            .where(ChapterRiskCardRecord.chapter_index == 1)
        )
        assert risk_card_record is not None
        assert risk_card_record.payload_json['risk_counts_by_domain']['character'] == 1
        assert risk_card_record.payload_json['risk_counts_by_domain']['rules'] == 1
        assert risk_card_record.payload_json['risk_counts_by_domain']['plot'] == 1
        assert risk_card_record.payload_json['risk_counts_by_domain']['timeline'] == 1
        assert risk_card_record.payload_json['risk_counts_by_domain']['power'] == 1


def test_generate_for_chapter_marks_skipped_without_signals(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '普通章节',
                'chapter_summary': '平稳推进。',
                'key_entities': [],
                'key_events': [],
                'continuity_notes': [],
                'unsupported_inferences': [],
                'ambiguous_points': [],
                'needs_human_review': False,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        assert card.top_risks == []
        records = session.scalars(
            select(GateCheckerResultRecord).where(GateCheckerResultRecord.branch_id == branch.id)
        ).all()
        assert {record.payload_json['status'] for record in records} == {'skipped'}


def test_phase1_future_checkers_degrade_without_strong_signals(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '边界测试',
                'chapter_summary': '本章存在一些可疑但不充分的连续性信号。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出新选择'],
                'continuity_notes': ['推进存在省略'],
                'unsupported_inferences': ['结论A缺少直接证据'],
                'ambiguous_points': ['行动动机与结果之间解释不足'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
                'timeline_signals': ['翌日回返', '同夜再次出现'],
                'power_signals': ['突然展现更强压制力'],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        assert card.checker_statuses['plot_logic_consistency'] == 'partial'
        assert card.checker_statuses['timeline_consistency'] == 'partial'
        assert card.checker_statuses['power_scaling_consistency'] == 'partial'
        risk_types = {risk.risk_type for risk in card.top_risks}
        assert 'logic_review_candidate' in risk_types
        assert 'timeline_support_gap' in risk_types
        assert 'power_support_gap' in risk_types


def test_plot_logic_checker_uses_artifact_progression_signals_for_better_candidates(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '逻辑信号增强测试',
                'chapter_summary': '本章声称解决了问题，但支撑链仍不足。',
                'key_entities': ['卫图'],
                'key_events': ['卫图宣布问题解决'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': ['“问题已经彻底解决”缺少直接证据支撑'],
                'ambiguous_points': [],
                'state_transition_notes': ['局势从受压转向稳定'],
                'evidence_backed_resolutions': ['主角认为当前危机已解除'],
                'unresolved_threads': ['真正幕后原因尚未查明'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        plot_risks = [risk for risk in card.top_risks if risk.checker_name == 'plot_logic_consistency']
        assert plot_risks
        assert plot_risks[0].risk_type == 'resolution_support_gap'
        assert any('解决' in item for item in plot_risks[0].supporting_evidence)
        assert card.checker_statuses['plot_logic_consistency'] == 'partial'


def test_plot_logic_checker_ranks_more_relevant_supporting_evidence_first(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '剧情排序测试',
                'chapter_summary': '本章剧情逻辑存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['主角突然得到结果'],
                'continuity_notes': ['主线推进。'],
                'plot_logic_issues': [
                    {
                        'risk_type': 'causality_break',
                        'severity': 'medium',
                        'summary': '本章因果链条不完整。',
                        'supporting_evidence': ['普通背景描述', '关键结果出现前缺少行动与前置因果支撑'],
                        'counter_evidence': ['也可能是中间过程被省略。'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        plot_risks = [risk for risk in card.top_risks if risk.checker_name == 'plot_logic_consistency']
        assert plot_risks
        assert '因果' in plot_risks[0].supporting_evidence[0] or '前置' in plot_risks[0].supporting_evidence[0]


def test_timeline_checker_uses_artifact_signals_for_better_candidates(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '时间线信号增强测试',
                'chapter_summary': '本章时间顺序存在可疑压缩。',
                'key_entities': ['卫图'],
                'key_events': ['卫图先撤离后当夜再现身'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': ['“当夜已完成全部恢复”缺少直接证据支撑'],
                'ambiguous_points': [],
                'timeline_signals': ['三日后回城', '当夜再次出现'],
                'state_transition_notes': ['局势由撤离转入重新介入'],
                'unresolved_threads': ['伤势恢复速度是否合理仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        timeline_risks = [risk for risk in card.top_risks if risk.checker_name == 'timeline_consistency']
        assert timeline_risks
        assert timeline_risks[0].risk_type == 'timeline_support_gap'
        assert any('三日后' in item or '当夜' in item for item in timeline_risks[0].supporting_evidence)
        assert card.checker_statuses['timeline_consistency'] == 'partial'


def test_timeline_checker_ranks_more_relevant_supporting_evidence_first(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '时间排序测试',
                'chapter_summary': '本章时间顺序存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['主角同日多次切换地点'],
                'continuity_notes': ['主线推进。'],
                'timeline_issues': [
                    {
                        'risk_type': 'timeline_conflict',
                        'severity': 'medium',
                        'summary': '本章时间顺序不一致。',
                        'supporting_evidence': ['普通背景描述', '同日内先后顺序与恢复时长存在冲突'],
                        'counter_evidence': ['也可能是叙事压缩。'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        timeline_risks = [risk for risk in card.top_risks if risk.checker_name == 'timeline_consistency']
        assert timeline_risks
        assert '顺序' in timeline_risks[0].supporting_evidence[0] or '恢复' in timeline_risks[0].supporting_evidence[0]


def test_power_checker_uses_artifact_signals_for_better_candidates(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '战力信号增强测试',
                'chapter_summary': '本章能力跃迁存在可疑支撑缺口。',
                'key_entities': ['卫图'],
                'key_events': ['卫图突然越阶压制对手'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': ['“已稳定掌握新层级能力”缺少直接证据支撑'],
                'ambiguous_points': [],
                'power_signals': ['越阶压制', '突然掌握新招式'],
                'state_transition_notes': ['局势由守转攻并迅速压制'],
                'unresolved_threads': ['能力来源是否一次性增益仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        power_risks = [risk for risk in card.top_risks if risk.checker_name == 'power_scaling_consistency']
        assert power_risks
        assert power_risks[0].risk_type == 'power_support_gap'
        assert any('越阶' in item or '新招式' in item for item in power_risks[0].supporting_evidence)
        assert card.checker_statuses['power_scaling_consistency'] == 'partial'


def test_power_checker_ranks_more_relevant_supporting_evidence_first(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '战力排序测试',
                'chapter_summary': '本章战力变化存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['主角突然越阶压制对手'],
                'continuity_notes': ['主线推进。'],
                'power_scaling_issues': [
                    {
                        'risk_type': 'capability_shift',
                        'severity': 'medium',
                        'summary': '本章战力跃迁缺少充分铺垫。',
                        'supporting_evidence': ['普通背景描述', '越阶压制与新招式掌握缺少直接支撑'],
                        'counter_evidence': ['也可能是一次性增益。'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        power_risks = [risk for risk in card.top_risks if risk.checker_name == 'power_scaling_consistency']
        assert power_risks
        assert '越阶' in power_risks[0].supporting_evidence[0] or '新招式' in power_risks[0].supporting_evidence[0]


def test_world_rule_checker_uses_artifact_signals_for_better_candidates(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '规则信号增强测试',
                'chapter_summary': '本章规则约束与解决性表述之间存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['规则限制似乎被突然解除'],
                'continuity_notes': ['主线推进。'],
                'world_rule_signals': ['命格限制', '修炼门槛'],
                'unsupported_inferences': ['“限制已经完全解除”缺少直接证据支撑'],
                'ambiguous_points': [],
                'evidence_backed_resolutions': ['主角认为当前约束已经不再成立'],
                'unresolved_threads': ['限制为何解除仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        rule_risks = [risk for risk in card.top_risks if risk.checker_name == 'world_rule_consistency']
        assert rule_risks
        assert rule_risks[0].risk_type == 'rule_support_gap'
        assert any('命格限制' in item or '修炼门槛' in item for item in rule_risks[0].related_entities)
        assert card.checker_statuses['world_rule_consistency'] == 'partial'


def test_world_rule_checker_backfills_rule_entities_and_supporting_from_signals(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '规则实体回填测试',
                'chapter_summary': '本章对规则限制给出了可疑结论。',
                'key_entities': ['卫图'],
                'key_events': ['主角判断限制已消失'],
                'continuity_notes': ['主线推进。'],
                'world_rule_signals': ['命格限制', '修炼门槛'],
                'world_rule_issues': [
                    {
                        'risk_type': 'rule_consistency',
                        'severity': 'medium',
                        'summary': '本章对限制是否解除的结论过强。',
                        'supporting_evidence': [],
                        'counter_evidence': ['也可能只是阶段性失效。'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        rule_risks = [risk for risk in card.top_risks if risk.checker_name == 'world_rule_consistency']
        assert rule_risks
        assert any('命格限制' in item or '修炼门槛' in item for item in rule_risks[0].related_entities)
        assert any('命格限制' in item or '修炼门槛' in item for item in rule_risks[0].supporting_evidence)


def test_world_rule_checker_distinguishes_exception_candidate(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '规则例外测试',
                'chapter_summary': '本章规则似乎因特殊条件阶段性变化。',
                'key_entities': ['卫图'],
                'key_events': ['限制短暂失效'],
                'continuity_notes': ['主线推进。'],
                'world_rule_signals': ['命格限制'],
                'unsupported_inferences': ['“限制彻底失效”更像阶段性例外，缺少直接证据支撑'],
                'ambiguous_points': ['也可能是特殊条件触发的暂时变化'],
                'evidence_backed_resolutions': ['主角暂时绕过当前限制'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        rule_risks = [risk for risk in card.top_risks if risk.checker_name == 'world_rule_consistency']
        assert rule_risks
        assert rule_risks[0].risk_type == 'rule_exception_candidate'


def test_world_rule_checker_ranks_more_relevant_supporting_evidence_first(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '规则排序测试',
                'chapter_summary': '本章规则设定存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['主角声称约束解除'],
                'continuity_notes': ['主线推进。'],
                'world_rule_issues': [
                    {
                        'risk_type': 'rule_support_gap',
                        'severity': 'medium',
                        'summary': '本章对规则限制的结论过强。',
                        'supporting_evidence': ['普通背景描述', '规则限制突然被解除，缺少直接证据'],
                        'counter_evidence': ['也可能只是暂时失效。'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        rule_risks = [risk for risk in card.top_risks if risk.checker_name == 'world_rule_consistency']
        assert rule_risks
        assert '规则' in rule_risks[0].supporting_evidence[0] or '限制' in rule_risks[0].supporting_evidence[0]


def test_character_ooc_checker_uses_artifact_signals_for_better_candidates(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '人物信号增强测试',
                'chapter_summary': '本章人物推进存在可疑支撑缺口。',
                'key_entities': ['卫图'],
                'key_events': ['卫图突然改变态度'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': ['“人物态度已经彻底转变”缺少直接证据支撑'],
                'ambiguous_points': [],
                'state_transition_notes': ['卫图从强硬转向缓和'],
                'evidence_backed_resolutions': ['人物关系似乎已经恢复'],
                'unresolved_threads': ['人物真实动机仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        character_risks = [risk for risk in card.top_risks if risk.checker_name == 'character_ooc']
        assert character_risks
        assert character_risks[0].risk_type == 'character_resolution_support_gap'
        assert card.checker_statuses['character_ooc'] == 'partial'


def test_character_ooc_checker_marks_title_only_inference_candidate_low_confidence(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '标题推断测试',
                'chapter_summary': '本章仅提供章节标题，无法提供有效总结。',
                'key_entities': [],
                'key_events': [],
                'continuity_notes': [],
                'unsupported_inferences': ['该人物变化仅基于标题推断，缺少正文证据。'],
                'ambiguous_points': [],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        character_risks = [risk for risk in card.top_risks if risk.checker_name == 'character_ooc']
        assert character_risks
        assert character_risks[0].risk_type == 'title_only_inference_candidate'
        assert character_risks[0].confidence == 0.22


def test_character_ooc_checker_subtypes_relationship_shift_candidate(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '关系漂移测试',
                'chapter_summary': '本章人物关系变化存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['卫图与友人突然疏远'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': [],
                'ambiguous_points': ['人物关系突然从亲近转向疏远，缺少足够铺垫。'],
                'unresolved_threads': ['师徒与兄弟关系后续仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        character_risks = [risk for risk in card.top_risks if risk.checker_name == 'character_ooc']
        assert character_risks
        assert character_risks[0].risk_type == 'relationship_shift_candidate'


def test_character_ooc_checker_subtypes_belief_shift_candidate(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '信念漂移测试',
                'chapter_summary': '本章人物原则变化存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['卫图突然放弃此前底线'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': [],
                'ambiguous_points': ['人物原则与誓言突然松动，缺少足够铺垫。'],
                'unresolved_threads': ['其价值选择后续仍未解释'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        character_risks = [risk for risk in card.top_risks if risk.checker_name == 'character_ooc']
        assert character_risks
        assert character_risks[0].risk_type == 'belief_shift_candidate'


def test_character_ooc_checker_ranks_more_relevant_supporting_evidence_first(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')
    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '动机排序测试',
                'chapter_summary': '本章人物动机变化存在可疑点。',
                'key_entities': ['卫图'],
                'key_events': ['卫图突然改变立场'],
                'continuity_notes': ['主线推进。'],
                'unsupported_inferences': ['普通描述信息', '人物动机突然改变，缺少直接证据支撑'],
                'ambiguous_points': ['人物选择与既有立场不一致'],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        card = RiskAuditService(session).generate_for_chapter(branch.id, 1)
        character_risks = [risk for risk in card.top_risks if risk.checker_name == 'character_ooc']
        assert character_risks
        assert character_risks[0].risk_type == 'motivation_shift_candidate'
        assert '动机' in character_risks[0].supporting_evidence[0] or '立场' in character_risks[0].supporting_evidence[0]


def test_generate_for_chapter_isolates_checker_failure(tmp_path: Path) -> None:
    novel_path = tmp_path / 'novel.txt'
    novel_path.write_text('第1章 一\n正文\n', encoding='utf-8')

    class _BoomChecker:
        name = 'boom_checker'
        domain = 'rules'

        def evaluate(self, **kwargs):
            raise RuntimeError('boom')

    with _session() as session:
        novel, manifest = IngestService(session).ingest_text_file(str(novel_path), '样例')
        _run, branch = RunService(session).create_run(novel.id, manifest.id)
        RunService(session).record_chapter_artifact(
            branch.id,
            1,
            {
                'chapter_index': 1,
                'normalized_title': '命格初现',
                'chapter_summary': '卫图在本章做出异常决定。',
                'key_entities': ['卫图'],
                'key_events': ['卫图做出异常决定'],
                'continuity_notes': ['主线推进。'],
                'ooc_candidates': [
                    {
                        'character_name': '卫图',
                        'risk_type': 'motivation_shift',
                        'severity': 'medium',
                        'summary': '卫图目标改变过快。',
                        'supporting_evidence': ['前文目标A'],
                        'counter_evidence': ['也许有新情报'],
                    }
                ],
                'needs_human_review': True,
                'quality_gate_notes': [],
                'dimensions': [],
            },
        )
        service = RiskAuditService(session)
        service.checkers = [service.checkers[0], _BoomChecker()]  # type: ignore[list-item]
        card = service.generate_for_chapter(branch.id, 1)
        assert card.checker_statuses['character_ooc'] in {'ready', 'partial'}
        assert card.checker_statuses['boom_checker'] == 'failed'
        stored = {
            record.checker_name: record.payload_json['status']
            for record in session.scalars(select(GateCheckerResultRecord)).all()
        }
        assert stored['boom_checker'] == 'failed'
