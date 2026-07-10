from __future__ import annotations

from app.config import Settings, settings


def test_vision_quality_settings_are_declared_with_expected_defaults() -> None:
    assert settings.vision_quality_enabled is True
    assert settings.vision_quality_provider == "doubao"
    assert settings.vision_quality_model_name == "doubao-vision-quality"
    assert settings.vision_quality_pass_threshold == 60
    assert settings.vision_quality_max_retries == 3


def test_seedream_settings_default_model_uses_current_5_0_lite(monkeypatch) -> None:
    monkeypatch.delenv("SEEDREAM_MODEL_NAME", raising=False)

    default_settings = Settings(_env_file=None)

    assert default_settings.seedream_model_name == "doubao-seedream-5-0-lite-260128"
