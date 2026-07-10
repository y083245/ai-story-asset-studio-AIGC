"""Google Imagen provider for text-to-image generation."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.modules.model_config.service import get_model_config_service
from app.modules.provider_adapter.base import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode
from app.modules.provider_adapter.image_utils import (
    http_error,
    validate_image_request,
)

_PROVIDER = "google_imagen"


class ImagenProvider(ImageGenerationProvider):
    """Generate images through Google Imagen's Gemini API predict endpoint."""

    def __init__(self) -> None:
        config = get_model_config_service().load_secret_config().image
        self._api_key = config.api_key
        if not self._api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message="[google_imagen] Missing API key. Save it in local_config/model-providers.json.",
                provider=_PROVIDER,
                retryable=False,
            )
        self._model = config.model or "imagen-4.0-generate-001"
        self._base_url = (config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    @property
    def provider_id(self) -> str:
        return _PROVIDER

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        validate_image_request(request, provider=_PROVIDER)
        start = time.perf_counter()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        payload = {
            "instances": [{"prompt": _imagen_prompt(request)}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": _aspect_ratio(request.width, request.height),
                "personGeneration": "allow_adult",
            },
        }
        if _supports_image_size(self._model):
            payload["parameters"]["imageSize"] = "2K" if max(request.width, request.height) >= 1536 else "1K"

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/models/{self._model}:predict",
                    headers=headers,
                    json=payload,
                )
                if response.status_code >= 400:
                    raise http_error(response, provider=_PROVIDER)
                data = response.json()
                images = _extract_imagen_images(data)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[google_imagen] request timed out",
                provider=_PROVIDER,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[google_imagen] request failed",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[google_imagen] unexpected response shape",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc

        if not images:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[google_imagen] response did not include image bytes",
                provider=_PROVIDER,
                retryable=True,
            )

        return ImageGenerationResponse(
            images=images,
            image_urls=[],
            model=self._model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_task_id=str(data.get("metadata", {}).get("predictionId") or "") if isinstance(data, dict) else "",
        )


def _aspect_ratio(width: int, height: int) -> str:
    ratio = width / height
    candidates = {
        "1:1": 1.0,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
    }
    return min(candidates, key=lambda key: abs(candidates[key] - ratio))


def _imagen_prompt(request: ImageGenerationRequest) -> str:
    prompt = request.prompt.strip()
    negative = request.negative_prompt.strip()
    if not negative:
        return prompt
    return f"{prompt}\n\nAvoid: {negative}"


def _supports_image_size(model: str) -> bool:
    return "generate" in model and ("fast" not in model)


def _extract_imagen_images(data: Any) -> list[bytes]:
    if not isinstance(data, dict):
        raise ValueError("response is not a JSON object")
    raw_items = data.get("predictions") or data.get("generatedImages") or data.get("generated_images")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("response image list is empty")

    images: list[bytes] = []
    for item in raw_items:
        b64_image = _find_base64_image(item)
        if b64_image:
            images.append(base64.b64decode(b64_image))
    return images


def _find_base64_image(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    for key in ("bytesBase64Encoded", "bytes_base64_encoded", "imageBytes", "image_bytes", "b64_json"):
        item = value.get(key)
        if isinstance(item, str) and item:
            return item

    image = value.get("image")
    if isinstance(image, dict):
        return _find_base64_image(image)

    return ""
