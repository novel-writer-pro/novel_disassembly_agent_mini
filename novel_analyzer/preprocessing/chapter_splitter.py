"""Heuristic chapter normalization and segmentation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256

TITLE_PATTERN = re.compile(
    r"^第\s*(?P<number>\d+|[零一二三四五六七八九十百千两]+)\s*(?P<unit>章|节)(?P<rest>[^\n]*)",
    re.MULTILINE,
)
DOUBLE_PREFIX_PATTERN = re.compile(
    r"^(?P<prefix>第\s*(?P<number>\d+|[零一二三四五六七八九十百千两]+)\s*(?P<unit>章|节))\s+\d+\.(第\s*(\d+|[零一二三四五六七八九十百千两]+)\s*(章|节))\s*(?P<title>.*)$"
)

_CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


@dataclass(frozen=True, slots=True)
class NormalizedChapter:
    """Normalized chapter descriptor."""

    chapter_index: int
    raw_heading: str
    normalized_chapter_no: int | None
    normalized_title: str
    start_offset: int
    end_offset: int
    content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class ChapterManifestPreview:
    """Cheap summary returned by inspect-novel."""

    raw_heading_count: int
    normalized_chapter_count: int
    duplicate_heading_count: int
    first_headings: list[str]


@dataclass(frozen=True, slots=True)
class _HeadingMatch:
    """Internal normalized heading match used to build clean chapter boundaries."""

    raw_heading: str
    normalized_chapter_no: int | None
    normalized_title: str
    start: int
    end: int
    cluster_start: int

def _parse_chapter_number(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    total = 0
    current = 0
    for char in text:
        if char in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[char]
            continue
        if char in _CHINESE_UNITS:
            unit = _CHINESE_UNITS[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
            continue
        return None
    return total + current if total + current > 0 else None


def _normalize_heading(raw_heading: str) -> tuple[int | None, str]:
    match = TITLE_PATTERN.match(raw_heading.strip())
    number = _parse_chapter_number(match.group("number")) if match else None

    deduped = DOUBLE_PREFIX_PATTERN.sub(
        lambda m: f"{m.group('prefix')} {m.group('title').strip()}".strip(),
        raw_heading.strip(),
    )
    rest = deduped
    if number is not None:
        rest = re.sub(r"^第\s*(\d+|[零一二三四五六七八九十百千两]+)\s*(章|节)", "", deduped).strip()
    normalized_title = rest or (raw_heading.strip() if number is None else f"第{number}章")
    return number, normalized_title


def _iter_heading_matches(text: str) -> Iterable[re.Match[str]]:
    return TITLE_PATTERN.finditer(text)


def _heading_key(match: _HeadingMatch) -> tuple[int | None, str]:
    return match.normalized_chapter_no, match.normalized_title


def _collapse_duplicate_headings(text: str) -> list[_HeadingMatch]:
    """Collapse duplicated/consecutive heading lines into one effective chapter start."""

    collapsed: list[_HeadingMatch] = []
    for match in _iter_heading_matches(text):
        raw_heading = match.group(0).strip()
        chapter_number, normalized_title = _normalize_heading(raw_heading)
        candidate = _HeadingMatch(
            raw_heading=raw_heading,
            normalized_chapter_no=chapter_number,
            normalized_title=normalized_title,
            start=match.start(),
            end=match.end(),
            cluster_start=match.start(),
        )
        if collapsed:
            previous = collapsed[-1]
            between = text[previous.end : candidate.start]
            if _heading_key(previous) == _heading_key(candidate) and not between.strip():
                collapsed[-1] = _HeadingMatch(
                    raw_heading=candidate.raw_heading,
                    normalized_chapter_no=candidate.normalized_chapter_no,
                    normalized_title=candidate.normalized_title,
                    start=candidate.start,
                    end=candidate.end,
                    cluster_start=previous.cluster_start,
                )
                continue
        collapsed.append(candidate)
    return collapsed


def inspect_text(text: str) -> ChapterManifestPreview:
    """Return a preview of the chapter structure."""

    raw_titles = [match.group(0).strip() for match in _iter_heading_matches(text)]
    collapsed = _collapse_duplicate_headings(text)
    duplicate_count = len(raw_titles) - len(collapsed)
    return ChapterManifestPreview(
        raw_heading_count=len(raw_titles),
        normalized_chapter_count=len(collapsed),
        duplicate_heading_count=duplicate_count,
        first_headings=[heading.raw_heading for heading in collapsed[:10]],
    )


def split_text_into_chapters(text: str) -> list[NormalizedChapter]:
    """Split a raw novel text into normalized chapters."""

    matches = _collapse_duplicate_headings(text)
    chapters: list[NormalizedChapter] = []

    for index, match in enumerate(matches):
        start = match.start
        end = matches[index + 1].cluster_start if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        chapters.append(
            NormalizedChapter(
                chapter_index=len(chapters) + 1,
                raw_heading=match.raw_heading,
                normalized_chapter_no=match.normalized_chapter_no,
                normalized_title=match.normalized_title,
                start_offset=start,
                end_offset=end,
                content=content,
                content_hash=sha256(content.encode("utf-8")).hexdigest(),
            )
        )
    return chapters
