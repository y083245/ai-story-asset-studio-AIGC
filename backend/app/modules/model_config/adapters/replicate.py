"""Replicate model-config adapter."""

from __future__ import annotations

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0


class ReplicateAdapter(BaseProviderAdapter):
    """Bearer-auth adapter for Replicate image models."""

    auth_label = "Replicate API Token"

    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        # Replicate has a search endpoint, but Phase 5 exposes a curated Flux
        # list so users do not accidentally select non-image models.
        return []

    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        url = f"{base_url.rstrip('/')}/account"
        headers = {"Authorization": f"Bearer {auth_value}", "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
            if response.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {response.status_code})，请检查 API Token"
            if response.status_code < 500:
                return True, "连接成功（API Token 有效）"
            return False, f"服务器错误 (HTTP {response.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"
