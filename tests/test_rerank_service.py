from unittest.mock import Mock, patch
import json
import urllib.error

from novel_analyzer.rerank.service import (
    DisabledRerankProvider,
    HttpRerankProvider,
)


def test_disabled_provider_returns_zeros() -> None:
    provider = DisabledRerankProvider()
    scores = provider.rerank('query', ['doc1', 'doc2', 'doc3'])
    assert scores == [0.0, 0.0, 0.0]


def test_http_rerank_tei_success() -> None:
    mock_response = Mock()
    mock_response.read.return_value = json.dumps([
        {'index': 0, 'score': 0.9},
        {'index': 1, 'score': 0.3},
    ]).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    
    mock_opener = Mock()
    mock_opener.open = Mock(return_value=mock_response)

    with patch('urllib.request.build_opener', return_value=mock_opener):
        provider = HttpRerankProvider(
            model_name='test-model',
            api_base='http://localhost:8081',
            api_format='tei',
        )
        scores = provider.rerank('query', ['doc1', 'doc2'])
        
        assert len(scores) == 2
        assert scores[0] == 0.9
        assert scores[1] == 0.3


def test_http_rerank_tei_index_reorder() -> None:
    mock_response = Mock()
    mock_response.read.return_value = json.dumps([
        {'index': 1, 'score': 0.3},
        {'index': 0, 'score': 0.9},
    ]).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)
    
    mock_opener = Mock()
    mock_opener.open = Mock(return_value=mock_response)

    with patch('urllib.request.build_opener', return_value=mock_opener):
        provider = HttpRerankProvider(
            model_name='test-model',
            api_base='http://localhost:8081',
            api_format='tei',
        )
        scores = provider.rerank('query', ['doc1', 'doc2'])
        
        assert len(scores) == 2
        assert scores[0] == 0.9
        assert scores[1] == 0.3


def test_http_rerank_empty_documents_short_circuit() -> None:
    with patch('urllib.request.build_opener') as mock_build:
        provider = HttpRerankProvider(
            model_name='test-reranker',
            api_base='http://localhost:8081',
        )
        scores = provider.rerank('query', [])
        
        assert scores == []
        assert mock_build.call_count == 0


def test_http_rerank_4xx_no_retry() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8081/rerank',
        400,
        'Bad Request',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Invalid query')
    
    mock_opener = Mock()
    mock_opener.open = Mock(side_effect=mock_error)

    with patch('urllib.request.build_opener', return_value=mock_opener):
        provider = HttpRerankProvider(
            model_name='test-model',
            api_base='http://localhost:8081',
            max_retries=2,
        )
        
        try:
            provider.rerank('query', ['doc1'])
            assert False, 'Should have raised RuntimeError'
        except RuntimeError as exc:
            assert 'HTTP 400' in str(exc)


def test_http_rerank_5xx_retry_then_fail() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8081/rerank',
        503,
        'Service Unavailable',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Service down')
    
    mock_opener = Mock()
    mock_opener.open = Mock(side_effect=mock_error)

    with patch('urllib.request.build_opener', return_value=mock_opener):
        with patch('time.sleep'):
            provider = HttpRerankProvider(
                model_name='test-model',
                api_base='http://localhost:8081',
                max_retries=2,
            )
            
            try:
                provider.rerank('query', ['doc1'])
                assert False, 'Should have raised RuntimeError'
            except RuntimeError as exc:
                assert 'HTTP 503' in str(exc)
                assert 'after 3 attempts' in str(exc)
