from pathlib import Path
from unittest.mock import Mock, patch
import json
import urllib.error

import numpy as np

from novel_analyzer.embedding.service import (
    DeterministicStubEmbeddingProvider,
    OnnxBgeEmbeddingProvider,
    HttpEmbeddingProvider,
)


def test_stub_embedding_provider_returns_normalized_vectors() -> None:
    provider = DeterministicStubEmbeddingProvider(dim=8)
    vectors = provider.embed_texts(['卫图', '命格'])
    assert len(vectors) == 2
    assert len(vectors[0]) == 8
    norm = np.linalg.norm(np.array(vectors[0], dtype=np.float32))
    assert abs(float(norm) - 1.0) < 1e-5


def test_onnx_provider_uses_local_model_path(monkeypatch, tmp_path: Path) -> None:
    model_dir = tmp_path / 'bge'
    (model_dir / 'onnx').mkdir(parents=True)
    (model_dir / '1_Pooling').mkdir(parents=True)
    (model_dir / 'onnx' / 'model.onnx').write_text('fake', encoding='utf-8')
    (model_dir / '1_Pooling' / 'config.json').write_text(
        '{"pooling_mode_cls_token": true}',
        encoding='utf-8',
    )

    class _Tokenizer:
        def __call__(self, texts, **_kwargs):
            return {
                'input_ids': np.array([[1, 2], [3, 4]], dtype=np.int64),
                'attention_mask': np.array([[1, 1], [1, 1]], dtype=np.int64),
            }

    class _Input:
        def __init__(self, name: str) -> None:
            self.name = name

    class _Session:
        def __init__(self, path: str, providers: list[str]) -> None:
            self.path = path
            self.providers = providers

        def get_inputs(self):
            return [_Input('input_ids'), _Input('attention_mask')]

        def run(self, _output_names, feeds):
            assert 'input_ids' in feeds
            return [
                np.array(
                    [
                        [[1.0, 0.0], [0.0, 1.0]],
                        [[0.0, 1.0], [1.0, 0.0]],
                    ],
                    dtype=np.float32,
                )
            ]

    monkeypatch.setattr(
        'novel_analyzer.embedding.service.AutoTokenizer.from_pretrained',
        lambda _path, **_kwargs: _Tokenizer(),
    )
    monkeypatch.setattr('novel_analyzer.embedding.service.ort.InferenceSession', _Session)

    provider = OnnxBgeEmbeddingProvider(
        model_name='BAAI/bge-m3',
        model_path=str(model_dir),
        cache_dir=str(tmp_path / 'cache'),
        max_length=8,
    )
    vectors = provider.embed_texts(['卫图', '命格'])
    assert len(vectors) == 2
    assert len(vectors[0]) == 2


def test_http_embedding_openai_format_success() -> None:
    mock_response = Mock()
    mock_response.read.return_value = json.dumps({
        'data': [
            {'index': 0, 'embedding': [0.1, 0.2, 0.3]},
            {'index': 1, 'embedding': [0.4, 0.5, 0.6]},
        ]
    }).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
        provider = HttpEmbeddingProvider(
            model_name='test-model',
            api_base='http://localhost:8080',
            api_key='test-key',
            api_format='openai',
        )
        vectors = provider.embed_texts(['text1', 'text2'])
        
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]
        assert vectors[1] == [0.4, 0.5, 0.6]
        
        assert mock_urlopen.call_count == 1
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == 'http://localhost:8080/v1/embeddings'
        assert request.get_header('Authorization') == 'Bearer test-key'


def test_http_embedding_tei_format_success() -> None:
    mock_response = Mock()
    mock_response.read.return_value = json.dumps([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response):
        provider = HttpEmbeddingProvider(
            model_name='test-model',
            api_base='http://localhost:8080',
            api_format='tei',
        )
        vectors = provider.embed_texts(['text1', 'text2'])
        
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]
        assert vectors[1] == [0.4, 0.5, 0.6]


def test_http_embedding_empty_input_short_circuit() -> None:
    with patch('urllib.request.urlopen') as mock_urlopen:
        provider = HttpEmbeddingProvider(
            model_name='test-model',
            api_base='http://localhost:8080',
        )
        vectors = provider.embed_texts([])
        
        assert vectors == []
        assert mock_urlopen.call_count == 0


def test_http_embedding_4xx_no_retry() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8080/v1/embeddings',
        400,
        'Bad Request',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Invalid request')

    with patch('urllib.request.urlopen', side_effect=mock_error):
        provider = HttpEmbeddingProvider(
            model_name='test-model',
            api_base='http://localhost:8080',
            max_retries=2,
        )
        
        try:
            provider.embed_texts(['text1'])
            assert False, 'Should have raised RuntimeError'
        except RuntimeError as exc:
            assert 'HTTP 400' in str(exc)
            assert 'Invalid request' in str(exc)


def test_http_embedding_5xx_retry_then_fail() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8080/v1/embeddings',
        503,
        'Service Unavailable',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Service down')

    with patch('urllib.request.urlopen', side_effect=mock_error):
        with patch('time.sleep'):
            provider = HttpEmbeddingProvider(
                model_name='test-model',
                api_base='http://localhost:8080',
                max_retries=2,
            )
            
            try:
                provider.embed_texts(['text1'])
                assert False, 'Should have raised RuntimeError'
            except RuntimeError as exc:
                assert 'HTTP 503' in str(exc)
                assert 'after 3 attempts' in str(exc)


def test_http_embedding_5xx_retry_then_recover() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8080/v1/embeddings',
        503,
        'Service Unavailable',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Service down')
    
    mock_success = Mock()
    mock_success.read.return_value = json.dumps({
        'data': [{'index': 0, 'embedding': [0.1, 0.2]}]
    }).encode('utf-8')
    mock_success.__enter__ = Mock(return_value=mock_success)
    mock_success.__exit__ = Mock(return_value=False)

    with patch('urllib.request.urlopen', side_effect=[mock_error, mock_error, mock_success]):
        with patch('time.sleep'):
            provider = HttpEmbeddingProvider(
                model_name='test-model',
                api_base='http://localhost:8080',
                max_retries=2,
            )
            
            vectors = provider.embed_texts(['text1'])
            assert len(vectors) == 1
            assert vectors[0] == [0.1, 0.2]
