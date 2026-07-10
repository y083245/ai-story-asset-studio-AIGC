"""Volcengine Ark / Doubao adapter — standard Bearer but models at ``/api/v3/models``.

Volcengine Ark's OpenAI-compatible endpoint is at ``/api/v3``, so the models
list is at ``{base}/models`` (not ``/v1/models``).
"""

from __future__ import annotations

from app.modules.model_config.adapters.openai_compat import OpenAICompatAdapter


class VolcengineAdapter(OpenAICompatAdapter):
    """Volcengine Ark uses ``/api/v3`` as base, so models are at ``/models`` relative to it."""

    auth_label = "API Key (Bearer)"

    def __init__(self) -> None:
        super().__init__(models_path="/models")
