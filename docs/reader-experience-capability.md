# Reader Experience 能力规划

## 1. 定位

当前系统主线能力是 **统一风险审查体系**，主要服务：

- 作家
- 编辑
- 审稿者

但你提出的另一类能力更偏向 **读者阅读体验增强**，其目标不是“发现设定错误”，而是：

1. 识别阅读风险 / 踩雷点
2. 判断情绪压力与剧情体验
3. 帮助读者跳转查看关键章节
4. 给出更适合读者的阅读导航建议

这类能力建议独立命名为：

- `Reader Experience`
- `Reading Guide`
- `Reader Navigation`

而不要直接并入 `risk_audit_service`。

---

## 2. 为什么这不是当前 risk checker 的一部分

风险审查体系当前主要判断：

- 人物 OOC
- 规则一致性
- 剧情逻辑
- 时间线
- 战力能力漂移

这些属于：

> **作者/编辑侧的质量门控**

而你新提的能力属于：

> **读者侧的阅读体验判断**

两者可以共用底座，但不应混成一个 checker 体系。

---

## 3. Reader Experience 能力分层

## A. 内容预警 / 踩雷标签

### 目标

给读者提前提示可能的阅读风险。

### 候选能力

- 踩雷预警
- 虐主/高压苦情
- 长时间压抑
- 重大误会
- 背刺 / 刀子 / 情绪冲击段

### 建议输出

- `warning_tags`
- `warning_confidence`
- `related_chapters`
- `warning_summary`

### 更合适的系统名

- `reader_trigger_warning`
- `content_warning_tags`

---

## B. 情绪与节奏体验判断

### 目标

帮助识别：

- 是否长期高压
- 是否一直苦情
- 是否有释放点
- 剧情节奏是否单调 / 密集 / 崩掉

### 候选能力

- 高压苦情检测
- 情绪曲线
- 节奏起伏判断
- 高潮/回落/转折判断

### 建议输出

- `emotional_pressure_level`
- `pressure_ranges`
- `pacing_wave`
- `arc_peaks`
- `release_points`

### 更合适的系统名

- `emotional_pressure_curve`
- `pacing_wave_detector`
- `climax_locator`

---

## C. 长跨度质量判断

### 目标

针对卷末/大段结尾/全书结尾做长跨度体验评估。

### 候选能力

- 结尾崩坏
- 收束草率
- 伏笔收不回
- 终局节奏断崖

### 建议输出

- `ending_quality_review`
- `arc_resolution_consistency`
- `payoff_density`
- `closure_risk`

注意：

> 这类能力不适合只按单章执行，应该按卷末 / 章节区间 / 全书末执行。

---

## D. 阅读跳转推荐

### 目标

帮助读者更高效地看书，而不是只给风险提示。

### 候选能力

1. 角色高光跳转
2. 冲突升级跳转
3. 高潮章节跳转
4. 反转章节跳转
5. 关键设定补课跳转
6. 伏笔首次出现 / 回收跳转
7. 关键必读章节推荐

### 建议输出

- `recommended_chapters`
- `jump_reason`
- `reader_goal`
- `importance_level`

### 更合适的系统名

- `reader_navigation`
- `chapter_jump_recommender`
- `reading_guide`

---

## 4. 当前系统已经具备哪些底座可复用

Reader Experience 不必从零开始，因为当前系统已经有很多底座：

- `chapter_bundle`
- `branch_bundle`
- `retrieval`
- `reasoning_graph`
- `thematic_contexts`
- `timeline_points`
- `active_conflicts`
- `open_foreshadowing`
- `state_summary`
- `chapter_output_summary`

因此 Reader Experience 的合理路线不是“重新做一套系统”，而是：

> 基于现有拆书 + 图谱 + state 输出，再加一层 reader-facing evaluator / recommender。

---

## 5. 推荐架构拆分

## 线 1：Risk Audit

面向作者/编辑：

- OOC
- 规则
- 逻辑
- 时间线
- 战力能力

目标：

- 质量门控
- 风险复核
- 审稿辅助

## 线 2：Reader Experience

面向读者：

- 踩雷标签
- 高压苦情
- 高潮定位
- 角色/冲突跳转推荐
- 结尾体验判断

目标：

- 阅读体验增强
- 阅读导航
- 内容预警

---

## 6. 第一批最值得落地的 3 个模块

如果只做第一批，我建议优先：

### 1. 踩雷 / 内容预警标签

原因：

- 读者直接受益
- 输出形态简单
- 可以先做 advisory 标签，不需要太复杂的聚合器

### 2. 高潮 / 转折章节定位

原因：

- 非常适合跳转推荐
- 可以直接复用冲突、时间线、事件推进底座

### 3. 角色 / 冲突跳转推荐

原因：

- 和现有 `thematic_contexts` 最容易衔接
- 可快速形成“推荐查看这些章节”的实用能力

---

## 7. 建议不要第一批做的

### 不建议第一批就做

- 全书结尾崩坏自动判定
- 复杂主观审美判断
- “好不好看”的统一评分

原因：

- 主观性高
- 长跨度依赖强
- 解释难度高

---

## 8. 一句话路线图

> 先把 Risk Audit 做成系统级门控能力；  
> 再基于同一底座，扩展 Reader Experience，重点先做预警标签、高潮定位和跳转推荐。

---

## 9. 额外能力规划（只规划，不在当前环境实施）

以下能力当前仅作为**后续规划项**存在，目的是帮助未来产品化时把 Reader Experience 做完整。

### 9.1 阅读模式切换

#### 目标

针对不同读者需求，提供不同的阅读导引模式。

#### 规划能力

- `safe_read_mode`
  - 尽量规避踩雷内容
- `plot_focus_mode`
  - 优先推荐主线推进章
- `character_focus_mode`
  - 优先推荐某角色高光/转折章
- `fast_catchup_mode`
  - 只看关键必读章与摘要

#### 输出形态

- `reading_mode`
- `mode_recommended_chapters`
- `mode_summary`

> 当前不实施，只保留产品规划。

---

### 9.2 内容强度与情绪阈值标记

#### 目标

帮助读者判断：

- 情绪压力是否过高
- 某段是否连续压抑
- 是否值得中途跳过或缓读

#### 规划能力

- `pressure_intensity_band`
- `suffering_density`
- `release_gap_warning`

#### 输出形态

- `pressure_score`
- `pressure_ranges`
- `release_gap_ranges`

> 当前不实施，只保留产品规划。

---

### 9.3 结尾体验评估

#### 目标

面向读者判断：

- 是否烂尾
- 是否草率收束
- 是否有断崖掉线感

#### 规划能力

- `ending_experience_review`
- `closure_satisfaction_estimate`
- `final_arc_drop_warning`

#### 输出形态

- `ending_quality_band`
- `closure_risk`
- `ending_issue_summary`

> 当前不实施，只保留产品规划。

---

### 9.4 阅读跳转清单生成器

#### 目标

不仅给出单个推荐章节，而是给出面向读者目标的“章节跳转清单”。

#### 规划能力

- `jump_list_for_character_arc`
- `jump_list_for_conflict_arc`
- `jump_list_for_world_rule_arc`
- `jump_list_for_climax_only`

#### 输出形态

- `jump_list`
- `jump_goal`
- `jump_reason`
- `must_read` / `optional`

> 当前不实施，只保留产品规划。

---

### 9.5 读者标签画像

#### 目标

针对不同偏好读者，生成更适合的导读。

#### 规划能力

- `reader_profile_matching`
- `taste_alignment_hint`
- `avoidance_profile`

#### 输出形态

- `reader_profile_tags`
- `recommended_reading_path`
- `avoid_tags`

> 当前不实施，只保留产品规划。

---

## 10. 当前明确不在本环境实施的内容

下面这些内容，当前只记入规划，不在本轮环境内实现：

1. Reader Experience 新 runtime service
2. 新 reader-facing checker / evaluator
3. 新数据库表
4. 新 API 输出字段
5. 新 UI 展示入口
6. 真正的读者画像建模
7. 长跨度结尾体验自动判定器

---

## 11. 当前建议的产品推进顺序

如果未来真的要做 Reader Experience，建议顺序：

1. 踩雷/内容预警标签
2. 高潮/转折章节定位
3. 角色/冲突跳转推荐
4. 阅读模式切换
5. 结尾体验评估
6. 读者画像与偏好导读

---

## 12. 规划边界一句话总结

> 这些能力当前先进入文档规划层，不进入本环境实施层；  
> 当前环境继续把重点放在 Risk Audit 的系统级门控能力上。
