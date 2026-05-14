# Dify Apps for Writer Studio

> v3 添加：X-User-Id header 转发让后端 owner_user_id scoping 真正生效。
> 详见 `.sisyphus/plans/writer-studio-v3-business-loop.md` T3 任务。

## 文件清单

| 文件 | 用途 |
|------|------|
| `writer-copilot.dsl.yml` | Dify Chatbot 应用配置（v2 N4） |
| `novel-analyzer-tools.openapi.yaml` | Custom Tool 三件套（search/ask/get-chapter） |

## 部署步骤

### 1. 导入 Custom Tool（先做）

1. Dify Studio → Tools → Custom → "Create Custom Tool"
2. **Schema** 标签页：粘贴 `novel-analyzer-tools.openapi.yaml` 全部内容
3. 点 "Save"，应用会自动检测出 3 个 tool：`search_chapter` / `ask_branch` / `get_chapter_source`
4. **Authorization**：选 None（v3 阶段后端不验签；future v4 接 IDP 后再说）

### 2. 在 Tool 调用层映射 systemVariables.user_id → X-User-Id header

这一步是 v3 owner_user_id scoping 生效的关键 — Dify 默认**不会**自动把
systemVariables 注入 header。

每次 tool 被调用时 Dify 都会重新发 HTTP 请求，header 透传需要在 Tool 配置里显式 wire：

1. 进 Custom Tool 详情 → 选某个 operation（例如 `search_chapter`）
2. 找到 **Headers** 配置区
3. 添加：
   - **Key**：`X-User-Id`
   - **Value**：`{{system.user_id}}`（Dify 模板语法引用 systemVariables）
4. 三个 operation 都重复一次

如果 Dify 版本里 systemVariables 写法不同（部分版本是 `{{sys.user_id}}` 或
`{{user_id}}` 直接读 chatbot input），按当前 Dify 版本 docs 调整。

### 3. 导入 Writer Copilot Chatbot

1. Dify Studio → Apps → "Import DSL"
2. 选 `writer-copilot.dsl.yml`
3. 在 Tool 关联页选刚配的 3 个 Custom Tool
4. Publish → 复制 token → 写入 `apps/web/.env.local`：
   ```
   NEXT_PUBLIC_DIFY_BASE_URL=http://localhost:8080
   NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN=app-xxxxxxxxxx
   ```

### 4. 验证

跑两个不同的 user_id：

```bash
# 在 Dify 控制台 / iframe 里以 user_id=alice 发问
# 然后到 ai-books 后端 log 看：
grep "X-User-Id" /var/log/ai-books-api.log
# 期望：每条 tool 调用 log 含 user_id=alice
```

或直接 curl 后端：

```bash
curl -H "X-User-Id: alice" 'http://localhost:8001/api/library' | jq '.items | length'
curl -H "X-User-Id: bob"   'http://localhost:8001/api/library' | jq '.items | length'
# 期望：两个数字不同（前提是两个 user 各自上传过书）
```

## 已知限制

- v3 阶段只有 `/api/library` 真正按 owner_user_id 过滤；其他 endpoint 仍返回任何 caller 看到的数据。后续要等 FastAPI surface 落地后用 IdentityMiddleware 全面接入。
- Dify 5.x → 6.x 之间 systemVariables 模板语法可能改名，按你的 Dify 版本调整。
