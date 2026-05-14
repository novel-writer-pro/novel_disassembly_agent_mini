# 拆书输入规范 (novel.txt)

## 概述

拆书系统通过 `IngestService.ingest_text_file(path, title)` 导入小说文本。导入时自动进行章节切分，切分器基于正则匹配章节标题行。

---

## 文件格式要求

| 项目 | 要求 |
|------|------|
| 编码 | UTF-8 (必须) |
| 文件类型 | 纯文本 .txt |
| 换行符 | `\n` (Unix) 或 `\r\n` (Windows) 均可 |
| 文件大小 | 无硬限制，已验证 5.2MB / 775 章 |

---

## 章节标题格式

切分器识别的标题模式：

```
第{数字}章 {标题}
第{数字}节 {标题}
```

### 支持的数字格式

| 格式 | 示例 |
|------|------|
| 阿拉伯数字 | `第1章 大器晚成` |
| 中文数字 | `第一章 大器晚成` |
| 混合 | `第十二章 觉醒` |

### 正则表达式

```python
r"^第\s*(?P<number>\d+|[零一二三四五六七八九十百千两]+)\s*(?P<unit>章|节)(?P<rest>[^\n]*)"
```

### 合法标题示例

```
第1章 大器晚成
第二章 命格觉醒
第100章 突破
第一百二十三章 决战
第3节 修炼
```

### 不合法标题（不会被识别）

```
Chapter 1 Beginning        ← 英文格式
第一回 起始               ← "回"不在识别范围
【第1章】大器晚成         ← 有额外符号包裹
1. 大器晚成               ← 纯数字序号
```

---

## 标准输入示例

```text
第1章 大器晚成

郑国，庆丰府。
青木县。
李宅。
夜色深沉。
三更天，卫图掐准生物钟，揉了揉惺忪的睡眼，从土炕上翻身而起。
"喂马的活计什么时候才能结束。"
卫图坐在马厩外面的青石上，从腰间摸出了一个旱烟杆子。

第2章 命格觉醒

卫图从床上坐起来，感觉体内有一股暖流涌动。
命格：大器晚成。
他知道自己的命运从此改变了。

第3章 养生功

清晨，卫图开始修炼养生功。
这是他在李宅偷学到的唯一功法。
```

---

## 注意事项

### 重复标题处理

如果同一章标题连续出现两次（某些网站抓取会重复），系统会自动合并：

```text
第1章 大器晚成

第1章 大器晚成
正文内容...
```

→ 自动识别为 1 章，不会切成 2 章。

### 章节前内容

标题之前的内容（如书名、作者信息、简介）会被忽略，不计入任何章节。

### 章节内格式

章节正文内部无格式要求：
- 段落用空行分隔或不分隔均可
- 对话用引号或不用均可
- 可以包含作者注、求收藏等（系统会在 intake 阶段标记）

### 最佳实践

1. 确保每章标题独占一行
2. 标题与正文之间建议有一个空行
3. 章节编号建议连续（第1章、第2章、第3章...）
4. 避免在正文中出现"第X章"格式的文本（会被误识别为新章节）
5. 文件开头的非章节内容（简介等）会被自动跳过

---

## 导入命令

### CLI

```bash
.venv/bin/python -m novel_analyzer.cli.app ingest /path/to/novel.txt --title "小说名"
```

### API

```bash
curl -X POST http://localhost:8000/api/import \
  -F "file=@/path/to/novel.txt" \
  -F "title=小说名"
```

### Python

```python
from novel_analyzer.services.ingest_service import IngestService
from novel_analyzer.database.session import create_session_factory
from novel_analyzer.config.settings import Settings

factory = create_session_factory(Settings())
with factory() as session:
    novel, manifest = IngestService(session).ingest_text_file('/path/to/novel.txt', '小说名')
    print(f'导入成功: {manifest.chapter_count} 章')
```

---

## 导入后验证

导入后可通过以下方式验证切分结果：

```bash
# 查看切分预览
.venv/bin/python -m novel_analyzer.cli.app inspect-novel /path/to/novel.txt

# 查看已导入的章节列表
.venv/bin/python -m novel_analyzer.cli.app show-chapters --branch-id <branch_id>
```

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 章节数为 0 | 标题格式不匹配 | 检查是否用了"第X章"格式 |
| 章节数异常多 | 正文中有"第X章"文本 | 清理正文中的章节引用 |
| 某章内容为空 | 连续两个标题之间无正文 | 检查是否有空章节 |
| 编码错误 | 文件不是 UTF-8 | 用 `iconv` 转换编码 |
| 中文数字识别错误 | 超出支持范围 | 改用阿拉伯数字 |
