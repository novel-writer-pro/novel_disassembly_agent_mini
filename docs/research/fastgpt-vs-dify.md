# FastGPT vs Dify — 选型决策备忘

> **范围**：v2 plan N11。**仅文档评估，不部署 FastGPT**。
> **结论先行**：**继续用 Dify**，FastGPT 暂不切换；保留观察，遇到 3 个明确触发条件之一时再讨论。

---

## 一、定位对比

| 维度 | Dify | FastGPT |
|------|------|--------|
| 定位 | LLMOps 平台（应用 + 工作流 + 评测） | RAG 优先平台（知识库 + 工作流） |
| 起源 | LangGenius，2023 (中) | 杭州 LabringHub，2023 (中) |
| Stars (2026) | ~70k | ~20k |
| License | Apache 2.0 + 商业条款（500 user / SaaS 限制）| Apache 2.0（更宽松）|
| 主要语言 | Python（API）+ TS（Web）| TS（全栈）|

## 二、能力对比（针对 novel-analyzer 场景）

| 我们的需求 | Dify | FastGPT | 胜者 |
|-----------|------|---------|-----|
| Chatbot 应用 + iframe 嵌入 | ✅ chat-bubble + iframe + JS widget | ✅ iframe + 分享链接 | 平 |
| 流式输出 / 取消 / 重试 | ✅ 完整 | ✅ 完整 | 平 |
| RAG / 知识库 | 标准 RAG，多种 chunk 策略 | **更精细**：QA 拆分、问题增强、向量+全文混合 | **FastGPT** |
| 工作流编排 | Workflow + Chatflow（状态机） | Workflow（更直观的 advance orchestration） | 略胜 FastGPT |
| Tool / Custom API | ✅ OpenAPI schema 自动生成工具 | ✅ HTTP 节点 + 自定义 plugin | 略胜 Dify |
| Prompt 版本管理 | ✅ Prompt Studio + 历史 | ⚠️ 弱 | **Dify** |
| 评测 / 数据集 | ✅ Annotation + 评测 + datasets | ⚠️ 实验性 | **Dify** |
| Langfuse 集成 | ✅ 内置一键开关 | ❌ 需自己写 webhook | **Dify** |
| 多 workspace / 多租户 | ✅ Workspace + API Key | ⚠️ Team 概念较弱 | **Dify** |
| 中文化 | ✅ 完整 | ✅ 母语级（更顺手） | 略胜 FastGPT |
| 文档 / 社区 | 国际化好、英文文档完整 | 中文文档优于英文，国内社区活跃 | 看团队 |
| 自托管复杂度 | 12 容器（重） | 7 容器（轻） | **FastGPT** |
| OpenAI-compatible API | ✅ 每个应用自动暴露 | ✅ 完整 | 平 |

## 三、对我们当下的差异点

**Dify 占优**（决定本次留 Dify）：
- ✅ Langfuse **零代码集成**：v2 plan 关键路径上，FastGPT 切走 = 自己写 trace
- ✅ Prompt Studio：imitation prompts 搬进来直接有版本管理
- ✅ Workspace + API key：未来对外 SaaS 拆租户的脚手架
- ✅ 评测/数据集：CHANGELOG 里 `eval_governance_service` 显示我们在意评测，能复用 Dify 的功能

**FastGPT 占优**（值得记录的）：
- ✅ 部署轻：12 → 7 容器，本地资源敏感时有用
- ✅ RAG 知识库的 QA 拆分能省一层活——但我们已有自家 RAG（`rag/`、`embedding/`、`rerank/`），用不上 FastGPT 的知识库
- ✅ License 更宽松（无 500 user 限制）

## 四、何时切换 FastGPT（明确触发条件）

| 条件 | 触发后做什么 |
|------|------------|
| Dify 商业 license 限制实际碰到（500+ user 或 SaaS）| 切 FastGPT 或买 Dify 商业版 |
| 我们决定不要自家 RAG，改用 FastGPT 的知识库 + QA 拆分 | 重新评估全套 |
| Dify 的 Chatbot iframe 在编辑器里出问题 3 次以上 | 试 FastGPT 的 iframe 看是否更好 |

## 五、混合策略（不推荐，但记录）

理论上可以同时跑 Dify（外部 chat UI）+ FastGPT（仅做 RAG）。
**不推荐**：双 framework 维护成本远超收益。

## 六、最终决策

**继续 v2 plan，用 Dify。**FastGPT 知道存在，遇到上面 3 个触发条件再讨论。本备忘 6 个月后 review 一次。

## 引用

- Dify GitHub: https://github.com/langgenius/dify
- FastGPT GitHub: https://github.com/labring/FastGPT
- Dify 商业 license: https://github.com/langgenius/dify/blob/main/LICENSE
- 评估时间盒：~2 小时（远少于 plan 预估的 4 小时）
