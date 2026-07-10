"""Standard OpenAI-compatible adapter — Bearer auth, /v1/models endpoint.

Covers: OpenAI, DeepSeek, Moonshot/Kimi, Tencent Hunyuan, xAI Grok,
Mistral, OpenRouter, Together AI, SiliconFlow, Alibaba DashScope.
"""

from __future__ import annotations

import re

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0

# Prefixes that, when already present at the end of the base URL, mean
# we should *not* prepend /v1 to the models path.
_VERSION_SEGMENT_RE = re.compile(r"/v\d+(\w+)?$")


def _build_models_url(base_url: str, models_path: str = "/v1/models") -> str:
    """Build the full models endpoint URL, avoiding double /v1 segments.

    ``base_url`` may or may not end with ``/v1`` (e.g. DeepSeek's base is
    ``https://api.deepseek.com`` while OpenAI's is ``https://api.openai.com/v1``).
    """
    trimmed = base_url.rstrip("/")

    # If base already ends with a version segment (/v1, /v1beta, /v4, etc.),
    # append just /models (or whatever the models_path says minus /v1).
    if _VERSION_SEGMENT_RE.search(trimmed):
        # If models_path is "/v1/models", use "/models" instead.
        # If it's something else like "/models" (for volcengine), use as-is.
        if models_path.startswith("/v1/"):
            return trimmed + models_path[3:]  # "/v1/models" → "/models"
        if models_path.startswith("/v"):
            # Non-/v1 version like /v3 — just use as-is if not already present
            return trimmed + models_path
        return trimmed + models_path
    else:
        return trimmed + models_path


def _extract_model_ids(data: object) -> list[str]:
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object with a 'data' array")
    raw_items = data.get("data") or []
    if not isinstance(raw_items, list):
        raise ValueError("Expected 'data' to be an array")
    seen: set[str] = set()
    ids: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)
    return sorted(ids)


def _humanize(model_id: str) -> str:
    return " ".join(
        part.upper() if part.isdigit() else part.capitalize()
        for part in model_id.replace("_", "-").split("-")
    )


class OpenAICompatAdapter(BaseProviderAdapter):
    """Bearer-auth providers with an OpenAI-compatible ``/v1/models`` endpoint."""

    auth_label = "API Key (Bearer)"

    def __init__(self, models_path: str = "/v1/models") -> None:
        self._models_path = models_path

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        url = _build_models_url(base_url, self._models_path)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_value}",
        }
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [
            ModelOption(value=mid, label=_humanize(mid))
            for mid in _extract_model_ids(data)
        ]

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        try:
            models = await self.list_models(base_url, auth_value)
            if models:
                return True, f"连接成功，获取到 {len(models)} 个模型"
            return True, "连接成功，但未获取到模型列表"
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code in {401, 403}:
                return False, f"鉴权失败 (HTTP {code})，请检查 API Key"
            return False, f"请求失败 (HTTP {code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"
