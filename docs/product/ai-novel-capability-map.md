# AI 小说完整能力地图 / Capability Map

> 版本：2026-05-05
> 目标：明确当前系统已经覆盖哪些 AI 小说能力、哪些还缺、哪些值得快速补、哪些暂时不要做重。

## 1. 四大能力域
### A. 创作前能力
- 世界观 / 规则体系设计
- 角色设计
- 卷纲 / 大纲 / 长线规划
- 伏笔 / 支线 / 节奏布局

### B. 创作中能力
- 续写准备
- 仿写准备
- 场景级写作控制
- 文风 / 节奏 / 对话控制
- 章尾钩子与追读控制
- assistant 控制面（planning / revision / feedback）

### C. 创作后能力
- 风险门控
- 连续性审查
- 读者反馈分析
- 改稿 / 编辑辅助
- retrieval benchmark / route benchmark

### D. 治理与平台能力
- 样例 / smoke / freeze gate
- 交接 / handoff
- 成本与模型策略
- 平台/API/独立 agent 能力包

## 2. 当前已覆盖较强的
### 2.1 拆书 / 信息抽取 / 检索
- chapter analysis
- facts
- retrieval
- graph / state / window
- branch report / QA context

### 2.2 风险门控
- risk checker
- semantic signals
- review workflow
- cluster / branch-level audit conclusion

### 2.3 受控仿写
- chapter imitation
- harness
- whole-book orchestration
- repair lanes
- long-book consistency diagnostics

### 2.4 平台治理
- sample artifacts
- freeze gate
- smoke path
- migration / self-check
- unified novel assistant pack

## 3. 还明显缺的
### 3.1 原创前期规划仍待深化
- 已有 original planning pack
- 仍缺角色卡 / 动机树 / 成长弧线的更细颗粒度输出
- 仍缺卷纲 / 长线规划器

### 3.2 创作过程控制已起步但仍不足
- 已有 creation control pack（scene controls / ending hook / risk notes / style axes）
- 仍缺爽点 / 钩子 / 节奏 KPI
- 仍缺平台风格适配

### 3.3 编辑改稿能力已起步但仍不足
- 已有 editor revision pack
- 仍缺真实 draft 对照下的风格偏移检测
- 仍缺自动 revision 回写链

### 3.4 读者反馈能力已起步但仍不足
- 已有 reader feedback pack
- 仍缺真实评论痛点提取
- 仍缺反馈驱动的修文建议自动回流

## 4. 最值得快速补的
### P1（短期高价值）
1. retrieval benchmark 样例化
2. author knowledge 的人物/规则/关系/线程摘要
3. assistant pack 的 continuation / imitation control surface
4. whole-book success density 继续补样例

### P2（中期扩展）
1. story control / scene card
2. next-chapter 与 imitation 更深绑定 author knowledge
3. 风险语义长窗口评估
4. 编辑改稿工作流

### P3（更远期）
1. 多作者协作
2. 平台风格适配
3. 读者反馈驱动改写
4. IP 改编前置分析

## 5. 暂时不要过重投入的
- 复杂前端花活优先级不应高于中台能力
- 全黑盒化 risk judgement
- 只追求“多写一点”的生成器能力
- 过早做大而全的 agentOS 绑定

## 6. 一句话结论
当前系统已经强覆盖了“理解、门控、仿写、治理”这半边；
下一步最重要的是把“续写控制、创作前规划、编辑改稿、读者反馈”这半边补起来，才会更接近真正完整的 AI 小说商业助手。
