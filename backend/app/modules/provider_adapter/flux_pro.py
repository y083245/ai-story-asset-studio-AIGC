"""Replicate-hosted Flux image provider."""

from __future__ import annotations

import asyncio
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

_PROVIDER = "replicate"
_TERMINAL_FAILURE_STATUSES = {"canceled", "failed"}


class FluxProProvider(ImageGenerationProvider):
    """Generate images through Replicate's Flux model predictions API."""

    def __init__(self) -> None:
        config = get_model_config_service().load_secret_config().image
        self._api_key = config.api_key
        if not self._api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message="[replicate] Missing API key. Save it in local_config/model-providers.json.",
                provider=_PROVIDER,
                retryable=False,
            )
        self._model = config.model or "black-forest-labs/flux-pro"
        self._base_url = (config.base_url or "https://api.replicate.com/v1").rstrip("/")

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
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait",
        }
        payload = {"input": _flux_input(request)}

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/models/{self._model}/predictions",
                    headers=headers,
                    json=payload,
                )
                if response.status_code >= 400:
                    raise http_error(response, provider=_PROVIDER)
                data = await _wait_for_prediction(response.json(), client, headers, request.timeout_seconds)
                images, image_urls = await _extract_replicate_images(data, client)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[replicate] request timed out",
                provider=_PROVIDER,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[replicate] request failed",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[replicate] unexpected response shape",
                provider=_PROVIDER,
                raw_error=str(exc)[:1000],
            ) from exc

        if not images:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[replicate] response did not include image bytes",
                provider=_PROVIDER,
                retryable=True,
            )

        return ImageGenerationResponse(
            images=images,
            image_urls=image_urls,
            model=self._model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_task_id=str(data.get("id") or "") if isinstance(data, dict) else "",
        )


def _flux_input(request: ImageGenerationRequest) -> dict[str, Any]:
    return {
        "prompt": image_prompt(request),
        "aspect_ratio": _aspect_ratio(request.width, request.height),
        "output_format": "png",
        "num_outputs": 1,
    }


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


async def _wait_for_prediction(
    data: Any,
    client: httpx.AsyncClient,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("prediction response is not a JSON object")
    deadline = time.monotonic() + timeout_seconds
    current = data
    while str(current.get("status") or "").lower() not in {"succeeded", *_TERMINAL_FAILURE_STATUSES}:
        poll_url = (current.get("urls") or {}).get("get")
        if not isinstance(poll_url, str) or not poll_url:
            break
        if time.monotonic() >= deadline:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[replicate] prediction timed out",
                provider=_PROVIDER,
            )
        await asyncio.sleep(1.0)
        response = await client.get(poll_url, headers=headers)
        if response.status_code >= 400:
            raise http_error(response, provider=_PROVIDER)
        current = response.json()
        if not isinstance(current, dict):
            raise ValueError("prediction poll response is not a JSON object")

    status = str(current.get("status") or "").lower()
    if status in _TERMINAL_FAILURE_STATUSES:
        raise ProviderError(
            code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
            message=f"[replicate] prediction {status}",
            provider=_PROVIDER,
            raw_error=str(current.get("error") or "")[:1000],
        )
    return current


async def _extract_replicate_images(
    data: dict[str, Any],
    client: httpx.AsyncClient,
) -> tuple[list[bytes], list[str]]:
    output = data.get("output")
    urls: list[str] = []
    if isinstance(output, str):
        urls = [output]
    elif isinstance(output, list):
        urls = [item for item in output if isinstance(item, str)]
    elif isinstance(output, dict):
        urls = [item for item in output.values() if isinstance(item, str)]

    images: list[bytes] = []
    image_urls: list[str] = []
    for url in urls:
        image_urls.append(url)
        images.append(await download_provider_image(url, client, provider=_PROVIDER))
    return images, image_urls
