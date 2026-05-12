#!/usr/bin/env python3
"""TEI end-to-end diagnostic script.

Checks all prerequisites and runtime state for TEI embedding/rerank services.
Exit code 0 if all checks pass, 1 if any fail.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def check_mark(passed: bool) -> str:
    return f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"


def print_header(text: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_check(num: int, name: str, passed: bool, details: str = "", fix: str = "") -> None:
    status = check_mark(passed)
    print(f"{status} Check {num:2d}: {name}")
    if details:
        print(f"           {details}")
    if not passed and fix:
        print(f"           {Colors.YELLOW}→ {fix}{Colors.RESET}")


def check_venv() -> bool:
    venv_path = Path('.venv')
    return venv_path.exists() and (venv_path / 'bin' / 'python').exists()


def check_huggingface_hub() -> bool:
    try:
        import huggingface_hub
        return True
    except ImportError:
        return False


def check_docker_access() -> tuple[bool, str]:
    try:
        subprocess.run(['docker', 'info'], capture_output=True, check=True, timeout=5)
        return True, "no sudo"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    try:
        subprocess.run(['sudo', '-n', 'docker', 'info'], capture_output=True, check=True, timeout=5)
        return True, "needs sudo"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False, "not accessible"


def check_docker_image(docker_cmd: str) -> bool:
    try:
        result = subprocess.run(
            f'{docker_cmd} images ghcr.io/huggingface/text-embeddings-inference:cpu-1.6 -q'.split(),
            capture_output=True,
            text=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def check_model_cache(model_id: str, cache_dir: Path) -> tuple[bool, str]:
    model_cache = cache_dir / f"models--{model_id.replace('/', '--')}"
    if not model_cache.exists():
        return False, "not found"
    
    try:
        size = sum(f.stat().st_size for f in model_cache.rglob('*') if f.is_file())
        if size < 1_000_000_000:
            return False, f"too small ({size / 1e9:.2f}GB)"
        return True, f"{size / 1e9:.2f}GB"
    except Exception as e:
        return False, f"error: {e}"


def check_port(port: int) -> tuple[str, str]:
    try:
        sock = __import__('socket').socket(__import__('socket').AF_INET, __import__('socket').SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result != 0:
            return "free", ""
        
        try:
            result = subprocess.run(
                ['lsof', '-Pi', f':{port}', '-sTCP:LISTEN', '-t'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.stdout.strip():
                pid = result.stdout.strip().split()[0]
                cmd_result = subprocess.run(
                    ['ps', '-p', pid, '-o', 'comm='],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                cmd = cmd_result.stdout.strip()
                if 'text-embeddings' in cmd or 'docker' in cmd:
                    return "tei", pid
                return "other", pid
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return "tei", ""
    except Exception:
        return "unknown", ""


def check_container(name: str, docker_cmd: str) -> str:
    try:
        result = subprocess.run(
            f'{docker_cmd} ps -a --filter name={name} --format {{{{.Status}}}}'.split(),
            capture_output=True,
            text=True,
            timeout=5
        )
        status = result.stdout.strip()
        if not status:
            return "not exist"
        if "Up" in status:
            if "(healthy)" in status:
                return "healthy"
            return "up"
        if "Exited" in status:
            return "exited"
        return status
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "error"


def check_http_endpoint(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        return response.status == 200, str(response.status)
    except urllib.error.HTTPError as e:
        return False, str(e.code)
    except Exception as e:
        return False, str(e)


def check_embed_inference(port: int) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(
            f'http://localhost:{port}/embed',
            data=json.dumps({"inputs": ["hello world"]}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req, timeout=5)
        data = json.loads(response.read())
        dim = len(data[0])
        return dim == 1024, f"dim={dim}"
    except Exception as e:
        return False, str(e)


def check_rerank_inference(port: int) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(
            f'http://localhost:{port}/rerank',
            data=json.dumps({
                "query": "machine learning",
                "texts": ["AI and ML", "cooking recipes"]
            }).encode(),
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req, timeout=45)
        data = json.loads(response.read())
        
        scores = [item['score'] for item in data]
        correct_order = scores[0] > scores[1]
        return correct_order, f"scores={[f'{s:.3f}' for s in scores]}"
    except Exception as e:
        return False, str(e)


def check_provider_integration() -> tuple[bool, str]:
    try:
        sys.path.insert(0, str(Path.cwd()))
        from novel_analyzer.config.settings import Settings
        from novel_analyzer.embedding.service import get_embedding_provider
        
        settings = Settings(
            embedding_backend='http',
            embedding_api_base='http://localhost:8080',
            embedding_api_format='tei'
        )
        provider = get_embedding_provider(settings)
        vectors = provider.embed_texts(["hi"])
        
        return len(vectors) == 1 and len(vectors[0]) == 1024, f"dim={len(vectors[0])}"
    except Exception as e:
        return False, str(e)


def check_latency(port: int, n: int = 20) -> tuple[bool, str]:
    latencies = []
    for _ in range(n):
        try:
            start = time.time()
            req = urllib.request.Request(
                f'http://localhost:{port}/embed',
                data=json.dumps({"inputs": ["test"]}).encode(),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=5)
            latencies.append((time.time() - start) * 1000)
        except Exception:
            pass
    
    if not latencies:
        return False, "all requests failed"
    
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    
    return True, f"P50={p50:.1f}ms P95={p95:.1f}ms (n={len(latencies)})"


def main() -> int:
    print_header("TEI Doctor - End-to-End Diagnostics")
    
    failures = []
    
    passed = check_venv()
    print_check(1, "Python venv exists", passed,
                ".venv/bin/python found" if passed else "not found",
                "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt")
    if not passed:
        failures.append(1)
    
    passed = check_huggingface_hub()
    print_check(2, "huggingface_hub installed", passed,
                "import successful" if passed else "not found",
                "Run: .venv/bin/pip install huggingface-hub")
    if not passed:
        failures.append(2)
    
    docker_ok, docker_mode = check_docker_access()
    print_check(3, "Docker accessible", docker_ok,
                docker_mode,
                "Add user to docker group or configure passwordless sudo")
    if not docker_ok:
        failures.append(3)
    
    docker_cmd = "sudo docker" if docker_mode == "needs sudo" else "docker"
    
    if docker_ok:
        passed = check_docker_image(docker_cmd)
        print_check(4, "TEI image pulled", passed,
                    "ghcr.io/huggingface/text-embeddings-inference:cpu-1.6" if passed else "not found",
                    f"Run: {docker_cmd} pull ghcr.io/huggingface/text-embeddings-inference:cpu-1.6")
        if not passed:
            failures.append(4)
    else:
        print_check(4, "TEI image pulled", False, "skipped (docker not accessible)", "")
        failures.append(4)
    
    cache_dir = Path('.cache/tei')
    passed, details = check_model_cache('BAAI/bge-m3', cache_dir)
    print_check(5, "Embed model cached", passed, details,
                "Run: python scripts/dev/tei-prefetch.py")
    if not passed:
        failures.append(5)
    
    passed, details = check_model_cache('BAAI/bge-reranker-v2-m3', cache_dir)
    print_check(6, "Rerank model cached", passed, details,
                "Run: python scripts/dev/tei-prefetch.py")
    if not passed:
        failures.append(6)
    
    port_status, pid = check_port(8080)
    passed = port_status in ("free", "tei")
    print_check(7, "Port 8080 available", passed,
                f"{port_status}" + (f" (PID {pid})" if pid else ""),
                "Stop the conflicting process or change TEI_EMBED_PORT")
    if not passed:
        failures.append(7)
    
    port_status, pid = check_port(8081)
    passed = port_status in ("free", "tei")
    print_check(8, "Port 8081 available", passed,
                f"{port_status}" + (f" (PID {pid})" if pid else ""),
                "Stop the conflicting process or change TEI_RERANK_PORT")
    if not passed:
        failures.append(8)
    
    if docker_ok:
        embed_status = check_container('tei-embed', docker_cmd)
        passed = embed_status in ("healthy", "up")
        print_check(9, "tei-embed container", passed, embed_status,
                    "Run: bash scripts/dev/tei-up.sh")
        if not passed:
            failures.append(9)
        
        rerank_status = check_container('tei-rerank', docker_cmd)
        passed = rerank_status in ("healthy", "up")
        print_check(10, "tei-rerank container", passed, rerank_status,
                    "Run: bash scripts/dev/tei-up.sh")
        if not passed:
            failures.append(10)
    else:
        print_check(9, "tei-embed container", False, "skipped (docker not accessible)", "")
        print_check(10, "tei-rerank container", False, "skipped (docker not accessible)", "")
        failures.extend([9, 10])
    
    passed, details = check_http_endpoint('http://localhost:8080/health')
    print_check(11, "Embed /health endpoint", passed, details,
                "Check container logs: docker logs tei-embed")
    if not passed:
        failures.append(11)
    
    passed, details = check_http_endpoint('http://localhost:8081/health')
    print_check(12, "Rerank /health endpoint", passed, details,
                "Check container logs: docker logs tei-rerank")
    if not passed:
        failures.append(12)
    
    passed, details = check_embed_inference(8080)
    print_check(13, "Embed inference", passed, details,
                "Verify model loaded correctly in container logs")
    if not passed:
        failures.append(13)
    
    passed, details = check_rerank_inference(8081)
    print_check(14, "Rerank inference", passed, details,
                "Verify model loaded correctly in container logs")
    if not passed:
        failures.append(14)
    
    passed, details = check_provider_integration()
    print_check(15, "Provider integration", passed, details,
                "Check novel_analyzer.embedding.service imports")
    if not passed:
        failures.append(15)
    
    passed, details = check_latency(8080)
    print_check(16, "Latency sampling", passed, details,
                "Check network/container performance")
    if not passed:
        failures.append(16)
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    if not failures:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All checks passed!{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ {len(failures)} check(s) failed: {failures}{Colors.RESET}")
        print(f"{Colors.YELLOW}See: docs/foundation-optimization/http-backend-guide.md{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
