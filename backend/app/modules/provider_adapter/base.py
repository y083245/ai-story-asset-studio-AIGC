"""Provider interfaces used by Story Asset Studio.

Business modules call these interfaces instead of importing vendor SDKs
directly. The open-source edition supports text analysis, image generation,
object storage, and image quality checks only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

# =============================================================================
# Text Generation (DeepSeek / LLM)
# =============================================================================


@dataclass
class TextGenerationRequest:
    """Standard text-generation request, provider-agnostic."""

    prompt: str
    system_prompt: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: int = 60
    thinking: Literal["enabled", "disabled"] | None = None
    reasoning_effort: Literal["high", "max"] | None = None
    user_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class TextGenerationResponse:
    """Standard text-generation response, provider-agnostic."""

    text: str
    json_data: dict[str, Any] | None = None
    model: str = ""
    latency_ms: int = 0
    provider_request_id: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""


class TextGenerationProvider(ABC):
    """Abstract provider for text / LLM generation."""

    @abstractmethod
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse: ...

    async def generate_json(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """Generate text and attempt to parse the top-level content as JSON.

        Override if the provider natively supports structured JSON output.
        The default implementation calls `generate` and tries `json.loads`.
        """
        import json as _json

        response = await self.generate(request)
        text = response.text.strip()

        # Attempt to extract a JSON block (```json ...``` or bare {...})
        if text.startswith("```"):
            # strip code fences
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        elif "```json" in text:
            block_start = text.index("```json") + len("```json")
            block_end = text.index("```", block_start) if "```" in text[block_start:] else len(text)
            text = text[block_start:block_end].strip()

        try:
            response.json_data = _json.loads(text)
        except (_json.JSONDecodeError, ValueError):
            response.json_data = None

        return response


# =============================================================================
# Image Generation (Seedream)
# =============================================================================


@dataclass
class ImageGenerationRequest:
    """Standard image-generation request."""

    prompt: str
    negative_prompt: str = ""
    width: int = 1080
    height: int = 1920
    reference_images: list[bytes] = field(default_factory=list)
    timeout_seconds: int = 120


@dataclass
class ImageGenerationResponse:
    """Standard image-generation response."""

    images: list[bytes] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    model: str = ""
    latency_ms: int = 0
    provider_task_id: str = ""


class ImageGenerationProvider(ABC):
    """Abstract provider for image generation."""

    @abstractmethod
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse: ...


# =============================================================================
# Object Storage (local / cloud)
# =============================================================================


@dataclass
class StorageUploadRequest:
    """Standard object-storage upload request."""

    file_bytes: bytes
    file_name: str
    content_type: str
    project_id: str


@dataclass
class StorageUploadResponse:
    """Standard object-storage upload response."""

    asset_id: str
    url: str
    signed_url: str
    expires_at: str  # ISO 8601


class ObjectStorageProvider(ABC):
    """Abstract provider for object storage (upload, signed URL, delete)."""

    @abstractmethod
    async def upload(self, request: StorageUploadRequest) -> StorageUploadResponse: ...

    @abstractmethod
    async def get_signed_url(self, asset_id: str, expires_seconds: int = 3600) -> str: ...

    @abstractmethod
    async def delete(self, asset_id: str) -> None: ...


# =============================================================================
# Vision Quality Provider
# =============================================================================


@dataclass
class VisionQualityRequest:
    """Standard vision-quality check request."""

    image: bytes | None = None
    reference_character_images: list[bytes] = field(default_factory=list)
    reference_scene_image: bytes | None = None
    check_dimensions: list[str] = field(default_factory=lambda: ["face", "outfit", "scene", "prop"])
    prompt: str = ""
    negative_prompt: str = ""
    asset_bible: dict[str, Any] | str | None = None
    style_keywords: list[str] = field(default_factory=list)
    expected_props: list[str] = field(default_factory=list)
    retry_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60


@dataclass
class VisionQualityResponse:
    """Standard vision-quality check response."""

    quality_score: float = 0.0
    face_consistency_score: float | None = None
    outfit_consistency_score: float | None = None
    scene_consistency_score: float | None = None
    prop_presence_score: float | None = None
    composition_score: float | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)
    retry_required: bool = False
    retry_prompt_patch: str = ""
    prompt_patch: str = ""


class VisionQualityProvider(ABC):
    """Abstract provider for image quality inspection."""

    @abstractmethod
    async def check_quality(self, request: VisionQualityRequest) -> VisionQualityResponse: ...
