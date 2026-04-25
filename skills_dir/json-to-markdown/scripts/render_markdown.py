from __future__ import annotations

import json
import sys
from pathlib import Path

from novel_analyzer.reporting.markdown import render_chapter_markdown


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: render_markdown.py <input.json> <output.md>', file=sys.stderr)
        return 2
    payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    Path(sys.argv[2]).write_text(render_chapter_markdown(payload), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
