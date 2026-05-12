# Reader Feedback / Rewrite Input Spec

本说明用于把**读者反馈**与**人工新思路**显式传递给后续仿写 / 改写流程。

目标：
- 不只看原章节与已有仿写稿
- 还要把新的读者反馈、商业判断、人工创作意图一起喂进去
- 让“下一轮仿写/改写”明确知道：**哪里不好、为什么要改、要往什么方向改**

---

## 1. 必须暴露的输入层

后续每轮改写，至少应显式输入这 4 层信息：

### A. source context（源上下文）
- 原始参考章节
- 当前分支已有 facts / graph / risk / thread
- 当前连续稿上下文（前后章）

### B. current draft（当前稿）
- 当前仿写章节正文
- 当前连续版位置
- 当前已知问题

### C. reader feedback（读者反馈）
- 哪些地方无聊 / 水 / 不爽
- 哪些角色不讨喜 / 不可信
- 哪些章节想继续看，哪些章节会弃书
- 哪些情节读者觉得拖、假、弱

### D. human steering（人工导向）
- 这一章这次到底想加强什么
- 商业方向要偏什么
- 要避免什么
- 新增的创作思路 / 卖点 / 节奏要求

---

## 2. 建议的反馈字段

## 2.1 基础定位
- `novel_version`: 当前稿版本，如 `novel-full-1-50`
- `chapter_range`: 反馈覆盖章节，如 `21-30`
- `target_chapter`: 本次重点改写章节，如 `24`
- `feedback_round`: 第几轮反馈

## 2.2 读者反馈
- `overall_impression`: 总体印象
- `drop_points`: 想弃书的位置
- `hook_feedback`: 钩子强弱反馈
- `pace_feedback`: 节奏反馈
- `emotion_feedback`: 情绪/代入感反馈
- `character_feedback`: 人设反馈
- `plot_feedback`: 剧情推进反馈
- `world_feedback`: 世界观/设定反馈
- `commercial_feedback`: 商业爽点反馈

## 2.3 人工导向
- `rewrite_goal`: 本轮改写目标
- `must_strengthen`: 必须增强的点
- `must_reduce`: 必须压掉的点
- `must_keep`: 必须保留的点
- `new_ideas`: 新增创作思路
- `benchmark_reference`: 想靠近的作品感受/节奏

## 2.4 输出要求
- `target_length`
- `target_hook_level`
- `target_tone`
- `target_reader_takeaway`

---

## 3. 推荐工作流

每次改写按这个顺序输入：

1. 当前章节 source context
2. 当前 draft
3. 读者反馈
4. 人工导向
5. 明确本轮只改哪几个核心问题

推荐原则：
- 一轮不要同时改太多维度
- 先改最影响弃书率的问题
- 先改 hook / pace / motivation，再改修辞

---

## 4. 最小可用输入模板

```yaml
novel_version: novel-full-1-50
target_chapter: 24
feedback_round: 1

overall_impression: >
  整体能读，但这一章名次出来后的爽点不够，
  情绪起伏偏平，读者会觉得“发生了事，但不够痛快”。

drop_points:
  - 名次揭晓前铺垫偏长
  - 回家/回旧场景的价值不够高

hook_feedback:
  - 章尾钩子中等
  - 还不足以强推下一章

pace_feedback:
  - 前半慢
  - 中段信息重复

character_feedback:
  - 主角克制是好的
  - 但压得太久，导致“不够想赢”

commercial_feedback:
  - 爽点不足
  - 打脸感不足
  - 读者期待更明确的上升确认

rewrite_goal: >
  把这一章改成“成绩揭晓 + 外界反应 + 主角压住情绪但读者更爽”的版本。

must_strengthen:
  - 名次揭晓瞬间冲击
  - 周围人的态度变化
  - 主角的内在野心
  - 章尾下一轮机会钩子

must_reduce:
  - 重复心理描写
  - 过多解释性文字

must_keep:
  - 克制型男主
  - 不直接写成无脑爽文
  - 保持现实压力

new_ideas:
  - 让旧主/旧熟人对主角态度出现明显反差
  - 章尾加入更高层级机会

target_length: 1800-2400字
target_hook_level: 强
target_tone: 克制但带压抑后反弹
target_reader_takeaway: >
  读者要明显感到主角真的往上走了一步，并愿意立刻看下一章。
```

---

## 5. 给人工评审者的最简填写项

如果不想写太复杂，至少传这几项：

- 哪一章
- 最大问题是什么
- 这章想改成什么感觉
- 哪三个点必须加强
- 哪两个点必须删弱
- 章尾要不要更强钩子

---

## 6. 推荐配套产物

建议后续固定同时维护：

1. `reader-feedback-log.md`
   - 逐轮记录真实读者反馈

2. `rewrite-briefs/`
   - 每章每轮一个 brief

3. `chapter-issues.md`
   - 当前 1~50 章的问题总表

4. `rewrite-checklist.md`
   - 每轮改完后核对是否真解决了反馈

---

## 7. 当前建议

对你当前这套 1~50 章稿，最适合先暴露给后续流程的输入是：

- 章节编号
- 当前正文
- 当前读者反馈
- 商业方向要求
- 想增强的爽点/情绪/钩子
- 不想要的风格偏移

也就是说，后面不该只说“帮我重写第24章”，而应该说：

> 帮我基于第24章当前稿 + 读者反馈 + 商业目标，重写成更强钩子版本。

