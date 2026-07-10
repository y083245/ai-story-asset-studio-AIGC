"""File parser for novel intake.

Handles: plain text, .txt files (UTF-8 + common Chinese encodings), .docx files.
Explicitly rejects: .pdf files.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass
class ParseResult:
    """Result of parsing a novel input."""

    raw_text: str
    encoding: str = "utf-8"
    input_type: str = "text"


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def parse_text(text: str) -> ParseResult:
    """Parse plain text directly from the request body."""
    return ParseResult(raw_text=text, encoding="utf-8", input_type="text")


# ---------------------------------------------------------------------------
# .txt file
# ---------------------------------------------------------------------------


# Encodings to try in order for Chinese text files
_TXT_ENCODINGS: list[str] = [
    "utf-8",
    "gbk",
    "gb2312",
    "gb18030",
    "big5",
    "utf-16",
    "latin-1",  # fallback — decodes everything
]


def parse_txt(file_bytes: bytes, file_name: str = "") -> ParseResult:
    """Parse a .txt file, trying common encodings.

    Tries UTF-8 first, then GBK/GB2312/GB18030/BIG5 for Chinese content.
    Falls back to latin-1 as a last resort.
    """
    if not file_name.lower().endswith(".txt"):
        raise ValueError(f"Expected .txt file, got: {file_name}")

    if not file_bytes:
        raise ValueError("File is empty")

    last_error: Exception | None = None

    for enc in _TXT_ENCODINGS:
        try:
            raw_text = file_bytes.decode(enc)
            # Simple heuristic: if the decoded text has a reasonable amount
            # of printable characters, treat it as successful.
            # Skip empty results from encoding mismatches.
            if len(raw_text.strip()) > 0:
                return ParseResult(raw_text=raw_text, encoding=enc, input_type="txt")
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
            continue

    # If all encodings failed, raise
    raise ValueError(f"Failed to decode .txt file with any encoding: {last_error}")


# ---------------------------------------------------------------------------
# .docx file
# ---------------------------------------------------------------------------


def parse_docx(file_bytes: bytes, file_name: str = "") -> ParseResult:
    """Parse a .docx file, extracting all paragraph text.

    Uses python-docx to extract text from paragraphs, filtering empty ones.
    """
    if not file_name.lower().endswith(".docx"):
        raise ValueError(f"Expected .docx file, got: {file_name}")

    if not file_bytes:
        raise ValueError("File is empty")

    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError("python-docx is required for .docx parsing. Install with: pip install python-docx") from exc

    doc = Document(BytesIO(file_bytes))
    paragraphs: list[str] = []

    for para in doc.paragraphs:
        text = para.text
        if text is not None and text.strip():
            paragraphs.append(text)

    raw_text = "\n".join(paragraphs)
    return ParseResult(raw_text=raw_text, encoding="utf-8", input_type="docx")


# ---------------------------------------------------------------------------
# .pdf — explicit rejection
# ---------------------------------------------------------------------------


class PdfRejectedError(ValueError):
    """PDF files are explicitly not supported for novel intake."""

    def __init__(self, file_name: str = "") -> None:
        super().__init__(
            f"PDF files are not supported for novel intake. "
            f"Please convert '{file_name}' to .txt or .docx format and try again."
        )
        self.file_name = file_name


def reject_pdf(file_name: str) -> None:
    """Raise PdfRejectedError if the file looks like a PDF."""
    if file_name.lower().endswith(".pdf"):
        raise PdfRejectedError(file_name)


# ---------------------------------------------------------------------------
# Router / unified entry point
# ---------------------------------------------------------------------------


def parse_input(
    input_type: str,
    text: str | None = None,
    file_bytes: bytes | None = None,
    file_name: str = "",
) -> ParseResult:
    """Unified entry point: dispatch to the correct parser based on input_type.

    Args:
        input_type: One of ``"text"``, ``"txt"``, ``"docx"``.
        text: Raw text (for ``input_type="text"``).
        file_bytes: Downloaded file content (for ``input_type="txt"`` / ``"docx"``).
        file_name: Original file name (used for extension detection).

    Returns:
        ParseResult with raw_text, encoding, input_type.

    Raises:
        ValueError: On unsupported format or parse failure.
        PdfRejectedError: When a .pdf file is detected.
    """
    if input_type == "text":
        if not text:
            raise ValueError("text is required for input_type='text'")
        return parse_text(text)

    if input_type == "txt":
        if file_bytes is None:
            raise ValueError("file_bytes is required for input_type='txt'")
        return parse_txt(file_bytes, file_name)

    if input_type == "docx":
        if file_bytes is None:
            raise ValueError("file_bytes is required for input_type='docx'")
        # Reject PDF disguised as other types
        reject_pdf(file_name)
        return parse_docx(file_bytes, file_name)

    raise ValueError(f"Unsupported input_type: {input_type}")
