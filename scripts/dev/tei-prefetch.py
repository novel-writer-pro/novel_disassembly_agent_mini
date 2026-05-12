#!/usr/bin/env python3
"""Pre-download TEI models to local cache with China network fallback.

This script downloads embedding and rerank models to the host filesystem
before starting TEI containers, avoiding container-side network issues.

Environment variables:
    TEI_EMBED_MODEL: Embedding model ID (default: BAAI/bge-m3)
    TEI_RERANK_MODEL: Rerank model ID (default: BAAI/bge-reranker-v2-m3)
    TEI_CACHE_DIR: Cache directory (default: .cache/tei)
    HF_ENDPOINT: Hugging Face mirror endpoint (default: https://hf-mirror.com)
"""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("ERROR: huggingface_hub not installed. Run: pip install huggingface-hub", file=sys.stderr)
    sys.exit(1)


DEFAULT_PATTERNS = [
    "*.json",
    "*.txt",
    "*.model",
    "*.bin",
    "*.safetensors",
    "tokenizer.json",
    "sentencepiece.bpe.model",
    "1_Pooling/*",
    "onnx/*",
    "model.onnx_data",
]


def prefetch_model(model_id: str, cache_dir: Path, hf_endpoint: str, require_onnx: bool = False) -> bool:
    print(f"\n{'='*60}")
    print(f"Downloading: {model_id}")
    print(f"Cache: {cache_dir}")
    print(f"Endpoint: {hf_endpoint}")
    print(f"{'='*60}")
    
    os.environ["HF_ENDPOINT"] = hf_endpoint
    
    try:
        repo_path = snapshot_download(
            repo_id=model_id,
            cache_dir=str(cache_dir),
            allow_patterns=DEFAULT_PATTERNS,
            resume_download=True,
        )
        print(f"✓ Downloaded to: {repo_path}")
        
        repo_path_obj = Path(repo_path)
        config_exists = (repo_path_obj / "config.json").exists()
        safetensors_exists = any(repo_path_obj.glob("*.safetensors"))
        bin_exists = any(repo_path_obj.glob("*.bin"))
        onnx_exists = (repo_path_obj / "onnx").exists()
        
        if not config_exists:
            print(f"✗ Sanity check failed: config.json not found in {repo_path}", file=sys.stderr)
            return False
        
        if not (safetensors_exists or bin_exists):
            print(f"✗ Sanity check failed: no model weights (*.safetensors or *.bin) found", file=sys.stderr)
            return False
        
        print(f"✓ Sanity check passed:")
        print(f"  - config.json: ✓")
        print(f"  - weights: {'safetensors' if safetensors_exists else 'bin'}")
        print(f"  - ONNX: {'✓' if onnx_exists else '✗ (will use Candle fallback)'}")
        
        if require_onnx and not onnx_exists:
            print(f"✗ ONNX required but not found", file=sys.stderr)
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Download failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    embed_model = os.getenv("TEI_EMBED_MODEL", "BAAI/bge-m3")
    rerank_model = os.getenv("TEI_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
    cache_dir = Path(os.getenv("TEI_CACHE_DIR", ".cache/tei"))
    hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    print("TEI Model Prefetch")
    print(f"Embed model: {embed_model}")
    print(f"Rerank model: {rerank_model}")
    print(f"Cache directory: {cache_dir.absolute()}")
    print(f"HF endpoint: {hf_endpoint}")
    
    success = True
    
    if not prefetch_model(embed_model, cache_dir, hf_endpoint, require_onnx=False):
        success = False
    
    if not prefetch_model(rerank_model, cache_dir, hf_endpoint, require_onnx=False):
        success = False
    
    if success:
        print("\n" + "="*60)
        print("✓ All models downloaded successfully")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("✗ Some models failed to download")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
