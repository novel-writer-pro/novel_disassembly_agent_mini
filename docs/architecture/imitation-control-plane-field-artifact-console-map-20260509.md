# Imitation Control-Plane Field → Artifact → Console Map / 仿写控制层 字段层→产物层→控制台层 映射图（2026-05-09）

这份文档专门回答一个非常接入侧的问题：

> 某一类字段，最后会落到哪个产物里？  
> 哪个产物应该给控制台哪一层消费？

它适合：

- 产品
- 运营
- 前端
- 控制台接入方
- 后续做字段瘦身/展示层治理的人

---

## 1. 三层映射总图

```mermaid
flowchart LR
    subgraph L1[字段层 / Field Layer]
        F1[session_operator_contract]
        F2[session_primary_verdicts]
        F3[session_primary_digests]
        F4[session_primary_contract_hints]
        F5[session_legacy_contract_layer]
        F6[session_legacy_retirement_readiness]
        F7[session_legacy_retirement_plan]
        F8[session_legacy_retirement_pilot_wave]
        F9[session_control_surface_entrypoints]
        F10[action backlog / transition / checkpoint]
    end

    subgraph L2[产物层 / Artifact Layer]
        A1[writer-imitate-session-state.json]
        A2[writer-imitate-operator-surface.json/.md]
        A3[writer-imitate-legacy-contract-surface.json/.md]
        A4[writer-imitate-action-queue.json/.md]
        A5[writer-imitate-execution-state.json/.md]
        A6[writer-imitate-execution-replay.json/.md]
        A7[writer-imitate-execution-apply.json/.md]
        A8[writer-imitate-execution-resume.json/.md]
        A9[writer-imitate-legacy-retirement-preview.json/.md]
        A10[writer-imitate-index.md]
    end

    subgraph L3[控制台层 / Console Layer]
        C1[默认首页 / Operator Home]
        C2[动作编排页 / Action Console]
        C3[执行态页 / Execution Console]
        C4[兼容治理页 / Legacy Console]
        C5[退休预演页 / Retirement Preview]
        C6[深层诊断页 / Deep Diagnostic]
    end

    F1 --> A2
    F1 --> A4
    F1 --> A5
    F1 --> A6
    F1 --> A7
    F1 --> A8

    F2 --> A2
    F2 --> A4
    F2 --> A5
    F2 --> A6
    F2 --> A7
    F2 --> A8

    F3 --> A2
    F3 --> A4
    F3 --> A5
    F3 --> A6
    F3 --> A7
    F3 --> A8

    F4 --> A2
    F4 --> A3
    F5 --> A3
    F6 --> A2
    F6 --> A3
    F6 --> A9
    F7 --> A2
    F7 --> A3
    F7 --> A9
    F8 --> A2
    F8 --> A3
    F8 --> A9
    F9 --> A1
    F9 --> A2
    F9 --> A3
    F9 --> A10
    F10 --> A4
    F10 --> A5
    F10 --> A6
    F10 --> A7
    F10 --> A8

    A2 --> C1
    A4 --> C2
    A5 --> C3
    A6 --> C3
    A7 --> C3
    A8 --> C3
    A3 --> C4
    A9 --> C5
    A1 --> C6
    A10 --> C6
```

---

## 2. 三层含义

### 2.1 字段层

字段层回答的是：

- 我们到底在治理什么信号？
- 哪些字段属于 primary？
- 哪些字段属于 legacy？
- 哪些字段属于 retirement 预备治理？

这一层更偏“模型/协议层”。

---

### 2.2 产物层

产物层回答的是：

- 这些字段到底落在哪些 json / markdown 里？
- 是默认入口产物，还是深层产物？

这一层更偏“交付物/接口层”。

---

### 2.3 控制台层

控制台层回答的是：

- 控制台首页应该读哪个产物？
- 动作页应该看 action queue 还是 execution state？
- legacy 治理应该看哪个 surface？

这一层更偏“最终使用面”。

---

## 3. 当前推荐映射

### 3.1 默认首页 / Operator Home

推荐读取：

- `writer-imitate-operator-surface.json`

原因：

- 已经收口第一层状态、队列、owner、primary verdict/digest
- 不需要先读更大的 session-state

---

### 3.2 动作编排页 / Action Console

推荐读取：

- `writer-imitate-action-queue.json`

重点字段：

- `session_operator_contract`
- `session_primary_verdicts`
- `session_primary_digests`
- action backlog
- transition queue
- checkpoint mutations

---

### 3.3 执行态页 / Execution Console

推荐读取：

- `writer-imitate-execution-state.json`
- `writer-imitate-execution-replay.json`
- `writer-imitate-execution-apply.json`
- `writer-imitate-execution-resume.json`

原因：

- 这几层共同回答“现在会怎么执行 / 怎么 apply / 怎么 resume”

---

### 3.4 兼容治理页 / Legacy Console

推荐读取：

- `writer-imitate-legacy-contract-surface.json`

原因：

- 专门聚焦 legacy family
- 不污染 primary 首页

---

### 3.5 退休预演页 / Retirement Preview

推荐读取：

- `writer-imitate-legacy-retirement-preview.json`

原因：

- readiness / plan / pilot wave / projected effect 已被收在一个面里

---

### 3.6 深层诊断页 / Deep Diagnostic

推荐读取：

- `writer-imitate-session-state.json`
- `writer-imitate-index.md`

原因：

- 这些仍然保留最全信息
- 更适合排障、审计、深层对照

---

## 4. 当前控制台接入建议

如果今天就要接一个最小控制台，建议这样分：

### 首页
- 直接读 `writer-imitate-operator-surface.json`

### 动作页
- 读 `writer-imitate-action-queue.json`

### 执行页
- 读 `writer-imitate-execution-state.json`
- 切页读 replay/apply/resume

### 兼容治理页
- 读 `writer-imitate-legacy-contract-surface.json`

### 退休试探页
- 读 `writer-imitate-legacy-retirement-preview.json`

---

## 5. 这张图解决什么问题

它主要解决 4 个问题：

1. **字段太多时，不知道落到哪个产物**
2. **产物太多时，不知道控制台该先接哪个**
3. **primary / legacy / retirement 三条线容易混在一起**
4. **后续做字段瘦身时，不知道会影响哪一层**

---

## 6. 当前仍然没闭环的地方

虽然三层映射已经比较清晰，但还没 fully closed-loop：

- live mutation 还没真正落地
- consumer telemetry 还没接
- automated gate 还没接
- 完整控制台 UI 还没 fully assembled

也就是说：

这张图更像是**商业 Agent 控制层接入蓝图**，而不是已经 fully shipped 的最终界面实现图。

---

## 7. 推荐与哪些文档一起看

1. `docs/architecture/imitation-commercial-agent-control-plane-architecture-20260509.md`
2. `docs/architecture/imitation-commercial-agent-ops-closed-loop-20260509.md`
3. `docs/architecture/imitation-control-plane-implementation-status-map-20260509.md`
4. `docs/imitation-control-plane-glossary.md`

---

## 8. 一句话总结

> 这张图把“字段层、产物层、控制台层”三者的关系第一次明确连起来，使当前仿写商业 Agent 控制层不仅有结构、有闭环，还有可接入的消费映射。
