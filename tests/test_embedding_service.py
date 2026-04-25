from pathlib import Path

import numpy as np

from novel_analyzer.embedding.service import (
    DeterministicStubEmbeddingProvider,
    OnnxBgeEmbeddingProvider,
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
