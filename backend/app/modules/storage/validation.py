"""File-type validation for M16 Storage.

All uploads pass through ``validate_file_type`` before they are written
to object storage. This prevents accidental or malicious uploads of
unsupported formats in production.
"""

from __future__ import annotations

from enum import StrEnum


class FileCategory(StrEnum):
    """Logical categories of accepted file types."""

    TEXT = "text"
    IMAGE = "image"


# Mapping from FileCategory to allowed extensions (lowercase, no dot)
_ALLOWED_EXTENSIONS: dict[FileCategory, frozenset[str]] = {
    FileCategory.TEXT: frozenset({"txt", "docx"}),
    FileCategory.IMAGE: frozenset({"png", "jpg", "jpeg", "webp"}),
}

# Allowed content types per extension (for the upload Content-Type header)
_CONTENT_TYPES: dict[str, str] = {
    "txt": "text/plain",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "json": "application/json",
}


def _extract_extension(file_name: str) -> str:
    """Return the lowercase file extension without the leading dot.

    Returns an empty string when the filename has no extension.
    """
    name = file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1].lower()


def _allowed_extensions_for_categories(allowed_categories: list[str]) -> frozenset[str]:
    """Return the union of allowed extensions for the given category names."""
    allowed: set[str] = set()
    for cat_name in allowed_categories:
        cat = FileCategory(cat_name)  # validates the category name
        allowed.update(_ALLOWED_EXTENSIONS[cat])
    return frozenset(allowed)


def validate_file_type(file_name: str, allowed_categories: list[str]) -> None:
    """Raise ``ValueError`` if *file_name* has a disallowed extension.

    Args:
        file_name: The original file name (e.g. ``"scene.jpg"``).
        allowed_categories: One or more ``FileCategory`` values (string form).

    Raises:
        ValueError: If the file extension is not in the allow-list for any
            of the given categories, or if *file_name* has no extension.

    Example:
        >>> validate_file_type("photo.png", ["image"])  # passes
        >>> validate_file_type("script.py", ["text"])  # raises ValueError
    """
    if not allowed_categories:
        raise ValueError("allowed_categories must not be empty")

    ext = _extract_extension(file_name)
    if not ext:
        raise ValueError(f"File '{file_name}' has no extension; allowed categories: {allowed_categories}")

    allowed = _allowed_extensions_for_categories(allowed_categories)
    if ext not in allowed:
        raise ValueError(
            f"File extension '.{ext}' is not allowed. "
            f"Allowed categories: {allowed_categories}. "
            f"Allowed extensions: {sorted(allowed)}"
        )


def infer_content_type(file_name: str) -> str:
    """Return the MIME content-type for the given file name.

    Returns ``"application/octet-stream"`` for unknown extensions.
    """
    ext = _extract_extension(file_name)
    return _CONTENT_TYPES.get(ext, "application/octet-stream")
