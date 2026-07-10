"""Text cleaning pipeline for novel intake.

Applies a sequence of cleaning rules to raw novel text and produces
a cleaning report counting what was removed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CleaningReport:
    """Statistics after running the cleaning pipeline."""

    original_word_count: int = 0
    clean_word_count: int = 0
    ads_removed: int = 0
    page_numbers_removed: int = 0
    garbled_lines_removed: int = 0
    blank_lines_removed: int = 0


# ---------------------------------------------------------------------------
# Character / word counting
# ---------------------------------------------------------------------------

# Match Chinese characters (CJK Unified Ideographs + Extension A)
_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")


def count_chinese_chars(text: str) -> int:
    """Count Chinese characters in *text*.

    A Chinese character counts as 1 word. Punctuation and whitespace are excluded.
    """
    return len(_CJK_RE.findall(text))


def count_text_units(text: str) -> int:
    """Count text length using the same user-facing rule as the frontend.

    Chinese text is counted by character. Non-Chinese text is counted as
    whitespace/punctuation-separated alphanumeric words.
    """
    if not text.strip():
        return 0
    chinese_chars = count_chinese_chars(text)
    non_chinese = _CJK_RE.sub(" ", text)
    latin_words = len(_LATIN_WORD_RE.findall(non_chinese))
    return chinese_chars + latin_words


# ---------------------------------------------------------------------------
# Individual cleaning rules
# ---------------------------------------------------------------------------


def _split_lines(text: str) -> list[str]:
    """Split text into lines, preserving empty ones."""
    return text.split("\n")


def _join_lines(lines: list[str]) -> str:
    """Join lines back into text."""
    return "\n".join(lines)


# ---- Ad patterns ----

_AD_PATTERNS: list[re.Pattern[str]] = [
    # URLs
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"www\.\S+", re.IGNORECASE),
    # Phone numbers (Chinese mobile)
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"\d{3,4}[-\s]?\d{7,8}"),
    # Social media handles
    re.compile(r"(加\s*微信|关注\s*公众号|扫码\s*关注|添加\s*好友)"),
    re.compile(r"(微信\s*[:：]\s*\S+|公众号\s*[:：]\s*\S+)"),
    re.compile(r"(QQ\s*[:：]\s*\d+|群号\s*[:：]\s*\d+)"),
    # Ad keywords
    re.compile(r"(求收藏|求推荐|求月票|求订阅|打赏|催更)", re.IGNORECASE),
    re.compile(r"(本章未完|请点击下一页|继续阅读|点击阅读|阅读更多)"),
    re.compile(r"(广告联系|广告合作|推广合作|赞助商|商务合作|本章广告)", re.IGNORECASE),
    # Email
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
]


def remove_ads(text: str) -> tuple[str, int]:
    """Remove advertisement-bearing lines.

    Returns (cleaned_text, ads_removed_count).
    """
    lines = _split_lines(text)
    kept: list[str] = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue

        is_ad = False
        for pat in _AD_PATTERNS:
            if pat.search(stripped):
                is_ad = True
                break
        if is_ad:
            removed += 1
        else:
            kept.append(line)

    return _join_lines(kept), removed


# ---- Page number patterns ----

_PAGE_NUMBER_PATTERNS: list[re.Pattern[str]] = [
    # "第X页" pattern
    re.compile(r"^第\s*[一二三四五六七八九十百千0-9]+\s*页\s*$"),
    # "- X -" or "-- X --" pattern
    re.compile(r"^[-—]+\s*\d+\s*[-—]+$"),
    # Pure digit line (likely page number when alone)
    re.compile(r"^\d{1,5}$"),
    # "Page X" pattern
    re.compile(r"^Page\s+\d+\s*$", re.IGNORECASE),
    # Chinese page number markers
    re.compile(r"^【[^】]*第[一二三四五六七八九十百千0-9]+页[^】]*】$"),
    re.compile(r"^[\[【]?\d+[\]】]?$"),
]


def remove_page_numbers(text: str) -> tuple[str, int]:
    """Remove page-number lines.

    Returns (cleaned_text, page_numbers_removed_count).
    """
    lines = _split_lines(text)
    kept: list[str] = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue

        is_page_num = False
        for pat in _PAGE_NUMBER_PATTERNS:
            if pat.match(stripped):
                is_page_num = True
                break
        if is_page_num and len(stripped) <= 15:
            removed += 1
        else:
            kept.append(line)

    return _join_lines(kept), removed


# ---- Garbled text detection ----


def _garbled_ratio(line: str) -> float:
    """Return the fraction of characters that are NOT CJK / letters / digits / common punctuation."""
    if not line:
        return 0.0

    valid = 0
    for ch in line:
        cp = ord(ch)
        # CJK Unified Ideographs
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or ord("a") <= cp <= ord("z")
            or ord("A") <= cp <= ord("Z")
            or ord("0") <= cp <= ord("9")
            or 0x3000 <= cp <= 0x303F
            or 0xFF00 <= cp <= 0xFFEF
            or cp
            in (
                0x2018,
                0x2019,
                0x201C,
                0x201D,  # '' ""
                0x2014,
                0x2026,  # — …
                0x3001,
                0x3002,  # 、。
                0x002E,
                0x002C,
                0x0021,
                0x003F,  # . , ! ?
                0x003B,
                0x003A,  # ; :
                0x0028,
                0x0029,
                0x2018,
                0x2019,  # ( )
                0x300A,
                0x300B,
                0x300C,
                0x300D,  # 《 》 「 」
                0x300E,
                0x300F,
                0x3008,
                0x3009,  # 『 』 〈 〉
                0xFF08,
                0xFF09,
                0xFF0C,
                0xFF0E,  # （ ） ， ．
                0xFF01,
                0xFF1F,
                0xFF1A,
                0xFF1B,  # ！ ？ ： ；
                0x201C,
                0x201D,  # " "
                0x0022,
                0x0027,  # " '
            )
            or ch in (" ", "\t", "\r", "\n")
        ):
            valid += 1

    return 1.0 - (valid / len(line))


def remove_garbled_lines(text: str) -> tuple[str, int]:
    """Remove lines where >50% of characters are non-CJK/non-ASCII/non-punctuation.

    Returns (cleaned_text, garbled_lines_removed_count).
    """
    lines = _split_lines(text)
    kept: list[str] = []
    removed = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue

        if _garbled_ratio(stripped) > 0.5:
            removed += 1
        else:
            kept.append(line)

    return _join_lines(kept), removed


# ---- Blank line compression ----


def compress_blank_lines(text: str) -> tuple[str, int]:
    """Compress 3+ consecutive blank lines down to 2 blank lines.

    Returns (cleaned_text, blank_lines_removed_count).
    """
    lines = _split_lines(text)
    kept: list[str] = []
    blank_run = 0
    removed = 0

    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                kept.append(line)
            else:
                removed += 1
        else:
            blank_run = 0
            kept.append(line)

    return _join_lines(kept), removed


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def clean_text(text: str) -> tuple[str, CleaningReport]:
    """Run the full cleaning pipeline on *text*.

    Order: ads → page numbers → garbled → blank-line compression.

    Returns (cleaned_text, CleaningReport).
    """
    original_count = count_text_units(text)

    cleaned = text
    total_ads = 0
    total_page = 0
    total_garbled = 0
    total_blank = 0

    # 1. Remove ads
    cleaned, removed = remove_ads(cleaned)
    total_ads += removed

    # 2. Remove page numbers
    cleaned, removed = remove_page_numbers(cleaned)
    total_page += removed

    # 3. Remove garbled lines
    cleaned, removed = remove_garbled_lines(cleaned)
    total_garbled += removed

    # 4. Compress blank lines
    cleaned, removed = compress_blank_lines(cleaned)
    total_blank += removed

    clean_count = count_text_units(cleaned)

    return cleaned, CleaningReport(
        original_word_count=original_count,
        clean_word_count=clean_count,
        ads_removed=total_ads,
        page_numbers_removed=total_page,
        garbled_lines_removed=total_garbled,
        blank_lines_removed=total_blank,
    )
