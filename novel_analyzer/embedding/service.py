"""Pluggable embedding providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError
from transformers import AutoTokenizer

from novel_analyzer.config.settings import Settings, get_settings


class EmbeddingProvider(Protocol):
    """Protocol for embedding backends."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per text."""


@dataclass(frozen=True, slots=True)
class DeterministicStubEmbeddingProvider:
    """A deterministic placeholder provider for development."""

    dim: int = 16

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = np.frombuffer(text.encode("utf-8"), dtype=np.uint8)
            if digest.size == 0:
                digest = np.arange(self.dim, dtype=np.uint8)
            repeated = np.resize(digest.astype(np.float32), self.dim)
            vector = ((repeated / 255.0) * 2.0) - 1.0
            norm = np.linalg.norm(vector) or 1.0
            vectors.append((vector / norm).tolist())
        return vectors


@dataclass(slots=True)
class OnnxBgeEmbeddingProvider:
    """BGE ONNX embedding backend using Hugging Face assets and ONNX Runtime."""

    model_name: str
    model_path: str | None = None
    cache_dir: str | None = None
    max_length: int = 2048
    _tokenizer: Any = None
    _session: ort.InferenceSession | None = None
    _pooling_mode: str = "cls"

    def _resolve_model_dir(self) -> Path:
        if self.model_path:
            local_path = Path(self.model_path)
            if local_path.exists():
                return local_path
            raise FileNotFoundError(f'Configured embedding model path does not exist: {local_path}')
        cache_dir = Path(self.cache_dir) if self.cache_dir else None
        try:
            repo_dir = snapshot_download(
                repo_id=self.model_name,
                cache_dir=str(cache_dir) if cache_dir else None,
                allow_patterns=[
                    'onnx/*.onnx',
                    'onnx/*.json',
                    'config.json',
                    'tokenizer.json',
                    'tokenizer_config.json',
                    'sentencepiece.bpe.model',
                    'spiece.model',
                    'special_tokens_map.json',
                    'vocab.txt',
                    '1_Pooling/config.json',
                ],
            )
        except LocalEntryNotFoundError as exc:
            raise RuntimeError(
                'Unable to download the ONNX embedding model from Hugging Face in this '
                'environment. Provide a local exported model directory via '
                'NOVEL_ANALYZER_EMBEDDING_MODEL_PATH or enable outbound access to '
                'huggingface.co.'
            ) from exc
        return Path(repo_dir)

    def _resolve_onnx_path(self, model_dir: Path) -> Path:
        candidates = [
            model_dir / 'onnx' / 'model.onnx',
            model_dir / 'model.onnx',
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        found = sorted(model_dir.rglob('*.onnx'))
        if not found:
            raise FileNotFoundError('No ONNX model file found for embedding backend')
        return found[0]

    def _load_pooling_mode(self, model_dir: Path) -> str:
        config_path = model_dir / '1_Pooling' / 'config.json'
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding='utf-8'))
            if data.get('pooling_mode_cls_token'):
                return 'cls'
            if data.get('pooling_mode_mean_tokens'):
                return 'mean'
        return 'cls'

    def _ensure_loaded(self) -> None:
        if self._session is not None and self._tokenizer is not None:
            return
        model_dir = self._resolve_model_dir()
        tokenizer_dir = (
            model_dir / 'onnx'
            if (model_dir / 'onnx' / 'tokenizer.json').exists()
            else model_dir
        )
        self._tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
            tokenizer_dir,
            local_files_only=True,
        )
        onnx_path = self._resolve_onnx_path(model_dir)
        try:
            self._session = ort.InferenceSession(
                str(onnx_path),
                providers=['CPUExecutionProvider'],
            )
        except Exception as exc:  # noqa: BLE001
            if 'model.onnx_data' in str(exc):
                raise RuntimeError(
                    'The ONNX graph references external weight files that are missing. '
                    'Ensure the full model export (including model.onnx_data) is present in '
                    'NOVEL_ANALYZER_EMBEDDING_MODEL_PATH or let Hugging Face finish downloading '
                    'the external data file.'
                ) from exc
            raise
        self._pooling_mode = self._load_pooling_mode(model_dir)

    @staticmethod
    def _mean_pool(last_hidden_state: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask = attention_mask.astype(np.float32)[..., None]
        summed = cast(np.ndarray, (last_hidden_state * mask).sum(axis=1))
        counts = cast(np.ndarray, np.clip(mask.sum(axis=1), 1e-6, None))
        return cast(np.ndarray, summed / counts)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        assert self._tokenizer is not None
        assert self._session is not None

        encoded = self._tokenizer(
            texts,
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
        model_output = cast(np.ndarray, outputs[0])
        attention_mask = cast(np.ndarray, encoded['attention_mask'])
        if model_output.ndim == 2:
            pooled = model_output
        elif self._pooling_mode == 'mean':
            pooled = self._mean_pool(model_output, attention_mask)
        else:
            pooled = model_output[:, 0, :]
        norms = cast(np.ndarray, np.linalg.norm(pooled, axis=1, keepdims=True))
        norms = cast(np.ndarray, np.clip(norms, 1e-12, None))
        normalized = cast(np.ndarray, pooled / norms)
        return cast(list[list[float]], normalized.astype(np.float32).tolist())


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Return the configured embedding provider."""

    runtime = settings or get_settings()
    if runtime.embedding_backend == 'onnx':
        return OnnxBgeEmbeddingProvider(
            model_name=runtime.embedding_model_name,
            model_path=runtime.embedding_model_path or None,
            cache_dir=runtime.embedding_cache_dir,
            max_length=runtime.embedding_max_length,
        )
    return DeterministicStubEmbeddingProvider(dim=runtime.embedding_stub_dim)
