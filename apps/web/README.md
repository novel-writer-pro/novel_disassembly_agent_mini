# apps/web

独立前端目录。

当前已经提供一个无依赖静态原型：

```bash
cd apps/web
python3 -m http.server 4173
```

然后打开：

`http://127.0.0.1:4173`

用于演示：
- 导入小说入口
- pipeline profile 切换
- run / branch snapshot 展示
- 左侧章节导航 + 右侧详情主视图
- 章节列表点击查看 chapter bundle / QA context
- 原始章节正文回看
- 拆书中的 `第N章` 引用跳转
- recovery 动作矩阵
- export 下载链接

当前界面重点：
- 让使用者更偏“阅读”和“浏览”章节拆书结果
- 减少直接盯 JSON
- 仍保留原始 JSON 折叠区，方便排查
