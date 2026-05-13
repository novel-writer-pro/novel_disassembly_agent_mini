import urllib.request
import urllib.error
import pytest


@pytest.fixture(scope="module")
def tei_live():
    """Check if TEI services are available and return ports."""
    embed_port = 8080
    rerank_port = 8081
    
    try:
        urllib.request.urlopen(f"http://localhost:{embed_port}/health", timeout=2).read()
        urllib.request.urlopen(f"http://localhost:{rerank_port}/health", timeout=2).read()
    except (urllib.error.URLError, TimeoutError, OSError):
        pytest.skip("TEI servers not running. Run: bash scripts/dev/tei-up.sh")
    
    return {"embed_port": embed_port, "rerank_port": rerank_port}
