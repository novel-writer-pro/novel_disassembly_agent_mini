# Novel Ingest & Chapter Split Standard / 小说导入、切章与保存规范

这份文档回答 5 个问题：

1. 系统当前如何自动切章。
2. 上传小说时推荐使用什么格式。
3. 原文是如何保存的，续跑/续传时应该怎么做。
4. 当前已经支持哪些导入接口。
5. `chapter list` 的逐章/多章导入应该如何组织，方便后续长期保留。

---

## 1. 当前自动切章标准

当前切章器是 `novel_analyzer/preprocessing/chapter_splitter.py`，默认版本：
- `chapter_splitter_version=heuristic-v1`

### 1.1 当前已识别标题模式
系统当前会把下面两类标题识别为章节边界：

- `第1章 标题`
- `第一节 标题` / `第2节 标题`

也就是说，至少支持：
- `第 + 数字 + 章`
- `第 + 数字 + 节`

其中数字当前以阿拉伯数字为主，例如：
- `第1章`
- `第2节`

### 1.2 重复标题去重规则
如果原文里连续出现重复标题，例如：

```text
第1章 大器晚成
第1章 大器晚成
正文
```

系统会自动塌缩为一个有效章节起点，而不会错误切成两个空章。

### 1.3 inspect-novel 会给出的关键信号
在正式导入前，建议先运行：

```bash
./.venv/bin/novel-analyzer inspect-novel /path/to/novel.txt
```

重点看：
- `raw_heading_count`
- `normalized_chapter_count`
- `duplicate_heading_count`
- 前几个识别到的标题样例

解释：
- `raw_heading_count=0`：说明当前标题格式没有被识别
- `normalized_chapter_count=0`：说明无法切出有效章节
- `duplicate_heading_count>0`：说明存在连续重复标题，系统会自动去重

---

## 2. 推荐上传格式

### 2.1 最推荐格式：全书单文件纯文本
推荐：
- UTF-8 编码
- 一个 `.txt` 文件
- 每章都显式带标题

推荐示例：

```text
第1章 青华
正文……

第2章 厌物丽人同行
正文……

第3章 狡舌
正文……
```

### 2.2 可接受格式：节级标题
目前也支持：

```text
第一节 青华
正文……

第二节 厌物丽人同行
正文……
```

但为了最稳定的下游处理，仍建议你在正式生产导入时优先统一成：
- `第N章 标题`

### 2.3 不推荐格式
以下格式容易让切章不稳定：
- 没有显式章节标题
- 标题夹杂目录、卷首语、广告、作者感言
- 标题格式在全书中频繁切换（例如一半是 `第一节`，一半是 `Chapter 3`）
- 把多章正文直接连在一起且没有清晰分隔

---

## 3. 小说保存方法与续传/续跑原则

## 3.1 原始小说文件的保存位置
当前上传/导入后的原文会持久化保存在：

- `.cache/novel-analyzer/uploads/`

这意味着：
- 原文不会只留在 `/tmp`
- 后续章节回看、导出、复跑时仍可定位原文

## 3.2 数据库存储层次
当前导入后会落 3 层核心结构：

1. `novel_sources`
   - 对应一本导入源小说
   - 保存 `title / source_path / source_hash / metadata_json`

2. `chapter_manifests`
   - 对应一次切章结果
   - 保存 `splitter_version / chapter_count / notes`

3. `chapter_segments`
   - 对应每一章/节的切分结果
   - 保存：
     - `raw_heading`
     - `normalized_chapter_no`
     - `normalized_title`
     - `start_offset / end_offset`

## 3.3 续跑不是重新导入
如果只是分析中断，应该优先：
- `resume-run`
- `retry-chapter`
- `retry-failed-jobs`
- `repair-branch`

而不是重复 `ingest`。

也就是说：
- **续跑/续分析**：沿用原 `run_id / branch_id`
- **重新导入新版本原文**：才需要重新 `ingest`

## 3.4 续传的推荐做法
如果小说内容后续还会继续追加，推荐：

### 方案 A：整本重导入（当前最稳）
适合：
- 原文发生较大变动
- 想重新生成一份完整 manifest

### 方案 B：保留 chapter list 边界后再导入
适合：
- 你自己已经有比较稳定的分章结果
- 想降低切章器误判概率

---

## 4. 当前已经支持的导入接口

## 4.1 CLI：全书文本导入
```bash
./.venv/bin/novel-analyzer ingest /path/to/novel.txt --title '小说名'
```

## 4.2 CLI：导入 + 建 run + 可选自动推进
```bash
./.venv/bin/novel-analyzer auto-run /path/to/novel.txt --max-chapters 0
```

## 4.3 CLI：chapter list 导入（新）
```bash
./.venv/bin/novel-analyzer ingest-chapter-list /path/to/chapters.json --title '小说名'
```

支持两种 JSON：

### 直接 list
```json
[
  {"title": "青华", "content": "正文1"},
  {"title": "厌物丽人同行", "content": "正文2"}
]
```

### object + chapters
```json
{
  "chapters": [
    {"title": "青华", "content": "正文1"},
    {"title": "厌物丽人同行", "content": "正文2"}
  ]
}
```

### 字段兼容
每章当前兼容这些字段：
- 标题字段：`raw_heading` / `title` / `chapter_title` / `normalized_title`
- 正文字段：`content` / `text` / `body`

如果只给 `title`，系统会自动合成：
- `第1章 title`
- `第2章 title`

## 4.4 API：整本上传导入
当前原型后端支持：
- `POST /api/import`

### multipart 文件上传
- `file`
- `title`
- `pipeline_profile`
- `max_chapters`
- `database_url`

## 4.5 API：chapter list 导入（新）
`POST /api/import` 现在也接受 JSON body：

```json
{
  "title": "章节导入样例",
  "pipeline_profile": "auto-lite",
  "max_chapters": 0,
  "chapters": [
    {"title": "青华", "content": "正文1"},
    {"title": "厌物丽人同行", "content": "正文2"}
  ]
}
```

适合：
- 你已经在外部做了切章
- 你希望按“逐章/多章列表”明确控制导入边界
- 你想避免真实原文标题格式对切章器的影响

---

## 5. chapter list 逐章 / 多章导入规范

为了方便后续长期保留接口，推荐统一采用下面的 canonical shape：

```json
{
  "title": "作品名",
  "source_name": "optional-batch-name",
  "chapters": [
    {
      "raw_heading": "第一节 青华",
      "title": "青华",
      "content": "章节正文..."
    },
    {
      "raw_heading": "第二节 厌物丽人同行",
      "title": "厌物丽人同行",
      "content": "章节正文..."
    }
  ]
}
```

### 5.1 单章导入
如果只导一章，也建议仍用 `chapters` list：

```json
{
  "chapters": [
    {"title": "青华", "content": "正文"}
  ]
}
```

### 5.2 多章批量导入
直接在 `chapters` 里按顺序排列即可。

### 5.3 为什么推荐保留 chapter list 接口
因为它能解决三类真实问题：
1. 原站标题格式不统一
2. 已有人工整理好的章节边界
3. 续传时只想补部分章节，而不是整本重切

---

## 6. 上传与续传建议

### 6.1 如果你手上是原始小说 txt
优先走：
- `inspect-novel`
- `ingest`

### 6.2 如果你手上已经有分章结果
优先走：
- `ingest-chapter-list`
- 或 `POST /api/import` + `chapters`

### 6.3 如果要继续分析已有分支
不要重复上传；优先走：
- `resume-run`
- `retry-chapter`
- `retry-failed-jobs`
- `repair-branch`

---

## 7. 当前实践建议

当前最稳的生产建议是：
1. 上传前先 `inspect-novel`
2. 能统一成 `第N章 标题` 就统一
3. 如果原文格式杂乱，优先转成 `chapter list` 再导入
4. 分析中断时优先续跑，不要重复 ingest
5. 把原文、chapter list、run/branch id 一起保留，便于后续复现
