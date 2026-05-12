# 底座模型建设专题：Embedding / Rerank / 分词词典

> 本文档详细说明如何基于大量小说文本，构建领域专用的 Embedding 模型、Rerank 模型和分词词典，以提升拆书系统的检索精度和分析质量。

---

## 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    检索链路 (当前)                                │
│                                                                  │
│  Query → BM25 (simple分词) ──┐                                  │
│                               ├── RRF 融合 → Rerank → Top-K     │
│  Query → Vector (bge-m3通用) ─┘                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    检索链路 (目标)                                │
│                                                                  │
│  Query → BM25 (领域词典分词) ──┐                                │
│                                 ├── RRF 融合 → 领域Rerank → Top-K│
│  Query → Vector (领域Embedding)─┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 一、分词领域词典建设

### 1.1 目标

让 BM25 检索正确处理小说领域专有名词，避免"卫图"被切成"卫"+"图"。

### 1.2 数据来源

| 来源 | 说明 | 预期词条数 |
|------|------|-----------|
| 已分析章节的 key_entities | 角色名、地名、组织名 | 500-2000/本 |
| GraphNode labels | 所有图谱节点 | 1000-5000/本 |
| 手工补充 | 功法名、境界名、特殊术语 | 100-500/类型 |
| 跨书通用词 | 仙侠/玄幻/都市通用术语 | 200-500/类型 |

### 1.3 词典格式

jieba 自定义词典格式：
```
卫图 5 nr
命格 3 n
大器晚成 4 i
养生功 3 n
青木县 3 ns
庆丰府 3 ns
```

格式：`词语 词频 词性`（词频和词性可选）

### 1.4 自动构建流程

```python
# 已实现: DomainDictionaryService 同时产出两份文件
# .cache/novel-analyzer/domain-dict.txt        — 纯词表 (flat whitelist)
# .cache/novel-analyzer/jieba-user-dict.txt    — "<term> <freq> <pos>" 格式
```

### 1.5 构建步骤

1. **收集原始词条**
   ```bash
   # 从已分析的分支导出所有实体
   .venv/bin/python -c "
   from novel_analyzer.services.domain_dictionary_service import DomainDictionaryService
   from novel_analyzer.database.session import create_session_factory
   from novel_analyzer.config.settings import Settings
   factory = create_session_factory(Settings())
   with factory() as session:
       svc = DomainDictionaryService(session)
       count = svc.update_from_branch('your-branch-id')
       print(f'词条数: {count}')
       print(f'词典路径: {svc._dict_path()}')
   "
   ```

2. **人工审核与补充**
   - 删除明显错误的词条（如"一个"、"没有"等通用词被误收录）
   - 补充功法名、境界名等 LLM 未提取到的术语
   - 按类型标注词性（nr=人名, ns=地名, n=名词）

3. **跨书通用词典**
   - 从多本同类型小说的词典中取交集
   - 形成类型级通用词典（如 `dict-xianxia.txt`、`dict-xuanhuan.txt`）

4. **加载与验证**
   ```python
   import jieba
   jieba.load_userdict('.cache/novel-analyzer/jieba-user-dict.txt')
   result = list(jieba.cut('卫图修炼养生功'))
   # 期望: ['卫图', '修炼', '养生功']
   # 而非: ['卫', '图', '修炼', '养生', '功']
   ```

### 1.6 效果评估

| 指标 | 评估方法 | 目标 |
|------|---------|------|
| 分词准确率 | 人工标注 100 句，对比切分结果 | >= 95% |
| BM25 召回率 | 用 20 个已知答案的 query 测试 | +20% vs 通用分词 |
| 误切率 | 统计专有名词被错切的比例 | < 5% |

---

## 二、Embedding 模型微调

### 2.1 目标

让向量检索理解小说领域的语义关系：
- "那个少年" ≈ "卫图"（指代关系）
- "觉醒命格" ≈ "突破" ≈ "实力提升"（语义等价）
- "第3章的伏笔" → 能检索到第3章的 foreshadowing facts

### 2.2 基座模型选择

| 模型 | 维度 | 中文能力 | 推理速度 | 推荐度 |
|------|------|---------|---------|--------|
| BAAI/bge-m3 (当前) | 1024 | 强 | 中 | 基线 |
| BAAI/bge-large-zh-v1.5 | 1024 | 强 | 中 | 推荐微调基座 |
| stella-mrl-large-zh-v3.5 | 1024 | 极强 | 中 | 备选 |
| BAAI/bge-small-zh-v1.5 | 512 | 中 | 快 | 轻量部署 |

**推荐**: 以 `bge-large-zh-v1.5` 为基座微调，兼顾中文能力和微调效率。

### 2.3 训练数据准备

#### 数据类型

| 类型 | 格式 | 来源 | 预期数量 |
|------|------|------|---------|
| 正样本对 (query, positive) | 语义相似的文本对 | 章节摘要 vs 原文 | 10K-50K |
| 负样本 (query, negative) | 语义不相关的文本对 | 随机章节配对 | 自动生成 |
| 硬负样本 (query, hard_negative) | 表面相似但语义不同 | BM25 高分但不相关 | 5K-20K |

#### 数据构造方法

**方法 A: 从已分析章节自动构造**

```python
# 正样本: chapter_summary <-> 原文片段
# 正样本: key_entity <-> 包含该实体的原文段落
# 正样本: continuity_note <-> 对应章节摘要
# 硬负样本: BM25 top-10 中不包含目标实体的结果

training_pairs = []
for artifact in analyzed_artifacts:
    summary = artifact.payload_json['chapter_summary']
    content = get_chapter_content(artifact.chapter_index)
    
    # 正样本: 摘要 <-> 原文段落
    paragraphs = content.split('\n\n')
    for para in paragraphs[:5]:
        if len(para) > 50:
            training_pairs.append({
                'query': summary,
                'positive': para,
                'negative': random_paragraph_from_other_chapter(),
            })
    
    # 正样本: 实体名 <-> 包含该实体的段落
    for entity in artifact.payload_json['key_entities']:
        for para in paragraphs:
            if entity in para:
                training_pairs.append({
                    'query': f'{entity}在这一章做了什么',
                    'positive': para,
                    'negative': random_paragraph_without_entity(entity),
                })
```

**方法 B: 从多本小说批量构造**

```python
# 对每本小说:
# 1. 用当前系统分析前 30 章
# 2. 从分析结果自动构造训练对
# 3. 合并所有小说的训练对

novels = ['仙侠A.txt', '玄幻B.txt', '都市C.txt', ...]
all_pairs = []
for novel in novels:
    pairs = extract_training_pairs(novel)
    all_pairs.extend(pairs)
# 预期: 10 本小说 × 30 章 × 50 对/章 = 15000 训练对
```

#### 数据清洗

```python
def clean_training_pair(pair):
    # 1. 去除过短文本 (< 20 chars)
    if len(pair['query']) < 20 or len(pair['positive']) < 20:
        return None
    
    # 2. 去除重复
    if pair['query'] == pair['positive']:
        return None
    
    # 3. 去除广告/求收藏等噪音
    noise_patterns = ['求收藏', '求追读', '本章完', '作者说']
    for pattern in noise_patterns:
        if pattern in pair['positive']:
            pair['positive'] = pair['positive'].replace(pattern, '')
    
    # 4. 截断过长文本 (> 512 chars)
    pair['query'] = pair['query'][:512]
    pair['positive'] = pair['positive'][:512]
    pair['negative'] = pair['negative'][:512]
    
    return pair
```

### 2.4 训练流程

#### 环境准备

```bash
pip install sentence-transformers torch
# GPU: NVIDIA A100/V100/4090 (推荐 >= 16GB VRAM)
# 无 GPU: 可用 CPU 训练但极慢 (不推荐)
```

#### 训练脚本

```python
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import json

# 1. 加载基座模型
model = SentenceTransformer('BAAI/bge-large-zh-v1.5')

# 2. 准备训练数据
train_examples = []
with open('training_pairs.jsonl') as f:
    for line in f:
        pair = json.loads(line)
        train_examples.append(InputExample(
            texts=[pair['query'], pair['positive'], pair['negative']]
        ))

train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

# 3. 定义损失函数
# MultipleNegativesRankingLoss: 最适合检索场景
train_loss = losses.MultipleNegativesRankingLoss(model)

# 4. 训练
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=3,
    warmup_steps=100,
    output_path='./models/novel-embedding-v1',
    show_progress_bar=True,
)

# 5. 导出 ONNX (用于生产部署)
model.save('./models/novel-embedding-v1')
# 然后用 optimum 转换为 ONNX:
# optimum-cli export onnx --model ./models/novel-embedding-v1 ./models/novel-embedding-v1-onnx
```

#### 训练参数建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| batch_size | 16-32 | 受 GPU 显存限制 |
| epochs | 3-5 | 过多会过拟合 |
| learning_rate | 2e-5 | 微调标准值 |
| warmup_steps | 100-200 | 防止初期震荡 |
| max_seq_length | 512 | 平衡精度和速度 |
| loss | MultipleNegativesRankingLoss | 检索场景最优 |

### 2.5 效果评估

#### 评估数据集构造

```python
# 从测试集小说中构造 100 个 query-answer 对
eval_queries = [
    {'query': '卫图的命格是什么', 'relevant_chapters': [1, 2]},
    {'query': '养生功的修炼方法', 'relevant_chapters': [3, 5]},
    ...
]
```

#### 评估指标

| 指标 | 计算方法 | 目标 |
|------|---------|------|
| Recall@5 | top-5 结果中包含正确章节的比例 | >= 0.80 |
| Recall@10 | top-10 结果中包含正确章节的比例 | >= 0.90 |
| MRR | 正确结果的平均倒数排名 | >= 0.60 |
| NDCG@10 | 归一化折损累积增益 | >= 0.70 |

#### 对比实验

```bash
# A/B 对比:
# A: bge-m3 通用模型 (当前基线)
# B: novel-embedding-v1 (微调后)

# 在相同 100 个 query 上对比 Recall@5
python eval_embedding.py --model-a bge-m3 --model-b novel-embedding-v1
```

### 2.6 部署

```bash
# 1. 转换为 ONNX
optimum-cli export onnx --model ./models/novel-embedding-v1 ./models/novel-embedding-v1-onnx

# 2. 量化 (可选, 减少 50% 体积, 精度损失 < 1%)
python -m onnxruntime.quantization.quantize \
  --input ./models/novel-embedding-v1-onnx/model.onnx \
  --output ./models/novel-embedding-v1-onnx-int8/model.onnx \
  --per_channel

# 3. 配置系统使用新模型
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=./models/novel-embedding-v1-onnx-int8
NOVEL_ANALYZER_EMBEDDING_MODEL_NAME=novel-embedding-v1
```

---

## 三、Rerank 模型微调

### 3.1 目标

在 BM25 + Vector 召回后，用 Rerank 模型精排，确保最相关的结果排在最前面。

### 3.2 基座模型选择

| 模型 | 参数量 | 中文能力 | 推荐度 |
|------|--------|---------|--------|
| bge-reranker-v2-m3 (当前) | 568M | 强 | 基线 |
| bge-reranker-large | 560M | 强 | 推荐微调基座 |
| bge-reranker-v2-gemma | 2B | 极强 | 精度优先 |

### 3.3 训练数据准备

Rerank 训练数据格式：`(query, document, relevance_score)`

```jsonl
{"query": "卫图的命格", "document": "卫图觉醒了大器晚成的命格...", "score": 1}
{"query": "卫图的命格", "document": "李宅的马需要三更天喂一次...", "score": 0}
{"query": "卫图的命格", "document": "命格是每个人天生的属性...", "score": 0.5}
```

#### 数据构造

```python
# 从已分析章节构造 rerank 训练数据
rerank_data = []

for query_entity in all_entities:
    # 用 BM25 召回 top-20
    candidates = bm25_search(query_entity, limit=20)
    
    for candidate in candidates:
        # 正样本: 包含该实体的章节
        if query_entity in candidate.content:
            rerank_data.append({
                'query': f'{query_entity}相关的情节',
                'document': candidate.summary,
                'score': 1,
            })
        else:
            rerank_data.append({
                'query': f'{query_entity}相关的情节',
                'document': candidate.summary,
                'score': 0,
            })
```

### 3.4 训练流程

```python
from sentence_transformers import CrossEncoder

# 1. 加载基座
model = CrossEncoder('BAAI/bge-reranker-large', max_length=512)

# 2. 准备数据
train_samples = []
for item in rerank_data:
    train_samples.append(InputExample(
        texts=[item['query'], item['document']],
        label=float(item['score']),
    ))

# 3. 训练
model.fit(
    train_dataloader=DataLoader(train_samples, shuffle=True, batch_size=16),
    epochs=3,
    warmup_steps=100,
    output_path='./models/novel-reranker-v1',
)

# 4. 导出 ONNX
# 使用 optimum 转换
```

### 3.5 效果评估

| 指标 | 方法 | 目标 |
|------|------|------|
| Rerank Accuracy | 正确文档是否排在 top-3 | >= 85% |
| NDCG@3 | top-3 排序质量 | >= 0.75 |
| Latency | 单次 rerank 20 条的耗时 | < 100ms |

---

## 四、文本清洗 Pipeline

### 4.1 原始文本问题

| 问题 | 示例 | 处理方法 |
|------|------|---------|
| 广告文本 | "求收藏求追读" | 正则删除 |
| 重复标题 | 章节标题出现两次 | 已有去重逻辑 |
| 乱码 | 编码错误字符 | 替换为空 |
| 作者注 | "（作者说：...）" | 正则删除 |
| 网站水印 | "本书来自XX网" | 正则删除 |
| 空白章节 | 只有标题无正文 | 跳过 |

### 4.2 清洗脚本

```python
import re

NOISE_PATTERNS = [
    r'求收藏.*?(?=\n|$)',
    r'求追读.*?(?=\n|$)',
    r'本章完\s*$',
    r'（作者.*?）',
    r'\(作者.*?\)',
    r'本书来自.*?(?=\n|$)',
    r'手机阅读.*?(?=\n|$)',
    r'正版阅读.*?(?=\n|$)',
    r'[★☆◆◇■□▲△▼▽]{3,}',  # 装饰符号
]

def clean_novel_text(text: str) -> str:
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.MULTILINE)
    # 合并多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
```

### 4.3 批量清洗流程

```bash
# 1. 收集原始小说文本
ls /data/novels/raw/*.txt

# 2. 批量清洗
python scripts/clean_novels.py \
  --input-dir /data/novels/raw/ \
  --output-dir /data/novels/cleaned/ \
  --report /data/novels/clean-report.json

# 3. 验证清洗结果
python scripts/validate_cleaned.py \
  --dir /data/novels/cleaned/ \
  --check-encoding \
  --check-chapters \
  --min-chapter-length 100
```

---

## 五、端到端建设路线

```
Phase 1 (1周): 分词词典
├── 从 10 本已分析小说导出实体词典
├── 人工审核 + 补充类型通用词
├── 集成到 BM25 检索路径
└── 评估: BM25 召回率对比

Phase 2 (2周): Embedding 微调
├── 从 10 本小说构造 15K+ 训练对
├── 清洗 + 去重 + 质量过滤
├── bge-large-zh-v1.5 微调 3 epochs
├── ONNX 导出 + INT8 量化
├── 评估: Recall@5 对比
└── 部署替换 bge-m3

Phase 3 (1周): Rerank 微调
├── 从 BM25 召回结果构造 rerank 训练数据
├── bge-reranker-large 微调
├── ONNX 导出
├── 评估: NDCG@3 对比
└── 部署替换 bge-reranker-v2-m3

Phase 4 (持续): 迭代优化
├── 收集线上 bad case
├── 补充训练数据
├── 定期重训练 (每月/每季度)
└── A/B 测试新版本
```

---

## 六、硬件需求

| 阶段 | 最低配置 | 推荐配置 |
|------|---------|---------|
| 分词词典 | 任意 CPU | 任意 CPU |
| Embedding 微调 | 1x RTX 3090 (24GB) | 1x A100 (40GB) |
| Rerank 微调 | 1x RTX 3090 (24GB) | 1x A100 (40GB) |
| ONNX 推理 | 4 核 CPU + 8GB RAM | 8 核 CPU + 16GB RAM |
| 量化 | 任意 CPU | 任意 CPU |

---

## 七、风险与注意事项

| 风险 | 影响 | 缓解 |
|------|------|------|
| 过拟合到特定小说 | 其他小说检索质量下降 | 多类型小说混合训练 |
| 训练数据质量差 | 模型学到错误模式 | 严格清洗 + 人工抽检 |
| ONNX 转换精度损失 | 微调收益被抵消 | 转换后对比评估 |
| 词典过大 | 分词速度下降 | 控制在 10K 词条以内 |
| 模型体积过大 | 部署困难 | INT8 量化 |

---

## 八、与当前系统的集成点

| 组件 | 当前 | 微调后 | 改动量 |
|------|------|--------|--------|
| `embedding/service.py` | bge-m3 ONNX | novel-embedding-v1 ONNX | 仅改配置 |
| `rerank/service.py` | bge-reranker-v2-m3 | novel-reranker-v1 ONNX | 仅改配置 |
| `retrieval_service.py` BM25 | simple 分词 | jieba + 领域词典 | 需改代码 |
| `DomainDictionaryService` | 已实现 (plain + jieba 双格式) | — | — |

系统设计为配置驱动，模型替换只需修改环境变量：
```bash
NOVEL_ANALYZER_EMBEDDING_MODEL_PATH=./models/novel-embedding-v1-onnx-int8
NOVEL_ANALYZER_RERANK_MODEL_PATH=./models/novel-reranker-v1-onnx
```
