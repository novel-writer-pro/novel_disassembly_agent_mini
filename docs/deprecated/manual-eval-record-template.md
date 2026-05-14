# Manual Eval Record Template / 人工测试记录模板

> 配合 `docs/novel-assistant-manual-eval-handbook-20260505.md` 使用。
> 一次测试一份，目标是把“能不能商用、薄弱点在哪、下一步修什么”记录清楚。

---

## 1. 基本信息
- 测试日期：
- 测试人：
- 小说标题：
- 小说类型 / 题材：
- 文本来源：
- 文本字数：
- 章节数：
- `novel_id`：
- `manifest_id`：
- `run_id`：
- `branch_id`：
- provider / model：
- 数据库环境：

---

## 2. 本轮目标
- [ ] 首轮导入验证
- [ ] 拆书质量验证
- [ ] retrieval / QA / rerank 验证
- [ ] risk semantic 验证
- [ ] continuation / imitation 验证
- [ ] whole-book readiness / execute 验证
- [ ] reader feedback 闭环验证
- [ ] governance / archive 验证

本轮重点：
- 
- 
- 

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
- 

---

## 5. 拆书 / 信息抽取评估

### 5.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| 切章正确性 |  |  |
| Summary 贴文本 |  |  |
| Key events 抓主线 |  |  |
| Facts 沉淀质量 |  |  |
| Graph / state 连续性 |  |  |

### 5.2 主要观察
- 做得好的点：
- 明显问题：
- 是否出现伪造剧情：
- 最弱章节：
- 最强章节：

### 5.3 判定
- [ ] 可继续推进
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
| Top1 准确性 |  |  |
| Top3 覆盖度 |  |  |
| 多路召回贡献 |  |  |
| rerank 改序价值 |  |  |
| latency 可接受度 |  |  |
| QA answer 可信度 |  |  |

### 6.3 主要观察
- 哪类 query 最稳：
- 哪类 query 最差：
- `entity_exact` 是否有用：
- `vector` 是否有用：
- rerank 是否在复杂 query 上产生提升：
- QA 是否存在“证据不足仍硬答”：

### 6.4 判定
- [ ] 已达到演示级
- [ ] 可用但还需补 query bank
- [ ] 召回/排序仍需重点修复

---

## 7. Risk Semantic / 人工复核评估

### 7.1 快速评分
| 项目 | 分数（1-5） | 结论 |
|---|---:|---|
| 高风险定位准确性 |  |  |
| cluster 可解释性 |  |  |
| 人工复核便利性 |  |  |
| 噪音控制 |  |  |

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
