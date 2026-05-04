# Branch Report

## Status
- run_id: ac9449b9-7326-474f-bb72-4416375a7491
- branch_id: 62e636f0-c901-4167-aa1c-aff3da9c83ef
- branch_name: main
- branch_status: active
- manifest_chapter_count: 775
- completed_chapters: 10
- failed_jobs: 0
- running_jobs: 0
- next_chapter: 11
- fact_count: 232
- window_count: 2
- graph_node_count: 351
- graph_edge_count: 11379

## Audit Conclusion
- Content Judgement: 当前分支已形成可用的阶段性审查结果，但候选风险分布较密集。
- Risk Judgement: 当前未发现明确高风险，但人工复核候选较多，需谨慎使用整体稳定结论。
- Blocking Judgement: 当前无执行阻塞。
- Recommended Action: 按章节优先级批量复核候选章节，再决定是否给出整体稳定判断。
- Review Progress: 仍待人工复核问题簇 1 个。
- Needs Review: 当前仍有 1 个问题簇处于 needs_review，建议优先安排人工复核。
- Review Storage: 当前 review 数据来自数据库主路径。

## Chapter Index
- chapter 1: 大器晚成 | job=validated | artifact=True | retrieval=True | hook=5.5 | review=False | risk=low | risk_count=0
- chapter 2: 二姑卫荭 | job=validated | artifact=True | retrieval=True | hook=4.5 | review=True | risk=low | risk_count=2
- chapter 3: 养生功法 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=True | risk=low | risk_count=2
- chapter 4: 珍惜眼下 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0
- chapter 5: 婚事敲定（求收藏，求追读） | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0
- chapter 6: 郑国官兵（求收藏，求追读） | job=validated | artifact=True | retrieval=True | hook=4.0 | review=True | risk=low | risk_count=2
- chapter 7: 不入祠堂（求收藏 求追读） | job=validated | artifact=True | retrieval=True | hook=5.0 | review=True | risk=low | risk_count=2
- chapter 8: 私房钱（求收藏，求追读） | job=validated | artifact=True | retrieval=True | hook=4.0 | review=True | risk=low | risk_count=2
- chapter 9: 逼上绝境（求收藏，求追读） | job=validated | artifact=True | retrieval=True | hook=4.5 | review=True | risk=low | risk_count=2
- chapter 10: 抬起头来（求收藏 求追读） | job=validated | artifact=True | retrieval=True | hook=5.5 | review=False | risk=low | risk_count=0
- chapter 11: 脱去奴籍（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 12: 老爷改性了（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 13: 改籍，单武举（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 14: 养生功大成（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 15: 单武举的教导（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 16: 武学奇才（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 17: 无根浮萍（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 18: 四粒银豆子（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 19: 虎鹤双形拳（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0
- chapter 20: 命格妙用（求收藏，求追读） | job=pending | artifact=False | retrieval=False | hook=None | review=False | risk=None | risk_count=0

## Failed Summary
- none

## Risk Summary
- risk_card_count: 10
- checker_result_count: 90
- review_candidate_count: 6
- high_risk_chapters: []
- risk_counts_by_domain: {'character': 6, 'plot': 6}
- risk_counts_by_severity: {'low': 12}

### Human Review Candidates
- chapter 2: risk=low | risk_count=2 | review=True | title=二姑卫荭
- chapter 3: risk=low | risk_count=2 | review=True | title=养生功法
- chapter 6: risk=low | risk_count=2 | review=True | title=郑国官兵（求收藏，求追读）
- chapter 7: risk=low | risk_count=2 | review=True | title=不入祠堂（求收藏 求追读）
- chapter 8: risk=low | risk_count=2 | review=True | title=私房钱（求收藏，求追读）
- chapter 9: risk=low | risk_count=2 | review=True | title=逼上绝境（求收藏，求追读）

### Review Candidate Evidence Preview
- chapter 2 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['relationship_shift_candidate', 'transition_support_gap'] | risk=low | confidence=0.35
  - summary: 本章推进结论与证据支撑之间存在可疑缺口，建议人工复核。
  - evidence: 本章状态推进集中体现在：卫图在李宅灶房试吃萝卜炖肉、厨娘杏给卫图送来萝卜炖肉并允许其试味、卫图得知黄家大少爷从府城游学回来了。
  - evidence: 本章主要写卫图在李宅的日常劳动中察觉命格信息，并借着去黄宅拜见二姑卫荭的机会，为后续打听养生功与武道资源埋下行动线。
  - counter: 当前人物变化可能是推进摘要过强，并不必然构成 OOC。
  - continuity: 推进: 本章状态推进集中体现在：卫图在李宅灶房试吃萝卜炖肉、厨娘杏给卫图送来萝卜炖肉并允许其试味、卫图得知黄家大少爷从府城游学回来了。
  - continuity: 推进: 本章关系面出现可见变化：卫图与杏存在暧昧关系、杏对李家主母的偷吃行为被默许。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差
- chapter 3 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: 证据只表明卫荭同意让阮武师教卫图几手，并未证明她会持续、实质性地帮卫图解决后续问题；将“可能会帮”上升为已验证，证据不足。
  - evidence: 前文伏笔“卫图怀疑自己所在世界可能存在仙人修行”在当前分支中已有兑现信号。
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：卫图向卫荭提出想学养生功、卫荭同意请阮武师教卫图几手养生功、卫荭离开时让丫鬟带走礼物。
  - continuity: 推进: 本章关系面出现可见变化：卫图与卫荭是亲属关系、卫荭已嫁入黄家。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差
- chapter 6 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
  - evidence: analysis.summary.one_sentence
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：卫图和杏婚后继续在李宅内外忙活、李童氏多次夸奖杏的勤快表现、杏不再私下偷吃灶房里的荤腥。
  - continuity: 推进: 本章关系面出现可见变化：卫图与杏已成婚、杏与李童氏保持主仆关系。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差
- chapter 7 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
  - evidence: 输入事实层与前情状态中没有关于章节标题或标题意涵的证据，属于元信息推断。
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：卫图从卫豹口中得知昨夜官兵所杀刀匪疑似来自隔壁白阳县、卫豹向卫图说明白阳县赈灾中义仓粮食短缺严重、卫豹拿出攒下的钱给卫图，表示可用于置办家业或赎回身契。
  - continuity: 推进: 本章关系面出现可见变化：卫图与杏是夫妻、卫图与卫豹是父子。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差
- chapter 8 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
  - evidence: 本章对角色位置没有出现跃迁，卫图仍处在‘家奴/身契未赎回’的受限状态；但信息掌握明显增加，已经确认自己若不赎身便无法入祠堂，这会直接影响他对家族、身份和未来安排的判断。
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：卫图得知脱奴籍需要先赎回身契，再去衙门户房办理手续、卫图判断自己赎身的最低门槛约为十两银子、卫图向杏询问她手上的私房钱。
  - continuity: 推进: 本章关系面出现可见变化：卫图与杏是夫妻关系，且共担脱籍压力、杏的私房钱被视为她自己的嫁奁，卫图未经同意不能动用。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差
- chapter 9 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
  - evidence: 本章对角色状态的变化主要是“延续中带推进”：卫图仍处于李宅马倌的低位劳动场景，但其眉心金光闪烁提示他身上可能出现了新的异常或能力变化；这一点属于状态层面的重要增量，后续大概率会继续展开。
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：李童氏把三亩河沿地租给卫图夫妇、李家地租按六成交粮，且包含官府地税、卫图计算种三亩地后还能留下四成收成。
  - continuity: 推进: 本章关系面出现可见变化：卫图与李耀祖存在主仆关系、卫图与李童氏是租地协商关系。
  - branch-signal: 活跃冲突: 卫图担心养马失误会遭李老爷责罚
  - branch-signal: 活跃冲突: 卫图的贫苦处境与求道愿望之间的现实落差

### Review Candidate Clusters
- status=needs_review (待复核) | priority=P1 | pattern=持续型问题 | title=人物风险簇：character_resolution_support_gap | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | chapters=[3, 6, 7, 8, 9] | span=3-9 | chapter_count=5 | confidence=0.35
  - sample: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - action: 优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。
  - workflow_lane: human_review_queue
  - queue_priority: high
  - action_required: True
  - suggested_deadline_level: soon
  - batch_operation_hint: batch_human_review_queue
  - auto_next_action: 优先安排人工复核 人物风险簇：character_resolution_support_gap，确认是否需要升级或关闭。
  - escalation_reason: 当前问题簇仍缺少人工确认，暂不适合直接关闭。
- status=open (待观察) | priority=P3 | pattern=单点问题 | title=人物风险簇：transition_support_gap | checkers=['character_ooc', 'plot_logic_consistency'] | types=['relationship_shift_candidate', 'transition_support_gap'] | chapters=[2] | span=2 | chapter_count=1 | confidence=0.35
  - sample: 本章推进结论与证据支撑之间存在可疑缺口，建议人工复核。
  - action: 优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。
  - workflow_lane: monitor_queue
  - queue_priority: low
  - action_required: False
  - suggested_deadline_level: backlog
  - batch_operation_hint: batch_monitoring_watchlist
  - auto_next_action: 继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。

## Review Summary
- cluster_count: 2
- history_event_count: 0
- current_owner_top: 
- current_owner_top_count: 0
- latest_actor_top: 
- latest_actor_top_count: 0
- latest_event_type_top: 
- latest_event_type_top_count: 0
- workflow_lane_top: human_review_queue
- workflow_lane_top_count: 1
- queue_priority_top: high
- queue_priority_top_count: 1
- deadline_level_top: backlog
- deadline_level_top_count: 1
- batch_operation_hint_top: batch_human_review_queue
- batch_operation_hint_top_count: 1
- batch_suggestions: [{'hint_code': 'batch_human_review_queue', 'hint_title': '可批量人工复核', 'action_bucket': 'review', 'batch_priority': 'medium', 'group_strategy': 'by_checker_span', 'group_key': 'character_ooc:long_run', 'span_bucket': 'long_run', 'cluster_count': 1, 'cluster_keys': ['character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap'], 'suggested_cluster_order': ['character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap'], 'suggested_cluster_order_titles': ['人物风险簇：character_resolution_support_gap'], 'suggested_cluster_order_details': [{'cluster_key': 'character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap', 'cluster_title': '人物风险簇：character_resolution_support_gap', 'queue_priority': 'high', 'review_priority': 'P1', 'chapter_count': 5, 'confidence': 0.35, 'human_review_batch_rank_score': 97.0, 'human_review_batch_rank_reason': 'priority=P1 | pattern=持续型问题 | chapter_count=5 | confidence=0.35 | human_review_batch_rank_score=97.00', 'escalation_tier': '', 'escalation_urgency_score': 0.0, 'escalation_rank_reason': '', 'escalation_batch_rank_score': 0.0, 'escalation_batch_rank_reason': '', 'close_stability_score': 13.5, 'close_ready_rank_reason': 'close_ready=False | history_count=0 | chapter_count=5 | confidence=0.35 | close_stability_score=13.50', 'close_batch_rank_score': 0.0, 'close_batch_rank_reason': '', 'chapter_span_width': 6, 'batch_rank_score': 449.5, 'order_reason': 'queue=high | priority=P1 | pattern=持续型问题 | chapter_count=5 | confidence=0.35 | span_width=6 | batch_rank_score=449.50'}], 'ordering_strategy': 'queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter', 'suggested_first_cluster_reason': 'queue=high | priority=P1 | pattern=持续型问题 | chapter_count=5 | confidence=0.35 | span_width=6 | batch_rank_score=449.50', 'cluster_titles': ['人物风险簇：character_resolution_support_gap'], 'owners': [], 'suggested_owner': '', 'primary_checker': 'character_ooc', 'pattern_label_top': '持续型问题', 'risk_types': ['character_resolution_support_gap', 'resolution_support_gap'], 'phase2_focus_top': '', 'chapter_spans': ['3-9'], 'queue_priority_top': 'high', 'deadline_level_top': 'soon', 'escalation_tier_top': '', 'action_required': True, 'resolved_candidate_count': 0, 'escalation_candidate_count': 0, 'recommended_batch_action': '优先安排人工复核 人物风险簇：character_resolution_support_gap，确认是否需要升级或关闭。', 'suggestion_rank_score': 345.0, 'suggestion_rank_reason': 'action_bucket=review | batch_priority=medium | cluster_count=1 | action_required=True | suggestion_rank_score=345.00'}, {'hint_code': 'batch_monitoring_watchlist', 'hint_title': '可批量观察跟踪', 'action_bucket': 'monitor', 'batch_priority': 'low', 'group_strategy': 'by_checker', 'group_key': 'character_ooc', 'span_bucket': 'single', 'cluster_count': 1, 'cluster_keys': ['character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap'], 'suggested_cluster_order': ['character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap'], 'suggested_cluster_order_titles': ['人物风险簇：transition_support_gap'], 'suggested_cluster_order_details': [{'cluster_key': 'character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap', 'cluster_title': '人物风险簇：transition_support_gap', 'queue_priority': 'low', 'review_priority': 'P3', 'chapter_count': 1, 'confidence': 0.35, 'human_review_batch_rank_score': 0.0, 'human_review_batch_rank_reason': '', 'escalation_tier': '', 'escalation_urgency_score': 0.0, 'escalation_rank_reason': '', 'escalation_batch_rank_score': 0.0, 'escalation_batch_rank_reason': '', 'close_stability_score': 5.5, 'close_ready_rank_reason': 'close_ready=False | history_count=0 | chapter_count=1 | confidence=0.35 | close_stability_score=5.50', 'close_batch_rank_score': 0.0, 'close_batch_rank_reason': '', 'chapter_span_width': 0, 'batch_rank_score': 215.5, 'order_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50'}], 'ordering_strategy': 'queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter', 'suggested_first_cluster_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50', 'cluster_titles': ['人物风险簇：transition_support_gap'], 'owners': [], 'suggested_owner': '', 'primary_checker': 'character_ooc', 'pattern_label_top': '单点问题', 'risk_types': ['relationship_shift_candidate', 'transition_support_gap'], 'phase2_focus_top': '', 'chapter_spans': ['2'], 'queue_priority_top': 'low', 'deadline_level_top': 'backlog', 'escalation_tier_top': '', 'action_required': False, 'resolved_candidate_count': 0, 'escalation_candidate_count': 0, 'recommended_batch_action': '继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。', 'suggestion_rank_score': 75.0, 'suggestion_rank_reason': 'action_bucket=monitor | batch_priority=low | cluster_count=1 | action_required=False | suggestion_rank_score=75.00'}]
- auto_next_action_code_top: observe_and_wait
- auto_next_action_code_top_count: 1
- auto_next_action_top: 优先安排人工复核 人物风险簇：character_resolution_support_gap，确认是否需要升级或关闭。
- auto_next_action_top_count: 1
- escalation_reason_code_top: awaiting_human_confirmation
- escalation_reason_code_top_count: 1
- escalation_reason_top: 当前问题簇仍缺少人工确认，暂不适合直接关闭。
- escalation_reason_top_count: 1
- phase2_focus_top: 
- phase2_focus_top_count: 0
- pending_assignment_count: 0
- pending_escalation_count: 0
- resolved_count: 0
- needs_review_count: 1
- action_required_count: 1
- by_status: {'needs_review': 1, 'open': 1}
- by_result: {}
- by_owner: {}
- by_actor: {}
- by_latest_event_type: {}
- by_workflow_lane: {'human_review_queue': 1, 'monitor_queue': 1}
- by_queue_priority: {'high': 1, 'low': 1}
- by_deadline_level: {'soon': 1, 'backlog': 1}
- by_batch_operation_hint: {'batch_human_review_queue': 1, 'batch_monitoring_watchlist': 1}
- by_auto_next_action_code: {'schedule_human_review': 1, 'observe_and_wait': 1}
- by_auto_next_action: {'优先安排人工复核 人物风险簇：character_resolution_support_gap，确认是否需要升级或关闭。': 1, '继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。': 1}
- by_escalation_reason_code: {'awaiting_human_confirmation': 1}
- by_escalation_reason: {'当前问题簇仍缺少人工确认，暂不适合直接关闭。': 1}
- by_phase2_focus: {}

## Windows
### Window 1-5
第1章：本章以卫图夜起喂马、抽旱烟缓解疲惫为日常底色，穿插其从佃奴升为李宅马倌的过往，以及眉心金光闪烁、准备去找二姑等信息，呈现出“低处谋变”的过渡状态。 第2章：卫图先在李宅做马倌与杂役，随后离开李宅去胭脂铺挑选礼物，再前往黄宅求见二姑卫荭，准备借亲属关系打听养生功等线索。 第3章：卫图借亲缘关系拜见二姑，请得养生功图册，并在回到李宅后开始学习《龟息养气功》，章节重点是求法、得法与初练。 第4章：卫图认清阶级难以跨越，转而持续苦练《龟息养气功》并初见成效；随后被大奶奶召见，得知与杏的婚事可能获准，心情由克制转为欣喜。 第5章：李童氏认可卫图的感恩态度，正式敲定他与杏的婚事并安排新房；次日两人成婚后开始规划回乡报喜、攒钱置业与未来子女教育，卫图也重新投入养生功修炼。

### Window 6-10
第6章：卫图和杏婚后继续勤勉在李宅忙活，李童氏持续夸奖杏的变化；章节末尾出现郑国官兵骑队，引出新的外部动向。 第7章：卫图回到乡下后，从卫豹口中了解到白阳县灾荒、刀匪来源及赈灾粮缺的乱象；同时卫豹拿出积攒的钱资助他，并明确告知赎回身契前家奴不能入祠堂拜祖先，令卫图对自身处境与未来出路产生新的思考。 第8章：卫图明确提出脱籍去考武举，并向杏打听私房钱；杏拿出三两七钱，说明两人正尝试为赎身与未来筹钱，但距离十两门槛仍有明显缺口。 第9章：卫图确认武举与脱籍路线后，进入攒钱、算账、租地的现实推进阶段。 第10章：卫图判断局势将变，决定尽快向李童氏提出赎身并参加武举；他先与杏商量并做应急安排，随后在内宅正式摊牌，引发李童氏的强烈震惊与审视。


## Graph Overview
- nodes: 351
- edges: 11379
- node types: {'conflict': 27, 'continuity': 58, 'entity': 31, 'event': 113, 'foreshadow': 28, 'relation': 33, 'world_rule': 61}
- edge types: {'carries_forward': 4072, 'co_occurs': 135, 'conflict_centers_on': 1109, 'conflict_involves': 46, 'constrains': 406, 'contextualizes': 1297, 'hints_at': 1401, 'participates_in': 640, 'pressured_by': 46, 'relates_to': 58, 'advances_to': 530, 'escalates_to': 114, 'evolves_to': 145, 'follows': 103, 'pays_off_as': 1154, 'persists_into': 123}

Top Nodes:
- conflict:卫图作为家奴无法进入卫家祠堂 (seen 1)
- conflict:卫图发现修炼龟息养气功需要五年 (seen 1)
- conflict:卫图和杏的回乡路线面临山匪与野兽风险 (seen 1)
- conflict:卫图在黄宅受到冷眼和轻视 (seen 1)
- conflict:卫图家贫，只能买便宜胭脂去见二姑 (seen 1)
- conflict:卫图想脱籍去考武举，但缺少赎身银且需要主家放行 (seen 1)
- conflict:卫图担心养马失误会遭李老爷责罚 (seen 1)
- conflict:卫图担心空手上门会遭二姑白眼 (seen 1)
- conflict:卫图担忧灾荒引发匪乱波及县城 (seen 1)
- conflict:卫图提出学武被卫荭拒绝为独门武功，只能转为养生功 (seen 1)

## State Summary
### 已回收伏笔
- “大器晚成”命格可能在晚年显效
- 卫图怀疑自己所在世界可能存在仙人修行
- 卫图计划从二姑处寻找养生功线索
- 黄宅可能存在武师和武功资源
- 二姑卫荭可能会帮卫图解决事情
- 卫图此次上门的真正请求尚未说出
- 黄宅可能存在可供卫图利用的人脉或资源
- 卫图下次不要再来找卫荭
- 卫图可能在五年后验证命格和功法效果
- 卫图可能继续依靠龟息养气功修炼
### 冲突升级
- 卫图担心养马失误会遭李老爷责罚
- 卫图的贫苦处境与求道愿望之间的现实落差
- 卫图家贫，只能买便宜胭脂去见二姑
- 卫图担心空手上门会遭二姑白眼
- 卫荭对卫图的来意先表现出明显防备
- 李宅饮食资源有限，肉食并不常见
- 卫图发现修炼龟息养气功需要五年
- 卫图在黄宅受到冷眼和轻视
- 卫图提出学武被卫荭拒绝为独门武功，只能转为养生功
- 卫荭对卫图的请求只提供有限帮助
### 关系变化
- 二姑与黄老爷存在偏房关系
- 卫图与李宅主家的雇佣从属关系
- 卫图受老刘头传授养马技艺
- 卫图与二姑卫荭是亲属关系
- 卫图与杏存在暧昧关系
- 卫图与黄宅之间存在外亲通行关系
- 卫荭已嫁入黄家，身份更接近黄家妇而非卫家人
- 卫图与卫荭是亲属关系
- 卫图与阮武师发生接触
- 卫图与黄宅护院存在上下资源关系
### 规则约束
- 命格以金紫之色呈现，且可在脑海中显化为玺印
- 本章确认存在“命格”设定
- 李宅主仆在饮食上存在明显等级差异
- 李宅仆役有佃奴与马倌的分化，待遇不同
- 李宅的马需要三更天加喂夜草
- 武功秘法中存在养生功，可用于延年益寿
- 厨娘偷吃在李家属于默认存在的现象

## Chapter Output Summary
### 推进摘要总览
- 第1章: 本章状态推进集中体现在：卫图夜里起身喂马、卫图抽旱烟缓解疲惫、卫图给自己洗漱并发现容貌异常老态。
- 第1章: 本章关系面出现可见变化：卫图与李宅主家的雇佣从属关系、卫图受老刘头传授养马技艺。
- 第1章: 本章冲突面继续推进：卫图的贫苦处境与求道愿望之间的现实落差、卫图担心养马失误会遭李老爷责罚。
- 第1章: 本章对角色状态的变化主要是“延续中带推进”：卫图仍处于李宅马倌的低位劳动场景，但其眉心金光闪烁提示他身上可能出现了新的异常或能力变化；这一点属于状态层面的重要增量，后续大概率会继续展开。
- 第1章: 卫图的社会位置并未在本章发生跃迁，仍是依靠养马技艺维持生计，但回顾其从佃奴升为马倌的经历，强化了“靠技艺改变命运”的主线方向，符合章节标题所指向的晚成意味。
- 第2章: 本章状态推进集中体现在：卫图在李宅灶房试吃萝卜炖肉、厨娘杏给卫图送来萝卜炖肉并允许其试味、卫图得知黄家大少爷从府城游学回来了。
- 第2章: 本章关系面出现可见变化：卫图与杏存在暧昧关系、杏对李家主母的偷吃行为被默许。
- 第2章: 本章冲突面继续推进：卫图家贫，只能买便宜胭脂去见二姑、卫图担心空手上门会遭二姑白眼。
- 第2章: 本章对主线的处理更接近“延续 + 局部推进”，没有回收旧伏笔，也没有明显的强冲突升级；此前关于命格、养生功、武师资源的伏笔仍处于开放状态。
- 第2章: 卫图的角色位置没有发生跃迁，仍是李宅马倌/杂役；但他已从单纯劳动转向主动搜集修行线索，信息掌握状态出现明确推进。
- 第3章: 本章状态推进集中体现在：卫图向卫荭提出想学养生功、卫荭同意请阮武师教卫图几手养生功、卫荭离开时让丫鬟带走礼物。
- 第3章: 本章关系面出现可见变化：卫图与卫荭是亲属关系、卫荭已嫁入黄家。
### 已解决线索总览
- 第3章: 前文伏笔“卫图怀疑自己所在世界可能存在仙人修行”在当前分支中已有兑现信号。
- 第3章: 前文伏笔“卫图计划从二姑处寻找养生功线索”在当前分支中已有兑现信号。
- 第3章: 前文伏笔“黄宅可能存在武师和武功资源”在当前分支中已有兑现信号。
- 第3章: 关系线“二姑与黄老爷存在偏房关系”已出现阶段性变化证据。
- 第3章: 关系线“卫图与李宅主家的雇佣从属关系”已出现阶段性变化证据。
- 第6章: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
- 第6章: 前文伏笔“卫图怀疑自己所在世界可能存在仙人修行”在当前分支中已有兑现信号。
- 第6章: 前文伏笔“卫图计划从二姑处寻找养生功线索”在当前分支中已有兑现信号。
- 第6章: 关系线“二姑与黄老爷存在偏房关系”已出现阶段性变化证据。
- 第6章: 关系线“卫图与李宅主家的雇佣从属关系”已出现阶段性变化证据。
- 第7章: 前文伏笔““大器晚成”命格可能在晚年显效”在当前分支中已有兑现信号。
- 第7章: 前文伏笔“卫图怀疑自己所在世界可能存在仙人修行”在当前分支中已有兑现信号。
### 未解线程总览
- 第1章: 新埋下的线程：“大器晚成”命格可能在晚年显效
- 第1章: 新埋下的线程：卫图计划从二姑处寻找养生功线索
- 第1章: 新埋下的线程：黄宅可能存在武师和武功资源
- 第2章: 新埋下的线程：二姑卫荭可能会帮卫图解决事情
- 第2章: 新埋下的线程：黄宅可能存在可供卫图利用的人脉或资源
- 第2章: 新埋下的线程：卫图此次上门的真正请求尚未说出
- 第2章: 持续施加约束的规则：命格以金紫之色呈现，且可在脑海中显化为玺印
- 第2章: 持续施加约束的规则：本章确认存在“命格”设定
- 第3章: 新埋下的线程：卫图下次不要再来找卫荭
- 第3章: 新埋下的线程：卫图可能继续依靠龟息养气功修炼
- 第3章: 新埋下的线程：龟息养气功修成后可进入感气之境
- 第3章: 仍待后续处理的升级冲突：卫图担心养马失误会遭李老爷责罚

## Reasoning Graph
### Central Nodes
- entity:卫图 degree=348
- foreshadow:卫图怀疑自己所在世界可能存在仙人修行 degree=192
- foreshadow:黄宅可能存在可供卫图利用的人脉或资源 degree=187
- foreshadow:卫图计划从二姑处寻找养生功线索 degree=185
- continuity:李童氏的反应说明她此前对卫图的低姿态形成了误判，后续主仆关系很可能进入更敏感的谈判或对抗。 degree=180
- continuity:赎身与武举为后续主线埋下明确目标，也把卫图从被动仆役位置推向主动争取身份的阶段。 degree=177
- continuity:关系层面没有出现剧烈反转，但卫图与杏的婚后关系更像共同承担生计压力的同盟；李童氏租地给卫图夫妇，也说明主家对这段关系的处置已进入可操作层面。 degree=176
- foreshadow:二姑卫荭可能会帮卫图解决事情 degree=175

### Reasoning Paths
- 卫图从佃奴升为李宅新的马倌 -[advances_to]-> 厨娘杏给卫图送来萝卜炖肉并允许其试味
- 卫图给自己洗漱并发现容貌异常老态 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图在水中看到自己容貌不断变老 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图发现脑海中的命格“大器晚成” -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图判断命格属性为坚韧不拔、必有所成 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图产生修炼养生功并求仙的计划 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图准备明天去找二姑打听养生功 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图次日继续在李宅做杂役和马倌工作 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图从佃奴升为李宅新的马倌 -[advances_to]-> 卫图在李宅灶房试吃萝卜炖肉
- 卫图给自己洗漱并发现容貌异常老态 -[advances_to]-> 厨娘杏给卫图送来萝卜炖肉并允许其试味
- 卫图在水中看到自己容貌不断变老 -[advances_to]-> 厨娘杏给卫图送来萝卜炖肉并允许其试味
- 卫图发现脑海中的命格“大器晚成” -[advances_to]-> 厨娘杏给卫图送来萝卜炖肉并允许其试味

### Active Conflicts
- 卫图担心养马失误会遭李老爷责罚
- 卫图的贫苦处境与求道愿望之间的现实落差
- 卫图家贫，只能买便宜胭脂去见二姑
- 卫图担心空手上门会遭二姑白眼
- 卫荭对卫图的来意先表现出明显防备
- 李宅饮食资源有限，肉食并不常见
- 卫图发现修炼龟息养气功需要五年
- 卫图在黄宅受到冷眼和轻视
- 卫图提出学武被卫荭拒绝为独门武功，只能转为养生功
- 卫荭对卫图的请求只提供有限帮助

### Open Foreshadowing
- 白阳县灾荒和赈灾账目异常暗示局势将乱

### World Rules
- 命格以金紫之色呈现，且可在脑海中显化为玺印
- 庆丰府存在武者与武道传承
- 庆丰府武者常兼具刀客、农人或匪徒身份
- 本章确认存在“命格”设定
- 李宅主仆在饮食上存在明显等级差异
- 李宅仆役有佃奴与马倌的分化，待遇不同
- 李宅的马需要三更天加喂夜草
- 武功秘法中存在养生功，可用于延年益寿
- 武者多靠血勇好斗，但年老后容易因暗伤暴毙
- 武道搏杀能力有限，十人敌已算强者

### Foreshadow States
- “大器晚成”命格可能在晚年显效 [paid_off]
- 卫图怀疑自己所在世界可能存在仙人修行 [paid_off]
- 卫图计划从二姑处寻找养生功线索 [paid_off]
- 黄宅可能存在武师和武功资源 [paid_off]
- 二姑卫荭可能会帮卫图解决事情 [paid_off]
- 卫图此次上门的真正请求尚未说出 [paid_off]
- 黄宅可能存在可供卫图利用的人脉或资源 [paid_off]
- 卫图下次不要再来找卫荭 [paid_off]
- 卫图可能在五年后验证命格和功法效果 [paid_off]
- 卫图可能继续依靠龟息养气功修炼 [paid_off]

### Conflict States
- 卫图担心养马失误会遭李老爷责罚 [escalated]
- 卫图的贫苦处境与求道愿望之间的现实落差 [escalated]
- 卫图家贫，只能买便宜胭脂去见二姑 [escalated]
- 卫图担心空手上门会遭二姑白眼 [escalated]
- 卫荭对卫图的来意先表现出明显防备 [escalated]
- 李宅饮食资源有限，肉食并不常见 [escalated]
- 卫图发现修炼龟息养气功需要五年 [escalated]
- 卫图在黄宅受到冷眼和轻视 [escalated]
- 卫图提出学武被卫荭拒绝为独门武功，只能转为养生功 [escalated]
- 卫荭对卫图的请求只提供有限帮助 [escalated]

### Relation States
- 二姑与黄老爷存在偏房关系 [evolved]
- 卫图与李宅主家的雇佣从属关系 [evolved]
- 卫图受老刘头传授养马技艺 [evolved]
- 卫图与二姑卫荭是亲属关系 [evolved]
- 卫图与杏存在暧昧关系 [evolved]
- 卫图与黄宅之间存在外亲通行关系 [evolved]
- 卫荭已嫁入黄家，身份更接近黄家妇而非卫家人 [evolved]
- 杏对李家主母的偷吃行为被默许 [stable]
- 卫图与卫荭是亲属关系 [evolved]
- 卫图与阮武师发生接触 [evolved]

### World Rule States
- 命格以金紫之色呈现，且可在脑海中显化为玺印 [constraining]
- 庆丰府存在武者与武道传承 [observed]
- 庆丰府武者常兼具刀客、农人或匪徒身份 [observed]
- 本章确认存在“命格”设定 [constraining]
- 李宅主仆在饮食上存在明显等级差异 [constraining]
- 李宅仆役有佃奴与马倌的分化，待遇不同 [constraining]
- 李宅的马需要三更天加喂夜草 [constraining]
- 武功秘法中存在养生功，可用于延年益寿 [constraining]
- 武者多靠血勇好斗，但年老后容易因暗伤暴毙 [observed]
- 武道搏杀能力有限，十人敌已算强者 [observed]
