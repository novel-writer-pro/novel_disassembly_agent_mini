# Helicone vs Langfuse — 部署形态对比评估

> **范围**：v2 plan N10。仅评估部署形态，**不**实际切换。
> **结论先行**：**主路径继续 Langfuse（Dify 内置）**，Helicone 作为"绕过 Dify 的 LLM 调用"的备选。两者**不互斥**，可以并存。

---

## 一、本质差异

| 维度 | Langfuse | Helicone |
|------|----------|----------|
| 模型 | SDK / OpenTelemetry / Dify-integrated | **Proxy 代理层**（透明拦截） |
| 接入方式 | `@observe` 装饰器 / 集成开关 | **改 base_url** 即可 |
| 业务代码侵入 | 装饰器：低；集成：零（Dify 内置） | **零**（仅改 env） |
| 适合的 LLM 调用 | 应用层调用（Dify、SDK） | **任意 OpenAI-compatible** 调用 |
| Trace 粒度 | 应用 / span / generation 三层 | 单次 request（更扁平） |
| Prompt 版本 | ✅ 有 Prompt Studio | ❌ 不主打 |
| 评测 / dataset | ✅ 完整 | 弱 |
| 成本归因 | ✅ user_id / session_id 维度 | ✅ user_id 维度（默认） |
| 自托管复杂度 | 6 容器（PG + ClickHouse + Redis + MinIO + web + worker）| 5 容器（PG + ClickHouse + 主容器 + worker + jawn） |
| 数据存储 | trace 体大（v3 用 ClickHouse）| 同样 ClickHouse 但更轻 |
| 缓存 / 限流 | 弱 | ✅ 自带（proxy 优势）|

## 二、对我们 v2 plan 的契合度

### v2 plan 的 LLM 调用边界

```
[FastAPI / WSGI 路由]
       ↓
[novel_analyzer/services/*]
       ↓
[novel_analyzer/llm/client.py]  ← LLM 调用唯一入口
       ↓ (base_url, model, key)
[OpenAI-compatible Provider]
```

### Langfuse via Dify 集成（v2 plan 主路径）

✅ **覆盖**：经过 Dify 应用的所有调用（Writer Copilot、未来的 Reader Q&A）
❌ **不覆盖**：
- `novel_analyzer/llm/client.py` 直接发的请求（imitation pipeline、章节分析、Loom 信号、QA 等）
- 这部分是**大头**——imitation 一次跑可能数十次 LLM 调用

### Helicone 代理层（候选补充）

把 `NOVEL_ANALYZER_LLM_BASE_URL` 从原 provider 改成 `http://localhost:8585/v1`，**所有**直连 LLM 都被透明 trace。

```bash
# 现状
export NOVEL_ANALYZER_LLM_BASE_URL=https://api.vip1129.cc/v1

# Helicone 接入（仅 dev）
export NOVEL_ANALYZER_LLM_BASE_URL=http://localhost:8585/v1/https://api.vip1129.cc/v1
# 或用环境头 Helicone-Target-URL
```

代码侧改动 = **0**。这正是 v2 plan 强调"零侵入"的目标。

## 三、组合方案（推荐）

```
┌─ Dify Chatbot 调用 ─→ Dify 内置 Langfuse trace ─┐
│                                                  ├→ 同一 Langfuse UI 看全图
└─ novel_analyzer/llm/client 直连 ─→ Helicone proxy → Langfuse OTLP / 自家 trace ─┘
```

注：Helicone 默认存自家 ClickHouse；想统一到 Langfuse 可让 Helicone 转发 OTLP 给 Langfuse。
**简化版**：Helicone 自存自看，Langfuse 看 Dify 的；两套 UI 都接受。

## 四、五维评估表

| 维度 | Langfuse only | Helicone only | 组合 |
|------|---------------|---------------|------|
| 部署复杂度 | 中（Dify 已部署，再加 Langfuse）| 低 | 中高 |
| 业务代码侵入 | 0 | 0 | 0 |
| Trace 完整度 | 仅 Dify 调用（**~30%**）| 全部直连（**~70%**） | **100%** |
| Prompt 版本 / 评测 | ✅ | ❌ | ✅ |
| 缓存 / 限流 | ❌ | ✅ | ✅ |

## 五、最终建议

**v2 阶段**：
1. **保留**：Langfuse 自托管 + 接 Dify（v2 plan N3+N5）
2. **新增建议**（v3 候选）：再起一个 Helicone proxy，把 `NOVEL_ANALYZER_LLM_BASE_URL` 切过去（dev only）

风险：
- Helicone proxy 成单点故障 → 只在 dev/staging 用
- 两套 trace UI = 心智负担 → 主看 Langfuse

## 六、何时实际部署 Helicone

| 触发条件 | 行动 |
|---------|------|
| 想看 imitation pipeline 的逐步 LLM 成本 | 部署 Helicone |
| Dify 内置 Langfuse 不够（Reader 端绕过 Dify）| 部署 Helicone |
| 需要 LLM 缓存降本 | 部署 Helicone（自带）|

## 七、引用

- Helicone OSS：https://github.com/Helicone/helicone
- Langfuse v3：https://github.com/langfuse/langfuse
- Helicone vs Langfuse 官方对比：https://www.helicone.ai/blog/langfuse-vs-helicone

评估时间盒：~1.5 小时
