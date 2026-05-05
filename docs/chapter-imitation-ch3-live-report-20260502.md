# 第3章《养生功法》live 仿写实验报告（2026-05-02）

## 1. 实验目标

验证当前章节仿写能力链是否已经具备：

1. 原章结构理解
2. LLM 仿写草案生成
3. 原章 vs 仿写结构化对比
4. review / gate / sandbox risk 评审
5. revised draft 输出
6. 多轮自动优化 runner

本次实验章节：

- 原章：**第3章《养生功法》**

---

## 2. 使用命令

### 2.1 仿写草案

```bash
novel-analyzer imitate-chapter 62e636f0-c901-4167-aa1c-aff3da9c83ef 3 \
  "延续主角获得功法后的行动线，并保持克制成长节奏" \
  --use-llm
```

### 2.2 原章对比

```bash
novel-analyzer compare-imitation 62e636f0-c901-4167-aa1c-aff3da9c83ef 3 \
  "延续主角获得功法后的行动线，并保持克制成长节奏" \
  --use-llm
```

### 2.3 多轮优化

```bash
novel-analyzer iterate-imitation 62e636f0-c901-4167-aa1c-aff3da9c83ef 3 \
  "延续主角获得功法后的行动线，并保持克制成长节奏" \
  --use-llm --max-rounds 2
```

---

## 3. 原章核心骨架

原章《养生功法》的关键结构功能：

1. 卫图求助二姑与黄宅资源
2. 受轻视与身份差异进一步显形
3. 得到有限资源（功法）
4. 将羞辱与阻力转为内部消化
5. 回到李宅后开始主动修炼
6. 命格给出长期成长路径的反馈

简化成一句话：

> **低位求助受阻 → 有限资源到手 → 克制消化羞辱 → 转入长期修炼主线**

---

## 4. live 仿写结果

### 4.1 实验 stop 条件结果

真实输出：

- `stop_reason = quality_threshold_reached`
- `round_count = 1`
- `comparison.overall_verdict = aligned`
- `gate.overall_verdict = aligned_but_needs_revision`
- `risk.overall_risk_level = low`
- `score.overall_score >= 80`

这说明：

- 第一轮草案已在结构层面达到可接受对齐
- 风险层面为低风险
- 当前评分器也已认为其达到可接受阈值
- 仍有修订建议，但没有进入高风险或结构性偏离

---

## 5. live 草案效果评价

### A. 做得好的部分

1. **保住了原章骨架**
   - 仍然围绕“功法到手后如何继续推进”展开
   - 没有直接跳到境界突破或资源暴涨

2. **保住了人物底色**
   - 卫图依然是克制、务实、能忍耐的
   - 没有写成情绪化反击或突然高姿态

3. **保住了低位资源受限感**
   - 草案通过“差事/时间/身份限制”继续制造阻力
   - 与原章“资源有限、身份受压”的底层逻辑一致

4. **保住了章尾钩子**
   - 仍然给出下一步可执行动作
   - 没有空泛收束，也没有无铺垫跳跃

### B. 还不够好的部分

1. **文学表现力还偏保守**
   - 更像结构正确的 draft
   - 还不是完成度很高的正文

2. **风险评审仍偏轻量**
   - 当前 `risk` 为 sandbox 级
   - 还未把 prose draft 送进正式 sandbox branch 的完整 materialization 链

3. **轮次只跑到一轮**
   - 因为当前阈值认为已达标
   - 但如果追求“更出色”，仍可继续多轮优化

### C. 当前 stop 逻辑含义

当前 `iterate-imitation` 会综合判断：

- `comparison.overall_verdict`
- `gate.overall_verdict`
- `risk.overall_risk_level`
- `score.overall_score`

这意味着它已经不再只是：

> “结构对齐 + 风险低”

而是进一步进入：

> “结构对齐 + 风险低 + 质量/风格得分达到阈值”

---

## 6. 当前系统能力判断

本次 live 实验表明：

### 已具备

- 章节规划
- LLM 仿写草案
- 原章对比
- review
- gate
- sandbox risk
- revised draft
- 多轮 runner

### 尚未完全具备

- prose draft 的正式 sandbox branch 风险链
- 更强的风格/张力/语言评分器
- 更激进的多轮自动优化策略

---

## 7. 一句话结论

> 第3章《养生功法》的 live 仿写实验已经证明：当前系统可以稳定地产出“结构对齐、风险较低、可继续优化”的章节仿写草案；它已经不是概念验证，而是可持续扩展的实验闭环。
