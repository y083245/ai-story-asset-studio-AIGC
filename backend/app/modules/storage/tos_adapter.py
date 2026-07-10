"""TOS (Volcengine TOS) adapter for M16 Storage.

This module wires the M17 Provider Adapter ``VolcengineTOSProvider``
(or its fake counterpart) into the Storage module WITHOUT importing
the TOS SDK directly. All cloud I/O flows through the abstract
``ObjectStorageProvider`` interface defined in M17.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.config import settings
from app.modules.provider_adapter.base import (
    ObjectStorageProvider,
)
from app.modules.provider_adapter.registry import ProviderRegistry

# =============================================================================
# Configuration validation
# =============================================================================


@dataclass
class TOSConfig:
    """Validated TOS connection parameters."""

    bucket: str
    region: str
    endpoint: str
    cdn_base_url: str


def validate_tos_config() -> TOSConfig:
    """Validate that all required TOS environment variables are set.

    Returns a ``TOSConfig`` on success.

    Raises:
        RuntimeError: If any required configuration value is missing.
    """
    missing: list[str] = []

    bucket = settings.tos_bucket
    if not bucket:
        missing.append("TOS_BUCKET")

    region = getattr(settings, "tos_region", "")
    if not region:
        missing.append("TOS_REGION")

    endpoint = settings.tos_endpoint
    if not endpoint:
        missing.append("TOS_ENDPOINT")

    cdn_base_url = getattr(settings, "cdn_base_url", "")
    if not cdn_base_url:
        missing.append("CDN_BASE_URL")

    if missing:
        raise RuntimeError(
            f"Missing required TOS configuration for production: {', '.join(missing)}. "
            f"Set these in your environment or .env file."
        )

    return TOSConfig(
        bucket=bucket,
        region=region,
        endpoint=endpoint,
        cdn_base_url=cdn_base_url,
    )


# =============================================================================
# Provider factory
# =============================================================================


def create_storage_provider() -> ObjectStorageProvider:
    """Create the storage provider based on current application config.

    - ``production`` with valid TOS config -> ``VolcengineTOSProvider``.
    - ``production`` with missing TOS config -> raises ``RuntimeError``.
    - ``development`` / ``staging`` / ``test`` -> ``FakeObjectStorageProvider``
      (in-memory, matches ``ProviderRegistry`` behavior).

    Returns:
        An ``ObjectStorageProvider`` instance.
    """
    if settings.app_env == "production":
        # Validate TOS config before creating the real provider
        validate_tos_config()
        registry = ProviderRegistry(env="production")
        return registry.get_storage()

    # Development / test: use the M17 registry which auto-selects fake
    registry = ProviderRegistry(env=settings.app_env)
    return registry.get_storage()


# =============================================================================
# Remote download helper (used when the provider is not local)
# =============================================================================


async def _download_via_signed_url(
    provider: ObjectStorageProvider,
    asset_id: str,
    client: httpx.AsyncClient | None = None,
) -> bytes:
    """Download file bytes by fetching the provider-generated signed URL.

    This is used by ``StorageService.download`` when the underlying
    provider does not expose a local ``download`` method.
    """
    url = await provider.get_signed_url(asset_id)

    async def _fetch(c: httpx.AsyncClient) -> bytes:
        resp = await c.get(url)
        resp.raise_for_status()
        return resp.content

    if client is not None:
        return await _fetch(client)
    async with httpx.AsyncClient(timeout=30.0) as c:
        return await _fetch(c)


async def _download_stream_via_signed_url(
    provider: ObjectStorageProvider,
    asset_id: str,
    chunk_size: int = 8192,
) -> AsyncIterator[bytes]:
    """Stream download via signed URL, yielding chunks."""
    url = await provider.get_signed_url(asset_id)
    async with httpx.AsyncClient(timeout=60.0) as client, client.stream("GET", url) as resp:
        resp.raise_for_status()
        async for chunk in resp.aiter_bytes(chunk_size):
            yield chunk
