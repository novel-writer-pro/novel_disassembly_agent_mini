#!/usr/bin/env python3
"""Helicone proxy end-to-end diagnostic.

Probes whether the Helicone self-host stack is reachable and whether
NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE is wired so build_chat_model() will
route through it. Read-only — does not start containers, does not mutate
env. Exit 0 = ready for trace; exit 1 = action required.

Usage:
    python scripts/dev/helicone-doctor.py
    python scripts/dev/helicone-doctor.py --verbose
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PROXY_PORT = 8585
DEFAULT_WEB_PORT = 8586
ENV_OVERRIDE = "NOVEL_ANALYZER_LLM_BASE_URL_OVERRIDE"


class C:
    G = '\033[92m'
    R = '\033[91m'
    Y = '\033[93m'
    B = '\033[94m'
    Z = '\033[0m'
    BOLD = '\033[1m'


def mark(ok: bool) -> str:
    return f"{C.G}✓{C.Z}" if ok else f"{C.R}✗{C.Z}"


def hdr(text: str) -> None:
    print(f"\n{C.BOLD}{C.B}=== {text} ==={C.Z}")


def show(num: int, name: str, ok: bool, detail: str = "", fix: str = "") -> None:
    print(f"{mark(ok)} {num:2d}. {name}")
    if detail:
        print(f"      {detail}")
    if not ok and fix:
        print(f"      {C.Y}→ {fix}{C.Z}")


def http_probe(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return exc.code < 500, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return False, str(exc.reason if hasattr(exc, 'reason') else exc)


def container_running(name_substr: str) -> tuple[bool, str]:
    for cmd in (['docker', 'ps', '--format', '{{.Names}}'],
                ['sudo', '-n', 'docker', 'ps', '--format', '{{.Names}}']):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True)
            names = [n for n in out.stdout.split() if name_substr in n.lower()]
            if names:
                return True, ', '.join(names)
            return False, "no matching container"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False, "docker not accessible"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-port', type=int, default=DEFAULT_PROXY_PORT)
    parser.add_argument('--web-port', type=int, default=DEFAULT_WEB_PORT)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    hdr("Helicone proxy diagnostic")
    fail_count = 0

    proxy_url = f"http://localhost:{args.proxy_port}"
    ok, detail = http_probe(f"{proxy_url}/healthcheck")
    if not ok:
        ok, detail = http_probe(proxy_url)
    show(1, f"Proxy port :{args.proxy_port} reachable", ok, detail,
         fix="cd infra/helicone/upstream && docker compose up -d")
    fail_count += not ok
    proxy_ok = ok

    web_url = f"http://localhost:{args.web_port}"
    ok, detail = http_probe(web_url)
    show(2, f"Web UI port :{args.web_port} reachable", ok, detail,
         fix="docker compose ps; check Helicone web container is up")
    fail_count += not ok

    override = os.getenv(ENV_OVERRIDE, '')
    ok = bool(override.strip())
    show(3, f"{ENV_OVERRIDE} is set", ok,
         detail=f"value={override!r}" if ok else "unset",
         fix=f"export {ENV_OVERRIDE}='http://localhost:{args.proxy_port}/v1/openai'")
    fail_count += not ok

    if override:
        points_at_proxy = f":{args.proxy_port}" in override or "helicone" in override.lower()
        show(4, "Override URL points at the proxy",
             points_at_proxy,
             detail=override,
             fix=f"set to http://localhost:{args.proxy_port}/v1/openai")
        fail_count += not points_at_proxy
    else:
        show(4, "Override URL points at the proxy", False, "skipped — env unset")
        fail_count += 1

    repo_root = Path(__file__).resolve().parents[2]
    client_path = repo_root / 'novel_analyzer' / 'llm' / 'client.py'
    ok = client_path.exists()
    if ok:
        text = client_path.read_text(encoding='utf-8')
        ok = 'llm_base_url_override' in text
    show(5, "build_chat_model() honors override", ok,
         detail=str(client_path),
         fix="restore novel_analyzer/llm/client.py override path")
    fail_count += not ok

    ok, detail = container_running('helicone')
    show(6, "Helicone container running (best effort)", ok, detail,
         fix="cd infra/helicone/upstream && docker compose up -d")

    if proxy_ok and override:
        try:
            req_url = override.rstrip('/') + '/models'
            ok, detail = http_probe(req_url, timeout=3.0)
            show(7, "GET /models through override succeeds", ok, detail,
                 fix="check Helicone API key + upstream LLM_BASE_URL config")
            fail_count += not ok
        except Exception as exc:
            show(7, "GET /models through override succeeds", False, str(exc))
            fail_count += 1
    else:
        show(7, "GET /models through override succeeds", False,
             "skipped — proxy or override not ready")

    print()
    if fail_count == 0:
        print(f"{C.G}{C.BOLD}All checks passed — Helicone trace is live.{C.Z}")
        return 0
    print(f"{C.R}{C.BOLD}{fail_count} check(s) failed.{C.Z}")
    print(f"  See docs/runbook/helicone-enable.md for the enable sequence.")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
