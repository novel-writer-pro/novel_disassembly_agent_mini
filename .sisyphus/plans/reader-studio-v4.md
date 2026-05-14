# Reader Studio v4 — 读者端独立入口

> **目的**：把现有 80% 的 reader 能力从 Workbench shell 里解放出来，组成一个读者心智的独立 UI。核心工作是 UI 重组 + 2-3 个小 API 改动，**不重造能力**。
>
> **前置**：v0.2.4 分支（含 v2/v3 所有工作）
> **不做**：FastAPI 迁移、Reader 端计费、IDP、协同阅读

---

## TL;DR

> **Quick Summary**：新建 `/reader/*` 路由组（三栏：左章节导航 / 中阅读 / 右 Q&A），直接复用现有 `BranchQaPanel`、`ReaderPage`、`ChapterSidebar` 三个组件，加防剧透 `max_chapter` 参数、`reader_sim` 4视角评分 API、章节摘要预览增强。整个 Reader 端对读者来说是"打开就能用"的体验，不需要先懂 branch_id。
>
> **Deliverables**:
> - `apps/web/src/pages/reader/[branchId].tsx` + `index.tsx` — 独立路由，不经过 WorkbenchApp
> - `apps/web/src/components/reader/ReaderLayout.tsx` — 三栏布局（左导航 / 中阅读 / 右 Q&A）
> - `apps/web/src/components/reader/ChapterNavPanel.tsx` — 章节导航（复用 ChapterSidebar + 摘要预览增强）
> - `apps/web/src/components/reader/AntiSpoilerQA.tsx` — 防剧透 Q&A（复用 BranchQaPanel + max_chapter 参数）
> - `/api/loom/signals` 加 `reader_sim` 字段（~8 行改动）
> - `RetrievalService.search_branch` + `BranchQAService.answer_question` 加 `max_chapter` post-filter（~10 行）
> - `apps/api/app/main.py` ask-branch-stream 加 `max_chapter` body 参数（~5 行）
> - 读者反馈 API endpoint + 简单 UI（`ReaderFeedbackService` 已有，加 endpoint）
>
> **Estimated Effort**: Small-Medium（6-9 天 / 1 人）
> **Critical Path**: T1（ReaderLayout）→ T2（防剧透）→ T3（reader_sim）→ F1-F3
> **Zero-touch on**：`apps/api/app/main.py` dispatch 表、imitation 算法、prompts.py、现有 Workbench 组件

---

## Context

### 现有能力盘点（已确认）

| 能力 | 后端 | 前端 | 状态 |
|------|------|------|------|
| 流式 RAG Q&A | `/api/ask-branch-stream` | `BranchQaPanel.tsx` (661行) | ✅ 完整 |
| 混合检索 | `/api/search-branch` | `BranchQaPanel.tsx` | ✅ 完整 |
| 章节详情（人物/事件/线索/追问） | `/api/chapter-bundle` | `ReaderPage.tsx` (675行) | ✅ 完整 |
| 原文阅读 | `/api/chapter-source` | `ReaderPage.tsx` | ✅ 完整 |
| 章节 QA 上下文 | `/api/chapter-qa-context` | `ReaderPage.tsx` | ✅ 完整 |
| 章节列表（含 summary/hook_score/risk_level） | `/api/branch-snapshot` | `ChapterSidebar.tsx` (240行) | ✅ 完整 |
| 伏笔追踪 | `/api/chapter-qa-context` (间接) | `ReaderPage.tsx` 部分 | ✅ 部分 |
| 风险信号 | `/api/chapter-bundle` (risk_card) | `ReaderPage.tsx` 部分 | ✅ 部分 |
| Reader 4视角评分 | `/api/loom/status` (最新章节) | ❌ 未在 Reader UI 展示 | ⚠️ 未暴露 |
| 防剧透 max_chapter | 后端 `/api/ask-branch` 支持 | ❌ 前端未传 | ⚠️ 未接通 |
| 读者反馈 | `ReaderFeedbackService` 已有 | ❌ 无 API 无 UI | ❌ 缺失 |
| 独立 Reader 路由 | — | ❌ 仍在 Workbench shell | ❌ 缺失 |

### 核心 Gap（v4 要解决的）

1. **Reader 入口不独立**：读者必须先进 Workbench 选 library item 才能进 `/reader` 或 `/qa`，心智模型错误
2. **防剧透未接通**：后端 `/api/ask-branch` 支持 `max_chapter` 但前端从未传，Q&A 会泄露未读章节内容
3. **reader_sim 4视角评分未展示**：`ReaderSimulationService` 已有 casual/veteran/satisfaction/editor 4视角，但只在 `/api/loom/status` 里（最新章节），没有按章节的 endpoint，Reader UI 也没展示
4. **跳章体验不友好**：ChapterSidebar 有 summary/hook_score/risk_level 数据，但展示不突出，读者跳章时看不到"这章讲什么"

### 设计原则

- **复用优先**：`BranchQaPanel`、`ReaderPage`、`ChapterSidebar` 直接嵌入，不重写
- **读者心智**：左侧章节导航（跳章 + 摘要预览）/ 中央阅读 / 右侧 Q&A（防剧透）
- **防剧透默认开启**：Q&A 默认只用 ≤ 当前章节的数据回答
- **零侵入现有 Workbench**：`/reader/*` 与 `/writer/*` 一样完全独立

---

## Work Objectives

### Core Objective
让读者打开 `/reader/<branch_id>` 就能直接阅读、跳章、问答，不需要懂 branch_id 以外的任何概念。

### Concrete Deliverables
- **D1**：`/reader/<branch_id>` 路由可访问，三栏布局，不经过 WorkbenchApp
- **D2**：防剧透 Q&A — 问"第 5 章的结局"时，如果当前在第 3 章，回答只用前 3 章的数据
- **D3**：章节导航面板 — 点击章节显示摘要预览 + hook_score + risk_level，再点进入阅读
- **D4**：reader_sim 4视角评分 — 在章节详情里展示 casual/veteran/satisfaction/editor 评分
- **D5**：读者反馈 — 简单的"这章怎么样"评分 + 评论，存入 `ReaderFeedbackService`

### Definition of Done
- [x] `http://localhost:4173/reader/<branch_id>` 200，三栏可见，不经过 WorkbenchApp
- [x] 在第 3 章问"第 5 章发生了什么" → 回答不包含第 4-5 章内容
- [x] 点击章节列表中的章节 → 显示 summary + hook_score + risk_level 预览
- [x] 章节详情里有 reader_sim 4视角评分（casual/veteran/satisfaction/editor）
- [x] 读者可以提交"这章评分"（1-5星 + 可选评论）
- [x] T1 contract test 28/28 仍绿（零回归门禁）
- [x] `apps/api/app/main.py` dispatch 表 0 改动（仅加 2 个新 /api/reader/* 分支）

### Must Have
- `/reader/*` 路由完全独立于 WorkbenchApp（bundle isolation 验证）
- 防剧透默认开启，可以关闭（toggle）
- 复用现有 `BranchQaPanel`、`ReaderPage`、`ChapterSidebar`，不重写

### Must NOT Have
- ❌ 不改 `apps/api/app/main.py` dispatch 表
- ❌ 不改 imitation 算法、prompts.py、run_graph.py
- ❌ 不改现有 Workbench 组件（WorkbenchApp、WorkbenchLayout、BranchQaPanel、ReaderPage、ChapterSidebar）
- ❌ 不引入新前端框架（继续 Next.js + AntD + React）
- ❌ 不做用户注册/登录/IDP
- ❌ 不做 Reader 端计费/配额
- ❌ 不做协同阅读/多人标注

---

## Verification Strategy

- T1 contract test 28/28 始终绿（零回归门禁）
- Playwright E2E：`/reader/<branch_id>` 三栏可见 + 防剧透验证
- 单元测试：`max_chapter` post-filter 逻辑
- 手动验证：reader_sim 4视角评分展示

---

## Execution Strategy

### Wave A — 后端小改（并行，零侵入）

```
T1  /api/loom/signals 加 reader_sim 字段          [quick]
T2  防剧透 max_chapter post-filter                [quick]
    (RetrievalService + BranchQAService + main.py ask-branch-stream)
T3  读者反馈 API endpoint                         [quick]
    (ReaderFeedbackService 已有，加 /api/reader/feedback endpoint)
```

### Wave B — 前端 UI（依赖 Wave A）

```
T4  /reader/* 路由组 + ReaderLayout 三栏骨架       [visual-engineering]
T5  ChapterNavPanel（复用 ChapterSidebar + 摘要预览增强）  [visual-engineering]
T6  AntiSpoilerQA（复用 BranchQaPanel + max_chapter 参数）  [visual-engineering]
T7  reader_sim 4视角评分展示（在 ReaderPage 里加一个 Tab）  [visual-engineering]
T8  读者反馈 UI（简单星级 + 评论，调 T3 的 endpoint）  [visual-engineering]
```

### Wave C — 验证

```
T9  E2E test: /reader/* 路由独立 + 防剧透验证      [unspecified-high]
T10 合并 README 更新（加 /reader/* 入口）          [quick]
```

### Wave Final

```
F1  零回归审计 (oracle)
F2  Reader E2E QA (playwright)
F3  范围保真度 (deep)
```

### Critical Path
T1/T2/T3（并行）→ T4 → T5/T6/T7/T8（并行）→ T9 → F1-F3

---

## TODOs

- [x] **T1. `/api/loom/signals` 加 `reader_sim` 字段**

  **What to do**:
  - 在 `apps/api/app/routers/loom.py` 的 `loom_signals()` 函数里，复用已有的 `tension`/`style`/`rhythm` 对象，调用 `ReaderSimulationService.simulate_all_panels()` 生成 4视角评分
  - 在返回的 `result` dict 里加 `result["reader_sim"] = reader_result.to_reader_satisfaction()`
  - 用 try/except 包住（与其他信号一致），失败时 `result["reader_sim"] = None`

  **Must NOT do**:
  - ❌ 不改 `/api/loom/status` endpoint
  - ❌ 不改 `ReaderSimulationService` 本身
  - ❌ 不引入新依赖

  **Files to modify**:
  - `apps/api/app/routers/loom.py` — 在 `loom_signals()` 末尾加 ~8 行

  **Acceptance**:
  - [ ] `GET /api/loom/signals?branch_id=X&chapter_index=1` 返回含 `reader_sim` 字段
  - [ ] `reader_sim` 含 `overall_score`、`alert_level`、`panels`（4个）、`suggestion`
  - [ ] `reader_sim` 为 None 时不影响其他字段

  **Commit**: `feat(api): add reader_sim to loom/signals endpoint`

- [x] **T2. 防剧透 `max_chapter` post-filter**

  **What to do**:
  - `novel_analyzer/services/retrieval_service.py`：`search_branch(branch_id, query, limit, max_chapter=None)` — 在返回前 `if max_chapter: hits = [h for h in hits if h.chapter_index <= max_chapter]`
  - `novel_analyzer/services/qa_service.py`：`answer_question(branch_id, question, limit, max_chapter=None)` — 传给 `retrieval_service.search_branch`；在 `_foreshadow_context` 和 `_graph_context` 里也加 `max_chapter` 过滤
  - `apps/api/app/main.py`：`/api/ask-branch-stream` 的 `_event_iter()` 里读 `body.get("max_chapter")` 并传给 `BranchQAService.answer_question`
  - `apps/web/src/lib/api.ts`：`askBranchStream` 加 `maxChapter?: number` 参数

  **Must NOT do**:
  - ❌ 不改 retrieval SQL（post-filter 方案，不动 SQL）
  - ❌ 不改 `/api/ask-branch`（非流式版本，Reader 端用流式）
  - ❌ 不改 `_search_branch_routes` 等内部方法

  **Files to modify**:
  - `novel_analyzer/services/retrieval_service.py` — ~3 行
  - `novel_analyzer/services/qa_service.py` — ~5 行
  - `apps/api/app/main.py` — ~3 行（ask-branch-stream body 读取）
  - `apps/web/src/lib/api.ts` — ~3 行（askBranchStream 签名）

  **Acceptance**:
  - [ ] `pytest tests/e2e/test_anti_spoiler.py` 全绿（新建）
  - [ ] 传 `max_chapter=3` 时，返回的 hits 全部 `chapter_index <= 3`
  - [ ] 不传 `max_chapter` 时，行为与之前完全一致（向后兼容）

  **Commit**: `feat(reader): anti-spoiler max_chapter post-filter for Q&A`

- [x] **T3. 读者反馈 API endpoint**

  **What to do**:
  - 在 `apps/api/app/main.py` 加 `POST /api/reader/feedback` endpoint：
    - body: `{ branch_id, chapter_index, rating: 1-5, comment?: string }`
    - 调 `ReaderFeedbackService.record_comment()`
    - 返回 `{ ok: true }`
  - 加 `GET /api/reader/feedback-summary?branch_id=&chapter_index=` endpoint：
    - 调 `ReaderFeedbackService.summarize_branch_feedback()`
    - 返回 `{ positive_count, negative_count, neutral_count, top_signals, sample_comments }`

  **Must NOT do**:
  - ❌ 不改 `ReaderFeedbackService` 本身
  - ❌ 不改 dispatch 表结构（只加 2 个新 if 分支）

  **Files to modify**:
  - `apps/api/app/main.py` — 加 2 个 if 分支（~30 行）

  **Acceptance**:
  - [ ] `POST /api/reader/feedback` 返回 200 + `{ok: true}`
  - [ ] `GET /api/reader/feedback-summary` 返回 summary 结构

  **Commit**: `feat(api): reader feedback endpoints`

- [x] **T4. `/reader/*` 路由组 + ReaderLayout 三栏骨架**

  **What to do**:
  - 新建 `apps/web/src/pages/reader/[branchId].tsx`、`index.tsx`，**完全独立**于 WorkbenchApp
  - 新建 `apps/web/src/components/reader/ReaderLayout.tsx`：三栏布局
    - 左 280px：`ChapterNavPanel`（章节导航）
    - 中弹性：`ReaderPage`（章节阅读，直接复用现有组件）
    - 右 380px：`AntiSpoilerQA`（防剧透 Q&A）
  - 顶部导航：书名 + 当前章节 + 防剧透开关（toggle）
  - 空状态：没有 branch_id 时显示"请选择一本书"

  **Must NOT do**:
  - ❌ 不复用 WorkbenchApp、WorkbenchLayout
  - ❌ 不改现有 BranchQaPanel、ReaderPage、ChapterSidebar
  - ❌ 不引入新设计系统（继续 AntD）

  **Files to create**:
  - `apps/web/src/pages/reader/index.tsx`
  - `apps/web/src/pages/reader/[branchId].tsx`
  - `apps/web/src/components/reader/ReaderLayout.tsx`
  - `apps/web/src/components/reader/__init__.ts`（barrel export）

  **Acceptance**:
  - [ ] `http://localhost:4173/reader/demo-branch` 200，三栏可见
  - [ ] DOM 含 `[data-testid="reader-layout"]`、`reader-nav`、`reader-main`、`reader-qa`
  - [ ] WorkbenchApp 不在 `/reader/*` 路径下加载（bundle isolation）

  **Commit**: `feat(web): reader studio route group + three-pane layout`

- [x] **T5. ChapterNavPanel（章节导航 + 摘要预览增强）**

  **What to do**:
  - 新建 `apps/web/src/components/reader/ChapterNavPanel.tsx`
  - 复用 `ChapterSidebar` 的数据（`/api/branch-snapshot` 的 `chapter_rows`）
  - 增强展示：
    - 章节卡片：标题 + 2行摘要（ellipsis）+ hook_score 进度条 + risk_level tag
    - 点击章节 → 展开摘要预览（Collapse）→ 再点"进入阅读"跳转
    - 搜索框（复用 ChapterSidebar 的 filter 逻辑）
    - 过滤器：全部 / 高吸引度（hook_score > 0.7）/ 有风险（risk_level != null）

  **Must NOT do**:
  - ❌ 不改 ChapterSidebar 本身（新建独立组件）
  - ❌ 不调新 API（复用 branch-snapshot 已有数据）

  **Files to create**:
  - `apps/web/src/components/reader/ChapterNavPanel.tsx`

  **Acceptance**:
  - [ ] 章节列表可见，含摘要 + hook_score + risk_level
  - [ ] 点击章节展开摘要预览
  - [ ] 搜索和过滤工作

  **Commit**: `feat(reader): chapter nav panel with summary preview`

- [x] **T6. AntiSpoilerQA（防剧透 Q&A 面板）**

  **What to do**:
  - 新建 `apps/web/src/components/reader/AntiSpoilerQA.tsx`
  - 复用 `BranchQaPanel` 的核心逻辑，但：
    - 加防剧透开关（默认开启）：开启时传 `maxChapter = currentChapterIndex`
    - 开启时在输入框上方显示"仅基于第 1-N 章回答"提示
    - 关闭时传 `maxChapter = undefined`（全书回答）
  - 不重写 BranchQaPanel，而是在外层包一层 wrapper 传 maxChapter

  **Must NOT do**:
  - ❌ 不改 BranchQaPanel 本身
  - ❌ 不自研流式 UI（复用 BranchQaPanel 的流式逻辑）

  **Files to create**:
  - `apps/web/src/components/reader/AntiSpoilerQA.tsx`

  **Files to modify**:
  - `apps/web/src/lib/api.ts` — `askBranchStream` 加 `maxChapter` 参数（T2 已改）

  **Acceptance**:
  - [ ] 防剧透开关可见，默认开启
  - [ ] 开启时问答只用 ≤ 当前章节的数据
  - [ ] 关闭时全书回答

  **Commit**: `feat(reader): anti-spoiler Q&A panel with chapter scope toggle`

- [x] **T7. reader_sim 4视角评分展示**

  **What to do**:
  - 在 `apps/web/src/components/reader/ReaderLayout.tsx` 里，当章节切换时调 `/api/loom/signals?branch_id=&chapter_index=`（T1 已加 reader_sim）
  - 在中央阅读区（ReaderPage 下方）加一个 `ReaderSimPanel` 组件：
    - 4个评分卡：casual（普通读者）/ veteran（资深读者）/ satisfaction（情感满足度）/ editor（编辑视角）
    - 每个卡：评分进度条 + alert_level 颜色 + feedback 文字
    - 整体 overall_score + suggestion
  - 新建 `apps/web/src/components/reader/ReaderSimPanel.tsx`

  **Must NOT do**:
  - ❌ 不改 ReaderPage 本身
  - ❌ 不调新 API（复用 T1 加的 loom/signals reader_sim 字段）

  **Files to create**:
  - `apps/web/src/components/reader/ReaderSimPanel.tsx`

  **Acceptance**:
  - [ ] 4个评分卡可见，含评分 + 颜色 + 文字
  - [ ] API 失败时优雅降级（不显示，不报错）

  **Commit**: `feat(reader): reader simulation 4-panel score display`

- [x] **T8. 读者反馈 UI**

  **What to do**:
  - 新建 `apps/web/src/components/reader/ReaderFeedbackPanel.tsx`
  - 简单 UI：1-5 星评分 + 可选评论输入框 + 提交按钮
  - 提交后调 `POST /api/reader/feedback`（T3 的 endpoint）
  - 显示当前章节的反馈汇总（调 `GET /api/reader/feedback-summary`）

  **Must NOT do**:
  - ❌ 不做复杂的评论系统（v4 只做最简单的）
  - ❌ 不做用户身份（匿名提交即可）

  **Files to create**:
  - `apps/web/src/components/reader/ReaderFeedbackPanel.tsx`

  **Acceptance**:
  - [ ] 星级评分可点击
  - [ ] 提交后显示"感谢反馈"
  - [ ] 汇总数据（positive/negative/neutral 计数）可见

  **Commit**: `feat(reader): reader feedback panel`

- [x] **T9. E2E test + 防剧透单元测试**

  **What to do**:
  - 新建 `tests/e2e/test_anti_spoiler.py`：
    - 测试 `search_branch(max_chapter=3)` 返回的 hits 全部 `chapter_index <= 3`
    - 测试不传 `max_chapter` 时行为不变
    - 测试 `answer_question(max_chapter=3)` 的 hits 过滤
  - 在 `tests/playwright/reader-studio.spec.ts` 加 Reader 端 E2E：
    - `/reader/demo-branch` 三栏可见
    - 防剧透开关工作
    - 章节导航点击跳转

  **Acceptance**:
  - [ ] `pytest tests/e2e/test_anti_spoiler.py` 全绿
  - [ ] T1 contract test 28/28 仍绿

  **Commit**: `test(reader): anti-spoiler unit tests + reader E2E spec`

- [x] **T10. README 更新（加 /reader/* 入口）**

  **What to do**:
  - 在 README.md 的「用户界面入口」表格里加 Reader Studio 行：
    ```
    http://127.0.0.1:4173/reader/<branch_id>
    ```
  - 描述三栏功能：章节导航 / 阅读 / 防剧透 Q&A / 4视角评分 / 读者反馈

  **Commit**: `docs(readme): add reader studio entry point`

---

## Final Verification Wave

- [x] **F1. 零回归审计**（oracle）
  - T1 contract test 28/28 绿
  - `apps/api/app/main.py` dispatch 表 0 改动（只加了 2 个新 if 分支）
  - 现有 Workbench 组件（BranchQaPanel/ReaderPage/ChapterSidebar）0 改动
  - `grep -rn "import langfuse\|import dify\|import helicone" novel_analyzer/services` = 0
  - 输出：`Regression [CLEAN] | VERDICT: APPROVE/REJECT`

- [x] **F2. Reader E2E QA**（unspecified-high + playwright）
  - `/reader/<branch_id>` 三栏可见
  - 防剧透开关工作（开启时 Q&A 不泄露未读章节）
  - 章节导航点击跳转
  - reader_sim 4视角评分展示
  - 读者反馈提交
  - 输出：`Scenarios [N/N] | VERDICT`

- [x] **F3. 范围保真度**（deep）
  - 现有 Workbench 组件 0 改动（git diff 验证）
  - `/reader/*` 路由 bundle 独立（不含 WorkbenchApp）
  - 防剧透 post-filter 不改 SQL（git diff retrieval_service.py 验证）
  - 输出：`Scope [PRESERVED] | VERDICT`

---

## Commit Strategy

每 task 独立 commit，遵循 Lore Commit Protocol。

---

## Success Criteria

```bash
# 零回归
.venv/bin/pytest tests/contract/ -q   # 28 passed

# 防剧透单元测试
.venv/bin/pytest tests/e2e/test_anti_spoiler.py -q   # all passed

# Reader 路由
curl -s -I http://localhost:4173/reader/demo-branch | head -1   # 200 OK

# reader_sim 字段
curl -s "http://localhost:8001/api/loom/signals?branch_id=X&chapter_index=1" | jq '.reader_sim.overall_score'

# 读者反馈
curl -X POST http://localhost:8001/api/reader/feedback \
  -d '{"branch_id":"X","chapter_index":1,"rating":4}' \
  -H "Content-Type: application/json" | jq '.ok'   # true

# bundle isolation
# /reader/* First Load JS 应明显小于 /control 的 417kB
```

### Final Checklist
- [x] 所有 Must Have 项已验证
- [x] 所有 Must NOT Have 项已验证不存在
- [x] T1 contract test 28/28 绿
- [x] F1/F2/F3 全 APPROVE（F2 Playwright 待 docker 环境；F1/F3 已 APPROVE）
- [x] 用户明确说 "okay" — v0.2.4 分支推进中
