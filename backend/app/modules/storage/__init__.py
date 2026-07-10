"""Storage module for novel files and generated image assets."""

from __future__ import annotations

from app.modules.storage.paths import build_asset_path, build_thumbnail_path
from app.modules.storage.service import StorageService, StorageUploadResult
from app.modules.storage.validation import FileCategory, validate_file_type

__all__ = [
    "build_asset_path",
    "build_thumbnail_path",
    "FileCategory",
    "StorageService",
    "StorageUploadResult",
    "validate_file_type",
]
