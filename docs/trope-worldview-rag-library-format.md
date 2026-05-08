# Trope / Worldview RAG Library Format / 套路与世界观 RAG 文档库格式

## 目标

为后续仿写创新 steering 提供一个**可检索、可维护、可审计**的轻量文档库格式。

这层不是直接替代 source chapter，而是给仿写链提供：
- 世界观底座
- 套路轴
- 创新导向
- 禁止越界项
- 读者预期参考

---

## 推荐目录结构

```text
rag/
  trope-library/
    xianxia-underdog-ledger.md
    clan-bureaucracy-power-climb.md
  worldview-dossiers/
    aura-decline-tax-state.md
    sect-credit-feudal-order.md
  audience-expectation-notes/
    male-xianxia-commercial-hooks.md
    cautious-growth-reader-signals.md
```

---

## 单个 trope 文档格式

```md
# xianxia-underdog-ledger

## label
底层逆袭 / 账本修仙

## tags
- 男频
- 账本修仙
- 收益可见

## use_when
- 主角处于资源匮乏阶段
- 需要把收益写得可见、可算、可追

## worldview_capsule
- 灵气不是无限资源，而是与身份和税制绑定
- 主角每次进步都会改变其社会信用与谈判筹码

## trope_axes
- 底层逆袭
- 资源账本化成长
- 先压后扬

## innovation_directives
- 把修炼收益写成社会关系变化
- 把升级写成制度位置变化，而不是只写战力

## taboo_innovations
- 不要直接无代价暴涨
- 不要跳过资源取得过程

## audience_expectation_notes
- 男频读者需要看到收益可见
- 每次进步都最好带来更大世界的入场券
```

---

## 单个 worldview dossier 文档格式

```md
# aura-decline-tax-state

## label
灵气衰败 + 税制化王朝

## core_claim
修炼不是私人行为，而是受国家、宗门、家族共同调控的稀缺资源竞争。

## worldview_capsule
- 灵气衰败导致修炼成本抬升
- 宗门控制功法、资源、认证
- 王朝通过税制与武籍管理修炼者

## conflict_generators
- 身份与资源强绑定
- 修炼收益会引发家族与官府重新定价
- 婚姻、功名、兵役都与修炼资格挂钩

## useful_for_imitation
- 强化“升级不仅是变强，也是社会位置变化”
- 强化“资源取得过程比结果更重要”

## taboo_innovations
- 不要把制度层完全写没
- 不要让主角轻易脱离代价系统
```

---

## audience note 文档格式

```md
# male-xianxia-commercial-hooks

## label
男频修仙商业钩子

## reader_expectations
- 章尾最好有更高层级机会或压力
- 收益要可见
- 主角不能一直被动

## boredom_signals
- 纯解释性文字太多
- 长时间没有外界态度变化
- 升级不带现实反馈

## rewrite_hints
- 让每次进步带来身份/资源/关系变化
- 章尾给下一层门槛，不只给情绪收束
```

---

## 如何接到当前 steering pack

从这些文档里抽取 5 类信息，映射到当前 CLI：

- `worldview_capsule` -> `--worldview-note`
- `trope_axes` -> `--trope-axis`
- `innovation_directives` -> `--innovation-directive`
- `taboo_innovations` -> `--taboo-innovation`
- `audience/knowledge refs` -> `--knowledge-ref`

---

## 当前建议

先不要一开始就做复杂数据库。

先做：
- markdown 文档库
- 统一 frontmatter / section naming
- 一层简单检索（至少覆盖 tag / label / query 三条命中线）

当前最小可用状态已经支持：
- `--trope-doc`
- `--worldview-doc`
- `--audience-doc`

也就是说，现在已经可以先用**本地 markdown 文档库装配 steering pack**，
后续再升级成真正的 RAG / embedding / retrieval surface。

等格式稳定后，再做真正的 RAG / embedding / retrieval surface。
