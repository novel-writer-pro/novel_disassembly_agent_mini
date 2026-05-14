# Promptfoo 评测套件

> v2 plan N9：用 promptfoo 锁 imitation prompts 的回归。
> **dev only**，不进生产 image。CI 手动 trigger，不阻断 PR（成本敏感）。

## 安装

```bash
npx --yes promptfoo@latest --version
# 或全局：npm install -g promptfoo
```

## 运行

需要 Dify 已起来（N1）+ Writer Copilot 应用 token（N4）。

```bash
export DIFY_API_HOST=http://localhost:8080
export DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxxxxx

cd tests/promptfoo
npx promptfoo eval -c imitation-style.yaml -o ../../.sisyphus/evidence/N9-imitation-style.json
npx promptfoo eval -c qa-citation.yaml      -o ../../.sisyphus/evidence/N9-qa-citation.json
npx promptfoo eval -c safety.yaml           -o ../../.sisyphus/evidence/N9-safety.json

# 查看 web UI
npx promptfoo view
```

## 用例分布

| 文件 | 用例数 | 检查类型 |
|------|-------|---------|
| imitation-style.yaml | 3 | 风格一致性、长度、负面拒绝 |
| qa-citation.yaml     | 3 | 章节引用格式、多引用、未知章节 |
| safety.yaml          | 3 | 危险信息、隐私、越权 |
| **合计** | **9** | 满足 plan N9 acceptance：≥9 个用例 |

## 阈值与失败判定

`promptfoo` 默认 fail 即整个 case 失败。我们用：
- `contains` / `contains-any` — 硬规则
- `regex` — 章节引用格式
- `javascript` — 长度、引用数量
- `llm-rubric` — 主观（风格保留），需 OpenAI key

## CI 接入（手动 trigger）

```yaml
# .github/workflows/promptfoo-eval.yml (示例)
name: promptfoo-eval
on:
  workflow_dispatch:  # 仅手动
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g promptfoo
      - run: cd tests/promptfoo && promptfoo eval -c imitation-style.yaml
```

## 不进 PR 阻断的理由

- LLM 调用有成本（每次 eval ≥ $0.05）
- 流式输出延迟，CI 慢
- v2 plan 明确"先 manual"

待生态稳定后，再考虑：
- 把 cheap 的 contains/regex 用例接入 PR check
- llm-rubric 留 manual
