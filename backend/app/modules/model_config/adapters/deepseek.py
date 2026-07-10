"""DeepSeek adapter — Bearer auth, models at ``/models`` (NOT ``/v1/models``).

DeepSeek's API is OpenAI-compatible but the models endpoint is at the root
``/models`` path, not under ``/v1/``.
"""

from __future__ import annotations

from app.modules.model_config.adapters.openai_compat import OpenAICompatAdapter


class DeepSeekAdapter(OpenAICompatAdapter):
    """DeepSeek has models at ``/models``, not ``/v1/models``."""

    auth_label = "API Key (Bearer)"

    def __init__(self) -> None:
        super().__init__(models_path="/models")
