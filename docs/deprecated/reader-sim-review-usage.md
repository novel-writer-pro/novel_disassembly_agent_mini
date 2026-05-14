# Reader Sim Review Usage / 模拟读者阅读使用说明

本说明回答一个实际问题：

> 我们现在有没有“模拟读者阅读章节”的能力？如果有，怎么用？

答案：

- **有**
- 但当前主要以 **skill + harness lane + feedback summary** 的形式存在
- 还不是一个超级独立、产品化、多 persona 面板式的入口

---

## 1. 当前已经有的能力

### A. `reader-sim-review` skill

位置：
- `skills_dir/reader-sim-review/SKILL.md`
- `skills_dir/reader-sim-review/prompts/main.md`

作用：
- 从**核心网文读者视角**看一章 draft
- 判断是否：
  - 清楚
  - 有期待感
  - 容易卡住
  - 动机不清
  - 关系难跟
  - 节奏平
  - 钩子弱
  - 信息负担高

输出：
- `reader_profile`
- `engagement_score`
- `concerns`
- `recommended_actions`

---

### B. imitation harness 中已接入 `reader_sim_review`

位置：
- `novel_analyzer/services/imitation_harness_service.py`

当前行为：
- `run_harness(...)` 时会构造 `reader-sim-review` 输入
- 会在 preflight 阶段生成：
  - `reader_sim_review` pass / warn
  - 读者体验问题
  - 推荐修复动作
- 会影响：
  - action queue
  - repair priority
  - 最终 verdict

也就是说，当前系统已经能在仿写/改写时自动回答：

- 读者会不会无聊
- 读者会不会困惑
- 章尾够不够让人想追

---

### C. 真实读者反馈导入与汇总

CLI 已有：
- `import_reader_feedback`
- `export_reader_feedback_summary`

位置：
- `novel_analyzer/cli/app.py`

作用：
- 导入真实评论 / 模拟评论
- 汇总为结构化 `reader_feedback_summary`
- 供后续 assistant / rewrite / governance 使用

---

## 2. 当前更接近什么形态

当前不是：

- 多 persona reader panel 成熟产品
- 不同读者画像并行打分系统
- 完整前台交互式“试读实验台”

当前更接近：

1. **核心网文读者模拟器**
2. **接入仿写 harness 的 reader-sim repair lane**
3. **真实读者反馈闭环**

---

## 3. 当前最实用的两种用法

## 用法 A：在仿写/改写时自动带上读者模拟

适合场景：
- 你已经有一章 draft
- 想知道读者会不会卡住
- 想让系统给出“从读者体验角度怎么修”

推荐入口：
- `harness_imitation`
- `writer-imitate-review`
- `writer-imitate-range`

本质上：
- 这些流程里已经会消费 `reader-sim-review`
- 你不用额外手工拼一套 reader sim 流程

---

## 用法 B：导入真实读者反馈，再回流改稿

适合场景：
- 你已经有 1~50 章连续稿
- 让人试读后收到了意见
- 想把这些意见结构化后喂回下一轮重写

推荐入口：
- `import_reader_feedback`
- `export_reader_feedback_summary`

再配合：
- `docs/reader-feedback-template.md`
- `docs/rewrite-brief-template.md`
- `docs/reader-feedback-rewrite-input-spec.md`

---

## 4. 当前能力边界

### 已有
- 单章读者模拟：**有**
- 仿写 harness 中 reader-sim lane：**有**
- 真实 reader feedback 导入/汇总：**有**

### 还不完整
- 小白读者 / 老书虫 / 爽文读者 / 编辑视角并行模拟：**未完全产品化**
- 批量对整本章节直接跑 reader sim CLI：**还没有独立成熟入口**
- 可视化 reader panel：**暂无**

---

## 5. 现在最推荐的工作流

### 对章节 draft 做模拟读者评审
1. 产出章节 draft
2. 走 `harness_imitation` / `writer-imitate-review`
3. 读取其中的：
   - `reader_sim_review`
   - `engagement_score`
   - `concerns`
   - `recommended_actions`

### 对整本稿做真实读者闭环
1. 读 `novel.txt`
2. 用 `reader-feedback-template.md` 收集反馈
3. 导入 reader feedback
4. 导出 `reader_feedback_summary`
5. 再写 `rewrite brief`
6. 基于 feedback 重写目标章节

---

## 6. 当前一句话判断

如果你的问题是：

> 我们有没有“模拟读者阅读我们的章节，看读者状态”的能力？

那么当前最准确的回答是：

> **有，而且已经接进仿写主流程；但它现在更像“核心网文读者模拟 lane”，不是完整的多画像读者实验台。**

---

## 7. 后续最值得补的增强

如果后面要继续做，最值钱的升级方向是：

1. 多 persona reader sim
   - 小白读者
   - 老书虫
   - 男频爽点读者
   - 严苛编辑视角

2. 单章 / 批量章节 reader sim CLI

3. 把 `reader_feedback_summary` 更直接接进 rewrite control

4. 给 1~50 章连续稿做批量“续读风险热区”标注

