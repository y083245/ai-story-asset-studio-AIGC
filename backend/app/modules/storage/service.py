"""StorageService — the single entry-point for file I/O in Story Asset Studio.

Business modules MUST use this service for object-storage operations.
They MUST NOT import or use cloud SDKs directly.

Usage::

    from app.modules.storage.service import StorageService, StorageUploadResult

    service = StorageService(provider)
    result = await service.upload(b"...", "front.png", "image/png",
                                  project_id, "characters", character_id="CH_001")
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.config import settings
from app.modules.provider_adapter.base import (
    ObjectStorageProvider,
    StorageUploadRequest,
)
from app.modules.storage.local_storage import LocalFileSystemStorage
from app.modules.storage.paths import build_asset_path, build_thumbnail_path
from app.modules.storage.tos_adapter import (
    _download_stream_via_signed_url,
    _download_via_signed_url,
    create_storage_provider,
    validate_tos_config,
)
from app.modules.storage.validation import infer_content_type, validate_file_type

# =============================================================================
# Result types
# =============================================================================


@dataclass
class StorageUploadResult:
    """Normalised result returned by ``StorageService.upload``."""

    asset_id: str
    url: str
    signed_url: str
    expires_at: str  # ISO 8601


# =============================================================================
# Category -> allowed file types mapping
# =============================================================================

_CATEGORY_ALLOWED_TYPES: dict[str, list[str]] = {
    "novels": ["text"],
    "characters": ["image"],
    "scenes": ["image"],
    "props": ["image"],
}


# =============================================================================
# StorageService
# =============================================================================


class StorageService:
    """Unified object-storage facade for the Story Asset Studio backend.

    Responsibilities:
    - Path generation via ``build_asset_path`` / ``build_thumbnail_path``.
    - File-type validation before every upload.
    - Delegating actual I/O to the underlying ``ObjectStorageProvider``.
    - Providing helpers for download, existence check, streaming, cleanup.

    Lifecycle:
    - Initialise once at application startup via ``StorageService.create()``.
    - Reuse the same instance across all requests.
    """

    def __init__(self, provider: ObjectStorageProvider) -> None:
        self._provider = provider
        self._httpx_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(cls) -> StorageService:
        """Create a ``StorageService`` wired to the configured provider.

        Provider is selected by ``settings.object_storage_provider``:

        - ``local`` -> ``LocalFileSystemStorage``.
        - ``volcengine`` -> ``VolcengineTOSProvider`` (validated config).
        - ``aliyun`` -> ``AliyunOSSProvider`` (validated config).
        """
        provider_name = settings.object_storage_provider
        if settings.app_env == "production" and provider_name == "local":
            provider_name = "volcengine"

        if provider_name == "local":
            provider: ObjectStorageProvider = LocalFileSystemStorage()
        elif provider_name == "volcengine":
            validate_tos_config()
            provider = create_storage_provider()
        elif provider_name == "aliyun":
            from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode
            from app.modules.provider_adapter.real import AliyunOSSProvider

            missing = [
                name
                for name in (
                    "aliyun_oss_access_key",
                    "aliyun_oss_secret_key",
                    "aliyun_oss_bucket",
                    "aliyun_oss_endpoint",
                )
                if not getattr(settings, name, "")
            ]
            if missing:
                raise ProviderError(
                    code=ProviderErrorCode.AUTH_FAILED,
                    message=f"Missing Aliyun OSS configuration: {', '.join(missing)}",
                    provider="aliyun-oss",
                    retryable=False,
                )
            provider = AliyunOSSProvider()
        else:
            raise ValueError(f"Unknown object_storage_provider: {provider_name}")

        return cls(provider)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    async def upload(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str,
        project_id: str,
        asset_type: str,
        **path_kwargs: str,
    ) -> StorageUploadResult:
        """Upload a file to object storage.

        Args:
            file_bytes: Raw file content.
            file_name: Original file name (used for extension validation).
            content_type: MIME type (e.g. ``"image/png"``).
            project_id: Owning project UUID.
            asset_type: One of the supported asset categories
                (``"novels"``, ``"characters"``, ``"scenes"``, ``"props"``).
            **path_kwargs: Additional identifiers required by the asset
                category (e.g. ``character_id``, ``scene_id``, ``prop_id``).

        Returns:
            ``StorageUploadResult`` with the canonical ``asset_id``,
            public URL, signed URL, and expiration timestamp.

        Raises:
            ValueError: If the file type is disallowed for the category.
        """
        # Validate file type
        allowed = _CATEGORY_ALLOWED_TYPES.get(asset_type, [])
        if allowed:
            validate_file_type(file_name, allowed)

        # Build the canonical path (asset_id)
        asset_id = self._build_path_for_upload(file_name, project_id, asset_type, **path_kwargs)

        # Infer content type if not provided
        if not content_type:
            content_type = infer_content_type(file_name)

        # Delegate to the provider
        request = StorageUploadRequest(
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=content_type,
            project_id=project_id,
        )

        # For LocalFileSystemStorage we store by our canonical asset_id
        if isinstance(self._provider, LocalFileSystemStorage):
            response = await self._provider._upload_with_asset_id(request, asset_id)
        else:
            response = await self._provider.upload(request)
            asset_id = response.asset_id

        return StorageUploadResult(
            asset_id=asset_id,
            url=response.url,
            signed_url=response.signed_url,
            expires_at=response.expires_at,
        )

    async def download(self, asset_id: str) -> bytes:
        """Download the full contents of an asset.

        For local storage this reads directly from disk.
        For remote (TOS) storage this fetches via signed URL.
        """
        if isinstance(self._provider, LocalFileSystemStorage):
            return await self._provider.download(asset_id)
        return await _download_via_signed_url(self._provider, asset_id, self._httpx_client)

    async def exists(self, asset_id: str) -> bool:
        """Check whether an asset exists in object storage."""
        if isinstance(self._provider, LocalFileSystemStorage):
            return await self._provider.exists(asset_id)
        # For remote providers, attempt a HEAD request via signed URL
        try:
            url = await self._provider.get_signed_url(asset_id, expires_seconds=60)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.head(url)
                return resp.status_code < 400
        except Exception:
            return False

    async def delete(self, asset_id: str) -> None:
        """Delete an asset from object storage."""
        await self._provider.delete(asset_id)

    async def signed_url(self, asset_id: str, expires_seconds: int = 3600) -> str:
        """Generate a time-limited signed URL for read-only access."""
        return await self._provider.get_signed_url(asset_id, expires_seconds)

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def check_assets_exist(self, asset_ids: list[str]) -> dict[str, bool]:
        """Batch existence check.

        Returns:
            ``{asset_id: exists}`` mapping for every asset in *asset_ids*.
        """
        result: dict[str, bool] = {}
        for aid in asset_ids:
            result[aid] = await self.exists(aid)
        return result

    async def download_stream(self, asset_id: str) -> AsyncIterator[bytes]:
        """Stream an asset in chunks without loading it entirely into memory.

        Useful for large image or document files.
        """
        if isinstance(self._provider, LocalFileSystemStorage):
            async for chunk in self._provider.download_stream(asset_id):
                yield chunk
        else:
            async for chunk in _download_stream_via_signed_url(self._provider, asset_id):
                yield chunk

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def plan_cleanup(self, project_id: str) -> list[str]:
        """Return a list of asset paths that belong to *project_id*.

        For local storage this walks the project directory on disk.
        For remote storage this is a best-effort listing; the actual
        deletion happens via ``execute_cleanup``.

        Note:
            This method does NOT delete any files. It only produces a plan.
        """
        if isinstance(self._provider, LocalFileSystemStorage):
            return await self._plan_cleanup_local(project_id)
        # Remote storage: return a marker that execute_cleanup can use
        return [f"projects/{project_id}/"]

    async def execute_cleanup(self, project_id: str) -> int:
        """Delete all assets for *project_id* and return the number removed.

        For local storage this deletes all files under the project directory.
        For remote storage this deletes by prefix via the provider.
        """
        if isinstance(self._provider, LocalFileSystemStorage):
            return await self._execute_cleanup_local(project_id)
        # Remote storage: delete project prefix
        # The provider's delete works on asset_id; we recursively delete
        # each known asset under the prefix.
        plans = await self.plan_cleanup(project_id)
        count = 0
        for plan_path in plans:
            try:
                await self._provider.delete(plan_path)
                count += 1
            except Exception:
                pass
        return count

    # ------------------------------------------------------------------
    # Thumbnail helper
    # ------------------------------------------------------------------

    @staticmethod
    def thumbnail_path(asset_path: str) -> str:
        """Return the thumbnail path derived from an asset path.

        Convenience static-method wrapper around ``build_thumbnail_path``.
        """
        return build_thumbnail_path(asset_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_path_for_upload(self, file_name: str, project_id: str, asset_type: str, **extra_kwargs: str) -> str:
        """Construct the canonical asset path for an upload.

        Extra keyword arguments (e.g. ``character_id``,
        ``scene_id``, ``prop_id``) are forwarded
        directly to ``build_asset_path``.
        """
        kwargs: dict[str, str] = dict(extra_kwargs)

        # Fill in sensible defaults when the caller did not provide them
        base_name, extension = os.path.splitext(file_name)
        if extension:
            kwargs.setdefault("extension", extension.lstrip(".").lower())
        if asset_type == "novels" and "file_name" not in kwargs:
            kwargs.setdefault("file_name", file_name)
        elif asset_type in ("characters", "scenes", "props"):
            kwargs.setdefault("asset_name", base_name)
            if asset_type == "characters":
                kwargs.setdefault("character_id", "unknown")
            elif asset_type == "scenes":
                kwargs.setdefault("scene_id", "unknown")
            else:
                kwargs.setdefault("prop_id", "unknown")
        return build_asset_path(project_id, asset_type, **kwargs)

    async def _plan_cleanup_local(self, project_id: str) -> list[str]:
        """List all files under the local project directory."""
        ls = self._provider
        assert isinstance(ls, LocalFileSystemStorage)
        project_dir = os.path.join(ls._storage_root, "projects", project_id)
        paths: list[str] = []
        if os.path.isdir(project_dir):
            for root, _dirs, files in os.walk(project_dir):
                for fname in files:
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, ls._storage_root)
                    paths.append(rel_path.replace("\\", "/"))
        return paths

    async def _execute_cleanup_local(self, project_id: str) -> int:
        """Delete all files under the local project directory."""
        ls = self._provider
        assert isinstance(ls, LocalFileSystemStorage)
        project_dir = os.path.join(ls._storage_root, "projects", project_id)
        if not os.path.isdir(project_dir):
            return 0
        count = 0
        for root, dirs, files in os.walk(project_dir, topdown=False):
            for fname in files:
                file_path = os.path.join(root, fname)
                rel_path = os.path.relpath(file_path, ls._storage_root)
                # Remove from index
                ls._index.pop(rel_path, None)
                os.remove(file_path)
                count += 1
            # Remove empty directories
            for d in dirs:
                dir_path = os.path.join(root, d)
                with contextlib.suppress(OSError):
                    os.rmdir(dir_path)
        with contextlib.suppress(OSError):
            os.rmdir(project_dir)
        return count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Release any held resources (e.g. httpx client)."""
        if self._httpx_client is not None:
            await self._httpx_client.aclose()
            self._httpx_client = None
