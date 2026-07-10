"""Chapter detection for novel text.

Identifies chapter boundaries using regex patterns for Chinese and English
naming conventions. Returns a list of chapter descriptors with start positions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypedDict


@dataclass
class ChapterDescriptor:
    """A detected chapter boundary."""

    title: str
    start: int  # paragraph index (0-based)


class ChapterDict(TypedDict):
    """Serialized chapter descriptor."""

    title: str
    start: int


class ChaptersDict(TypedDict):
    """Serialized chapter detection result."""

    chapters: list[ChapterDict]


# ---------------------------------------------------------------------------
# Chapter patterns
# ---------------------------------------------------------------------------

# Chinese: 第[一二三四五六七八九十百千0-9]+[章节卷部篇回]
_CN_DIGIT_MAP = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "百": 100,
    "千": 1000,
    "零": 0,
}

_CN_CHAPTER_RE = re.compile(
    r"第\s*([一二三四五六七八九十百千零0-9]+)\s*([章节卷部篇回])",
)

# English: Chapter\s+\d+, Part\s+\d+
_EN_CHAPTER_RE = re.compile(
    r"(Chapter|Part)\s+(\d+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_chapters(paragraphs: list[str]) -> list[ChapterDescriptor]:
    """Detect chapters from a list of paragraphs.

    Each paragraph is scanned for a chapter heading pattern.
    If a heading is found, that paragraph is treated as a chapter title
    and everything after it (until the next heading) belongs to that chapter.

    If no chapters are detected, a single default chapter ``{"title": "正文", "start": 0}``
    is returned.
    """
    chapters: list[ChapterDescriptor] = []

    for idx, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue

        # Check Chinese pattern first
        m = _CN_CHAPTER_RE.search(stripped)
        if m:
            title = stripped
            chapters.append(ChapterDescriptor(title=title, start=idx))
            continue

        # Check English pattern
        m = _EN_CHAPTER_RE.search(stripped)
        if m:
            title = stripped
            chapters.append(ChapterDescriptor(title=title, start=idx))

    if not chapters:
        chapters.append(ChapterDescriptor(title="正文", start=0))

    return chapters


def chapters_to_dict(chapters: list[ChapterDescriptor]) -> ChaptersDict:
    """Convert chapter descriptors to a serialisable dict.

    Returns ``{"chapters": [{"title": ..., "start": ...}, ...]}``.
    """
    return {
        "chapters": [{"title": ch.title, "start": ch.start} for ch in chapters],
    }
