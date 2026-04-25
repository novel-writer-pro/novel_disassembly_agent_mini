# 阶段评估结论（前 12 章）

本文件用于对当前示例小说前 12 章真实试跑结果做阶段性结论整理。

---

## 1. 当前评估范围

- 小说：`/home/user/txt111/novel.txt`
- run_id：`34545dc4-9db4-4619-86b4-d91e2153c575`
- branch_id：`e321854a-8f3f-4af4-9244-c86338ca62ad`
- 已完成章节：1~12
- 已生成窗口：
  - `1~5`
  - `6~10`

---

## 2. 当前阶段结论

### 2.1 系统结论
当前系统已经具备：
1. 真实文本切章与串行推进能力
2. 单章拆书落盘能力
3. 事实层 / retrieval / reasoning graph 派生能力
4. 窗口级总结能力
5. branch report / chapter markdown / QA context 导出能力

### 2.2 内容结论
前 12 章结果已经足够证明：
- 系统不是只会生成摘要
- 系统已经能抓住阶段主线推进
- continuity notes 是当前最有价值的输出之一
- 第二个窗口（6~10）已开始体现结构性拆书价值

---

## 3. 当前最明显的优点

### 3.1 主线推进识别稳定
已稳定抓到：
- 命格觉醒线
- 资源获取线
- 功法成长线
- 婚姻/生活线
- 奴籍/脱籍线
- 外部风险线
- 冲突升级线

### 3.2 continuity 质量较高
在这些章节中尤为明显：
- 第 7 章
- 第 9 章
- 第 10 章
- 第 11 章

### 3.3 窗口总结有阶段价值
- `1~5`：立设定 / 稳生活 / 建主线
- `6~10`：外部压力抬升 / 冲突升级 / 主角正面对抗

---

## 4. 当前最明显的短板

### 4.1 writer-learning 仍偏弱
尽管已做 fallback 增强，但真实章节中仍偏少。

### 4.2 summary 仍偏长
部分章节仍更像剧情概述，而不是拆书卡片。

### 4.3 当前模型 JSON 稳定性一般
在真实长跑中已经出现过损坏 JSON，需要重试。

### 4.4 当前模型吞吐偏慢
长程连续推进效率较低，不适合无人值守长跑。

---

## 5. 当前模型正式判断

模型：`Qwen/Qwen3.5-122B-A10B`

### 适合
- 小批次试跑
- 质量验证
- 人工盯跑
- prompt / 结构评估

### 不适合
- 100 章无人值守长程跑批
- 高稳定性生产拆书主模型

### 正式结论
当前模型：
**适合做质量验证 / 人工盯跑，不适合长程无人值守生产跑批。**

---

## 6. 当前是否继续往后跑

### 建议
不建议当前继续长程自动推进作为主要目标。

### 更合理的动作
1. 停在前 12 章
2. 以当前结果作为阶段评估样本
3. 做针对性优化：
   - writer-learning
   - summary 压缩
   - JSON 稳定性增强
4. 之后再换更稳或更快模型继续长跑

---

## 7. 下一轮优化优先级

### P1
1. writer-learning 增强
2. summary 压缩
3. JSON 稳定性增强

### P2
1. thematic contexts 稠密度增强
2. QA 回答风格优化
3. hook score 可解释性增强

---

## 8. 关联文档

- [`./real-run-evaluation-1-12.md`](./real-run-evaluation-1-12.md)
- [`./real-run-checklist.md`](./real-run-checklist.md)
- [`./review-template.md`](./review-template.md)
- [`./model-eval-template.md`](./model-eval-template.md)
- [`./session-handoff-manual.md`](./session-handoff-manual.md)
- [`./final-handoff.md`](./final-handoff.md)
