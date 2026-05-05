# Problem Trace

| 问题编号 | 现象 | 所在层 | 严重级别 | 初步原因 | 证据文件 | 建议动作 |
|---|---|---|---|---|---|---|
| P1 | 原始真实文本使用“第一节/第二节”标题导致 ingest chapter_count=0 | 源文本 | P1 | 当前切章器未覆盖节级标题模式 | inspect-original.txt | 扩展 heading parser，支持“第X节”/卷-节模式 |
| P2 | 第2章 small_model_pipeline 的 dialogue_candidates 返回对象而非字符串，触发 schema 校验失败 | 生成 | P1 | 小模型结构化输出与 ChapterIntakeOutput schema 不一致 | list-job-events / run-status | 放宽/兼容 dialogue_candidates schema，或在 intake parser 做对象->字符串适配 |
| P3 |  | 源文本 / 知识 / 检索 / 生成 / 治理 |  |  |  |  |
