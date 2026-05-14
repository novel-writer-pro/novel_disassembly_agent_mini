import numpy as np
import pytest

from novel_analyzer.config.settings import Settings
from novel_analyzer.embedding.service import get_embedding_provider
from novel_analyzer.rerank.service import get_rerank_provider


@pytest.mark.integration
def test_embedding_openai_format(tei_live):
    settings = Settings(
        embedding_backend='http',
        embedding_api_base='http://localhost:8080',
        embedding_api_format='openai',
        embedding_model_name='BAAI/bge-m3',
    )
    provider = get_embedding_provider(settings)
    
    texts = ['这是一个测试文本', '另一个不同的文本', '第三个测试样本']
    vectors = provider.embed_texts(texts)
    
    assert len(vectors) == 3
    assert len(vectors[0]) == 1024
    assert len(vectors[1]) == 1024
    assert len(vectors[2]) == 1024
    
    for vec in vectors:
        norm = np.linalg.norm(np.array(vec))
        assert 0.99 < norm < 1.01


@pytest.mark.integration
def test_embedding_tei_format(tei_live):
    settings = Settings(
        embedding_backend='http',
        embedding_api_base='http://localhost:8080',
        embedding_api_format='tei',
        embedding_model_name='BAAI/bge-m3',
    )
    provider = get_embedding_provider(settings)
    
    texts = ['小说分析系统', '章节内容提取']
    vectors = provider.embed_texts(texts)
    
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert len(vectors[1]) == 1024


@pytest.mark.integration
def test_embedding_determinism(tei_live):
    settings = Settings(
        embedding_backend='http',
        embedding_api_base='http://localhost:8080',
        embedding_api_format='openai',
        embedding_model_name='BAAI/bge-m3',
    )
    provider = get_embedding_provider(settings)
    
    text = '确定性测试文本'
    vec1 = provider.embed_texts([text])[0]
    vec2 = provider.embed_texts([text])[0]
    
    vec1_arr = np.array(vec1)
    vec2_arr = np.array(vec2)
    cosine_sim = np.dot(vec1_arr, vec2_arr) / (np.linalg.norm(vec1_arr) * np.linalg.norm(vec2_arr))
    
    assert cosine_sim > 0.999


@pytest.mark.integration
def test_rerank_tei_format(tei_live):
    settings = Settings(
        rerank_backend='http',
        rerank_api_base='http://localhost:8081',
        rerank_api_format='tei',
        rerank_model_name='BAAI/bge-reranker-v2-m3',
    )
    provider = get_rerank_provider(settings)
    
    query = '主角的性格特点'
    documents = [
        '主角是一个勇敢的战士',
        '今天天气很好',
        '主角性格复杂，既有善良的一面，也有冷酷的一面',
        '数据库连接失败',
        '这个角色的心理描写非常细腻',
    ]
    
    scores = provider.rerank(query, documents)
    
    assert len(scores) == 5
    
    relevant_indices = [0, 2, 4]
    irrelevant_indices = [1, 3]
    
    avg_relevant = np.mean([scores[i] for i in relevant_indices])
    avg_irrelevant = np.mean([scores[i] for i in irrelevant_indices])
    
    assert avg_relevant > avg_irrelevant


@pytest.mark.integration
def test_embedding_batch_consistency(tei_live):
    settings = Settings(
        embedding_backend='http',
        embedding_api_base='http://localhost:8080',
        embedding_api_format='tei',
        embedding_model_name='BAAI/bge-m3',
    )
    provider = get_embedding_provider(settings)
    
    texts = ['文本A', '文本B', '文本C']
    batch_vectors = provider.embed_texts(texts)
    
    single_vectors = [provider.embed_texts([text])[0] for text in texts]
    
    for i in range(len(texts)):
        batch_arr = np.array(batch_vectors[i])
        single_arr = np.array(single_vectors[i])
        cosine_sim = np.dot(batch_arr, single_arr) / (np.linalg.norm(batch_arr) * np.linalg.norm(single_arr))
        assert cosine_sim > 0.999


@pytest.mark.integration
def test_embedding_batch_chunking(tei_live):
    settings = Settings(
        embedding_backend='http',
        embedding_api_base='http://localhost:8080',
        embedding_api_format='tei',
        embedding_model_name='BAAI/bge-m3',
    )
    provider = get_embedding_provider(settings)
    
    texts = [f'测试文本{i}' for i in range(40)]
    vectors = provider.embed_texts(texts)
    
    assert len(vectors) == 40
    for vec in vectors:
        assert len(vec) == 1024
        norm = np.linalg.norm(np.array(vec))
        assert 0.99 < norm < 1.01


@pytest.mark.integration
def test_rerank_batch_chunking(tei_live):
    settings = Settings(
        rerank_backend='http',
        rerank_api_base='http://localhost:8081',
        rerank_api_format='tei',
        rerank_model_name='BAAI/bge-reranker-v2-m3',
        rerank_http_batch_size=5,
    )
    provider = get_rerank_provider(settings)
    
    query = '机器学习'
    documents = [f'文档{i}关于人工智能和机器学习' if i % 2 == 0 else f'文档{i}关于烹饪' for i in range(12)]
    
    scores = provider.rerank(query, documents)
    
    assert len(scores) == 12
    
    relevant_scores = [scores[i] for i in range(0, 12, 2)]
    irrelevant_scores = [scores[i] for i in range(1, 12, 2)]
    
    avg_relevant = np.mean(relevant_scores)
    avg_irrelevant = np.mean(irrelevant_scores)
    
    assert avg_relevant > avg_irrelevant
