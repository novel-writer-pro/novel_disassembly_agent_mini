# Novel Assistant 全能力人工测试与评估手册（2026-05-05）

这份手册面向 **手动测试 / 新小说导入 / 商业化能力验收**。
目标不是只证明“能跑”，而是回答下面 6 个问题：

1. 新小说导入后，拆书 / 检索 / 风险 / 仿写 / 治理链路是否能完整打通。
2. 每个能力的效果到底怎么样，是否足够接近可商业化使用。
3. 如果效果一般，**薄弱点具体在哪一层**（切章、抽取、召回、rerank、风险 linking、风格控制、长书一致性等）。
4. 哪些问题可以人工直接看出来，哪些需要借助导出 artifact。
5. 当前版本是否适合继续扩大样例库、做客户演示、做编辑/作者试用。
6. 每轮测试后，如何沉淀成可复跑、可对比、可交接的证据。

---

## 0. 本手册覆盖的能力面

### 0.1 核心能力线
- 拆书 / chapter analysis
- facts / graph / state / story bible
- retrieval / search / QA / rerank benchmark
- risk semantic / cluster review / manual override
- continuation / imitation / whole-book orchestration
- reader feedback ingestion / feedback revision bridge
- governance / release gate / archive / handoff

### 0.2 推荐搭配阅读
- `docs/cli-operations-manual.md`
- `docs/direct-usage-guide.md`
- `docs/real-run-checklist.md`
- `docs/features/novel-assistant-control-checkout-20260505.md`
- `docs/architecture/novel-assistant-system-architecture.md`
- `docs/examples/sample-branch-novel-assistant-20260505.sample.json`

---

## 1. 测试前准备

## 1.1 环境
当前运行建议仍以 PostgreSQL 为主。

```bash
poetry install
poetry run novel-analyzer init-db
poetry run novel-analyzer db-health
poetry run novel-analyzer db-capabilities
poetry run novel-analyzer test-embedding
```

## 1.2 LLM 配置
如果本轮要验证真实生成/whole-book，请先配置 LLM 环境变量。

示例（不要把真实密钥直接写进仓库文档或脚本）：

```bash
export NOVEL_ANALYZER_LLM_PROVIDER_NAME=deepseek
export NOVEL_ANALYZER_LLM_BASE_URL=https://api.deepseek.com/v1
export NOVEL_ANALYZER_LLM_API_KEY='YOUR_KEY'
export NOVEL_ANALYZER_LLM_MODEL_NAME=deepseek-v4-flash
export NOVEL_ANALYZER_LLM_STAGE_MODEL_NAME=deepseek-v4-flash
export NOVEL_ANALYZER_LLM_QA_MODEL_NAME=deepseek-v4-flash
export NOVEL_ANALYZER_LLM_FALLBACK_MODEL_NAME=deepseek-v4-flash
```

## 1.3 建议测试目录结构
每导入一本新小说，建议单独建一个目录，保存本轮所有人工检查证据。

```bash
mkdir -p runs/manual_eval/<novel_slug>/{artifacts,notes,exports}
```

也可以直接使用一键脚本：

```bash
python3 scripts/bootstrap_manual_eval_workspace.py <novel_slug>
```

建议至少保留：
- `branch-report.md`
- `novel-assistant.json`
- `retrieval-benchmark.json`
- `search-diagnostics-*.json`
- `reader-feedback-summary.json`
- `whole-book-readiness.json`
- `whole-book-run.json`
- `governance-dashboard.json`
- `final-release-archive.json`
- `manual-review-notes.md`

---

## 2. 一次完整的人工测试主流程

## 2.1 导入新小说
```bash
poetry run novel-analyzer ingest /path/to/novel.txt --title '新小说标题'
poetry run novel-analyzer start-run <novel_id> <manifest_id>
```

记录：
- `novel_id`
- `manifest_id`
- `run_id`
- `branch_id`

## 2.2 首轮只跑前 3 章
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 1 3
poetry run novel-analyzer show-run-status <run_id> <branch_id>
poetry run novel-analyzer show-branch <branch_id>
```

先不要一口气长跑。首轮目的是确认：
- 切章是否合理
- summary / facts / graph 是否贴文本
- retrieval 是否能召回关键章节
- 风险层是否没有明显误报/漏报

## 2.3 稳定后推进到 10 章左右
```bash
poetry run novel-analyzer analyze-range <run_id> <branch_id> 4 10
poetry run novel-analyzer validate-branch <branch_id>
poetry run novel-analyzer repair-branch <branch_id>
```

10 章左右通常已经足以验证：
- 主线与副线是否成形
- entity / relation / rule / thread 是否有连续沉淀
- retrieval / QA 是否开始具备实用价值
- imitation / continuation 的准备信息是否可信

## 2.4 导出总包
```bash
poetry run novel-analyzer export-branch-report <run_id> <branch_id> runs/manual_eval/<novel_slug>/exports/branch-report.md
poetry run novel-analyzer export-branch-package <run_id> <branch_id> runs/manual_eval/<novel_slug>/exports/branch-package
poetry run novel-analyzer export-novel-assistant <branch_id> runs/manual_eval/<novel_slug>/artifacts/novel-assistant.json
```

---

## 3. 拆书 / 信息抽取人工检查手册

## 3.1 要跑哪些命令
```bash
poetry run novel-analyzer show-chapter <branch_id> 1
poetry run novel-analyzer show-context <branch_id> 1
poetry run novel-analyzer show-raw-output <branch_id> 1
poetry run novel-analyzer show-facts <branch_id> --chapter-index 1
poetry run novel-analyzer summarize-graph <branch_id>
poetry run novel-analyzer show-window <branch_id> 1 5
```

## 3.2 人工重点看什么
### A. 切章
- 章节边界是否正确
- 目录/番外/作者话是否被误当正文
- 长章节是否被切坏

### B. Summary
- 是否贴文本
- 是否抓到真正推进点，而不是只复述开头
- 是否把暗示误写成确定事实

### C. Facts / Graph / State
- 主角、配角、势力、规则是否能持续出现
- 是否有明显漏抓（重要角色/设定没沉淀）
- 是否有明显乱抓（无关句子被当核心事实）

## 3.3 判定标准
### 通过
- 至少 80% 章节 summary 贴文本
- 没有严重伪造剧情
- facts 能覆盖主角 / 主线冲突 / 核心规则

### 不通过
- 大量伪造剧情
- 把未发生事件写成已发生
- 图谱完全无法反映主线推进

## 3.4 常见薄弱点与定位
| 症状 | 优先检查 | 常见原因 |
|---|---|---|
| 章节内容明显串章 | `show-chapter` + 原文 | ingest/split 边界不稳 |
| summary 很空或很飘 | `show-raw-output` | LLM 输出偏空、context 不足 |
| 人物/规则漏掉很多 | `show-facts` | fact extractor 粒度不足 |
| 图谱看不出主线 | `summarize-graph` | entity/relation/event 沉淀不连续 |

---

## 4. Retrieval / Search / QA / Rerank 人工检查手册

## 4.1 最低必跑命令
```bash
poetry run novel-analyzer search-branch <branch_id> '主角 金手指'
poetry run novel-analyzer search-branch-diagnostics <branch_id> '主角 金手指'
poetry run novel-analyzer export-search-branch-diagnostics <branch_id> '主角 金手指' runs/manual_eval/<novel_slug>/artifacts/search-diagnostics-main.json
poetry run novel-analyzer export-retrieval-benchmark <branch_id> runs/manual_eval/<novel_slug>/artifacts/retrieval-benchmark.json --query '主角 金手指' --query '反派 初次出场' --query '世界规则 代价'
poetry run novel-analyzer ask-branch <branch_id> '主角前十章的核心矛盾是什么？'
```

## 4.2 人工要检查的 4 个维度
### A. 召回是否找对章
看：
- `top_raw_chapters`
- `top_reranked_chapters`
- `route_counts`

人工问题：
- 关键问题能否打到真正相关章节
- 返回的前 3 章是否“明显是对的”

### B. 多路召回是否真的有贡献
重点看：
- `fusion_applied`
- `route_counts`
- `route_diagnostics`

人工判定：
- 不应长期只有单一路由工作
- `entity_exact` / `vector` / `fts/similarity` 最好能各自覆盖一部分 query

### C. rerank 是否真的改序
重点看：
- `rerank_applied`
- `top_raw_chapters` vs `top_reranked_chapters`

人工判定：
- rerank 不是必须每次都改序
- 但对复杂 query，至少应在部分 case 中把更相关章节提到前面

### D. 延迟是否可接受
重点看：
- `raw_latency_ms`
- `rerank_latency_ms`
- benchmark 中 `avg_raw_latency_ms` / `avg_rerank_latency_ms`

## 4.3 Retrieval 人工评分建议
| 项目 | 0 | 1 | 2 |
|---|---|---|---|
| Top1 是否正确 | 明显错误 | 勉强相关 | 明显正确 |
| Top3 是否覆盖主要证据 | 基本没有 | 覆盖一部分 | 覆盖充分 |
| route diversity | 单一路由 | 偶尔双路 | 多路稳定参与 |
| rerank 价值 | 无变化且无收益 | 偶有收益 | 能明显提升排序 |
| latency 可接受度 | 很慢 | 可接受 | 快且稳定 |

## 4.4 Retrieval 薄弱点溯源表
| 现象 | 看哪里 | 说明 |
|---|---|---|
| 明明相关却搜不到 | `route_counts=0` / raw hits | recall 层问题 |
| 能搜到但排太后 | raw vs reranked | rerank / score 融合问题 |
| QA 回答不稳 | `ask-branch` + `branch_qa_context` | retrieval context 质量不足 |
| 某类 query 总失败 | benchmark queries | query bank 设计不足或 lane 不匹配 |

---

## 5. Author Knowledge / Story Bible / 创作准备人工检查手册

## 5.1 最低必跑命令
```bash
poetry run novel-analyzer show-author-knowledge <branch_id>
poetry run novel-analyzer export-author-knowledge <branch_id> runs/manual_eval/<novel_slug>/artifacts/author-knowledge.json
poetry run novel-analyzer show-novel-assistant <branch_id>
```

## 5.2 人工重点看哪些字段
建议重点看：
- `story_bible_pack`
- `entity_profiles`
- `relationship_index`
- `rule_index`
- `thread_index`
- `unresolved_threads`
- `recommended_questions`

## 5.3 判断是否“对作者真有用”
### 好的表现
- 能快速回答“这本书到底在讲什么”
- 能看到角色、关系、规则、线程的结构化组织
- 能直接为下一章/续写/仿写提供准备信息

### 不好的表现
- 只是把 summary 换个名字重复一遍
- 结构很多，但没有实际决策帮助
- unresolved threads 不能反映真正未闭环的线

---

## 6. 风险检测 / Risk Semantic 人工检查手册

## 6.1 最低必跑命令
```bash
poetry run novel-analyzer export-novel-assistant <branch_id> runs/manual_eval/<novel_slug>/artifacts/novel-assistant.json
poetry run novel-analyzer show-cluster-status <branch_id>
poetry run novel-analyzer show-cluster-history <branch_id> <cluster_key>
```

必要时可做人审覆写：
```bash
poetry run novel-analyzer set-cluster-status <branch_id> <cluster_key> reviewed --review-notes '人工确认：误报，可接受' --review-owner 'tester'
```

## 6.2 人工重点看什么
### A. risk_summary
重点看：
- `high_risk_chapters`
- `review_candidate_clusters`
- `risk_counts_by_domain`
- `risk_counts_by_severity`

### B. 逐个簇人工判断
每个 cluster 建议判断：
- 真问题 / 假问题 / 信息不足
- 是否影响商业化演示
- 是否需要在下一轮生成前先修掉

## 6.3 风险人审标准
### 应判为真风险
- 明显逻辑断裂
- 世界规则自相矛盾
- 角色行为严重 OOC
- 续写设定会直接破坏前文 contract

### 可以接受但要记录
- 语义边界模糊
- 当前只是疑似风险
- 需要更多章节才能确认

## 6.4 风险薄弱点溯源
| 现象 | 优先看 | 常见原因 |
|---|---|---|
| 风险太多，噪音大 | `review_candidate_clusters` | canonicalization / linking 过宽 |
| 明显问题没被抓住 | `high_risk_chapters` 为空 | entity/rule/relation/thread linking 不足 |
| 风险描述太空泛 | cluster detail / branch report | checker contract 太弱 |
| 人工很难复核 | cluster history/status | 缺少可追溯证据 |

---

## 7. 续写 / 仿写 / Whole-book 人工检查手册

## 7.1 先看 readiness
```bash
poetry run novel-analyzer show-whole-book-imitation-readiness --branch-id <branch_id>
```

重点看：
- `ready_for_whole_book`
- `chapter_analysis_count`
- `provider_last_status`
- `api_key_present`（若 payload 有体现）

## 7.2 看 assistant pack 的创作控制面
```bash
poetry run novel-analyzer export-novel-assistant <branch_id> runs/manual_eval/<novel_slug>/artifacts/novel-assistant.json
```

重点人工检查：
- `continuation_pack`
- `imitation_pack`
- `chapter_draft_preparation_pack`
- `direct_draft_skeleton_pack`
- `direct_revision_loop_pack`
- `automatic_rewrite_guidance_pack`
- `automatic_prose_rewrite_pack`
- `whole_book_consistency_backflow_pack`

## 7.3 计划 whole-book 仿写
```bash
poetry run novel-analyzer plan-whole-book-imitation <branch_id> '项目名' '源作品' '目标作品' '1:建立开篇钩子' '2:放大核心矛盾' --character-map '张三->李四' --rule-override '金手指代价必须前置'
```

## 7.4 先 dry-run，再 sandbox execute
```bash
poetry run novel-analyzer export-whole-book-imitation-run <branch_id> '项目名' '源作品' '目标作品' runs/manual_eval/<novel_slug>/artifacts/whole-book-run.json '1:建立开篇钩子' '2:放大核心矛盾'

poetry run novel-analyzer export-whole-book-imitation-run <branch_id> '项目名' '源作品' '目标作品' runs/manual_eval/<novel_slug>/artifacts/whole-book-run-executed.json '1:建立开篇钩子' '2:放大核心矛盾' --execute --max-rounds 1 --use-llm
```

## 7.5 人工重点看什么
### A. continuation / imitation 是否可执行
- scene plan 是否具体
- 角色推进 / 关系推进 / 规则约束是否清楚
- risk notes 是否能提前提醒踩坑点

### B. 风格与节奏控制是否像“系统能力”
- 是否明确 style / rhythm / dialogue / reader-sim repair lanes
- 是否不是只给一句“请模仿某某风格”

### C. long-book consistency 是否有闭环
看：
- `whole_book_consistency_backflow_pack.requires_consistency_pass`
- `top_repair_recommendations`
- `candidate_backflow_actions`
- `release_impact`

## 7.6 仿写能力薄弱点溯源
| 现象 | 优先看 | 常见原因 |
|---|---|---|
| 能写但不稳 | `direct_draft_skeleton_pack` | 准备信息不够具体 |
| 文风像但剧情跑偏 | `imitation_pack` + rule constraints | style 强、story control 弱 |
| 人设崩 | `entity_profiles` + feedback bridge | 角色卡/动机约束不足 |
| 长篇后段漂移 | `whole_book_consistency_backflow_pack` | consistency pass 不够强 |

---

## 8. Reader Feedback 闭环人工检查手册

## 8.1 先准备评论 JSON
导入格式建议：

```json
[
  {
    "chapter_index": 8,
    "comment_text": "这段节奏有点慢，但是章尾钩子还不错",
    "source": "manual",
    "sentiment": "mixed"
  },
  {
    "chapter_index": 9,
    "comment_text": "主角这里的反应有点不像之前的人设",
    "source": "manual"
  }
]
```

## 8.2 导入与导出
```bash
poetry run novel-analyzer import-reader-feedback <branch_id> ./comments.json
poetry run novel-analyzer export-reader-feedback-summary <branch_id> runs/manual_eval/<novel_slug>/artifacts/reader-feedback-summary.json
```

## 8.3 人工要看什么
- `signal_counts`
- `pain_point_hypotheses`
- `revision_recommendations`
- `sample_comments`

## 8.4 判断标准
### 好的表现
- 能把评论归纳成可执行修文建议
- 能识别节奏慢 / 逻辑疑惑 / 人设偏移 / 追读欲这类高价值信号

### 不好的表现
- 只是做情绪分类，无法进入修文动作
- 所有评论都落成 `general_feedback`

---

## 9. Governance / Release / Archive 人工检查手册

## 9.1 最低必跑命令
```bash
poetry run novel-analyzer export-governance-dashboard <branch_id> runs/manual_eval/<novel_slug>/artifacts/governance-dashboard.json
poetry run novel-analyzer export-governance-report-brief <branch_id> runs/manual_eval/<novel_slug>/exports/governance-report-brief.md
poetry run novel-analyzer export-release-review-note <branch_id> runs/manual_eval/<novel_slug>/exports/release-review-note.md
poetry run novel-analyzer export-approval-decision-memo <branch_id> runs/manual_eval/<novel_slug>/exports/approval-decision-memo.md
poetry run novel-analyzer export-external-report-bundle <branch_id> runs/manual_eval/<novel_slug>/artifacts/external-report-bundle.json
poetry run novel-analyzer export-final-release-archive <branch_id> runs/manual_eval/<novel_slug>/artifacts/final-release-archive.json
```

## 9.2 人工重点看什么
### A. release gate 是否说得清楚
- 到底能不能发布
- 卡在哪一层
- 是 retrieval / risk / generation / feedback 哪条线的问题

### B. archive 是否能交接
- 是否含 candidate / governance / feedback / whole-book / archive metadata
- 是否便于后续维护者快速接手

### C. 对外材料是否可读
- 商务/产品/交付对象是否能看懂
- 是否过度技术化

---

## 10. “薄弱点溯源”统一方法

当你发现系统表现不好，不要只写“效果一般”，而要按下面顺序定位。

## 10.1 五层定位法
1. **源文本层**：切章、原文质量、章节标题、脏数据。
2. **知识沉淀层**：summary / facts / graph / story bible 是否可靠。
3. **召回与问答层**：query、route、RRF、rerank、QA evidence。
4. **控制与生成层**：continuation / imitation / rewrite / consistency。
5. **治理与交接层**：feedback、release gate、archive、handoff。

## 10.2 一条问题的标准记录格式
建议每发现一个问题，都记录：
- 现象：例如“第 8 章问答答错主角动机”
- 触发命令：例如 `ask-branch`
- 对应 artifact：例如 `search-diagnostics-main.json`
- 影响层：retrieval / QA
- 初步原因：entity recall 不足 / rerank 未提升 / facts 漏抓
- 严重级别：P0 / P1 / P2
- 是否可人工修复验证：是 / 否

---

## 11. 商业化验收建议打分表

## 11.1 能力打分
| 能力 | 评分 1-5 | 是否可演示 | 是否可试商用 | 备注 |
|---|---:|---|---|---|
| 拆书质量 |  |  |  |  |
| 事实/图谱沉淀 |  |  |  |  |
| retrieval / QA |  |  |  |  |
| risk semantic |  |  |  |  |
| 续写准备 |  |  |  |  |
| 仿写控制 |  |  |  |  |
| whole-book consistency |  |  |  |  |
| reader feedback 闭环 |  |  |  |  |
| governance / handoff |  |  |  |  |

## 11.2 发布建议
### 可对外演示
满足以下至少 4 条：
- 前 10 章拆书稳定
- retrieval benchmark 有可读 evidence
- risk cluster 可人工复核
- continuation / imitation pack 对作者真实有帮助
- governance dashboard 能明确说清是否 ready

### 可试商用
建议额外满足：
- 至少 2 本不同风格小说完成同口径复测
- 有 1 轮真实 reader feedback 导入与修文闭环
- whole-book 至少有一轮成功执行或足够强的 dry-run / backflow evidence

---

## 12. 建议的标准测试节奏

## 12.1 第一天
- 导入
- 前 3 章拆书
- 拆书 / retrieval / risk 首轮检查

## 12.2 第二天
- 跑到 10 章
- 导出 assistant pack / retrieval benchmark / author knowledge
- 做 continuation / imitation 准备评估

## 12.3 第三天
- 导入 reader feedback
- 做 rewrite / revision / governance 闭环
- 输出最终结论与风险清单

---

## 13. 建议最终交付物

每本新小说人工测试结束后，建议至少交出：
- `manual-review-notes.md`
- `branch-report.md`
- `novel-assistant.json`
- `author-knowledge.json`
- `retrieval-benchmark.json`
- 2~5 个 `search-diagnostics-*.json`
- `reader-feedback-summary.json`（若有评论）
- `whole-book-run.json` / `whole-book-run-executed.json`
- `governance-dashboard.json`
- `final-release-archive.json`

---

## 14. 一句话使用建议

如果你只是想快速判断一部新小说是否值得继续投入，建议最少做这 5 步：

1. 跑前 3~10 章拆书。
2. 导出 `novel-assistant.json`。
3. 跑 3 个 retrieval benchmark query。
4. 导入 5~20 条模拟读者评论。
5. 看 whole-book readiness + governance dashboard。

这样你就能比较快地判断：
- 这本书是否适合继续做拆书中台
- retrieval/风控/仿写哪一层最弱
- 当前版本离可商业化演示还有多远
