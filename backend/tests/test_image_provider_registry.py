from __future__ import annotations

import json

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import dalle as dalle_module
from app.modules.provider_adapter import flux_pro as flux_module
from app.modules.provider_adapter import imagen as imagen_module
from app.modules.provider_adapter import registry as registry_module
from app.modules.provider_adapter.dalle import DalleProvider
from app.modules.provider_adapter.fake import FakeSeedreamProvider
from app.modules.provider_adapter.flux_pro import FluxProProvider
from app.modules.provider_adapter.imagen import ImagenProvider


def _service(tmp_path, provider_id: str, model: str, base_url: str, api_key: str = "sk-live-image") -> ModelConfigService:
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "base_url": "https://api.deepseek.com",
                    "api_key": "sk-text",
                },
                "image": {
                    "provider_id": provider_id,
                    "model": model,
                    "base_url": base_url,
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigService(config_path=config_path)


def test_registry_selects_openai_image_provider(monkeypatch, tmp_path) -> None:
    service = _service(tmp_path, "openai", "dall-e-3", "https://api.openai.com/v1")
    monkeypatch.setattr(registry_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(dalle_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(registry_module.settings, "provider_mode", "real")

    provider = registry_module.ProviderRegistry(env="production").get_image_generator()

    assert isinstance(provider, DalleProvider)
    assert provider.provider_id == "openai"
    assert provider.model_name == "dall-e-3"


def test_registry_selects_replicate_flux_provider(monkeypatch, tmp_path) -> None:
    service = _service(
        tmp_path,
        "replicate",
        "black-forest-labs/flux-pro",
        "https://api.replicate.com/v1",
        api_key="r8_live_image_token",
    )
    monkeypatch.setattr(registry_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(flux_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(registry_module.settings, "provider_mode", "real")

    provider = registry_module.ProviderRegistry(env="production").get_image_generator()

    assert isinstance(provider, FluxProProvider)
    assert provider.provider_id == "replicate"
    assert provider.model_name == "black-forest-labs/flux-pro"


def test_registry_selects_google_imagen_provider(monkeypatch, tmp_path) -> None:
    service = _service(
        tmp_path,
        "google_imagen",
        "imagen-4.0-generate-001",
        "https://generativelanguage.googleapis.com/v1beta",
        api_key="gemini-live-image-key",
    )
    monkeypatch.setattr(registry_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(imagen_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(registry_module.settings, "provider_mode", "real")

    provider = registry_module.ProviderRegistry(env="production").get_image_generator()

    assert isinstance(provider, ImagenProvider)
    assert provider.provider_id == "google_imagen"
    assert provider.model_name == "imagen-4.0-generate-001"


def test_registry_keeps_fake_mode_fallback(monkeypatch, tmp_path) -> None:
    service = _service(tmp_path, "openai", "dall-e-3", "https://api.openai.com/v1")
    monkeypatch.setattr(registry_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(registry_module.settings, "provider_mode", "fake")

    provider = registry_module.ProviderRegistry(env="development").get_image_generator()

    assert isinstance(provider, FakeSeedreamProvider)
