# Novel Assistant System Architecture / 小说助手系统架构

## 1. 目标
这个架构文档描述的是“可商业化小说助手”整体能力，不是单个模块。
它强调三点：
- 能力必须独立、可维护、可抽离
- 主链必须可验证、可交接、可运营
- 生成能力必须建立在知识层与门控层之上

## 2. 技术架构图

```mermaid
flowchart TD
    A[Novel Source / 小说源文本] --> B[Ingest + Split]
    B --> C[Chapter Analysis]
    C --> D[Facts / State / Graph / Retrieval Materialization]

    D --> E[Retrieval Layer]
    E --> E1[FTS / Similarity / Like]
    E --> E2[Entity Exact Recall]
    E --> E3[Vector Recall]
    E1 --> E4[RRF Fusion]
    E2 --> E4
    E3 --> E4
    E4 --> E5[Optional Rerank]
    E5 --> F[QA / Search / Diagnostics]

    D --> G[Risk Semantic Layer]
    G --> G1[Signal Store]
    G --> G2[Signal Linking]
    G --> G3[Signal Clustering]
    G1 --> H[Risk Checkers]
    G2 --> H
    G3 --> H
    H --> I[Review Workflow / Branch Report]

    D --> J[Author Knowledge Layer]
    J --> J1[Knowledge Index]
    J --> J2[Entity Profiles]
    J --> J3[Relationship / Rule / Thread Views]

    J --> K[Next Chapter Planning]
    J --> L[Chapter Imitation Harness]
    H --> L
    L --> M[Whole-Book Orchestration]
    M --> N[Repair Lanes / Consistency Diagnostics]

    F --> O[Novel Assistant Capability Pack]
    I --> O
    J --> O
    N --> O
    O --> O1[Original Planning Pack]
    O --> O2[Creation Control Pack]
    O --> O3[Editor Revision Pack]
    O --> O4[Reader Feedback Pack]
    O --> O5[Retrieval Benchmark Summary]
    O --> P[CLI / API / Future Independent Agent Runtime]

    O --> Q[Eval / Freeze Gate / Sample Artifacts]
    Q --> R[Docs / Handoff / Commercial Materials]
```

## 3. 业务架构图

```mermaid
flowchart LR
    A[作者 / 工作室] --> B[小说助手]
    C[编辑 / 审校] --> B
    D[平台内容运营] --> B
    E[IP 开发 / 改编团队] --> B

    B --> F[拆书与知识化]
    B --> G[检索与问答]
    B --> H[风险门控与复核]
    B --> I[续写 / 仿写准备]
    B --> J[整书编排与评估]

    F --> K[知识中台价值]
    G --> L[效率提升价值]
    H --> M[质量与事故成本控制]
    I --> N[产能提升价值]
    J --> O[平台级治理与规模化价值]
```

## 4. 核心设计原则
1. **知识先于生成**：先理解，再写。
2. **门控先于放量**：先可控，再规模化。
3. **能力独立可抽离**：不把系统价值绑在某个外部 agentOS 上。
4. **样例/交付可追踪**：任何关键能力都要有 sample、checkout、handoff、smoke path。

## 5. 当前最重要的未闭环项
- original planning pack 继续前推到卷纲 / 人物成长弧 / story bible
- editor revision / reader feedback pack 接入真实 draft 与真实评论
- whole-book 多 provider 成功样例密度
- 风险语义层的长窗口质量评估
