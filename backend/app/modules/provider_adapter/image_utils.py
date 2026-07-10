"""Shared helpers for real image-generation providers."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx

from app.modules.provider_adapter.base import ImageGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode

MAX_PROVIDER_IMAGE_DOWNLOAD_BYTES = 20 * 1024 * 1024


def validate_image_request(request: ImageGenerationRequest, *, provider: str) -> None:
    if not request.prompt.strip():
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="prompt must not be empty",
            provider=provider,
            retryable=False,
        )
    if request.width < 64 or request.height < 64:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="image dimensions must be at least 64x64",
            provider=provider,
            retryable=False,
        )


def image_prompt(request: ImageGenerationRequest) -> str:
    prompt = request.prompt.strip()
    negative = request.negative_prompt.strip()
    if not negative:
        return prompt
    return f"{prompt}\n\n避免出现：{negative}"


def http_error(response: httpx.Response, *, provider: str) -> ProviderError:
    code = ProviderErrorCode.UNEXPECTED
    retryable = True
    if response.status_code in (401, 403):
        code = ProviderErrorCode.AUTH_FAILED
        retryable = False
    elif response.status_code == 429:
        code = ProviderErrorCode.RATE_LIMITED
    elif response.status_code == 400:
        code = ProviderErrorCode.INVALID_REQUEST
        retryable = False
    elif response.status_code >= 500:
        code = ProviderErrorCode.PROVIDER_UNAVAILABLE

    detail = _extract_error_message(response)
    suffix = f": {detail}" if detail else ""
    return ProviderError(
        code=code,
        message=f"[{provider}] request failed with HTTP {response.status_code}{suffix}",
        provider=provider,
        retryable=retryable,
        raw_error=response.text[:1000],
    )


async def download_provider_image(url: str, client: httpx.AsyncClient, *, provider: str) -> bytes:
    validate_provider_image_url(url, provider=provider)
    response = await client.get(url)
    if response.status_code >= 400:
        raise http_error(response, provider=provider)
    content = response.content
    if len(content) > MAX_PROVIDER_IMAGE_DOWNLOAD_BYTES:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"[{provider}] downloaded image is too large",
            provider=provider,
            retryable=False,
        )
    return content


def validate_provider_image_url(url: str, *, provider: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"[{provider}] image download URL must use https",
            provider=provider,
            retryable=False,
        )
    host = parsed.hostname
    if not host:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"[{provider}] image download URL is missing a host",
            provider=provider,
            retryable=False,
        )
    if host.lower() == "localhost":
        _raise_private_url(provider)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        _raise_private_url(provider)


def _raise_private_url(provider: str) -> None:
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message=f"[{provider}] image download URL must not resolve to private, localhost, or link-local hosts",
        provider=provider,
        retryable=False,
    )


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message[:300]
        if isinstance(error, str):
            return error[:300]
        detail = data.get("detail") or data.get("message")
        if isinstance(detail, str):
            return detail[:300]
    return ""
