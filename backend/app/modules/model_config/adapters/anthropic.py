"""Anthropic adapter — ``x-api-key`` header auth, static model list.

Anthropic does not expose a public ``/v1/models`` endpoint for API users.
We use a curated static list and a lightweight status check via the
Messages API (empty prompt rejected → credentials are valid).
"""

from __future__ import annotations

import re

import httpx

from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.schemas import ModelOption

_FETCH_TIMEOUT = 15.0
_VERSION_SEGMENT_RE = re.compile(r"/v\d+(\w+)?$")

# Keep this list roughly up-to-date with https://docs.anthropic.com/en/docs/about-claude/models
_ANTHROPIC_MODELS: list[ModelOption] = [
    ModelOption(value="claude-opus-4-8", label="Claude Opus 4.8"),
    ModelOption(value="claude-sonnet-4-6", label="Claude Sonnet 4.6"),
    ModelOption(value="claude-haiku-4-5-20251001", label="Claude Haiku 4.5"),
    ModelOption(value="claude-fable-5", label="Claude Fable 5"),
    ModelOption(value="claude-opus-4-5", label="Claude Opus 4.5"),
    ModelOption(value="claude-opus-4", label="Claude Opus 4"),
    ModelOption(value="claude-sonnet-4-5", label="Claude Sonnet 4.5"),
    ModelOption(value="claude-sonnet-4", label="Claude Sonnet 4"),
    ModelOption(value="claude-3-5-sonnet-20241022", label="Claude 3.5 Sonnet"),
    ModelOption(value="claude-3-5-haiku-20241022", label="Claude 3.5 Haiku"),
]


class AnthropicAdapter(BaseProviderAdapter):
    """Anthropic uses ``x-api-key`` header (not Bearer)."""

    auth_label = "API Key (x-api-key header)"

    # ------------------------------------------------------------------
    async def authenticate(self, api_key: str) -> str:
        return api_key.strip()

    # ------------------------------------------------------------------
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        # Anthropic doesn't have a /v1/models — return known models.
        return list(_ANTHROPIC_MODELS)

    # ------------------------------------------------------------------
    def build_auth_headers(self, auth_value: str) -> dict[str, str]:
        return {
            "x-api-key": auth_value,
            "anthropic-version": "2023-06-01",
        }

    def build_chat_url(self, base_url: str) -> str:
        trimmed = base_url.rstrip("/")
        if _VERSION_SEGMENT_RE.search(trimmed):
            return trimmed + "/messages"
        return trimmed + "/v1/messages"

    # ------------------------------------------------------------------
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        """Send a minimal Messages request.  A 401/403 means bad key."""
        trimmed = base_url.rstrip("/")
        url = trimmed + "/messages" if _VERSION_SEGMENT_RE.search(trimmed) else trimmed + "/v1/messages"
        headers = {
            "Accept": "application/json",
            "x-api-key": auth_value,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        # Smallest valid body — will be rejected for missing content, but auth is checked first.
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }
        try:
            async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=body)
            if resp.status_code in {401, 403}:
                return False, f"鉴权失败 (HTTP {resp.status_code})，请检查 API Key"
            # Any non-auth error (including invalid model) means the key works.
            if resp.status_code < 500:
                return True, "连接成功（API Key 有效）"
            return False, f"服务器错误 (HTTP {resp.status_code})"
        except httpx.RequestError as exc:
            return False, f"网络错误: {exc}"
        except Exception as exc:
            return False, f"连接测试失败: {exc}"
