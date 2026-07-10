"""Local JSON-backed model provider configuration service."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import settings
from app.modules.model_config.adapters.registry import get_adapter_registry
from app.modules.model_config.presets import IMAGE_PROVIDER_PRESETS, TEXT_PROVIDER_PRESETS, provider_presets
from app.modules.model_config.schemas import (
    LocalModelConfigInput,
    LocalModelPublicConfig,
    LocalModelSecretConfig,
    ModelOption,
    ModelProviderPublicConfig,
    ModelProviderSecretConfig,
    ProviderModelListRequest,
    ProviderModelListResponse,
    ProviderPreset,
    ProviderPresetResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)

DEFAULT_CONFIG_PATH = Path("local_config/model-providers.json")
FETCH_MODEL_TIMEOUT_SECONDS = 15.0
_PLACEHOLDER_API_KEYS = {
    "your-api-key",
    "your-seedream-api-key",
    "replace-with-your-api-key",
    "replace-with-your-text-model-api-key",
    "replace-with-your-seedream-api-key",
}


class ModelConfigService:
    """Read and write local model provider configuration."""

    def __init__(self, config_path: Path | str = DEFAULT_CONFIG_PATH) -> None:
        self._config_path = Path(config_path)

    @property
    def config_path(self) -> Path:
        return self._config_path

    def get_presets(self) -> ProviderPresetResponse:
        return provider_presets()

    # ── model list ───────────────────────────────────────────────────

    async def list_provider_models(
        self, payload: dict[str, Any] | ProviderModelListRequest
    ) -> ProviderModelListResponse:
        request = (
            payload if isinstance(payload, ProviderModelListRequest)
            else ProviderModelListRequest.model_validate(payload)
        )
        preset = _find_preset(request.kind, request.provider_id)
        preset_models = preset.models if preset is not None else []
        base_url = (request.base_url or preset.base_url if preset else request.base_url).strip()
        api_key = _normalize_api_key(request.api_key) or self._saved_api_key_for(
            request.kind, request.provider_id
        )

        if not base_url or "{" in base_url or "}" in base_url:
            return _preset_model_response(
                request.provider_id, preset_models, "请先填写完整 Base URL 后再获取上游模型"
            )

        if not api_key:
            return _preset_model_response(
                request.provider_id, preset_models,
                "未填写该厂商 API Key，已使用内置模型列表；填写后可获取上游模型",
            )

        adapter = get_adapter_registry().get(request.provider_id)

        try:
            auth_value = await adapter.authenticate(api_key)
        except ValueError as exc:
            return _preset_model_response(request.provider_id, preset_models, str(exc))

        try:
            models = await adapter.list_models(base_url, auth_value)
        except ValueError as exc:
            return _preset_model_response(request.provider_id, preset_models, str(exc))
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                message = f"上游模型列表请求未通过 API Key 验证（HTTP {status_code}），已使用内置模型列表"
            else:
                message = f"上游模型列表请求失败（HTTP {status_code}），已使用内置模型列表"
            return _preset_model_response(request.provider_id, preset_models, message)
        except httpx.RequestError:
            return _preset_model_response(
                request.provider_id, preset_models, "上游模型列表请求失败，请检查 Base URL 或网络"
            )

        if not models:
            return _preset_model_response(request.provider_id, preset_models, "上游模型列表为空，已使用内置默认模型")

        if request.kind == "image" and request.provider_id == "doubao_seedream":
            seedream_models = [m for m in models if "seedream" in m.value.lower()]
            if seedream_models:
                models = seedream_models
        if request.kind == "image" and request.provider_id == "openai":
            image_models = [
                m
                for m in models
                if m.value.lower().startswith("dall-e") or m.value.lower().startswith("gpt-image")
            ]
            if image_models:
                models = image_models

        return ProviderModelListResponse(
            provider_id=request.provider_id, models=models, source="remote"
        )

    # ── connection test ──────────────────────────────────────────────

    async def test_connection(
        self, payload: dict[str, Any] | TestConnectionRequest
    ) -> TestConnectionResponse:
        request = (
            payload if isinstance(payload, TestConnectionRequest)
            else TestConnectionRequest.model_validate(payload)
        )
        preset = _find_preset(request.kind, request.provider_id)
        base_url = (request.base_url or preset.base_url if preset else request.base_url).strip()
        api_key = _normalize_api_key(request.api_key) or self._saved_api_key_for(
            request.kind, request.provider_id
        )

        if not base_url:
            return TestConnectionResponse(success=False, message="请先填写 Base URL")
        if not api_key:
            return TestConnectionResponse(success=False, message="请先填写 API Key")

        adapter = get_adapter_registry().get(request.provider_id)

        try:
            auth_value = await adapter.authenticate(api_key)
        except ValueError as exc:
            return TestConnectionResponse(success=False, message=str(exc))

        ok, message = await adapter.test_connection(base_url, auth_value)
        return TestConnectionResponse(success=ok, message=message)

    # ── public config ────────────────────────────────────────────────

    def get_public_config(self) -> LocalModelPublicConfig:
        return self._to_public(self.load_secret_config())

    def save_config(
        self, payload: dict[str, Any] | LocalModelConfigInput
    ) -> LocalModelPublicConfig:
        incoming = (
            payload if isinstance(payload, LocalModelConfigInput)
            else LocalModelConfigInput.model_validate(payload)
        )
        current = self.load_secret_config()

        text = current.text
        image = current.image
        if incoming.text is not None:
            text = ModelProviderSecretConfig(
                provider_id=incoming.text.provider_id,
                model=incoming.text.model,
                base_url=incoming.text.base_url,
                api_key=_normalize_api_key(incoming.text.api_key)
                or (
                    current.text.api_key
                    if incoming.text.provider_id == current.text.provider_id
                    else ""
                ),
            )
        if incoming.image is not None:
            image = ModelProviderSecretConfig(
                provider_id=incoming.image.provider_id,
                model=incoming.image.model,
                base_url=incoming.image.base_url,
                api_key=_normalize_api_key(incoming.image.api_key)
                or (
                    current.image.api_key
                    if incoming.image.provider_id == current.image.provider_id
                    else ""
                ),
            )

        updated = LocalModelSecretConfig(text=text, image=image)
        self._write_secret_config(updated)
        return self._to_public(updated)

    def load_secret_config(self) -> LocalModelSecretConfig:
        if not self._config_path.exists():
            return self._default_secret_config()
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            return _normalize_secret_config(LocalModelSecretConfig.model_validate(data))
        except (json.JSONDecodeError, OSError, ValidationError):
            return self._default_secret_config()

    def has_text_api_key(self) -> bool:
        return bool(self.load_secret_config().text.api_key.strip())

    def has_image_api_key(self) -> bool:
        return bool(self.load_secret_config().image.api_key.strip())

    # ── internals ────────────────────────────────────────────────────

    def _saved_api_key_for(self, kind: str, provider_id: str) -> str:
        config = self.load_secret_config()
        provider = config.text if kind == "text" else config.image
        if provider.provider_id != provider_id:
            return ""
        return _normalize_api_key(provider.api_key)

    def _write_secret_config(self, config: LocalModelSecretConfig) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with contextlib.suppress(OSError):
            self._config_path.chmod(0o600)

    def _default_secret_config(self) -> LocalModelSecretConfig:
        text_preset = TEXT_PROVIDER_PRESETS[0]
        image_preset = IMAGE_PROVIDER_PRESETS[0]
        return LocalModelSecretConfig(
            text=ModelProviderSecretConfig(
                provider_id=text_preset.provider_id,
                model=settings.deepseek_model_name or text_preset.default_model,
                base_url=settings.deepseek_base_url or text_preset.base_url,
                api_key=_normalize_api_key(settings.deepseek_api_key),
            ),
            image=ModelProviderSecretConfig(
                provider_id=image_preset.provider_id,
                model=settings.seedream_model_name or image_preset.default_model,
                base_url=settings.seedream_base_url or image_preset.base_url,
                api_key=_normalize_api_key(settings.seedream_api_key),
            ),
        )

    def _to_public(self, config: LocalModelSecretConfig) -> LocalModelPublicConfig:
        return LocalModelPublicConfig(
            configured=bool(config.text.api_key.strip() and config.image.api_key.strip()),
            config_path=str(self._config_path),
            text=self._public_provider(config.text),
            image=self._public_provider(config.image),
        )

    @staticmethod
    def _public_provider(config: ModelProviderSecretConfig) -> ModelProviderPublicConfig:
        return ModelProviderPublicConfig(
            provider_id=config.provider_id,
            model=config.model,
            base_url=config.base_url,
            api_key_set=bool(config.api_key.strip()),
            api_key_preview=_mask_key(config.api_key),
        )


# ── helpers ──────────────────────────────────────────────────────────


def _mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _normalize_api_key(api_key: str) -> str:
    normalized = api_key.strip()
    lowered = normalized.lower()
    if lowered.startswith("authorization:"):
        normalized = normalized.split(":", 1)[1].strip()
        lowered = normalized.lower()
    if lowered.startswith("bearer "):
        normalized = normalized[7:].strip()
        lowered = normalized.lower()
    if _looks_like_placeholder_api_key(lowered):
        return ""
    return normalized


def _looks_like_placeholder_api_key(lowered_api_key: str) -> bool:
    return (
        lowered_api_key in _PLACEHOLDER_API_KEYS
        or lowered_api_key.startswith("replace-with-your-")
        or lowered_api_key.startswith("dummy-")
        or lowered_api_key.startswith("example-")
        or (
            lowered_api_key.startswith("test")
            and any(marker in lowered_api_key for marker in ("api", "key", "seedream", "image"))
        )
    )


def _normalize_secret_config(config: LocalModelSecretConfig) -> LocalModelSecretConfig:
    return LocalModelSecretConfig(
        text=ModelProviderSecretConfig(
            provider_id=config.text.provider_id,
            model=config.text.model,
            base_url=config.text.base_url,
            api_key=_normalize_api_key(config.text.api_key),
        ),
        image=ModelProviderSecretConfig(
            provider_id=config.image.provider_id,
            model=config.image.model,
            base_url=config.image.base_url,
            api_key=_normalize_api_key(config.image.api_key),
        ),
    )


def _find_preset(kind: str, provider_id: str) -> ProviderPreset | None:
    presets = TEXT_PROVIDER_PRESETS if kind == "text" else IMAGE_PROVIDER_PRESETS
    return next((p for p in presets if p.provider_id == provider_id), None)


def _preset_model_response(
    provider_id: str,
    models: list[ModelOption],
    error_message: str,
) -> ProviderModelListResponse:
    return ProviderModelListResponse(
        provider_id=provider_id, models=models, source="preset", error_message=error_message,
    )


# ── singleton ────────────────────────────────────────────────────────

_service = ModelConfigService()


def get_model_config_service() -> ModelConfigService:
    return _service
