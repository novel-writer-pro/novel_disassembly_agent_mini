# Imitation Innovation & Steering / 仿写创新与外置引导

## 为什么当前仿写会显得保守

如果仿写只消费：
- source chapter
- branch facts / graph / rules
- risk gate

那么系统天然会偏向：
- 保守
- 稳定
- 不越界

这对“不写崩”有利，但对“底座与内涵创新”不够。

---

## 当前新增的改进

本轮新增了一个**外置 steering pack** 入口，让仿写不只复述原章，而能显式接入：

- `worldview_capsule`：世界观外置胶囊
- `trope_axes`：题材套路轴
- `innovation_directives`：创新导向
- `taboo_innovations`：创新禁区
- `external_knowledge_refs`：外部知识 / 读者预期参考

它会进入：
- imitation plan
- constraint pack
- harness prompt previews
- reader/rhythm/style 等辅助判断链

---

## 这层能力解决什么问题

### 1. 让仿写不只是“像”
而是能回答：
- 这章新的底座是什么？
- 这章新的世界观驱动力是什么？
- 这章新的题材抓手是什么？

### 2. 让创新有边界
不是任意创新，而是：
- 明确创新导向
- 明确禁止越界
- 明确外部读者预期

### 3. 让后续能自然接 RAG
当前先是显式人工注入 steering pack。
下一阶段最自然的升级就是：

- trope library RAG
- worldview dossier RAG
- audience expectation RAG
- genre pressure / novelty matrix RAG

---

## 推荐的创新来源

可以外置的，不只是世界观，还包括：

### A. 世界观骨架
- 灵气衰败
- 资源税制化
- 宗门垄断
- 家族信用网络
- 修炼与军功/地位绑定

### B. 套路轴
- 底层逆袭
- 资源账本化成长
- 家族-宗门-官府三方博弈
- 先压后扬
- 小收益滚大格局

### C. 创新导向
- 把功法收益写成社会信用变化
- 把升级写成权力结构再分配
- 把修炼线和婚姻/家族/身份线绑定
- 把资源获得写成更强的制度博弈

### D. 禁止项
- 无代价外挂
- 无铺垫强行升级
- 突然超大设定跳变
- 为创新而破坏主角连续性

---

## 当前最推荐的使用方式

### 场景 1：单章改写
在 `writer-imitate` / `writer-imitate-review` 时显式传：
- `--worldview-note`
- `--trope-axis`
- `--innovation-directive`
- `--taboo-innovation`
- `--knowledge-ref`

### 场景 2：批量章节推进
在 `writer-imitate-range` 时给一组稳定的 steering pack，
确保同一批次的底座统一。

### 场景 3：真实商业化打样
先做：
- trope/worldview brief
- 读者预期 brief
- taboo list

再进入仿写。

---

## 顺写（forward-writing）建议

如果不是只仿一章，而是要顺写推进：

1. 先定这 10~20 章的世界观底座
2. 再定这 10~20 章的套路轴
3. 再定每 3~5 章的创新收益点
4. 每章只兑现其中一部分
5. 用 taboo list 防止创新把系统写崩

也就是说：

> 真正的创新不是每章都乱发明，而是把创新底座提前外置，然后让章节逐步兑现。

---

## 下一阶段最值得做的技术升级

### P1
- trope/worldview steering pack 持久化
- CLI / API 统一暴露 steering surface
- 输出里显式记录本轮创新导向

### P2
- trope dossier RAG
- worldview dossier RAG
- audience expectation RAG

### P3
- 创新收益 / 越界风险双评分
- multi-reader persona 对创新接受度评估

