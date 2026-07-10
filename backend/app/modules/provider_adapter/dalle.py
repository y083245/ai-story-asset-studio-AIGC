"""OpenAI Images provider for DALL-E style image generation."""

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
    download_provider_image,
    http_error,
    image_prompt,
    validate_image_request,
)

_PROVIDER = "openai"


class DalleProvider(ImageGenerationProvider):
    """Generate images through OpenAI's Images API."""

    def __init__(self) -> None:
        config = get_model_config_service().load_secret_config().image
        self._api_key = config.api_key
        if not self._api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message="[openai] Missing API key. Save it in local_config/model-providers.json.",
                provider=_PROVIDER,
                retryable=False,
            )
        self._model = config.model or "dall-e-3"
        self._base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")

    @property
    def provider_id(self) -> str:
        return _PROVIDER

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        validate_image_request(request, provider=_PROVIDER)
        start = time.perf_counter()
        payload = self._build_payload(request)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )
                if response.status_code >= 400:
                    raise http_error(response, provider=_PROVIDER)
                data = response.json()
                images, image_urls = await _extract_openai_images(data, client)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[openai] request timed out",
                provider=_PROVIDER,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[openai] request failed",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[openai] unexpected response shape",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc

        if not images:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[openai] response did not include image bytes",
                provider=_PROVIDER,
                retryable=True,
            )

        return ImageGenerationResponse(
            images=images,
            image_urls=image_urls,
            model=str(data.get("model") or self._model) if isinstance(data, dict) else self._model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_task_id=str(data.get("id") or "") if isinstance(data, dict) else "",
        )

    def _build_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": image_prompt(request),
            "n": 1,
            "size": _openai_size(self._model, request.width, request.height),
        }
        if self._model.startswith("dall-e"):
            payload["response_format"] = "b64_json"
            if self._model == "dall-e-3":
                payload["quality"] = "hd"
                payload["style"] = "natural"
        return payload


def _openai_size(model: str, width: int, height: int) -> str:
    if not model.startswith("dall-e"):
        return f"{width}x{height}"
    if model == "dall-e-2":
        return "1024x1024"
    if width > height:
        return "1792x1024"
    if height > width:
        return "1024x1792"
    return "1024x1024"


async def _extract_openai_images(
    data: Any,
    client: httpx.AsyncClient,
) -> tuple[list[bytes], list[str]]:
    if not isinstance(data, dict):
        raise ValueError("response is not a JSON object")
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise ValueError("response data is empty")

    images: list[bytes] = []
    image_urls: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        b64_image = item.get("b64_json")
        if isinstance(b64_image, str) and b64_image:
            images.append(base64.b64decode(b64_image))
            continue
        image_url = item.get("url")
        if isinstance(image_url, str) and image_url:
            image_urls.append(image_url)
            images.append(await download_provider_image(image_url, client, provider=_PROVIDER))
    return images, image_urls
