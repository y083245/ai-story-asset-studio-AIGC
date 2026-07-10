"""Semantic text chunking with context windows and overlap.

Splits cleaned novel text into overlapping chunks suitable for downstream
processing (analysis, embedding, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.modules.novel_intake.cleaning import count_text_units


@dataclass
class ChunkResult:
    """A single semantic chunk."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    chunk_index: int = 0
    content: str = ""
    start_char: int = 0
    end_char: int = 0
    word_count: int = 0
    context_before: str = ""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CHUNK_SIZE: int = 800  # target chunk size in characters
DEFAULT_CHUNK_MIN: int = 500  # minimum chunk size
DEFAULT_OVERLAP: int = 150  # overlap between adjacent chunks in characters


def _count_cjk(text: str) -> int:
    """Count text units for backward-compatible internal callers."""
    return count_text_units(text)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_min: int = DEFAULT_CHUNK_MIN,
    overlap: int = DEFAULT_OVERLAP,
) -> list[ChunkResult]:
    """Split *text* into overlapping semantic chunks.

    The algorithm:
    1. Splits text by paragraph boundaries (double newline).
    2. Accumulates paragraphs until the chunk reaches *chunk_size* characters.
    3. The last *overlap* characters of chunk N become the first *overlap*
       characters of chunk N+1.
    4. If the last chunk is too small (< *chunk_min*), it is merged into
       the previous chunk.

    Each chunk records:
    - ``chunk_index``: 0-based sequence number
    - ``start_char`` / ``end_char``: byte positions in the original text
    - ``content``: the chunk text
    - ``context_before``: the last sentence of the previous chunk (for context)
    - ``word_count``: Chinese character + non-Chinese word count
    """
    if not text.strip():
        return []

    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return []

    chunks: list[ChunkResult] = []
    current_chunk: list[str] = []
    current_start = 0
    char_offset = 0

    for para in paragraphs:
        para_len = len(para)
        current_len = sum(len(p) for p in current_chunk)

        if current_len + para_len > chunk_size and current_chunk:
            # Finalise current chunk
            content = "\n\n".join(current_chunk)
            end_offset = char_offset
            context_before = ""
            if chunks:
                prev = chunks[-1]
                # Use the last ~50 chars of the previous chunk as context
                context_before = prev.content[-min(len(prev.content), 80) :].strip()

            chunks.append(
                ChunkResult(
                    chunk_index=len(chunks),
                    content=content,
                    start_char=current_start,
                    end_char=end_offset,
                    word_count=_count_cjk(content),
                    context_before=context_before,
                )
            )

            # Start new chunk with overlap from the end of the previous chunk
            previous_content = content
            overlap_text = previous_content[-overlap:] if len(previous_content) > overlap else previous_content

            current_chunk = [overlap_text, para] if overlap_text else [para]
            current_start = end_offset - len(overlap_text) if overlap_text else char_offset
        else:
            if not current_chunk:
                current_start = char_offset
            current_chunk.append(para)

        char_offset += para_len + 2  # +2 for the "\n\n" separator

    # Final chunk
    if current_chunk:
        content = "\n\n".join(current_chunk)
        context_before = ""
        if chunks:
            prev = chunks[-1]
            context_before = prev.content[-min(len(prev.content), 80) :].strip()

        chunks.append(
            ChunkResult(
                chunk_index=len(chunks),
                content=content,
                start_char=current_start,
                end_char=len(text),
                word_count=_count_cjk(content),
                context_before=context_before,
            )
        )

    # Merge the last chunk if it's too small
    if len(chunks) >= 2 and chunks[-1].word_count < chunk_min:
        last = chunks.pop()
        prev = chunks[-1]
        merged_content = prev.content + "\n\n" + last.content
        prev.content = merged_content
        prev.end_char = last.end_char
        prev.word_count = _count_cjk(merged_content)

    return chunks
