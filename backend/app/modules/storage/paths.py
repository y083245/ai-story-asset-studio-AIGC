"""Object-storage path generation for M16 Storage.

All asset paths follow the convention::

    projects/{project_id}/{category}/{...}.{extension}

The path is the canonical ``asset_id`` used throughout the system.
"""

from __future__ import annotations

import os
import re
from typing import Any

# =============================================================================
# Path templates per asset category
# =============================================================================

# Each entry maps a category key to a path template relative to
# ``projects/{project_id}/``. Templates use ``{placeholder}``
# substitution from the keyword arguments passed to ``build_asset_path``.

_PATH_TEMPLATES: dict[str, str] = {
    # Novels
    "novels": "novels/{file_name}",
    # Characters
    "characters": "characters/{character_id}/{asset_name}.png",
    # Scenes
    "scenes": "scenes/{scene_id}/{asset_name}.png",
    # Props
    "props": "props/{prop_id}/{asset_name}.png",
}

# ---------------------------------------------------------------------------
# Required keyword arguments per category (used for validation)
# ---------------------------------------------------------------------------

_REQUIRED_KWARGS: dict[str, list[str]] = {
    "novels": ["file_name"],
    "characters": ["character_id", "asset_name"],
    "scenes": ["scene_id", "asset_name"],
    "props": ["prop_id", "asset_name"],
}

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_IMAGE_ASSET_CATEGORIES = {"characters", "scenes", "props"}


def build_asset_path(project_id: str, asset_category: str, **kwargs: Any) -> str:
    """Build a canonical storage path for the given asset type.

    Args:
        project_id: The project UUID.
        asset_category: One of the supported categories:
            ``novels``, ``characters``, ``scenes``, ``props``.
        **kwargs: Category-specific identifiers (e.g. ``character_id``,
            ``scene_id``, ``prop_id``, ``asset_name``, ``file_name``).

    Returns:
        Absolute object-storage path (no leading slash).

    Raises:
        ValueError: If ``asset_category`` is unknown or required keyword
            arguments are missing.

    Example:
        >>> build_asset_path("proj-1", "characters", character_id="CH_001", asset_name="front")
        'projects/proj-1/characters/CH_001/front.png'

        >>> build_asset_path("proj-1", "novels", file_name="chapter1.txt")
        'projects/proj-1/novels/chapter1.txt'
    """
    if asset_category not in _PATH_TEMPLATES:
        raise ValueError(
            f"Unknown asset_category '{asset_category}'. Must be one of: {', '.join(sorted(_PATH_TEMPLATES))}"
        )

    _validate_path_segment(project_id)

    # Validate required kwargs
    required = _REQUIRED_KWARGS[asset_category]
    missing = [k for k in required if k not in kwargs]
    if missing:
        raise ValueError(f"Asset category '{asset_category}' requires keyword arguments: {missing}")
    for key in required:
        _validate_path_segment(str(kwargs[key]))

    # Build relative path from template
    relative = _PATH_TEMPLATES[asset_category].format(**kwargs)
    extension = str(kwargs.get("extension", "")).lstrip(".").lower()
    if extension and asset_category in _IMAGE_ASSET_CATEGORIES:
        _validate_path_segment(extension, message="Invalid file extension")
        relative = re.sub(r"\.png$", f".{extension}", relative)
    # Sanitize: strip leading/trailing slashes or backslashes
    relative = relative.strip("/\\")

    return os.path.join("projects", project_id, relative).replace("\\", "/")


def build_thumbnail_path(asset_path: str) -> str:
    """Derive a thumbnail path from an existing asset path.

    The thumbnail is placed in the same directory as the original asset,
    with a ``thumb_`` prefix prepended to the filename and the extension
    changed to ``.png``.

    Example:
        >>> build_thumbnail_path("projects/p1/characters/CH_001/front.png")
        'projects/p1/characters/CH_001/thumb_front.png'
    """
    normalized = asset_path.replace("\\", "/")
    if normalized.startswith("/") or any(part in ("", ".", "..") for part in normalized.split("/")):
        raise ValueError("Invalid asset path")
    for part in normalized.split("/"):
        _validate_path_segment(part, message="Invalid asset path")

    directory = os.path.dirname(normalized)
    basename = os.path.basename(normalized)
    stem, _ = os.path.splitext(basename)
    thumb_name = f"thumb_{stem}.png"
    return os.path.join(directory, thumb_name).replace("\\", "/")


def _validate_path_segment(value: str, *, message: str = "Invalid path segment") -> None:
    if not value or "/" in value or "\\" in value or value in {".", ".."} or not _SAFE_SEGMENT_RE.fullmatch(value):
        raise ValueError(f"{message}: {value!r}")
