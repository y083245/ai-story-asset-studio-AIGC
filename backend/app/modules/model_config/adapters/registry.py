"""Adapter registry — maps provider_id to adapter instance."""

from __future__ import annotations

from app.modules.model_config.adapters.anthropic import AnthropicAdapter
from app.modules.model_config.adapters.baidu_qianfan import BaiduQianfanAdapter
from app.modules.model_config.adapters.base import BaseProviderAdapter
from app.modules.model_config.adapters.deepseek import DeepSeekAdapter
from app.modules.model_config.adapters.google_gemini import GeminiAdapter
from app.modules.model_config.adapters.google_imagen import GoogleImagenAdapter
from app.modules.model_config.adapters.moonshot import MoonshotAdapter
from app.modules.model_config.adapters.openai_compat import OpenAICompatAdapter
from app.modules.model_config.adapters.replicate import ReplicateAdapter
from app.modules.model_config.adapters.static_models import StaticModelsAdapter
from app.modules.model_config.adapters.volcengine import VolcengineAdapter
from app.modules.model_config.adapters.zhipu import ZhipuAdapter


class AdapterRegistry:
    """Look up the right adapter for a given provider_id."""

    def __init__(self) -> None:
        # Default adapter — works for most OpenAI-compatible providers
        self._default_adapter = OpenAICompatAdapter()

        # Adapters that need special preset model lists passed at build time.
        # The preset models for each provider get wired in from presets.py via
        # register_preset_models() rather than through a constructor argument
        # to avoid circular imports.
        self._preset_adapter_ids: set[str] = set()

        # Provider-specific adapters for non-standard auth or endpoints
        self._adapters: dict[str, BaseProviderAdapter] = {
            # Auth mechanism differences
            "anthropic": AnthropicAdapter(),
            "google_gemini": GeminiAdapter(),
            "google_imagen": GoogleImagenAdapter(),
            "zhipu_bigmodel": ZhipuAdapter(),
            "baidu_qianfan": BaiduQianfanAdapter(),
            # Endpoint differences
            "deepseek": DeepSeekAdapter(),
            "volcengine_ark": VolcengineAdapter(),
            "doubao_seedream": VolcengineAdapter(),
            "replicate": ReplicateAdapter(),
            # No models endpoint — returns preset models
            "tencent_hunyuan": StaticModelsAdapter(),
            # Parameter restrictions (temperature, etc.)
            "moonshot_kimi": MoonshotAdapter(),
        }

    def get(self, provider_id: str) -> BaseProviderAdapter:
        """Return the adapter for *provider_id*, falling back to OpenAI-compat."""
        adapter = self._adapters.get(provider_id)
        if adapter is not None:
            return adapter
        return self._default_adapter


_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    return _registry
