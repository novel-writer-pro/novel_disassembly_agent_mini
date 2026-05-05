# Branch Report

## Status
- run_id: b0fb667b-ce1e-47a0-8346-92e3dbc6d3bc
- branch_id: 86ce179e-475a-42b9-ade3-a81a8626dc5f
- branch_name: main
- branch_status: active
- manifest_chapter_count: 3
- completed_chapters: 3
- failed_jobs: 0
- running_jobs: 0
- next_chapter: None
- fact_count: 37
- window_count: 0
- graph_node_count: 48
- graph_edge_count: 256

## Audit Conclusion
- Content Judgement: 当前分支已形成可用审查结果。
- Risk Judgement: 当前未发现明确高风险，但存在低/中风险人工复核候选。
- Blocking Judgement: 当前无执行阻塞。
- Recommended Action: 优先复核候选章节，再结合上下文决定是否继续推进。
- Review Storage: 当前 review 数据来自数据库主路径。

## Chapter Index
- chapter 1: 青华 | job=validated | artifact=True | retrieval=True | hook=4.5 | review=False | risk=low | risk_count=0
- chapter 2: 厌物丽人同行 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0
- chapter 3: 狡舌 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=True | risk=low | risk_count=2

## Failed Summary
- none

## Risk Summary
- risk_card_count: 3
- checker_result_count: 27
- review_candidate_count: 1
- high_risk_chapters: []
- risk_counts_by_domain: {'character': 1, 'plot': 1}
- risk_counts_by_severity: {'low': 2}

### Human Review Candidates
- chapter 3: risk=low | risk_count=2 | review=True | title=狡舌

### Review Candidate Evidence Preview
- chapter 3 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['relationship_shift_candidate', 'transition_support_gap'] | risk=low | confidence=0.35
  - summary: 本章推进结论与证据支撑之间存在可疑缺口，建议人工复核。
  - evidence: fact-layer 中没有任何角色的对话或事件证据提到‘祖师洞’或‘碑林’，这些地点名称未在本章事实层中出现。虽然可选图谱摘要中含有这些节点，但本章文本并未提供支撑，属于无证据的场景推断。
  - evidence: 本章状态推进集中体现在：布衣少年讽刺白衣丽人和紫衣小子、白衣丽人被逗笑、青旒斥责小六并指出其失态。
  - counter: 当前人物变化可能是推进摘要过强，并不必然构成 OOC。
  - continuity: 推进: 本章状态推进集中体现在：布衣少年讽刺白衣丽人和紫衣小子、白衣丽人被逗笑、青旒斥责小六并指出其失态。
  - continuity: 推进: 本章关系面出现可见变化：布衣少年与青衫少女为师兄妹、青衫少女对白衣丽人羡慕并自卑。
  - branch-signal: 活跃冲突: 青旒对小六嬉皮笑脸的不满
  - branch-signal: 未回收伏笔: 黑牌受外力召唤异常振动

### Review Candidate Clusters
- status=open (待观察) | priority=P3 | pattern=单点问题 | title=人物风险簇：transition_support_gap | checkers=['character_ooc', 'plot_logic_consistency'] | types=['relationship_shift_candidate', 'transition_support_gap'] | chapters=[3] | span=3 | chapter_count=1 | confidence=0.35
  - sample: 本章推进结论与证据支撑之间存在可疑缺口，建议人工复核。
  - action: 优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。
  - workflow_lane: monitor_queue
  - queue_priority: low
  - action_required: False
  - suggested_deadline_level: backlog
  - batch_operation_hint: batch_monitoring_watchlist
  - auto_next_action: 继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。

## Review Summary
- cluster_count: 1
- history_event_count: 0
- current_owner_top: 
- current_owner_top_count: 0
- latest_actor_top: 
- latest_actor_top_count: 0
- latest_event_type_top: 
- latest_event_type_top_count: 0
- workflow_lane_top: monitor_queue
- workflow_lane_top_count: 1
- queue_priority_top: low
- queue_priority_top_count: 1
- deadline_level_top: backlog
- deadline_level_top_count: 1
- batch_operation_hint_top: batch_monitoring_watchlist
- batch_operation_hint_top_count: 1
- batch_suggestions: [{'hint_code': 'batch_monitoring_watchlist', 'hint_title': '可批量观察跟踪', 'action_bucket': 'monitor', 'batch_priority': 'low', 'group_strategy': 'by_checker', 'group_key': 'character_ooc', 'span_bucket': 'single', 'cluster_count': 1, 'cluster_keys': ['character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap'], 'suggested_cluster_order': ['character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap'], 'suggested_cluster_order_titles': ['人物风险簇：transition_support_gap'], 'suggested_cluster_order_details': [{'cluster_key': 'character_ooc|plot_logic_consistency|::|relationship_shift_candidate|transition_support_gap', 'cluster_title': '人物风险簇：transition_support_gap', 'queue_priority': 'low', 'review_priority': 'P3', 'chapter_count': 1, 'confidence': 0.35, 'human_review_batch_rank_score': 0.0, 'human_review_batch_rank_reason': '', 'escalation_tier': '', 'escalation_urgency_score': 0.0, 'escalation_rank_reason': '', 'escalation_batch_rank_score': 0.0, 'escalation_batch_rank_reason': '', 'close_stability_score': 5.5, 'close_ready_rank_reason': 'close_ready=False | history_count=0 | chapter_count=1 | confidence=0.35 | close_stability_score=5.50', 'close_batch_rank_score': 0.0, 'close_batch_rank_reason': '', 'chapter_span_width': 0, 'batch_rank_score': 215.5, 'order_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50'}], 'ordering_strategy': 'queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter', 'suggested_first_cluster_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50', 'cluster_titles': ['人物风险簇：transition_support_gap'], 'owners': [], 'suggested_owner': '', 'primary_checker': 'character_ooc', 'pattern_label_top': '单点问题', 'risk_types': ['relationship_shift_candidate', 'transition_support_gap'], 'phase2_focus_top': '', 'chapter_spans': ['3'], 'queue_priority_top': 'low', 'deadline_level_top': 'backlog', 'escalation_tier_top': '', 'action_required': False, 'resolved_candidate_count': 0, 'escalation_candidate_count': 0, 'recommended_batch_action': '继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。', 'suggestion_rank_score': 75.0, 'suggestion_rank_reason': 'action_bucket=monitor | batch_priority=low | cluster_count=1 | action_required=False | suggestion_rank_score=75.00'}]
- auto_next_action_code_top: observe_and_wait
- auto_next_action_code_top_count: 1
- auto_next_action_top: 继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。
- auto_next_action_top_count: 1
- escalation_reason_code_top: 
- escalation_reason_code_top_count: 0
- escalation_reason_top: 
- escalation_reason_top_count: 0
- phase2_focus_top: 
- phase2_focus_top_count: 0
- pending_assignment_count: 0
- pending_escalation_count: 0
- resolved_count: 0
- needs_review_count: 0
- action_required_count: 0
- by_status: {'open': 1}
- by_result: {}
- by_owner: {}
- by_actor: {}
- by_latest_event_type: {}
- by_workflow_lane: {'monitor_queue': 1}
- by_queue_priority: {'low': 1}
- by_deadline_level: {'backlog': 1}
- by_batch_operation_hint: {'batch_monitoring_watchlist': 1}
- by_auto_next_action_code: {'observe_and_wait': 1}
- by_auto_next_action: {'继续观察 人物风险簇：transition_support_gap，等待更多证据后再决定是否升级。': 1}
- by_escalation_reason_code: {}
- by_escalation_reason: {}
- by_phase2_focus: {}

## Windows
- none

## Graph Overview
- nodes: 48
- edges: 256
- node types: {'continuity': 14, 'entity': 10, 'event': 13, 'foreshadow': 2, 'relation': 3, 'world_rule': 5, 'conflict': 1}
- edge types: {'carries_forward': 105, 'constrains': 11, 'contextualizes': 10, 'hints_at': 17, 'participates_in': 43, 'relates_to': 6, 'co_occurs': 16, 'follows': 9, 'advances_to': 15, 'conflict_centers_on': 7, 'conflict_involves': 4, 'evolves_to': 1, 'persists_into': 8, 'pressured_by': 4}

Top Nodes:
- conflict:青旒对小六嬉皮笑脸的不满 (seen 1)
- continuity:世界观通过‘祖师洞’‘碑林’‘仙师’等词初步展现修仙背景。 (seen 1)
- continuity:位置信息：从对话推断二人处于青华门附近（如‘祖师洞’、‘碑林’等场景提及），但无明确移动变化。 (seen 1)
- continuity:关系变化：小六与青旒的关系在本章中未发生质变，仍维持师兄妹互动，但青旒对小六的批评可能埋下后续争执伏笔。 (seen 1)
- continuity:前情状态摘要中的未回收伏笔——黑牌受外力召唤异常振动（第一章）在本章完全没有提及，属于‘暂缓’处理，悬念仍然开放，但本章未推进。 (seen 1)
- continuity:前情状态摘要为空，无未回收伏笔或冲突升级，因此本章属于独立的新事件引入，延续性体现在后续需解释异常现象。 (seen 1)
- continuity:力量与信息掌握：青旒提供了关于青华门入门试炼的具体规则（每三个月一次，目测关淘汰率高），小六知晓后立下宏愿，信息掌握程度提升。 (seen 1)
- continuity:小六子眼神变得深邃有神，可能暗示其身份或心境变化，为后续伏笔。 (seen 1)
- continuity:少年对黑牌的掌握状态从普通持有变为感知异常，信息掌握发生显著变化；但位置（仍在山中下山途中）未变，关系与力量无明确变化。 (seen 1)
- continuity:无新冲突升级或新伏笔引入，主要延续角色性格刻画和世界观规则（青华门选拔制度）的揭示。 (seen 1)

## State Summary
### 新增伏笔
- 黑牌受外力召唤异常振动
- 小六立下宏愿将在青华门出人头地
### 新增冲突
- 青旒对小六嬉皮笑脸的不满
### 关系变化
- 少年持有黑牌
### 规则约束
- 口诀蕴含世界观理念
- 存在一种非金非木、触之凉意的奇异黑牌
- 黑牌能响应外界召唤而产生振动和热量
- 青华门入门试炼规则
- 青华门弟子需通过三道入门关

## Chapter Output Summary
### 推进摘要总览
- 第1章: 本章状态推进集中体现在：少年念诵口诀、少年抛接黑牌、少年将黑牌放入衣襟并扛柴下山。
- 第1章: 本章关系面出现可见变化：少年持有黑牌。
- 第1章: 本章结尾黑牌突发振动发热，构成一个明确的悬念钩子，强度中等偏强，驱动下一章探索振动来源与黑牌的真正作用。
- 第1章: 少年对黑牌的掌握状态从普通持有变为感知异常，信息掌握发生显著变化；但位置（仍在山中下山途中）未变，关系与力量无明确变化。
- 第3章: 本章状态推进集中体现在：布衣少年讽刺白衣丽人和紫衣小子、白衣丽人被逗笑、青旒斥责小六并指出其失态。
- 第3章: 本章关系面出现可见变化：布衣少年与青衫少女为师兄妹、青衫少女对白衣丽人羡慕并自卑。
- 第3章: 本章冲突面继续推进：青旒对小六嬉皮笑脸的不满。
- 第3章: 本章明确建立了赵小六（赵井泉）与褚青旒的师兄妹关系（置信度0.85），以及小六面对入门试炼的强烈进取心。
- 第3章: 位置信息：从对话推断二人处于青华门附近（如‘祖师洞’、‘碑林’等场景提及），但无明确移动变化。
### 未解线程总览
- 第1章: 新埋下的线程：黑牌受外力召唤异常振动
- 第3章: 新埋下的线程：小六立下宏愿将在青华门出人头地
- 第3章: 持续施加约束的规则：口诀蕴含世界观理念
- 第3章: 持续施加约束的规则：存在一种非金非木、触之凉意的奇异黑牌

## Reasoning Graph
### Central Nodes
- event:青旒嗔怪小六子油嘴滑舌 degree=24
- entity:小六子 degree=20
- conflict:青旒对小六嬉皮笑脸的不满 degree=20
- event:青旒发现小六子凝视自己而害羞 degree=18
- event:小六子称赞青旒动作像仙女 degree=18
- event:青旒质疑小六要先过三道入门关 degree=18
- foreshadow:小六立下宏愿将在青华门出人头地 degree=18
- entity:青旒师妹 degree=17

### Reasoning Paths
- 黑牌突发振动发热 -[follows]-> 小六子称赞青旒动作像仙女
- 黑牌突发振动发热 -[follows]-> 青旒嗔怪小六子油嘴滑舌
- 黑牌突发振动发热 -[follows]-> 青旒发现小六子凝视自己而害羞
- 青旒发现小六子凝视自己而害羞 -[advances_to]-> 青旒斥责小六并指出其失态
- 青旒嗔怪小六子油嘴滑舌 -[advances_to]-> 青旒质疑小六要先过三道入门关
- 小六子称赞青旒动作像仙女 -[advances_to]-> 青旒质疑小六要先过三道入门关
- 青旒发现小六子凝视自己而害羞 -[advances_to]-> 青旒质疑小六要先过三道入门关
- 青旒嗔怪小六子油嘴滑舌 -[advances_to]-> 小六立下宏愿要通过试炼出人头地
- 小六子称赞青旒动作像仙女 -[advances_to]-> 小六立下宏愿要通过试炼出人头地
- 青旒发现小六子凝视自己而害羞 -[advances_to]-> 小六立下宏愿要通过试炼出人头地
- 青旒嗔怪小六子油嘴滑舌 -[advances_to]-> 小六讨好青旒并指责紫衣小子
- 小六子称赞青旒动作像仙女 -[advances_to]-> 小六讨好青旒并指责紫衣小子

### Active Conflicts
- 青旒对小六嬉皮笑脸的不满

### Open Foreshadowing
- 黑牌受外力召唤异常振动
- 小六立下宏愿将在青华门出人头地

### World Rules
- 口诀蕴含世界观理念
- 存在一种非金非木、触之凉意的奇异黑牌
- 黑牌能响应外界召唤而产生振动和热量
- 青华门入门试炼规则
- 青华门弟子需通过三道入门关

### Foreshadow States
- 黑牌受外力召唤异常振动 [open]
- 小六立下宏愿将在青华门出人头地 [open]

### Conflict States
- 青旒对小六嬉皮笑脸的不满 [active]

### Relation States
- 少年持有黑牌 [evolved]
- 布衣少年与青衫少女为师兄妹 [stable]
- 青衫少女对白衣丽人羡慕并自卑 [stable]

### World Rule States
- 口诀蕴含世界观理念 [constraining]
- 存在一种非金非木、触之凉意的奇异黑牌 [constraining]
- 黑牌能响应外界召唤而产生振动和热量 [constraining]
- 青华门入门试炼规则 [constraining]
- 青华门弟子需通过三道入门关 [constraining]
