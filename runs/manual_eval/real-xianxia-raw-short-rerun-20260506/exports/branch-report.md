# Branch Report

## Status
- run_id: 51499b32-cdd0-475f-bbc7-2ac27ea0f529
- branch_id: 23685de0-a53e-4229-a946-14d53d5b026d
- branch_name: main
- branch_status: active
- manifest_chapter_count: 5
- completed_chapters: 5
- failed_jobs: 0
- running_jobs: 0
- next_chapter: None
- fact_count: 51
- window_count: 1
- graph_node_count: 64
- graph_edge_count: 524

## Audit Conclusion
- Content Judgement: 当前分支已形成可用审查结果。
- Risk Judgement: 当前未发现明确高风险，但存在低/中风险人工复核候选。
- Blocking Judgement: 当前无执行阻塞。
- Recommended Action: 优先复核候选章节，再结合上下文决定是否继续推进。
- Review Storage: 当前 review 数据来自数据库主路径。

## Chapter Index
- chapter 1: 青华 | job=validated | artifact=True | retrieval=True | hook=4.5 | review=False | risk=low | risk_count=0
- chapter 2: 厌物丽人同行 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0
- chapter 3: 狡舌 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0
- chapter 4: 仙道无凭 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=True | risk=low | risk_count=2
- chapter 5: 世界 | job=validated | artifact=True | retrieval=True | hook=4.0 | review=False | risk=low | risk_count=0

## Failed Summary
- none

## Risk Summary
- risk_card_count: 5
- checker_result_count: 45
- review_candidate_count: 1
- high_risk_chapters: []
- risk_counts_by_domain: {'character': 1, 'plot': 1}
- risk_counts_by_severity: {'low': 2}

### Human Review Candidates
- chapter 4: risk=low | risk_count=2 | review=True | title=仙道无凭

### Review Candidate Evidence Preview
- chapter 4 | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | risk=low | confidence=0.35
  - summary: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - evidence: analysis-layer 的 summary.detailed 中描述‘少年通过指桑骂槐（蛤蟆精）的方式讽刺了路过的白衣丽人’，该事件在 fact-layer 中无直接证据支持（fact-layer events 仅包含少女指责、少年讨好、少女喜悦三项），属于过度推断。
  - evidence: 关系线“小六子和青旒是同门师兄妹”已出现阶段性变化证据。
  - counter: 当前人物变化与“已解决/已兑现”类表述之间仍可能存在解释空间。
  - continuity: 推进: 本章状态推进集中体现在：青衫少女指责布衣少年盯着其他女子看、布衣少年讨好青衫少女并提及修炼入门、青衫少女因布衣少年的赞美而喜悦。
  - continuity: 推进: 本章关系面出现可见变化：布衣少年与青衫少女是同门师兄妹。
  - branch-signal: 活跃冲突: 布衣少年用言语打压/讽刺白衣丽人
  - branch-signal: 未回收伏笔: 黑牌暗藏神秘力量

### Review Candidate Clusters
- status=open (待观察) | priority=P3 | pattern=单点问题 | title=人物风险簇：character_resolution_support_gap | checkers=['character_ooc', 'plot_logic_consistency'] | types=['character_resolution_support_gap', 'resolution_support_gap'] | chapters=[4] | span=4 | chapter_count=1 | confidence=0.35
  - sample: 本章人物状态变化与解决性表述之间存在支撑缺口，建议人工复核。
  - action: 优先核对人物动机、关系与行为是否有前文支撑，避免只依据标题或摘要推断人物变化。
  - workflow_lane: monitor_queue
  - queue_priority: low
  - action_required: False
  - suggested_deadline_level: backlog
  - batch_operation_hint: batch_monitoring_watchlist
  - auto_next_action: 继续观察 人物风险簇：character_resolution_support_gap，等待更多证据后再决定是否升级。

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
- batch_suggestions: [{'hint_code': 'batch_monitoring_watchlist', 'hint_title': '可批量观察跟踪', 'action_bucket': 'monitor', 'batch_priority': 'low', 'group_strategy': 'by_checker', 'group_key': 'character_ooc', 'span_bucket': 'single', 'cluster_count': 1, 'cluster_keys': ['character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap'], 'suggested_cluster_order': ['character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap'], 'suggested_cluster_order_titles': ['人物风险簇：character_resolution_support_gap'], 'suggested_cluster_order_details': [{'cluster_key': 'character_ooc|plot_logic_consistency|::|character_resolution_support_gap|resolution_support_gap', 'cluster_title': '人物风险簇：character_resolution_support_gap', 'queue_priority': 'low', 'review_priority': 'P3', 'chapter_count': 1, 'confidence': 0.35, 'human_review_batch_rank_score': 0.0, 'human_review_batch_rank_reason': '', 'escalation_tier': '', 'escalation_urgency_score': 0.0, 'escalation_rank_reason': '', 'escalation_batch_rank_score': 0.0, 'escalation_batch_rank_reason': '', 'close_stability_score': 5.5, 'close_ready_rank_reason': 'close_ready=False | history_count=0 | chapter_count=1 | confidence=0.35 | close_stability_score=5.50', 'close_batch_rank_score': 0.0, 'close_batch_rank_reason': '', 'chapter_span_width': 0, 'batch_rank_score': 215.5, 'order_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50'}], 'ordering_strategy': 'queue_priority -> review_priority -> chapter_count -> confidence -> chapter_span_width -> first_chapter', 'suggested_first_cluster_reason': 'queue=low | priority=P3 | pattern=单点问题 | chapter_count=1 | confidence=0.35 | span_width=0 | batch_rank_score=215.50', 'cluster_titles': ['人物风险簇：character_resolution_support_gap'], 'owners': [], 'suggested_owner': '', 'primary_checker': 'character_ooc', 'pattern_label_top': '单点问题', 'risk_types': ['character_resolution_support_gap', 'resolution_support_gap'], 'phase2_focus_top': '', 'chapter_spans': ['4'], 'queue_priority_top': 'low', 'deadline_level_top': 'backlog', 'escalation_tier_top': '', 'action_required': False, 'resolved_candidate_count': 0, 'escalation_candidate_count': 0, 'recommended_batch_action': '继续观察 人物风险簇：character_resolution_support_gap，等待更多证据后再决定是否升级。', 'suggestion_rank_score': 75.0, 'suggestion_rank_reason': 'action_bucket=monitor | batch_priority=low | cluster_count=1 | action_required=False | suggestion_rank_score=75.00'}]
- auto_next_action_code_top: observe_and_wait
- auto_next_action_code_top_count: 1
- auto_next_action_top: 继续观察 人物风险簇：character_resolution_support_gap，等待更多证据后再决定是否升级。
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
- by_auto_next_action: {'继续观察 人物风险簇：character_resolution_support_gap，等待更多证据后再决定是否升级。': 1}
- by_escalation_reason_code: {}
- by_escalation_reason: {}
- by_phase2_focus: {}

## Windows
### Window 1-5
第1章：黑牌异动，神秘力量初显。 第2章：本章聚焦于小六子与青旒师妹的亲密对话，少年被少女魅力所惑，少女羞恼回应，结尾埋下黑牌异常伏笔。 第3章：布衣少年通过指桑骂槐的玩笑讽刺白衣丽人，青衫师妹茫然，白衣丽人一笑而过，本章以幽默对话展现角色性格与关系。 第4章：青衫少女指责布衣少年看其他女子，少年认错并赞美少女，提及她未来可入门仙师座下，少女转怒为喜，关系缓和但暗藏冲突。 第5章：布衣少年向褚青旒表达苦练精修、出人头地的决心，褚青旒则提醒他先过三道入门关；本章详细介绍了青华门每三个月一次的试炼，目测关通过率极低（十不存一），以及山中三十六座馆舍的布局。


## Graph Overview
- nodes: 64
- edges: 524
- node types: {'continuity': 26, 'entity': 8, 'event': 15, 'foreshadow': 3, 'world_rule': 9, 'relation': 2, 'conflict': 1}
- edge types: {'carries_forward': 316, 'constrains': 13, 'hints_at': 23, 'participates_in': 32, 'advances_to': 50, 'co_occurs': 5, 'follows': 13, 'persists_into': 28, 'relates_to': 7, 'conflict_centers_on': 8, 'conflict_involves': 3, 'contextualizes': 10, 'evolves_to': 1, 'pressured_by': 3, 'pays_off_as': 12}

Top Nodes:
- conflict:布衣少年用言语打压/讽刺白衣丽人 (seen 1)
- continuity:下一章应揭示黑牌振动的具体成因、主角后续反应，以及这枚黑牌与当前仙道世界的关联。 (seen 1)
- continuity:主角对黑牌的认知从普通玩物变为神秘器物，信息掌握状态发生显著变化。角色位置、关系、力量未变，但潜在威胁/机遇已然浮现。 (seen 1)
- continuity:主角对黑牌的认知状态发生显著变化——从普通玩物转变为神秘器物，属于『信息掌握状态』的升级。 (seen 1)
- continuity:伏笔‘布衣少年擅伪装和讲笑话的表演能力’在本章得到局部兑现（指桑骂槐讽刺白衣丽人），但该能力仍有进一步发展的空间。 (seen 1)
- continuity:伏笔‘黑牌暗藏神秘力量’在本章未涉及，仍保持开放状态，但本章结尾无直接钩子指向黑牌。 (seen 1)
- continuity:关系‘布衣少年与青衫少女是同门师兄妹’保持稳定，无变化。 (seen 1)
- continuity:冲突‘布衣少年用言语打压/讽刺白衣丽人’维持 latent 状态，未在本章升级或兑现。 (seen 1)
- continuity:前情中未回收的伏笔（黑牌暗藏神秘力量、青衫少女未来可能入门）在本章暂缓处理，未涉及。 (seen 1)
- continuity:前情摘要为空，无待回收伏笔或升级冲突，本章属于独立引入新线索的情节点。 (seen 1)

## State Summary
### 新增伏笔
- 黑牌暗藏神秘力量
### 已回收伏笔
- 布衣少年擅伪装和讲笑话的表演能力
- 青衫少女未来可能入门成为仙师座下弟子
### 新增冲突
- 布衣少年用言语打压/讽刺白衣丽人
### 关系变化
- 小六子和青旒是同门师兄妹
### 规则约束
- 黑牌材质非金非木且触感凉意
- 黑牌能响应外来召唤
- 存在仙道修炼和入门体系
- 青华门入门第一关为目测关，通过率极低
- 青华门入门需通过三道关
- 青华门有三十六座馆舍，掌院仙师分驻
- 青华门每三个月举行一次试炼

## Chapter Output Summary
### 推进摘要总览
- 第1章: 本章状态推进集中体现在：少年抛接黑牌、黑牌异常振动发热。
- 第1章: 本章末尾黑牌振动发热并伴随胸口炽热感，制造了强烈悬念（钩子），明确指向下一章应当揭示黑牌的来源、召唤力量或主角后续反应。
- 第1章: 主角对黑牌的认知从普通玩物变为神秘器物，信息掌握状态发生显著变化。角色位置、关系、力量未变，但潜在威胁/机遇已然浮现。
- 第2章: 本章状态推进集中体现在：青衫少女拂弄秀发引起少年凝视、少年夸赞少女动作像仙女、少女害羞并嗔怪少年油嘴滑舌。
- 第2章: 本章关系面出现可见变化：小六子和青旒是同门师兄妹。
- 第2章: 本章人物互动部分（少年少女同行）为独立日常片段，未直接推进主线，但通过对话丰满了角色关系（同门师兄妹）。
- 第2章: 本章结尾（来自图谱摘要）黑牌出现异常振动发热，制造了强烈的『继续阅读钩子』，悬念强度高，驱动读者探寻黑牌来源与召唤力量。
- 第3章: 本章状态推进集中体现在：布衣少年指桑骂槐讽刺白衣丽人、青衫少女因白衣丽人出现而失神、布衣少年一本正经解释蛤蟆精。
- 第3章: 本章关系面出现可见变化：布衣少年与青衫少女是同门师兄妹。
- 第3章: 本章冲突面继续推进：布衣少年用言语打压/讽刺白衣丽人。
- 第3章: 本章为日常片段，未直接推进黑牌主线（黑牌暗藏神秘力量等伏笔仍保持开放状态）。
- 第3章: 引入白衣丽人，其与布衣少年的互动为后续可能的关系或冲突埋下线索，但当前无明确钩子。
### 已解决线索总览
- 第4章: 关系线“小六子和青旒是同门师兄妹”已出现阶段性变化证据。
- 第5章: 前文伏笔“布衣少年擅伪装和讲笑话的表演能力”在当前分支中已有兑现信号。
- 第5章: 关系线“小六子和青旒是同门师兄妹”已出现阶段性变化证据。
### 未解线程总览
- 第1章: 新埋下的线程：黑牌暗藏神秘力量
- 第2章: 持续施加约束的规则：黑牌材质非金非木且触感凉意
- 第2章: 持续施加约束的规则：黑牌能响应外来召唤
- 第3章: 新埋下的线程：布衣少年擅伪装和讲笑话的表演能力
- 第3章: 持续施加约束的规则：黑牌材质非金非木且触感凉意
- 第3章: 持续施加约束的规则：黑牌能响应外来召唤
- 第4章: 新埋下的线程：青衫少女未来可能入门成为仙师座下弟子
- 第4章: 持续施加约束的规则：黑牌材质非金非木且触感凉意
- 第4章: 持续施加约束的规则：黑牌能响应外来召唤
- 第5章: 持续施加约束的规则：黑牌材质非金非木且触感凉意
- 第5章: 持续施加约束的规则：黑牌能响应外来召唤

## Reasoning Graph
### Central Nodes
- event:少女害羞并嗔怪少年油嘴滑舌 degree=36
- event:少年抛接黑牌 degree=34
- entity:布衣少年（小六子） degree=34
- event:布衣少年讨好青衫少女并提及修炼入门 degree=32
- relation:布衣少年与青衫少女是同门师兄妹 degree=31
- event:青衫少女因布衣少年的赞美而喜悦 degree=31
- event:布衣少年指桑骂槐讽刺白衣丽人 degree=30
- event:布衣少年一本正经解释蛤蟆精 degree=30

### Reasoning Paths
- 少年抛接黑牌 -[advances_to]-> 少年夸赞少女动作像仙女
- 少年抛接黑牌 -[advances_to]-> 少女害羞并嗔怪少年油嘴滑舌
- 少年抛接黑牌 -[advances_to]-> 青衫少女拂弄秀发引起少年凝视
- 黑牌异常振动发热 -[follows]-> 少年夸赞少女动作像仙女
- 黑牌异常振动发热 -[follows]-> 少女害羞并嗔怪少年油嘴滑舌
- 黑牌异常振动发热 -[follows]-> 青衫少女拂弄秀发引起少年凝视
- 少年夸赞少女动作像仙女 -[advances_to]-> 青衫少女因白衣丽人出现而失神
- 少年抛接黑牌 -[advances_to]-> 布衣少年指桑骂槐讽刺白衣丽人
- 青衫少女拂弄秀发引起少年凝视 -[advances_to]-> 布衣少年指桑骂槐讽刺白衣丽人
- 少年夸赞少女动作像仙女 -[advances_to]-> 布衣少年指桑骂槐讽刺白衣丽人
- 少女害羞并嗔怪少年油嘴滑舌 -[advances_to]-> 布衣少年指桑骂槐讽刺白衣丽人
- 少女害羞并嗔怪少年油嘴滑舌 -[advances_to]-> 布衣少年一本正经解释蛤蟆精

### Active Conflicts
- 布衣少年用言语打压/讽刺白衣丽人

### Open Foreshadowing
- 黑牌暗藏神秘力量

### World Rules
- 存在仙道口诀
- 黑牌材质非金非木且触感凉意
- 黑牌能响应外来召唤
- 存在五谷堂这一场所或组织
- 存在仙道修炼和入门体系
- 青华门入门第一关为目测关，通过率极低
- 青华门入门需通过三道关
- 青华门有三十六座馆舍，掌院仙师分驻
- 青华门每三个月举行一次试炼

### Foreshadow States
- 黑牌暗藏神秘力量 [open]
- 布衣少年擅伪装和讲笑话的表演能力 [paid_off]
- 青衫少女未来可能入门成为仙师座下弟子 [paid_off]

### Conflict States
- 布衣少年用言语打压/讽刺白衣丽人 [active]

### Relation States
- 小六子和青旒是同门师兄妹 [evolved]
- 布衣少年与青衫少女是同门师兄妹 [stable]

### World Rule States
- 存在仙道口诀 [observed]
- 黑牌材质非金非木且触感凉意 [constraining]
- 黑牌能响应外来召唤 [constraining]
- 存在五谷堂这一场所或组织 [observed]
- 存在仙道修炼和入门体系 [constraining]
- 青华门入门第一关为目测关，通过率极低 [constraining]
- 青华门入门需通过三道关 [constraining]
- 青华门有三十六座馆舍，掌院仙师分驻 [constraining]
- 青华门每三个月举行一次试炼 [constraining]
