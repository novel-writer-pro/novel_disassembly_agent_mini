# Novel Assistant Business Architecture / 小说助手业务架构

## 1. 商业目标
把小说助手做成一个“可交付、可运营、可扩能力”的系统，而不是一次性的写作工具。

## 2. 价值链
### 2.1 前台价值
- 作者更快回看、检索、问答
- 作者更稳地续写 / 仿写
- 编辑更早发现风险和断裂

### 2.2 中台价值
- 小说知识中台
- 风险审查中台
- 生成准备中台
- 样例与治理中台

### 2.3 后台价值
- 交接、复盘、回归、审计
- 可接 API / CLI / 独立 agent
- 可逐步抽离成更大平台能力

## 3. 商业能力包
1. **拆书包**：知识化、章节理解、branch report
2. **审查包**：风险卡、review workflow、cluster summary
3. **生成包**：author knowledge、chapter imitation、whole-book orchestration
4. **治理包**：sample artifact、freeze gate、smoke path、handoff docs

## 4. 适合的客户 / 使用方
- 作者工作室
- 编辑团队
- 平台内容团队
- IP 开发与改编团队
- AI 内容系统集成商

## 5. 商业推进顺序
### 第一阶段
- 先卖“拆书 + 检索 + 风险审查”
- 因为最容易证明 ROI

### 第二阶段
- 再卖“续写 / 仿写辅助”
- 因为它依赖前面的知识层和门控层成熟

### 第三阶段
- 再卖“平台化中台能力”
- 因为这时才真正形成壁垒

## 6. 为什么现在有商业化基础
- 已有真实样例
- 已有 whole-book provider-backed 成功运行
- 已有 DB migration / self-check / smoke path
- 已有统一 assistant capability pack
