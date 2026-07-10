"""Adapter for providers that do NOT expose a models-list endpoint.

Returns preset/static model lists only.
"""

from __future__ import annotations

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0


class StaticModelsAdapter(BaseProviderAdapter):
    """For providers with no programmatic model listing (e.g. Zhipu, Hunyuan).

    ``list_models`` always returns the provided static list.
    ``test_connection`` sends a minimal chat request to verify credentials.
    """

    auth_label = "API Key (Bearer)"

    def __init__(self, static_models: list[ModelOption] | None = None) -> None:
        self._static_models = static_models or []

    def set_models(self, models: list[ModelOption]) -> None:
        self._static_models = models

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        return list(self._static_models)

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        """Send a minimal chat completions request to verify the key."""
        trimmed = base_url.rstrip("/")
        url = f"{trimmed}/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_value}",
            "Content-Type": "application/json",
        }
        body = {
            "model": (self._static_models[0].value if self._static_models else "default"),
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
            if resp.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {resp.status_code})，请检查 API Key"
            if resp.status_code < 500:
                return True, "连接成功（API Key 有效）"
            return False, f"服务器错误 (HTTP {resp.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"
