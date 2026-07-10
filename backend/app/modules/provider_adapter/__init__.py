"""Story Asset Studio provider adapter module.

Isolates external model SDKs (DeepSeek, Seedream, Vision Quality, object
storage) behind standard request/response interfaces.

Business modules MUST call providers through this module only;
they MUST NOT import or use provider SDKs directly.
"""

from app.modules.provider_adapter.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResponse,
    ObjectStorageProvider,
    StorageUploadRequest,
    StorageUploadResponse,
    TextGenerationProvider,
    TextGenerationRequest,
    TextGenerationResponse,
    VisionQualityProvider,
    VisionQualityRequest,
    VisionQualityResponse,
)
from app.modules.provider_adapter.registry import ProviderRegistry

__all__ = [
    # Text
    "TextGenerationRequest",
    "TextGenerationResponse",
    "TextGenerationProvider",
    # Image
    "ImageGenerationRequest",
    "ImageGenerationResponse",
    "ImageGenerationProvider",
    # Storage
    "StorageUploadRequest",
    "StorageUploadResponse",
    "ObjectStorageProvider",
    # Vision Quality
    "VisionQualityRequest",
    "VisionQualityResponse",
    "VisionQualityProvider",
    # Registry
    "ProviderRegistry",
]
