# Process / 开发过程文档治理入口

## 1. 目标
把“开发过程文档”从 canonical 交付面中拆出来单独管理，减少主入口噪音。

## 2. 当前原则
- **主入口保留**：README / 角色入口 / 架构入口 / feature checkout / checklist
- **过程性说明下沉**：开发过程、历史推导、临时复验说明统一归类到 process / evidence / .omx reports
- **canonical 不堆叠过程文档**：对外/对接/交接优先看到 checklist 和当前结论，而不是长过程记录

## 3. 当前 canonical 过程面
- `docs/strategy/docs-governance-and-handoff-checklist.md`
- `docs/features/feature-checkout-template.md`
- `docs/features/*checkout*.md`

## 4. 当前归档/过程面
- `docs/*evidence*.md`
- `.omx/reports/**`
- 其他阶段性过程文档逐步在后续整理时归档到这里的索引里

## 5. 整理原则
1. 过程记录保留，但不抢 canonical 入口位置。
2. checklist 永远比长过程说明更靠前。
3. 如果文档只服务开发过程，应优先考虑收纳，不要直接堆进 README 主路径。
