# External Integration Checklist — 2026-05-14

> **范围**:`external-integration-roadmap-20260514.md` 中每个 Stage 的可执行落地清单。
> **粒度**:每条 ≤ 2 小时可验证;失败有显式回滚路径。
> **不做**:不重复路线图的决策依据;只列"做什么、怎么验、怎么退"。

---

## 使用约定

```
[ ] = 未做
[~] = 进行中
[x] = 完成
[-] = 取消(注明原因)
```

每条任务格式固定:

```
[ ] T<id>: <一句话目标>
    DO    : 具体动作
    VERIFY: 怎么证明做完了(命令 / curl / UI 检查)
    ROLLBACK: 失败如何还原
    OWNER : 谁(默认主控 = Sisyphus)
    BLOCKS: 依赖哪些前置任务
```

---

## Stage 1 — 现有 Wired 系统全面 GA(本月 / Week 3-4)

> **目标**:Dify / n8n / Helicone / Langfuse 四个 🟡 系统在 production 上真有流量。
> **完成定义**:每个系统都有 1 条以上真实业务数据 + 至少 1 个回滚演练记录。

### S1.1 — Helicone Proxy 启用(P0,1 天)

```
[ ] T-S1.1.a: Helicone self-host 拉起
    DO    : cd infra/helicone && docker compose up -d
    VERIFY: curl http://localhost:8585/healthz 200 OK
    ROLLBACK: docker compose down
    OWNER : platform
    BLOCKS: —

[ ] T-S1.1.b: 配置 LLM proxy override
    DO    : .env.local 加 NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE=http://localhost:8585/v1/<llm-target>
            (Helicone 接受 path-prefix 转发或 Helicone-Target-URL header)
    VERIFY: 一次 chapter analysis 跑完后,Helicone UI 看到 trace,延迟 P50 < 原直连 + 100ms
    ROLLBACK: 注释掉 OVERRIDE 行
    OWNER : platform
    BLOCKS: T-S1.1.a

[ ] T-S1.1.c: 一次完整 imitation 跑作回归
    DO    : 用卫图样例做一次 chapter-imitation;跑完后 Helicone 上看完整 trace 链
    VERIFY: trace 数 = LLM 调用次数(含 5→3 stage merge 后)
    ROLLBACK: —
    OWNER : platform
    BLOCKS: T-S1.1.b

[ ] T-S1.1.d: 验证 user_id / branch_id 维度可分组
    DO    : Helicone 设置 Helicone-User-Id / Helicone-Property header,llm/client.py 写入
    VERIFY: Helicone UI 按 user 分组看到分支
    ROLLBACK: 移除 header 注入
    OWNER : platform
    BLOCKS: T-S1.1.c
```

### S1.2 — Langfuse self-host 拉起(P0,1 天)

```
[ ] T-S1.2.a: Langfuse v3 compose 拉起
    DO    : 按 infra/langfuse/README 走;先用 PG-only 简化版(不上 ClickHouse)
    VERIFY: http://localhost:3000 登录页可见;创建 org/project 拿到 PUBLIC_KEY/SECRET_KEY
    ROLLBACK: docker compose down -v
    OWNER : platform
    BLOCKS: —

[ ] T-S1.2.b: Dify 集成 Langfuse 开关打开
    DO    : Dify 后台 → 监控 → Langfuse → 填 keys
    VERIFY: Dify 内随便一个应用跑一次,Langfuse 看到 trace
    ROLLBACK: Dify 后台关开关
    OWNER : platform
    BLOCKS: T-S1.2.a + Dify 已部署

[ ] T-S1.2.c: 评估 Langfuse 资源占用
    DO    : docker stats 观察 1 周
    VERIFY: 内存 < 4G,磁盘日增 < 200MB(以无 ClickHouse 简化版为基线)
    ROLLBACK: 若过大,启用 ClickHouse(增 2 容器)
    OWNER : platform
    BLOCKS: T-S1.2.b
```

### S1.3 — Dify Writer Copilot 真上线(P0,3 天)

```
[ ] T-S1.3.a: Dify self-host 拉起 + writer-copilot 应用导入
    DO    : cd infra/dify/upstream && docker compose up -d
            后台导入 infra/dify/apps/writer-copilot.dsl.yml
    VERIFY: 应用列表显示 "Writer Copilot",可在 chatbot 内对话
    ROLLBACK: 删除应用 / docker compose down -v
    OWNER : platform
    BLOCKS: —

[ ] T-S1.3.b: 关联 Dify Tools(novel-analyzer-tools.openapi)
    DO    : 后台 → Tools → 导入 infra/dify/apps/novel-analyzer-tools.openapi.yaml
            填 API Base = http://host.docker.internal:8011
    VERIFY: 在 Dify Workflow 调用 listLibrary tool 返回真实 library 数据
    ROLLBACK: 删除 tool
    OWNER : platform
    BLOCKS: T-S1.3.a + apps/api 已起

[ ] T-S1.3.c: apps/web 配置 NEXT_PUBLIC_DIFY_*
    DO    : apps/web/.env.local 填 BASE_URL + WRITER_COPILOT_TOKEN
            重启 dev server
    VERIFY: 浏览器打开 /writer/<branch_id> → Copilot iframe 加载,流式输出可见
    ROLLBACK: 注释 env
    OWNER : platform
    BLOCKS: T-S1.3.b

[ ] T-S1.3.d: 写者真用 1 章作回归
    DO    : 找一个 branch,在 Writer Studio 用 Copilot 问 5 个问题(章节内容、人物、风险)
    VERIFY: 5 个问答都能给出 grounded 答案,Langfuse 看到完整 trace
    ROLLBACK: —
    OWNER : product/QA
    BLOCKS: T-S1.3.c + T-S1.2.b
```

### S1.4 — n8n daily-eval-report 真跑(P0,1 天)

```
[ ] T-S1.4.a: n8n self-host 拉起
    DO    : cd infra/n8n && docker compose up -d
    VERIFY: http://localhost:5678 登录,basic auth = admin/novel_n8n_dev
    ROLLBACK: docker compose down -v
    OWNER : platform
    BLOCKS: —

[ ] T-S1.4.b: 导入 daily-eval-report workflow
    DO    : 后台 import infra/n8n/workflows/daily-eval-report.json
            修改 HTTP Request 节点 URL = http://host.docker.internal:8011/api/quality-dashboard?branch_id=<demo>
    VERIFY: 手动触发,workflow 跑通,输出 markdown
    ROLLBACK: 删除 workflow
    OWNER : platform
    BLOCKS: T-S1.4.a

[ ] T-S1.4.c: 启用 9am schedule
    DO    : 启用 schedule 节点
    VERIFY: 第二天 9am 自动跑了一次,通知到位(echo / Slack / 邮件,任选)
    ROLLBACK: 关闭 schedule
    OWNER : platform
    BLOCKS: T-S1.4.b
```

### S1.5 — n8n pipeline-complete-notify(P1,1 天)

```
[ ] T-S1.5.a: 导入 pipeline-complete-notify workflow
    DO    : 后台 import infra/n8n/workflows/pipeline-complete-notify.json
            激活 Webhook 触发器拿到 URL
    VERIFY: curl 模拟 POST,workflow 跑通
    ROLLBACK: 删除 workflow
    OWNER : platform
    BLOCKS: T-S1.4.a

[ ] T-S1.5.b: 配置 N8N_WEBHOOK_PIPELINE_COMPLETE_URL
    DO    : .env.local 加该 env
    VERIFY: 跑一次 pipeline,收到 webhook,n8n 处理成功
    ROLLBACK: 删除 env(代码 fire-and-forget,不影响主流程)
    OWNER : platform
    BLOCKS: T-S1.5.a

[ ] T-S1.5.c: 故障演练
    DO    : 改 URL 为不可达地址,跑 pipeline
    VERIFY: pipeline 正常完成,日志有 WARNING 但不报错
    ROLLBACK: 改回正常 URL
    OWNER : QA
    BLOCKS: T-S1.5.b
```

### S1 完成定义(Definition of Done)

- [ ] Helicone UI 累计 trace ≥ 100 条真实业务调用
- [ ] Langfuse UI 累计 trace ≥ 50 条 Dify 应用调用
- [ ] Dify Writer Copilot 至少 1 个作家用过 1 个 branch
- [ ] n8n daily-eval-report 连续 7 天自动跑成功
- [ ] 4 个系统的回滚路径都演练过,记录在 `docs/runbook/external-integration-rollback-20260514.md`(待建)

---

## Stage 2 — 拓宽与 Letta PoC(下月)

> **前提**:Stage 1 DoD 全部满足。
> **目标**:Dify 加 Reader Q&A;Langfuse 接评估面板;Letta PoC。

### S2.1 — Dify Reader Q&A 应用(2-3 天)

```
[ ] T-S2.1.a: 复制 writer-copilot DSL,改名 reader-qa
    DO    : 编辑 dataset 配置:仅 ≤ 当前章节 chunks
    VERIFY: Dify 后台跑测试,answer 不超出 chapter_index 上界
    ROLLBACK: 删除应用
    OWNER : platform
    BLOCKS: T-S1.3.a

[ ] T-S2.1.b: apps/web Reader Studio 接 Reader QA iframe(可选)
    DO    : 在 /reader/<branch_id> 右栏加 Dify chatbot iframe
    VERIFY: 防剧透行为与自研 Anti-Spoiler 路径一致
    ROLLBACK: 撤回前端改动
    OWNER : frontend
    BLOCKS: T-S2.1.a
```

### S2.2 — Langfuse evaluator + dataset 接 pairwise_eval(3 天)

```
[ ] T-S2.2.a: 创建 Langfuse dataset = pairwise-imitation
    DO    : Langfuse UI 创建 dataset
    VERIFY: dataset 列表可见
    ROLLBACK: 删除 dataset
    OWNER : platform
    BLOCKS: T-S1.2.a

[ ] T-S2.2.b: pairwise_eval 写入 Langfuse score
    DO    : pairwise_eval_service 加入 langfuse SDK 调用,把 (winner, loser, dimension) 上报为 score
    VERIFY: Langfuse UI 看到 score 序列
    ROLLBACK: env LANGFUSE_PUBLIC_KEY 留空 → SDK 静默
    OWNER : kernel
    BLOCKS: T-S2.2.a

[ ] T-S2.2.c: Langfuse evaluator 自动跑
    DO    : 配置 evaluator(LLM-as-judge prompt)
    VERIFY: 新 trace 自动有评分
    ROLLBACK: 关 evaluator
    OWNER : platform
    BLOCKS: T-S2.2.b
```

### S2.3 — Letta PoC(1 周)

```
[ ] T-S2.3.a: Letta self-host 拉起
    DO    : docker run letta/letta + 配 PG
    VERIFY: ADE 面板可登,创建 agent
    ROLLBACK: docker rm
    OWNER : platform
    BLOCKS: —

[ ] T-S2.3.b: 创建 Reader-Session-Memory agent
    DO    : Letta agent 初始化 + persona = "novel reader"
            archival memory 接入 reader_feedback 数据导出
    VERIFY: 同一读者跨 session 能记住"我喜欢硬核修仙"偏好
    ROLLBACK: 删除 agent
    OWNER : kernel
    BLOCKS: T-S2.3.a

[ ] T-S2.3.c: PoC 评估
    DO    : 写一份 1 页评估:Letta vs 内核 memory_assembler 在跨 session 场景的覆盖差
    VERIFY: 评估文档落到 docs/research/letta-poc-20260614.md
    ROLLBACK: PoC 失败则文档说明拒绝理由
    OWNER : kernel + product
    BLOCKS: T-S2.3.b
```

### S2.4 — bge-m3 三路融合(可选,1 周)

```
[ ] T-S2.4.a: TEI 切到 bge-m3 multi-mode
    DO    : docker-compose.tei.yml 模型参数改 multi-mode=true
    VERIFY: TEI /info endpoint 返回 dense/sparse/colbert
    ROLLBACK: 改回 dense-only
    OWNER : platform
    BLOCKS: TEI 已 GA

[ ] T-S2.4.b: embedding/service.py 加 encode_full
    DO    : 接受 mode = dense | sparse | colbert | multi
    VERIFY: 单元测试覆盖三模式
    ROLLBACK: 保留 ensure_dense_only 默认路径
    OWNER : kernel
    BLOCKS: T-S2.4.a

[ ] T-S2.4.c: retrieval_service RRF 加入新两路
    DO    : 现 6 路 → 8 路
    VERIFY: 召回 benchmark 比当前 baseline +15%
    ROLLBACK: feature flag 关闭新两路
    OWNER : kernel
    BLOCKS: T-S2.4.b
```

---

## Stage 3 — 长尾评估(2-3 个月后,有触发条件再启)

> 触发条件:见 roadmap §12

### S3.1 — LiteLLM Proxy 评估
### S3.2 — vLLM 自托管 LLM 评估
### S3.3 — LobeChat 读者社群分发评估
### S3.4 — OpenLLMetry / OTel 上 Tempo

每项启动前**必须**用决策基线表(roadmap §2.2)5 题答完。本文档不预先展开。

---

## 安全 / 合规 Checklist(横切)

```
[ ] SEC-1 : 任何 self-host 系统 admin 凭据**不进 git**(.env.* 已 gitignore,二次确认)
[ ] SEC-2 : Helicone proxy 不存 prompt 全文(sanitize / sampling)
[ ] SEC-3 : Langfuse 落地的 prompt 含 PII 时启用 redaction 规则
[ ] SEC-4 : n8n basic auth 默认密码必改(生产环境)
[ ] SEC-5 : Dify API key 走 secret store,不 commit
[ ] SEC-6 : 任何外部对接默认网络 = 内网 / VPN;不暴露 0.0.0.0
[ ] SEC-7 : 所有 webhook URL 不带敏感信息(已验证 runtime/notify.py 仅传 metadata,不传 chapter text)
```

---

## 性能基线(横切)

每个 Stage 结束后必须重跑:

```
[ ] PERF-1 : 单章 imitation P50 延迟变化 < 100ms
[ ] PERF-2 : QA stream first-byte 延迟变化 < 50ms
[ ] PERF-3 : pipeline 整本跑总时长变化 < 5%
[ ] PERF-4 : DB 慢查询数(slow_log)变化 < 5%
[ ] PERF-5 : 内存峰值变化 < 10%
```

任一项超阈值 → 立即触发 roadmap §9 风险与回滚。

---

## 文档同步 Checklist(每个 Stage 关闭时)

```
[ ] DOC-1 : 更新 README 技术栈 + 入口表
[ ] DOC-2 : CHANGELOG 增加本 Stage 条目
[ ] DOC-3 : docs/runbook/* 增加运维步骤
[ ] DOC-4 : docs/strategy/external-integration-roadmap-20260514.md 状态标记从 🟡 → ✅
[ ] DOC-5 : docs/architecture/external-integration-architecture-20260514.md 状态线刷新
```

---

## 完结条件(本 Checklist 整体)

- Stage 1 DoD ✅
- Stage 2 DoD ✅
- Stage 3 触发条件出现 → 单独立项,本文档归档
- 任何一项 SEC-* 失败 → 整体停止 → root cause 修复 → 复查
