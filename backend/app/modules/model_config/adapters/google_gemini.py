"""Google Gemini adapter — API key as query parameter.

Gemini uses ``?key={api_key}`` rather than an Authorization header for
the public API at ``generativelanguage.googleapis.com``.
"""

from __future__ import annotations

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0

# Known Gemini models (the /models endpoint doesn't return a clean list for v1beta).
_GEMINI_MODELS: list[ModelOption] = [
    ModelOption(value="gemini-3-pro-preview", label="Gemini 3 Pro Preview"),
    ModelOption(value="gemini-3-flash-preview", label="Gemini 3 Flash Preview"),
    ModelOption(value="gemini-2.5-pro", label="Gemini 2.5 Pro"),
    ModelOption(value="gemini-2.5-flash", label="Gemini 2.5 Flash"),
    ModelOption(value="gemini-2.0-flash", label="Gemini 2.0 Flash"),
    ModelOption(value="gemini-2.0-flash-lite", label="Gemini 2.0 Flash Lite"),
]


class GeminiAdapter(BaseProviderAdapter):
    """Google Gemini uses API key as a query parameter."""

    auth_label = "API Key (query param)"

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        """Try the models endpoint, fall back to known list."""
        url = f"{base_url.rstrip('/')}/models?key={auth_value}"
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data = resp.json()
            models = _parse_gemini_models(data)
            if models:
                return models
        except Exception:
            pass
        return list(_GEMINI_MODELS)

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        url = f"{base_url.rstrip('/')}/models?key={auth_value}"
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {resp.status_code})，请检查 API Key"
            if resp.is_success:
                return True, "连接成功（API Key 有效）"
            return False, f"请求失败 (HTTP {resp.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"


def _parse_gemini_models(data: object) -> list[ModelOption]:
    if not isinstance(data, dict):
        return []
    raw = data.get("models") or []
    if not isinstance(raw, list):
        return []
    models: list[ModelOption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        # Name format: "models/gemini-2.0-flash"
        if name.startswith("models/"):
            name = name[7:]
        display = str(item.get("displayName") or name).strip()
        if name and "gemini" in name.lower():
            models.append(ModelOption(value=name, label=display or name))
    return models
