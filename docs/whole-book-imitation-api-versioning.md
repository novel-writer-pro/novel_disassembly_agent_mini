# Whole-Book Imitation API 版本化策略

## 1. 当前版本口径

当前 whole-book imitation report 使用：

- `contract_version = whole-book-imitation.v1`
- `stable_contract_version = whole-book-imitation-pre-v1`

含义：
- `contract_version` 表示当前共享 report contract 的主名称
- `stable_contract_version` 表示当前仍按 **pre-v1 稳定合同** 管理

---

## 2. 当前推荐策略

当前最合理的策略是：

> **共享 contract 已命名为 v1，但稳定级别仍是 pre-v1。**

也就是说：
- 可以让自动化系统用 `contract_version` 识别 payload 家族
- 可以让下游用 `stable_contract_version` 判断当前是否已进入 fully-stable freeze

---

## 3. 稳定字段的变更规则

### 规则 A：稳定字段不轻易改名

当前稳定字段如：
- 顶层版本字段
- `execution_mode`
- `queue`
- `executed_steps`
- `policy_summary`
- `dashboard_summary`
- `book_handoff_summary`

原则：
- 不轻易删除
- 不轻易改名
- 必须调整时，优先新增字段兼容旧字段

### 规则 B：增强字段允许继续演进

以下更偏增强：
- 自然语言提示文案
- 排序细节
- 某些 summary 内部统计细节

原则：
- 可以增强
- 可以补充
- 下游不应强绑定文案和细粒度排序

### 规则 C：以下变化应视为高风险 breaking change

- 删除顶层版本字段
- 删除 `book_handoff_summary`
- 修改 `execution_mode` 枚举语义
- 大改 `queue[*]` / `executed_steps[*]` 的核心层级结构
- 将现有字段从结构化对象改成自由文本

---

## 4. 未来升级建议

### 从 pre-v1 到 stable v1

建议满足：
1. provider-backed sandbox run 回归稳定
2. CLI / export / API 三路 payload 连续多轮不变
3. `book_handoff_summary` 等系统关键字段已被真实消费验证
4. 增强字段边界不再继续移动

届时可考虑升级为：
- `stable_contract_version = whole-book-imitation-v1-stable`

### 未来更大变更

如果后续出现：
- queue / executed_steps 主结构重排
- orchestration 模型重大变化
- handoff summary 结构重做

建议进入新的 contract family，例如：
- `contract_version = whole-book-imitation.v2`

---

## 5. 一句话总结

> 当前最好的做法不是假装“已经 fully stable”，而是让 payload 自己带着版本与稳定级别说话。
