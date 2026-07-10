"""Moonshot / Kimi adapter — drops ``temperature`` for strict models.

Some Moonshot models (e.g. ``moonshot-v1-8k``) only accept ``temperature=0.6``
and reject any other value with HTTP 400.  To avoid this, we simply omit
``temperature`` from the payload and let the model use its default.
"""

from __future__ import annotations

from app.modules.model_config.adapters.openai_compat import OpenAICompatAdapter


class MoonshotAdapter(OpenAICompatAdapter):
    """Moonshot/Kimi has temperature restrictions on some models."""

    auth_label = "API Key (Bearer)"

    def sanitize_payload(self, payload: dict) -> dict:
        # Drop temperature — some models only accept 0.6, others accept a
        # different range.  Using the model default is safer.
        payload.pop("temperature", None)
        return payload
