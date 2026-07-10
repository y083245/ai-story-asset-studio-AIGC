"""Google Imagen model-config adapter."""

from __future__ import annotations

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0
_IMAGEN_MODELS: list[ModelOption] = [
    ModelOption(value="imagen-4.0-generate-001", label="Imagen 4"),
    ModelOption(value="imagen-4.0-ultra-generate-001", label="Imagen 4 Ultra"),
    ModelOption(value="imagen-4.0-fast-generate-001", label="Imagen 4 Fast"),
]


class GoogleImagenAdapter(BaseProviderAdapter):
    """Adapter for Google Imagen's Gemini API surface."""

    auth_label = "Gemini API Key (x-goog-api-key)"

    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        # Imagen's public docs expose a small curated model family. The general
        # /models endpoint may omit image-only models, so return the supported
        # preset list instead of mixing in text Gemini models.
        return list(_IMAGEN_MODELS)

    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Accept": "application/json", "x-goog-api-key": auth_value}
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
            if response.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {response.status_code})，请检查 Gemini API Key"
            if response.status_code < 500:
                return True, "连接成功（Gemini API Key 有效）"
            return False, f"服务器错误 (HTTP {response.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"
