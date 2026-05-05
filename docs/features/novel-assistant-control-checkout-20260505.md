# Novel Assistant Control Checkout — 2026-05-05

## 1. 本轮范围
- assistant composition layer 再升级
- author knowledge 的 story bible pack
- story bible 第二层：character_cards / motivation_tree / growth_arc
- story bible 第三层：volume_outline / arc_outline
- retrieval benchmark 系统化
- 原创前期规划 / 创作过程控制 / 编辑改稿 / 读者反馈闭环 四个控制包落地
- 目标：让小说助手从“检索+仿写准备”推进到“可商业化创作控制面”

## 2. 当前已完成
- `AuthorKnowledgeService` 新增：
  - `story_bible_pack`
- `NovelAssistantService` 新增：
  - `retrieval_benchmark_summary`
  - `original_planning_pack`
  - `creation_control_pack`
  - `editor_revision_pack`
  - `reader_feedback_pack`
- assistant pack 已把 continuation / imitation / review / risk / author knowledge 串成一个更完整的作者工作流。
- 真实 sample branch 已重新导出新版 assistant artifact。
- 真实 sample branch 已补一份可复用 retrieval benchmark artifact。

## 3. 预期效果
1. **原创前期规划**：不再只有拆书结果，而是能直接给角色/规则/线程的规划入口。
2. **创作过程控制**：续写时直接给 scene controls、ending hook、risk notes、style axes。
3. **编辑改稿**：生成后不再只看 risk summary，而是有明确 revision lanes 和 done definition。
4. **读者反馈闭环**：把“读者可能卡在哪里、该收集什么反馈、反馈如何回流改稿”变成结构化输出。
5. **retrieval benchmark**：可直接比较 query set、route contribution、latency、rerank 是否真的改变排序。

## 4. 解决的问题
- 之前 assistant pack 更像“统一摘要层”，还不够像真正作者/编辑会用的控制面。
- 现在 assistant pack 已经开始承担：
  - 写前规划
  - 写中控制
  - 写后改稿
  - 反馈回流
  - 检索 benchmark

## 5. Fresh evidence
- author knowledge sample 已包含 `story_bible_pack`，assistant sample 已包含其嵌套版本。
- 最新样例已进一步包含 `character_cards`、`motivation_tree`、`growth_arc`。
- 最新样例已包含 `volume_outline` 与 `arc_outline`。
### 5.1 回归
- `./.venv/bin/pytest -q tests/test_novel_assistant_service.py tests/test_cli_extra.py::test_novel_assistant_cli tests/test_cli_extra.py::test_export_retrieval_benchmark_cli`
- 结果：`3 passed`

### 5.2 真实样例
- `docs/examples/sample-branch-novel-assistant-20260505.sample.json`
- `docs/examples/sample-branch-retrieval-benchmark-20260505.sample.json`

### 5.3 真实 branch benchmark 观察
- query set：`卫图 命格` / `二姑 资源` / `婚事 养生功`
- route contribution：当前主要来自 `fts + similarity + like + keyword`
- rerank：本次样例中 `rerank_applied=false`，说明 benchmark 已把“是否真正启用 rerank”显式暴露出来
- top result 稳定：3 个 query 的 raw / reranked top chapters 一致，当前更像“多路召回质量确认”，还不是“rerank 已显著改序”阶段

## 6. 当前测试 / 评估是否符合预期
- **符合预期**：assistant pack 的控制面已经明显更完整，可直接给作者/编辑/运营消费。
- **部分未闭环**：real benchmark 中 rerank 仍未产生排序差异；这说明 rerank 接入点存在，但“效果证明”还需要继续做真库/真模型样例。

## 7. 还需要闭环与优化
1. 把 benchmark 再扩成固定 query bank + route delta 对照。
2. 把 editor revision pack 接到 draft / harness / revise 实际链路。
3. 把 reader feedback pack 接到真实评论样本而不是当前启发式摘要。
4. 把 original planning pack 继续前推到卷纲 / 人物成长弧 / story bible 层。

## 8. 新的主链接入
- next chapter planner 已开始消费 `volume_outline / arc_outline`。
- 这意味着 long-horizon planning 不再只是 knowledge surface，而是已经进入续写主链。
- 真实样例中，`continuation_pack.chapter_goal` 已从通用目标收敛为：`完成赎身/脱籍并争取进入更高身份路径`。

## 9. 未来章节骨架
- story bible 现已提供 `future_chapter_outline`。
- 真实样例中已给出未来 3 章的 goal / core_conflict / payoff_target / turning_point。
- 这让长线规划开始具备“可执行 outline”形态，而不只是抽象结构。

## 10. Scene-level 主链接入
- next chapter planner 的 `scene_plan` 已开始消费 `future_chapter_outline`。
- 真实 assistant 样例中，scene2 / scene3 的 must_include 与 foreshadow_to_touch 已出现 future outline 派生信号。
- 这意味着未来章节骨架不再只是交接文档，而是进入了单章续写编排。

## 11. Direct draft preparation
- assistant pack 现已提供 `chapter_draft_preparation_pack`。
- 真实样例中已给出 `draft_goal / draft_conflict / draft_payoff / draft_turning_point`。
- 这让“长线规划 -> 单章规划 -> 起草前准备”形成了直接闭环。
