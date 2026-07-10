"""Provider registry for Story Asset Studio.

The ProviderRegistry selects fake or real providers based on the application
environment. In "test" or "development" mode it returns fake providers. In
"production" it returns real providers where configured.

Usage::

    registry = ProviderRegistry(env="development")
    text_gen = registry.get_text_generator()
    response = await text_gen.generate(request)
"""

from __future__ import annotations

from app.config import settings
from app.modules.model_config.service import get_model_config_service
from app.modules.provider_adapter.base import (
    ImageGenerationProvider,
    ObjectStorageProvider,
    TextGenerationProvider,
    VisionQualityProvider,
)
from app.modules.provider_adapter.dalle import DalleProvider
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode
from app.modules.provider_adapter.fake import (
    FakeDeepSeekProvider,
    FakeObjectStorageProvider,
    FakeSeedreamProvider,
    FakeVisionQualityProvider,
)
from app.modules.provider_adapter.flux_pro import FluxProProvider
from app.modules.provider_adapter.imagen import ImagenProvider
from app.modules.provider_adapter.real import (
    AliyunOSSProvider,
    OpenAICompatibleTextProvider,
    RealVisionQualityProvider,
    SeedreamProvider,
    VolcengineTOSProvider,
)


class ProviderRegistry:
    """Registry that wires provider interfaces to concrete implementations.

    Selection logic:
    1. If ``env`` is ``"test"`` -> always fake.
    2. If ``settings.app_env`` is ``"development"`` and any required API key is
       missing -> fake (so local dev works without credentials).
    3. Otherwise -> real provider.
    """

    def __init__(self, env: str = "development") -> None:
        self._env = env
        self._use_fake = self._should_use_fake()

    def _should_use_fake(self) -> bool:
        """Determine whether to use fake providers."""
        if self._env == "test":
            return True
        if self._is_production() and settings.provider_mode == "fake":
            raise ProviderError(
                code=ProviderErrorCode.INVALID_REQUEST,
                message="provider_mode=fake is not allowed in production",
                provider="registry",
                retryable=False,
            )
        if settings.provider_mode == "fake":
            return True
        if settings.provider_mode == "real":
            return False
        return self._env != "production" and settings.app_env != "production"

    def _is_production(self) -> bool:
        return self._env == "production" or settings.app_env == "production"

    def _require_production_config(self, provider: str, *key_names: str) -> None:
        if self._use_fake or not self._is_production():
            return
        missing = [key_name for key_name in key_names if not getattr(settings, key_name, "")]
        if missing:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message=f"Missing production provider configuration for {provider}: {', '.join(missing)}",
                provider=provider,
                retryable=False,
            )

    # ------------------------------------------------------------------
    # Provider accessors
    # ------------------------------------------------------------------

    def get_text_generator(self) -> TextGenerationProvider:
        """Return the configured text generation provider."""
        config_service = get_model_config_service()
        if settings.provider_mode == "fake":
            return FakeDeepSeekProvider()
        if self._use_fake and not config_service.has_text_api_key():
            return FakeDeepSeekProvider()
        return OpenAICompatibleTextProvider()

    def get_image_generator(self) -> ImageGenerationProvider:
        """Return the configured image generation provider."""
        config_service = get_model_config_service()
        if settings.provider_mode == "fake":
            return FakeSeedreamProvider()
        if self._use_fake and not config_service.has_image_api_key():
            return FakeSeedreamProvider()
        provider_id = config_service.load_secret_config().image.provider_id
        if provider_id == "doubao_seedream":
            return SeedreamProvider()
        if provider_id == "replicate":
            return FluxProProvider()
        if provider_id == "google_imagen":
            return ImagenProvider()
        if provider_id == "openai":
            return DalleProvider()
        return SeedreamProvider()

    def get_storage(self) -> ObjectStorageProvider:
        """Return the configured object storage provider."""
        if self._use_fake:
            return FakeObjectStorageProvider()

        provider_name = settings.object_storage_provider
        if provider_name == "local":
            from app.modules.storage.local_storage import LocalFileSystemStorage

            return LocalFileSystemStorage()
        if provider_name == "volcengine":
            self._require_production_config("tos", "tos_access_key", "tos_secret_key", "tos_bucket", "tos_endpoint")
            return VolcengineTOSProvider()
        if provider_name == "aliyun":
            self._require_production_config(
                "aliyun-oss",
                "aliyun_oss_access_key",
                "aliyun_oss_secret_key",
                "aliyun_oss_bucket",
                "aliyun_oss_endpoint",
            )
            return AliyunOSSProvider()

        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"Unknown object_storage_provider: {provider_name}",
            provider="registry",
            retryable=False,
        )

    def get_vision_quality(self) -> VisionQualityProvider:
        """Return the configured vision quality provider."""
        if self._use_fake:
            return FakeVisionQualityProvider()
        return RealVisionQualityProvider()
