"""Pluggable rerank providers."""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
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
                local_files_only=True,
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
                'The ONNX rerank model is not available in local cache. Provide a '
                'local exported model directory via NOVEL_ANALYZER_RERANK_MODEL_PATH '
                'or prewarm the Hugging Face cache before enabling rerank in runtime '
                'request paths.'
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


@dataclass
class HttpRerankProvider:
    model_name: str
    api_base: str
    api_key: str = ""
    api_format: str = "tei"
    timeout: float = 30.0
    max_retries: int = 2
    verify_ssl: bool = True
    batch_size: int = 0
    _opener: Any = None

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        
        if self.batch_size > 0 and len(documents) > self.batch_size:
            return self._rerank_chunked(query, documents)
        
        return self._rerank_single(query, documents)
    
    def _get_opener(self) -> urllib.request.OpenerDirector:
        if self._opener is None:
            handlers = []
            if not self.verify_ssl:
                import ssl
                context = ssl._create_unverified_context()
                handlers.append(urllib.request.HTTPSHandler(context=context))
            self._opener = urllib.request.build_opener(*handlers)
        return self._opener
    
    def _rerank_single(self, query: str, documents: list[str]) -> list[float]:
        api_base = self.api_base.rstrip("/")
        
        if self.api_format == "tei":
            url = f"{api_base}/rerank"
            body = {
                "query": query,
                "texts": documents,
                "raw_scores": False,
                "return_text": False,
                "truncate": True,
            }
        else:
            raise ValueError(f"Unsupported api_format: {self.api_format}")

        opener = self._get_opener()
        
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                
                if self.api_key:
                    req.add_header("Authorization", f"Bearer {self.api_key}")

                with opener.open(req, timeout=self.timeout) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                    
                    index_to_score = {item["index"]: item["score"] for item in response_data}
                    return [index_to_score[i] for i in range(len(documents))]

            except urllib.error.HTTPError as exc:
                status_code = exc.code
                response_body = exc.read().decode("utf-8", errors="replace")[:500]
                
                if 400 <= status_code < 500:
                    raise RuntimeError(
                        f"HTTP {status_code} from {url}: {response_body}"
                    ) from exc
                
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                
                raise RuntimeError(
                    f"HTTP {status_code} from {url} after {self.max_retries + 1} attempts: {response_body}"
                ) from exc

            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < self.max_retries:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                
                raise RuntimeError(
                    f"Failed to connect to {url} after {self.max_retries + 1} attempts: {exc}"
                ) from exc

        raise RuntimeError(f"Unexpected: exhausted retries for {url}")
    
    def _rerank_chunked(self, query: str, documents: list[str]) -> list[float]:
        results: list[float] = []
        failed_chunks: list[tuple[int, int, str]] = []
        
        for i in range(0, len(documents), self.batch_size):
            chunk = documents[i:i + self.batch_size]
            try:
                chunk_results = self._rerank_single(query, chunk)
                results.extend(chunk_results)
            except Exception as e:
                failed_chunks.append((i, i + len(chunk), str(e)))
                results.extend([0.0] * len(chunk))
        
        if failed_chunks:
            chunk_desc = ", ".join(f"[{start}:{end}]" for start, end, _ in failed_chunks)
            raise RuntimeError(
                f"Failed to rerank {len(failed_chunks)} chunk(s) at indices {chunk_desc}. "
                f"First error: {failed_chunks[0][2]}"
            )
        
        return results


@lru_cache(maxsize=8)
def _cached_rerank_provider(
    backend: str,
    model_name: str,
    model_path: str,
    cache_dir: str,
    max_length: int,
    api_base: str,
    api_key: str,
    api_format: str,
    http_timeout: float,
    http_max_retries: int,
    http_verify_ssl: bool,
    http_batch_size: int,
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
    if backend in ('http', 'tei'):
        return HttpRerankProvider(
            model_name=model_name,
            api_base=api_base,
            api_key=api_key,
            api_format=api_format,
            timeout=http_timeout,
            max_retries=http_max_retries,
            verify_ssl=http_verify_ssl,
            batch_size=http_batch_size,
        )
    return DisabledRerankProvider()


def get_rerank_provider(settings: Settings | None = None) -> RerankProvider:
    """Return the configured rerank provider."""

    runtime = settings or get_settings()
    batch_size = runtime.rerank_http_batch_size if runtime.rerank_http_batch_size > 0 else 32
    if runtime.rerank_backend not in ('http', 'tei'):
        batch_size = 0
    
    return _cached_rerank_provider(
        runtime.rerank_backend,
        runtime.rerank_model_name,
        runtime.rerank_model_path,
        runtime.rerank_cache_dir,
        runtime.rerank_max_length,
        runtime.rerank_api_base,
        runtime.rerank_api_key,
        runtime.rerank_api_format,
        runtime.rerank_http_timeout,
        runtime.rerank_http_max_retries,
        runtime.rerank_http_verify_ssl,
        batch_size,
    )
