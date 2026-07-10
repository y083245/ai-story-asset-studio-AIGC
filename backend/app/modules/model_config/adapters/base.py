"""Abstract base class for provider adapters."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.modules.model_config.schemas import ModelOption

_VERSION_SEGMENT_RE = re.compile(r"/v\d+(\w+)?$")


class BaseProviderAdapter(ABC):
    """Each provider gets its own adapter that knows its auth mechanism and model-list endpoint."""

    # Human-readable label for auth instructions shown in the UI.
    auth_label: str = "API Key"

    # ── abstract ─────────────────────────────────────────────────────

    @abstractmethod
    async def authenticate(self, api_key: str) -> str:
        """Resolve a raw API key / credential string into the value sent in the HTTP request.

        For Bearer providers this is the key itself.  For JWT providers it is the signed
        token.  For AK/SK providers it is the access token obtained via OAuth.
        """
        ...

    @abstractmethod
    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        """Fetch the list of available model IDs from the provider."""
        ...

    @abstractmethod
    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:
        """Quickly verify credentials work.  Returns (ok, message)."""
        ...

    # ── helpers (override if needed) ──────────────────────────────────

    def build_auth_headers(self, auth_value: str) -> dict[str, str]:
        """Return HTTP headers that carry the resolved auth value.

        The default is ``Authorization: Bearer {auth_value}``.  Adapters like
        Anthropic override this to ``x-api-key``.
        """
        return {"Authorization": f"Bearer {auth_value}"}

    def build_chat_url(self, base_url: str) -> str:
        """Return the chat-completions URL, avoiding double /v1 segments."""
        trimmed = base_url.rstrip("/")
        if _VERSION_SEGMENT_RE.search(trimmed):
            return trimmed + "/chat/completions"
        return trimmed + "/v1/chat/completions"

    def sanitize_payload(self, payload: dict) -> dict:
        """Normalize request payload for provider-specific constraints.

        Override this to fix incompatible parameters (e.g. temperature ranges)
        before the request is sent.  The default is a no-op pass-through.
        """
        return payload
