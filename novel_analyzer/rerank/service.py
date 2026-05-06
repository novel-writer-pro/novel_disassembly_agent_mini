"""Pluggable rerank providers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError
from transformers import AutoTokenizer

from novel_analyzer.config.settings import Settings, get_settings


class RerankProvider(Protocol):
    """Protocol for rerank backends."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Return one score per document."""


@dataclass(frozen=True, slots=True)
class DisabledRerankProvider:
    """Fallback reranker that preserves original order/score."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        _ = query
        return [0.0 for _ in documents]


@dataclass(slots=True)
class OnnxCrossEncoderRerankProvider:
    """ONNX cross-encoder reranker using Hugging Face assets and ONNX Runtime."""

    model_name: str
    model_path: str | None = None
    cache_dir: str | None = None
    max_length: int = 512
    _tokenizer: Any = None
    _session: ort.InferenceSession | None = None

    def _resolve_model_dir(self) -> Path:
        if self.model_path:
            local_path = Path(self.model_path)
            if local_path.exists():
                return local_path
            raise FileNotFoundError(f'Configured rerank model path does not exist: {local_path}')
        cache_dir = Path(self.cache_dir) if self.cache_dir else None
        try:
            repo_dir = snapshot_download(
                repo_id=self.model_name,
                cache_dir=str(cache_dir) if cache_dir else None,
                allow_patterns=[
                    'onnx/*.onnx',
                    'config.json',
                    'tokenizer.json',
                    'tokenizer_config.json',
                    'special_tokens_map.json',
                    'vocab.txt',
                    'sentencepiece.bpe.model',
                    'spiece.model',
                ],
            )
        except LocalEntryNotFoundError as exc:
            raise RuntimeError(
                'Unable to download the ONNX rerank model from Hugging Face in this '
                'environment. Provide a local exported model directory via '
                'NOVEL_ANALYZER_RERANK_MODEL_PATH or enable outbound access to '
                'huggingface.co.'
            ) from exc
        return Path(repo_dir)

    def _resolve_onnx_path(self, model_dir: Path) -> Path:
        candidates = [
            model_dir / 'onnx' / 'model_quantized.onnx',
            model_dir / 'onnx' / 'model_int8.onnx',
            model_dir / 'onnx' / 'model_q4.onnx',
            model_dir / 'onnx' / 'model_uint8.onnx',
            model_dir / 'onnx' / 'model.onnx',
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = sorted(model_dir.rglob('*.onnx'))
        if not found:
            raise FileNotFoundError('No ONNX model file found for rerank backend')
        return found[0]

    def _ensure_loaded(self) -> None:
        if self._session is not None and self._tokenizer is not None:
            return
        model_dir = self._resolve_model_dir()
        tokenizer_dir = model_dir / 'onnx' if (model_dir / 'onnx' / 'tokenizer.json').exists() else model_dir
        self._tokenizer = AutoTokenizer.from_pretrained(
            tokenizer_dir,
            local_files_only=True,
        )
        onnx_path = self._resolve_onnx_path(model_dir)
        self._session = ort.InferenceSession(
            str(onnx_path),
            providers=['CPUExecutionProvider'],
        )

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        self._ensure_loaded()
        assert self._tokenizer is not None
        assert self._session is not None

        encoded = self._tokenizer(
            [query] * len(documents),
            documents,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors='np',
        )
        input_names = {input_meta.name for input_meta in self._session.get_inputs()}
        feeds = {
            key: value.astype(np.int64)
            for key, value in encoded.items()
            if key in input_names
        }
        outputs = self._session.run(None, feeds)
        logits = cast(np.ndarray, outputs[0])
        if logits.ndim == 2 and logits.shape[1] == 1:
            logits = logits[:, 0]
        return cast(list[float], logits.astype(np.float32).tolist())


@lru_cache(maxsize=8)
def _cached_rerank_provider(
    backend: str,
    model_name: str,
    model_path: str,
    cache_dir: str,
    max_length: int,
) -> RerankProvider:
    if not model_name:
        return DisabledRerankProvider()
    if backend == 'onnx':
        return OnnxCrossEncoderRerankProvider(
            model_name=model_name,
            model_path=model_path or None,
            cache_dir=cache_dir or None,
            max_length=max_length,
        )
    return DisabledRerankProvider()


def get_rerank_provider(settings: Settings | None = None) -> RerankProvider:
    """Return the configured rerank provider."""

    runtime = settings or get_settings()
    return _cached_rerank_provider(
        runtime.rerank_backend,
        runtime.rerank_model_name,
        runtime.rerank_model_path,
        runtime.rerank_cache_dir,
        runtime.rerank_max_length,
    )
