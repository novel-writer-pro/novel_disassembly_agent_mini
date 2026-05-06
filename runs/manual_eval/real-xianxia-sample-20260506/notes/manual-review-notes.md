# Manual Eval Record Template / 人工测试记录模板

> 配合 `docs/novel-assistant-manual-eval-handbook-20260505.md` 使用。
> 一次测试一份，目标是把“能不能商用、薄弱点在哪、下一步修什么”记录清楚。

---

## 1. 基本信息
- 测试日期：2026-05-062026-05-06
- 测试人：
- 小说标题：真实中文修仙样例-青华（原文 + 最小标题归一化副本）真实中文修仙样例-青华（原文 + 最小标题归一化副本）
- 小说类型 / 题材：中文修仙 / 男频向开篇样例中文修仙 / 男频向开篇样例
- 文本来源：仓库本地缓存 `.cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`仓库本地缓存 `.cache/novel-analyzer/uploads/c495a0a263b947058a19dad743dab8a1-novel.txt`
- 文本字数：
- 章节数：原文 3 节（归一化后 3 章）原文 3 节（归一化后 3 章）
- `novel_id`：78ff3ac4-1e4f-4dc9-bf84-a3107421fdbe
- `manifest_id`：90030aca-da86-4956-bef9-b1ec54106148
- `run_id`：b0fb667b-ce1e-47a0-8346-92e3dbc6d3bcb0fb667b-ce1e-47a0-8346-92e3dbc6d3bc
- `branch_id`：86ce179e-475a-42b9-ade3-a81a8626dc5f86ce179e-475a-42b9-ade3-a81a8626dc5f
- provider / model：DeepSeek / deepseek-v4-flashDeepSeek / deepseek-v4-flash
- 数据库环境：PostgreSQL `novel_analyzer`（本地 127.0.0.1:5432）

---

## 2. 本轮目标
- [x] 首轮导入验证
- [x] 拆书质量验证
- [x] retrieval / QA / rerank 验证
- [x] risk semantic 验证
- [ ] continuation / imitation 验证
- [ ] whole-book readiness / execute 验证
- [ ] reader feedback 闭环验证
- [x] governance / archive 验证

本轮重点：
- 验证真实中文修仙文本在当前 ingest/analysis 主链上的兼容性
- 验证前 3 章拆书、风险与 retrieval 物化是否能跑通
- 记录真实格式兼容问题与小模型结构化 schema 兼容问题

---

## 3. 执行命令记录
> 只记录关键命令，方便复跑。

```bash
# ingest / start

# analyze

# retrieval / qa

# risk / review

# imitation / whole-book

# governance / archive
```

---

## 4. 导出 artifact 清单
- [ ] `branch-report.md`
- [ ] `novel-assistant.json`
- [ ] `author-knowledge.json`
- [ ] `retrieval-benchmark.json`
- [ ] `search-diagnostics-*.json`
- [ ] `reader-feedback-summary.json`
- [ ] `whole-book-readiness.json`
- [ ] `whole-book-run.json`
- [ ] `governance-dashboard.json`
- [ ] `final-release-archive.json`
- [ ] `manual-review-notes.md`

实际保存路径：
- `runs/manual_eval/real-xianxia-sample-20260506/`

---

## 5. 拆书 / 信息抽取评估

### 5.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| 切章正确性 | 2 | 原文标题格式不兼容；最小归一化后可正常切 3 章 |
| Summary 贴文本 | 4 | 第1章略泛化，第2章人物互动总结较贴文本 |
| Key events 抓主线 | 4 | 主事件与情感推进都能抓到 |
| Facts 沉淀质量 | 4 | 3章完成后 fact_count=37，世界观/关系/伏笔沉淀明显 |
| Graph / state 连续性 | 4 | graph_node_count=48 / graph_edge_count=256，连续性已成形 |

### 5.2 主要观察
- 做得好的点：世界观维度、伏笔维度、人物情绪曲线提炼较强；第2章 fallback 后仍成功收口。
- 明显问题：原文“第X节”标题不兼容；第2章 small_model_pipeline 的 dialogue_candidates schema 不兼容。
- 是否出现伪造剧情：当前未见明显硬编，但第1章摘要偏泛。
- 最弱章节：第1章（summary 略泛）；第2章（需要 fallback）。
- 最强章节：第2章的人物互动、情绪与关系刻画提炼。

### 5.3 判定
- [x] 可继续推进
- [ ] 需局部重跑
- [ ] 不建议继续

---

## 6. Retrieval / QA / RRF / Rerank 评估

### 6.1 Query 集
1. 
2. 
3. 
4. 
5. 

### 6.2 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| Top1 准确性 | 3 | search diagnostics CLI 在本轮 40s 超时，未拿到完整检索排序证据 |
| Top3 覆盖度 | 3 | 当前以 chapter bundle / author knowledge 侧证为主 |
| 多路召回贡献 | 2 | 本轮未成功导出 benchmark/diagnostics 结果，需要后续单独排查 |
| rerank 改序价值 | 2 | 本轮缺少可落盘 diagnostics 证据 |
| latency 可接受度 | 2 | diagnostics / governance 导出 40s 超时，存在体验风险 |
| QA answer 可信度 | 2 | ask-branch 本轮未成功返回，需后续单独复测 |

### 6.3 主要观察
- 哪类 query 最稳：待补（本轮 diagnostics CLI 超时）。
- 哪类 query 最差：待补（本轮 diagnostics CLI 超时）。
- `entity_exact` 是否有用：待补直接证据。
- `vector` 是否有用：待补直接证据。
- rerank 是否在复杂 query 上产生提升：待补。
- QA 是否存在“证据不足仍硬答”：本轮未拿到 QA 返回。

### 6.4 判定
- [ ] 已达到演示级
- [x] 可用但还需补 query bank
- [ ] 召回/排序仍需重点修复

---

## 7. Risk Semantic / 人工复核评估

### 7.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| 高风险定位准确性 | 3 | 3章完成后 chapter3 标记 review=True，说明风险链已参与，但还未展开人工逐簇复核 |
| cluster 可解释性 | 3 | 需后续补 cluster 明细导出 |
| 人工复核便利性 | 3 | 需要单独补 show-cluster-status/history 复核 |
| 噪音控制 | 3 | 当前没有明显误报证据，也没有足够导出明细 |

### 7.2 主要观察
- 真风险样例：
- 误报样例：
- 漏报样例：
- 最难人工判断的点：

### 7.3 人审状态记录
| cluster_key | 判定 | 备注 |
|---|---|---|
|  |  |  |
|  |  |  |

---

## 8. Author Knowledge / Story Bible / 创作准备评估

### 8.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| story bible 价值 |  |  |
| 角色信息组织 |  |  |
| 关系/规则索引价值 |  |  |
| unresolved threads 价值 |  |  |
| 下一章准备价值 |  |  |

### 8.2 主要观察
- 对作者最有帮助的字段：
- 对编辑最有帮助的字段：
- 哪些字段还像“技术摘要”而不是“创作控制面”：

---

## 9. Continuation / Imitation / Whole-book 评估

### 9.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| continuation pack 可执行性 |  |  |
| imitation pack 可执行性 |  |  |
| style/rhythm/dialogue 控制感 |  |  |
| long-book consistency 闭环 |  |  |
| whole-book readiness 可信度 |  |  |

### 9.2 主要观察
- 续写准备是否足够具体：
- 仿写控制是否能避免剧情跑偏：
- 人设保护是否足够：
- consistency backflow 是否真正指出了修复重点：

### 9.3 判定
- [ ] 可做内部演示
- [ ] 可做有限试商用
- [ ] 仍偏实验性质

---

## 10. Reader Feedback 闭环评估

### 10.1 输入评论规模
- 评论数：
- 覆盖章节：
- 来源：

### 10.2 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| 信号归纳质量 |  |  |
| 修文建议可执行性 |  |  |
| 节奏/逻辑/人设识别 |  |  |
| 闭环价值 |  |  |

### 10.3 主要观察
- 最有价值的 reader signal：
- 最无效的 signal：
- 是否能真正指导 revision / rewrite：

---

## 11. Governance / Release / Archive 评估

### 11.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| release gate 清晰度 |  |  |
| dashboard 可读性 |  |  |
| archive 交接价值 |  |  |
| 对外材料可用性 |  |  |

### 11.2 主要观察
- 当前是否 ready：
- 不 ready 的主因：
- 对商务/产品演示最有帮助的输出：
- 最不容易看懂的输出：

---

## 12. 薄弱点溯源

| 问题编号 | 现象 | 所在层 | 严重级别 | 初步原因 | 建议动作 |
|---|---|---|---|---|---|
| P1 |  | 源文本 / 知识 / 检索 / 生成 / 治理 |  |  |  |
| P2 |  | 源文本 / 知识 / 检索 / 生成 / 治理 |  |  |  |
| P3 |  | 源文本 / 知识 / 检索 / 生成 / 治理 |  |  |  |

---

## 13. 商业化判断

### 13.1 当前最适合展示的能力
1. 
2. 
3. 

### 13.2 当前最不适合承诺的能力
1. 
2. 
3. 

### 13.3 综合判断
- [ ] 适合外部演示
- [ ] 适合内部试点
- [ ] 适合小范围试商用
- [ ] 暂不建议对外承诺

一句话结论：
- 

---

## 14. 下一步建议

### 必做
1. 
2. 
3. 

### 可选增强
1. 
2. 
3. 

### 是否需要重跑
- [ ] 需要
- [ ] 不需要

重跑建议：
- 


## 15. 本轮补充结论
- 原始真实文本存在格式兼容性问题：`第一节/第二节` 标题未被切章器识别，direct ingest 得到 `chapter_count=0`。
- 采用最小归一化副本后，3 章主链成功完成，说明当前系统对真实中文修仙文本内容本身是可处理的，但对章节标题格式仍需增强。
- 第 2 章触发 `small_model_pipeline` schema 不兼容（`dialogue_candidates` 返回对象），系统自动通过 `monolithic_fallback` 收口，鲁棒性有效。
- `export-author-knowledge` 成功；但 `export-governance-dashboard` 与 `export-search-branch-diagnostics` 在本轮单独验证中 40s 超时，说明 operator-facing 导出链仍需继续优化。


## 15. 本轮补充结论
- 原始真实文本存在格式兼容性问题：`第一节/第二节` 标题未被切章器识别，direct ingest 得到 `chapter_count=0`。
- 采用最小归一化副本后，3 章主链成功完成，说明当前系统对真实中文修仙文本内容本身是可处理的，但对章节标题格式仍需增强。
- 第 2 章触发 `small_model_pipeline` schema 不兼容（`dialogue_candidates` 返回对象），系统自动通过 `monolithic_fallback` 收口，鲁棒性有效。
- 第 1 章的世界观/伏笔抽取较强，但摘要略偏泛化；第 2 章的人物互动和情绪曲线抓取得较好。
- 当前最明确的两个产品化改进点：
  1. ingest heading parser 支持“第X节/卷-节”格式；
  2. chapter intake 对 `dialogue_candidates` 增加对象兼容解析。
