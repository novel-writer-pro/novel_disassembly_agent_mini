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
        {'index': 1, 'score': 0.5},
        {'index': 2, 'score': 0.3},
    ]).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response) as mock_urlopen:
        provider = HttpRerankProvider(
            model_name='test-reranker',
            api_base='http://localhost:8081',
            api_format='tei',
        )
        scores = provider.rerank('query text', ['doc1', 'doc2', 'doc3'])
        
        assert len(scores) == 3
        assert scores[0] == 0.9
        assert scores[1] == 0.5
        assert scores[2] == 0.3
        
        assert mock_urlopen.call_count == 1
        request = mock_urlopen.call_args[0][0]
        assert request.full_url == 'http://localhost:8081/rerank'


def test_http_rerank_tei_index_reorder() -> None:
    mock_response = Mock()
    mock_response.read.return_value = json.dumps([
        {'index': 2, 'score': 0.9},
        {'index': 0, 'score': 0.5},
        {'index': 1, 'score': 0.3},
    ]).encode('utf-8')
    mock_response.__enter__ = Mock(return_value=mock_response)
    mock_response.__exit__ = Mock(return_value=False)

    with patch('urllib.request.urlopen', return_value=mock_response):
        provider = HttpRerankProvider(
            model_name='test-reranker',
            api_base='http://localhost:8081',
        )
        scores = provider.rerank('query', ['doc1', 'doc2', 'doc3'])
        
        assert len(scores) == 3
        assert scores[0] == 0.5
        assert scores[1] == 0.3
        assert scores[2] == 0.9


def test_http_rerank_empty_documents_short_circuit() -> None:
    with patch('urllib.request.urlopen') as mock_urlopen:
        provider = HttpRerankProvider(
            model_name='test-reranker',
            api_base='http://localhost:8081',
        )
        scores = provider.rerank('query', [])
        
        assert scores == []
        assert mock_urlopen.call_count == 0


def test_http_rerank_4xx_no_retry() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8081/rerank',
        400,
        'Bad Request',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Invalid query')

    with patch('urllib.request.urlopen', side_effect=mock_error):
        provider = HttpRerankProvider(
            model_name='test-reranker',
            api_base='http://localhost:8081',
            max_retries=2,
        )
        
        try:
            provider.rerank('query', ['doc1'])
            assert False, 'Should have raised RuntimeError'
        except RuntimeError as exc:
            assert 'HTTP 400' in str(exc)
            assert 'Invalid query' in str(exc)


def test_http_rerank_5xx_retry_then_fail() -> None:
    mock_error = urllib.error.HTTPError(
        'http://localhost:8081/rerank',
        503,
        'Service Unavailable',
        {},
        None,
    )
    mock_error.read = Mock(return_value=b'Service down')

    with patch('urllib.request.urlopen', side_effect=mock_error):
        with patch('time.sleep'):
            provider = HttpRerankProvider(
                model_name='test-reranker',
                api_base='http://localhost:8081',
                max_retries=2,
            )
            
            try:
                provider.rerank('query', ['doc1'])
                assert False, 'Should have raised RuntimeError'
            except RuntimeError as exc:
                assert 'HTTP 503' in str(exc)
                assert 'after 3 attempts' in str(exc)
