# Level-3 诊断版:1 章 dry-run 重跑 — 2026-05-13

## TL;DR

> **Quick Summary**:用当前 prompt 对 BAD 分支最脏的 1 章重跑 LLM(不写 DB),对比新旧 `key_entities`,验证 §4 假设 A/C 的相对权重。
>
> **Deliverables**:
> - 一次性脚本 `/tmp/l3_dryrun.py`(不入库)
> - 实测结果追加到 `docs/foundation-optimization/entity-extraction-noise-diagnosis-20260513.md` §9
> - 1 个 atomic commit
>
> **Estimated Effort**: 0.5 天
> **Cost**: ¥0.1-0.3 LLM,无 DB 写入

---

## Context

### 用户原话(P0 三选一里选 A)
> "我选择A" — 即"做 Level 3 诊断版 — 1 章,不写 DB"

### 选择的目标章节

`e5becabd-e2f3-4045-9249-fa91f382dc9a` ch16(诛仙第十六章 驱物)
- 当前 stored `key_entities`: `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']`
- 5 项里 4 项都是噪声(80%),是 BAD 分支里最差的样本
- 同分支 ch1 的 `key_entities` 是干净的(`['青云门','青云子','张小凡',...]`)→ 同 prompt 不同章节差异大,值得隔离

### 已有调查(§7 §8)结论汇总
- **§7**:噪声分布量化(GOOD 96.6% / BAD-b2 90.6% / BAD-b3 78.2%)
- **§8**:Hypothesis A(prompt 缺负样本)+ C(后处理无过滤)成立,D(prompt 飘移)排除
- **§9 任务**:用同一份 prompt 重跑 ch16,看新输出的 `key_entities` 是否仍有噪声
  - 如果**仍有相同类型噪声** → 假设 A 主因(prompt 本身不够),修 prompt 优先级最高
  - 如果**新输出干净** → 历史抽取时存在 transient 因素(模型不稳定 / context 注入差异 / merged-stage JSON 截断),修后处理过滤优先级最高,prompt 改动可暂缓
  - 如果**部分变化** → 两者都有贡献

---

## Work Objectives

### Must Have
- 找到 ch16 的章节原文(可能在 chapter_raw_outputs 的 invocation_metadata,或某个 manifests 表;executor 先 grep 定位)
- 用 `novel_analyzer.skills.assets.render_skill_prompt('chapter-intake-and-facts', payload)` 渲染当前 prompt
- 用 `novel_analyzer.llm.client.build_chat_model()` 调 LLM 一次
- 解析返回 JSON,提取 `facts.characters[].label` 作为 new_key_entities
- 对比表格:term / 旧分类 / 新输出是否还包含
- 写入 §9 追加诊断备忘

### Must NOT Have (Guardrails)
- **不写 DB** — 不通过 `analysis_service.process_chapter` 路径,直接调 LLM 客户端
- **不修 prompt** — 用现行 prompt 原样
- **不持久化任何 chapter_artifacts**
- **不修 `analysis_service.py:773`**
- **不替代 §5 全套 Level 2-3 排查规划**(本任务只覆盖 1 章 dry-run)
- **不合并到 main prompt** — 一次性脚本,跑完销毁

### Verification Strategy
- LLM 返回必须是合法 JSON(否则记 retry × 2 后报错并标注)
- 输出向用户报告:旧 entities / 新 entities / 是否仍有噪声
- 保留 LLM 输出 JSON 文件到 `.sisyphus/evidence/l3-dryrun-e5becabd-ch16-20260513.json`(供未来复盘)
- 一次成功就够,不做 N 轮统计(本身是诊断不是 benchmark)

---

## TODOs

### Phase 1 — 定位章节原文 + 写一次性脚本

- [ ] 1. **写 `/tmp/l3_dryrun.py`**

  **What to do**:
  
  Step 1: 找 ch16 原文。可能位置依次:
  - `chapter_raw_outputs.invocation_metadata`(最可能)
  - 通过 `chapter_segments` join `chapter_manifests` 找原始 txt 文件
  - 通过 `branch.source_path` 读文件

  Step 2: 渲染 prompt:
  ```python
  from novel_analyzer.skills.assets import render_skill_prompt
  payload = {
      'chapter_index': 16,
      'normalized_title': '...',  # 从 chapter_segments 拿
      'previous_summary': '',
      'prior_context_json': '{}',
      'graph_context_json': '{}',
      'state_summary_json': '{}',
      'chapter_content': chapter_text,
  }
  prompt = render_skill_prompt('chapter-intake-and-facts', payload)
  ```

  Step 3: 调 LLM:
  ```python
  from novel_analyzer.llm.client import build_chat_model
  model = build_chat_model()
  resp = model.invoke(prompt)
  raw_text = resp.content
  ```
  
  Step 4: 解析 + 提取:
  - 用 `novel_analyzer.services.analysis_service.AnalysisService._extract_json_payload` 风格的 regex 提 JSON
  - 取 `data['facts']['characters']`,提 label 列表
  - 对比 stored `['第十六章', '驱物', '汪汪汪', '吱吱吱吱', '犬吠声与']`

  Step 5: 输出报告:
  ```
  === L3 dry-run e5becabd ch16 ===
  stored entities: [...]
  new entities:    [...]
  removed: [...]      # 旧有 + 新无
  added:   [...]      # 旧无 + 新有
  preserved: [...]    # 旧有 + 新有
  noise classification (rule-based, same as §7):
    stored: ordinal=1, onomatopoeia=2, truncated_tail=2, valid=0
    new:    [...]
  verdict: [hypothesis A 主因 / hypothesis C 主因 / 两者都有 / 难以判断]
  ```
  
  Step 6: 保存 JSON evidence:
  ```
  .sisyphus/evidence/l3-dryrun-e5becabd-ch16-20260513.json
  {
    "branch_id": "...",
    "chapter_index": 16,
    "stored_key_entities": [...],
    "new_key_entities": [...],
    "new_full_facts": {...},  # 完整 facts 对象
    "llm_model": "...",
    "prompt_chars": N,
    "response_chars": N,
    "elapsed_sec": N
  }
  ```

  **Must NOT do**:
  - 不调 `analysis_service.process_chapter` 任何路径
  - 不写 chapter_artifacts / chapter_raw_outputs
  - 不打印章节全文(只摘要,避免长输出)
  - 不重试超过 2 次(一次成功就够)

  **Acceptance Criteria**:
  - [ ] 脚本运行结束,产生 evidence JSON
  - [ ] 终端输出明确的 "verdict:" 行
  - [ ] DB 没有新写入(可 SELECT count 前后对比)

### Phase 2 — 把结果追加到 §9

- [ ] 2. **追加 §9 到 `entity-extraction-noise-diagnosis-20260513.md`**

  **What to do**:

  结构(follow §7 §8 的风格):
  ```markdown
  ## 9. Level-3 诊断版执行结果(2026-05-13)
  
  > §8 把根因缩到假设 A+C,本节用 1 章 dry-run 隔离 prompt 本身 vs 章节内容因素。
  
  ### 9.1 实验设置
  - 目标:`e5becabd-e2f3-4045-9249-fa91f382dc9a` ch16(诛仙 驱物)
  - 当前 prompt 原样调用,不修改任何代码
  - 不写 DB(脚本只读 + 调 LLM 一次)
  - LLM 配置:`{model_name}`(通过 build_chat_model 默认)
  - Evidence: `.sisyphus/evidence/l3-dryrun-e5becabd-ch16-20260513.json`
  
  ### 9.2 输出对比
  
  | | stored(2026-05-13 历史) | new(本次重跑) |
  |---|---|---|
  | key_entities | [...] | [...] |
  | 噪声分类(规则) | ordinal=1 / onomatopoeia=2 / truncated_tail=2 / valid=0 | ordinal=N / onomatopoeia=N / truncated_tail=N / valid=N |
  
  ### 9.3 判定
  - [新输出仍含相同噪声 → 假设 A 是主因]
  - [新输出干净 → 假设 C(后处理过滤)更优先;历史抽取受 transient 因素]
  - [部分变化 → 两者都有贡献]
  
  ### 9.4 推论
  - 修复优先级 reorder:[基于 9.3 判定填]
  - 仍未排除的因素:[填,如 complexity router 副作用 / context 注入差异]
  
  ### 9.5 不立即做的事(同 §6/§8 原则保持)
  ```

  **Must NOT do**:
  - 不在备忘里贴出 prompt 修改 PR
  - 不把判定上升为"必须立即修"

  **Acceptance Criteria**:
  - [ ] §9 追加在 §8 之后
  - [ ] 9.2 表格数字与 evidence JSON 一致
  - [ ] 9.3 判定明确(三选一,不要含糊)

### Phase 3 — 清理 + commit

- [ ] 3. **commit + 清理**
  - `rm /tmp/l3_dryrun.py`(脚本不入库,evidence JSON 入 .sisyphus/evidence/)
  - git add `.sisyphus/evidence/l3-dryrun-e5becabd-ch16-20260513.json` + 修改的 memo
  - **注意**:`.sisyphus/evidence/` 目前未 tracked(`.gitignore` 可能排除),executor 需检查 — 若被忽略,改为 commit 到 `docs/foundation-optimization/evidence/` 或在 commit 里包 inline JSON
  - Lore commit:
    ```
    Append L3 dry-run findings: hypothesis [A/C/both] confirmed
    
    1-chapter re-run with current prompt on e5becabd ch16 (worst BAD
    sample) shows [verdict summary]. [...]
    
    Constraint: 1 chapter is anecdotal — N≥5 required for statistical claim
    Confidence: high (single-chapter signal) / medium (generalization)
    Scope-risk: narrow (memo append + 1 evidence JSON)
    Tested: LLM call returned valid JSON, no DB write
    Not-tested: chapter content variance (15+/91 chapters not sampled)
    Directive: do not deploy fix until §10 (broader sample) confirms
    ```

---

## Commit Strategy

1 atomic commit covering §9 + evidence JSON.

---

## Success Criteria

- [ ] LLM 真实调用一次,evidence JSON 落地
- [ ] §9 追加且结论明确
- [ ] DB chapter_artifacts 行数前后一致(可校验)
- [ ] /tmp/l3_dryrun.py 已删除
- [ ] 1 atomic commit Lore 格式

---

## Notes for the Executor

1. 章节原文位置:**先用 1 分钟 grep** `chapter_text|raw_chapter_text|chapter_content` in services/, 找 process_chapter 的输入源,大概率从 `chapter_raw_outputs.invocation_metadata` 或独立 manifest 文件读
2. 如果章节内容找不到,**回退方案**:用 `chapter_raw_outputs.parsed_json` 反推(可能含 cleaned_text 字段)— 这样 prompt 输入就用历史 cleaned_text,与原始抽取条件一致
3. LLM 调用如果失败,**重试 1 次**就停,不要写复杂重试逻辑(一次性脚本)
4. 输出尽量精简:旧/新 entities + 判定一行,不要 dump 完整 facts JSON 到终端(放 evidence 文件)
5. 写完后跑 grep `git status` 自检无未预期改动
6. evidence JSON 位置选择:
   - 优先 `.sisyphus/evidence/`(若已 tracked)
   - 否则 `docs/foundation-optimization/evidence/`(新建目录)
   - executor 自己决定,在 commit 里说明
