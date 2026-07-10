"""Real provider implementations (config shells for production use).

Each provider reads its configuration from the global `settings` object and
validates required environment variables. In the first phase, real providers
perform parameter validation but raise NotImplementedError when API keys are
missing. Concrete API calls will be added in subsequent phases.

IMPORTANT: API keys are read ONLY from settings / environment variables.
They MUST NEVER be hard-coded, logged, or embedded in error messages.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.modules.model_config.adapters.registry import get_adapter_registry
from app.modules.model_config.service import get_model_config_service
from app.modules.observability.logger import get_logger
from app.modules.observability.provider_log import log_provider_call
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
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode

logger = logging.getLogger("storyasset.provider")
structured_logger = get_logger("storyasset.provider")

_DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_MAX_SEEDREAM_DOWNLOAD_BYTES = 20 * 1024 * 1024
_SEEDREAM_PRO_REFERENCE_LIMIT = 10
_SEEDREAM_DEFAULT_REFERENCE_LIMIT = 14


def _require_api_key(key_name: str, provider: str) -> None:
    """Raise ProviderError if the named API key is not configured."""
    value = getattr(settings, key_name, "")
    if not value:
        raise ProviderError(
            code=ProviderErrorCode.AUTH_FAILED,
            message=f"[{provider}] Missing API key: {key_name}. Set the environment variable.",
            provider=provider,
            retryable=False,
        )


# =============================================================================
# OpenAICompatibleTextProvider
# =============================================================================


class OpenAICompatibleTextProvider(TextGenerationProvider):
    """Text-generation provider that adapts to the configured model provider.

    Reads the provider config from ``local_config/model-providers.json`` and
    uses the corresponding adapter for authentication and endpoint discovery.
    """

    def __init__(self) -> None:
        config = get_model_config_service().load_secret_config().text
        if not config.api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message=f"[{config.provider_id}] Missing API key. Save it in local_config/model-providers.json.",
                provider=config.provider_id,
                retryable=False,
            )
        self._provider = config.provider_id
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._model = config.model

        # Resolve auth once at init time (JWT / OAuth tokens are cached for the
        # lifetime of the provider instance, which is per-request in practice).
        self._adapter = get_adapter_registry().get(self._provider)
        self._auth_value: str | None = None  # resolved lazily

    async def _resolve_auth(self) -> str:
        if self._auth_value is None:
            self._auth_value = await self._adapter.authenticate(self._api_key)
        return self._auth_value

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        _validate_text_request(request, provider=self._provider)
        return await self._chat(request, json_mode=False)

    async def generate_json(self, request: TextGenerationRequest) -> TextGenerationResponse:
        _validate_text_request(request, provider=self._provider)
        response = await self._chat(request, json_mode=True)
        response.json_data = _parse_json_object(response.text)
        return response

    async def _chat(self, request: TextGenerationRequest, *, json_mode: bool) -> TextGenerationResponse:
        start = time.perf_counter()
        model = request.model or self._model
        auth_value = await self._resolve_auth()
        url = self._adapter.build_chat_url(self._base_url)
        headers = {
            "Content-Type": "application/json",
            **self._adapter.build_auth_headers(auth_value),
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": _build_messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.thinking:
            payload["thinking"] = {"type": request.thinking}
        if request.reasoning_effort:
            payload["reasoning_effort"] = request.reasoning_effort
        if request.user_id:
            payload["user_id"] = request.user_id
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        # Let the adapter fix provider-specific parameter constraints
        # (e.g. Moonshot requires temperature=0.6, DeepSeek accepts [0,2])
        payload = self._adapter.sanitize_payload(payload)

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message=f"[{self._provider}] request timed out",
                provider=self._provider,
                raw_error=_sanitize_error(str(exc)),
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message=f"[{self._provider}] request failed",
                provider=self._provider,
                raw_error=_sanitize_error(str(exc)),
            ) from exc

        if response.status_code >= 400:
            raise _http_error(response, provider=self._provider)

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message=f"[{self._provider}] response did not include choices",
                provider=self._provider,
                retryable=True,
            )
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = str(message.get("content", ""))
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        latency_ms = int((time.perf_counter() - start) * 1000)
        finish_reason = str(choices[0].get("finish_reason") or "") if isinstance(choices[0], dict) else ""
        provider_request_id = str(data.get("id") or "")

        await log_provider_call(
            logger=structured_logger,
            provider=self._provider,
            model_name=str(data.get("model") or model),
            latency_ms=latency_ms,
            status="success",
            request_id=provider_request_id,
            project_id=request.metadata.get("project_id"),
            task_id=request.metadata.get("module_id"),
            prompt_tokens=_int_or_none(usage.get("prompt_tokens")),
            completion_tokens=_int_or_none(usage.get("completion_tokens")),
            module_id=request.metadata.get("module_id"),
            chunk_index=_int_or_none(request.metadata.get("chunk_index")),
            chunk_count=_int_or_none(request.metadata.get("chunk_count")),
            stage=request.metadata.get("stage"),
            asset_type=request.metadata.get("asset_type"),
            thinking=request.thinking,
            input_chars=len(request.system_prompt) + len(request.prompt),
            output_chars=len(content),
            prompt_cache_hit_tokens=_int_or_none(usage.get("prompt_cache_hit_tokens")),
            prompt_cache_miss_tokens=_int_or_none(usage.get("prompt_cache_miss_tokens")),
            finish_reason=finish_reason,
            retry_count=_int_or_none(request.metadata.get("retry_count")),
        )

        return TextGenerationResponse(
            text=content,
            model=str(data.get("model") or model),
            latency_ms=latency_ms,
            provider_request_id=provider_request_id,
            usage=usage,
            finish_reason=finish_reason,
        )


# =============================================================================
# _build_messages / _strip_json_fences / _parse_json_object helpers
# =============================================================================


def _build_messages(request: TextGenerationRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system_prompt.strip():
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    return messages


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _parse_json_object(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from provider text without logging raw content."""
    candidates = [_strip_json_fences(text)]
    candidates.extend(_json_code_blocks(text))
    candidates.extend(_balanced_json_objects(text))

    for i, candidate in enumerate(candidates):
        parsed = _loads_json_object(candidate)
        if parsed is not None:
            return parsed
        # Log parse failure details for debugging
        if i == 0:
            logger.debug(
                "JSON parse attempt %d failed: text_len=%d first_char=%r last_char=%r candidate_len=%d",
                i,
                len(text),
                text[:1] if text else "",
                text[-1:] if text else "",
                len(candidate),
            )

    # Log summary when all candidates fail
    logger.warning(
        "All %d JSON parse candidates failed. text_len=%d repr_head=%s repr_tail=%s",
        len(candidates),
        len(text),
        repr(text[:80]) if text else "EMPTY",
        repr(text[-80:]) if text else "EMPTY",
    )
    return None


def _loads_json_object(candidate: str, *, depth: int = 0) -> dict[str, Any] | None:
    if depth > 1:
        return None
    try:
        parsed = json.loads(candidate.strip())
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, str):
        return _loads_json_object(parsed, depth=depth + 1)
    return None


def _json_code_blocks(text: str) -> list[str]:
    return [match.strip() for match in re.findall(r"```(?:json|JSON)?\s*(.*?)```", text, flags=re.DOTALL)]


def _balanced_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None

    return objects


def _http_error(response: httpx.Response, *, provider: str) -> ProviderError:
    code = ProviderErrorCode.UNEXPECTED
    retryable = True
    if response.status_code in (401, 403):
        code = ProviderErrorCode.AUTH_FAILED
        retryable = False
    elif response.status_code == 429:
        code = ProviderErrorCode.RATE_LIMITED
    elif 400 <= response.status_code < 500:
        code = ProviderErrorCode.INVALID_REQUEST
        retryable = False
    elif response.status_code >= 500:
        code = ProviderErrorCode.PROVIDER_UNAVAILABLE

    detail = _sanitize_error(_extract_error_message(response))
    suffix = f": {detail}" if detail else ""
    return ProviderError(
        code=code,
        message=f"[{provider}] request failed with HTTP {response.status_code}{suffix}",
        provider=provider,
        retryable=retryable,
        raw_error=_sanitize_error(response.text),
    )


def _sanitize_error(value: str) -> str:
    sanitized = value
    local_config = get_model_config_service().load_secret_config()
    for secret in (
        settings.deepseek_api_key,
        settings.seedream_api_key,
        local_config.text.api_key,
        local_config.image.api_key,
        settings.tos_access_key,
        settings.tos_secret_key,
    ):
        if secret:
            sanitized = sanitized.replace(secret, "[redacted]")
    return re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", sanitized)


def _extract_error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or "")[:300]
    return ""


def _validate_text_request(request: TextGenerationRequest, *, provider: str) -> None:
    """Validate text generation request parameters."""
    if not request.prompt.strip():
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="prompt must not be empty",
            provider=provider,
            retryable=False,
        )
    if request.temperature < 0.0 or request.temperature > 2.0:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="temperature must be between 0.0 and 2.0",
            provider=provider,
            retryable=False,
        )
    if request.max_tokens < 1:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="max_tokens must be >= 1",
            provider=provider,
            retryable=False,
        )
    if request.thinking not in (None, "enabled", "disabled"):
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="thinking must be enabled or disabled",
            provider=provider,
            retryable=False,
        )
    if request.reasoning_effort not in (None, "high", "max"):
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="reasoning_effort must be high or max",
            provider=provider,
            retryable=False,
        )
    if request.user_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request.user_id):
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="user_id must contain only letters, numbers, underscores, or hyphens",
            provider=provider,
            retryable=False,
        )


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# =============================================================================
# SeedreamProvider
# =============================================================================


class SeedreamProvider(ImageGenerationProvider):
    """Image-generation provider that adapts to the configured image provider.

    Reads the image provider config from ``local_config/model-providers.json``
    and uses the corresponding adapter for authentication.
    """

    def __init__(self) -> None:
        config = get_model_config_service().load_secret_config().image
        self._api_key = config.api_key or settings.seedream_api_key
        if not self._api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message="[seedream] Missing API key. Save it in local_config/model-providers.json.",
                provider="seedream",
                retryable=False,
            )
        self._provider = config.provider_id
        self._model = config.model or settings.seedream_model_name
        self._base_url = (config.base_url or settings.seedream_base_url or _DEFAULT_ARK_BASE_URL).rstrip("/")

        # Use adapter for auth resolution
        self._adapter = get_adapter_registry().get(self._provider)
        self._auth_value: str | None = None

    @property
    def provider_id(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    async def _resolve_auth(self) -> str:
        if self._auth_value is None:
            self._auth_value = await self._adapter.authenticate(self._api_key)
        return self._auth_value

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Generate image bytes through the configured provider."""
        _validate_image_request(request)

        start = time.perf_counter()
        model = self._model
        _validate_seedream_reference_images(request.reference_images, model=model)
        auth_value = await self._resolve_auth()
        headers = {
            "Content-Type": "application/json",
            **self._adapter.build_auth_headers(auth_value),
        }
        payload = _build_seedream_payload(request, model=model)

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )
                if response.status_code >= 400:
                    raise _http_error(response, provider="seedream")
                data = response.json()
                images, image_urls = await _extract_seedream_images(data, client)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[seedream] request timed out",
                provider="seedream",
                raw_error=_sanitize_error(str(exc)),
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[seedream] request failed",
                provider="seedream",
                raw_error=_sanitize_error(str(exc)),
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[seedream] unexpected response shape",
                provider="seedream",
                raw_error=_sanitize_error(str(exc)),
            ) from exc

        if not images:
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[seedream] response did not include image bytes",
                provider="seedream",
                retryable=True,
            )

        return ImageGenerationResponse(
            images=images,
            image_urls=image_urls,
            model=str(data.get("model") or model) if isinstance(data, dict) else model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider_task_id=str(data.get("id") or "") if isinstance(data, dict) else "",
        )


def _validate_image_request(request: ImageGenerationRequest) -> None:
    """Validate image generation request parameters."""
    if not request.prompt.strip():
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="prompt must not be empty",
            provider="seedream",
            retryable=False,
        )
    if request.width < 64 or request.height < 64:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="image dimensions must be at least 64x64",
            provider="seedream",
            retryable=False,
        )


def _validate_seedream_reference_images(reference_images: list[bytes], *, model: str) -> None:
    limit = _seedream_reference_image_limit(model)
    if len(reference_images) > limit:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"[seedream] reference image count exceeds {limit} for model {model}",
            provider="seedream",
            retryable=False,
        )


def _seedream_reference_image_limit(model: str) -> int:
    if "pro" in model.lower():
        return _SEEDREAM_PRO_REFERENCE_LIMIT
    return _SEEDREAM_DEFAULT_REFERENCE_LIMIT


def _is_seedream_5_model(model: str) -> bool:
    normalized = model.lower().replace("_", "-")
    return "seedream" in normalized and ("5.0" in normalized or "5-0" in normalized)


def _normalized_seedream_model(model: str) -> str:
    return model.lower().replace("_", "-").replace(".", "-")


def _is_seedream_5_pro_model(model: str) -> bool:
    normalized = _normalized_seedream_model(model)
    return "seedream" in normalized and "5-0-pro" in normalized


def _is_seedream_5_lite_model(model: str) -> bool:
    normalized = _normalized_seedream_model(model)
    return "seedream" in normalized and "5-0-lite" in normalized


def _is_seedream_45_or_40_model(model: str) -> bool:
    normalized = _normalized_seedream_model(model)
    return "seedream" in normalized and ("4-5" in normalized or "4-0" in normalized)


def _supports_seedream_group_control(model: str) -> bool:
    return _is_seedream_5_lite_model(model) or _is_seedream_45_or_40_model(model)


def _build_seedream_payload(request: ImageGenerationRequest, *, model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "prompt": _image_prompt(request),
        "size": f"{request.width}x{request.height}",
        "response_format": "b64_json",
        "watermark": False,
    }
    if _supports_seedream_group_control(model):
        payload["sequential_image_generation"] = "disabled"
    if request.reference_images:
        payload["image"] = [_seedream_reference_data_url(image) for image in request.reference_images]
    return payload


def _seedream_reference_data_url(image: bytes) -> str:
    image_format = _detect_seedream_reference_image_format(image)
    encoded = base64.b64encode(image).decode("ascii")
    return f"data:image/{image_format};base64,{encoded}"


def _detect_seedream_reference_image_format(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(image) >= 12 and image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "webp"
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message="[seedream] reference image must be png, jpeg, or webp",
        provider="seedream",
        retryable=False,
    )


def _image_prompt(request: ImageGenerationRequest) -> str:
    prompt = request.prompt.strip()
    negative = request.negative_prompt.strip()
    if not negative:
        return prompt
    return f"{prompt}\n\n避免出现：{negative}"


def _seedream_item_error(item: dict[str, Any]) -> ProviderError | None:
    error = item.get("error")
    if not isinstance(error, dict):
        return None
    message = _sanitize_error(str(error.get("message") or "image generation failed"))
    code_text = str(error.get("code") or "")
    provider_code = ProviderErrorCode.PROVIDER_UNAVAILABLE if "internal" in code_text.lower() else ProviderErrorCode.INVALID_REQUEST
    return ProviderError(
        code=provider_code,
        message=f"[seedream] image generation item failed: {message}",
        provider="seedream",
        retryable=provider_code == ProviderErrorCode.PROVIDER_UNAVAILABLE,
        raw_error=_sanitize_error(json.dumps(error, ensure_ascii=False)),
    )


async def _extract_seedream_images(
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

        item_error = _seedream_item_error(item)
        if item_error is not None:
            if not images:
                raise item_error
            logger.warning("Seedream item failed after %d successful image(s): %s", len(images), item_error.message)
            continue

        b64_image = item.get("b64_json") or item.get("image")
        if isinstance(b64_image, str) and b64_image:
            images.append(base64.b64decode(b64_image))
            continue

        image_url = item.get("url")
        if isinstance(image_url, str) and image_url:
            image_urls.append(image_url)
            images.append(await _download_seedream_image(image_url, client))

    return images, image_urls


async def _download_seedream_image(url: str, client: httpx.AsyncClient) -> bytes:
    _validate_seedream_download_url(url)
    response = await client.get(url)
    if response.status_code >= 400:
        raise _http_error(response, provider="seedream")
    content = response.content
    if len(content) > _MAX_SEEDREAM_DOWNLOAD_BYTES:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="[seedream] downloaded image is too large",
            provider="seedream",
            retryable=False,
        )
    return content


def _validate_seedream_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="[seedream] image download URL must use https",
            provider="seedream",
            retryable=False,
        )
    host = parsed.hostname
    if not host:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="[seedream] image download URL is missing a host",
            provider="seedream",
            retryable=False,
        )
    if host.lower() == "localhost":
        _raise_private_seedream_url()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        _raise_private_seedream_url()


def _raise_private_seedream_url() -> None:
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message="[seedream] image download URL must not resolve to private, localhost, or link-local hosts",
        provider="seedream",
        retryable=False,
    )


# =============================================================================
# VolcengineTOSProvider
# =============================================================================


class VolcengineTOSProvider(ObjectStorageProvider):
    """Real Volcengine TOS object storage provider.

    Reads ``tos_access_key``, ``tos_secret_key``, ``tos_bucket``, ``tos_endpoint``
    from settings.
    """

    def __init__(self) -> None:
        for key_name in ("tos_access_key", "tos_secret_key", "tos_bucket", "tos_endpoint"):
            _require_api_key(key_name, "tos")

    async def upload(self, request: StorageUploadRequest) -> StorageUploadResponse:  # pragma: no cover
        """Phase 1: validate request, raise NotImplementedError."""
        _validate_storage_request(request)
        raise NotImplementedError(
            "Volcengine TOS upload not yet implemented. Use FakeObjectStorageProvider for local development."
        )

    async def get_signed_url(self, asset_id: str, expires_seconds: int = 3600) -> str:  # pragma: no cover
        """Phase 1: raise NotImplementedError."""
        raise NotImplementedError(
            "Volcengine TOS signed URL not yet implemented. Use FakeObjectStorageProvider for local development."
        )

    async def delete(self, asset_id: str) -> None:  # pragma: no cover
        """Phase 1: raise NotImplementedError."""
        raise NotImplementedError(
            "Volcengine TOS delete not yet implemented. Use FakeObjectStorageProvider for local development."
        )


class AliyunOSSProvider(ObjectStorageProvider):
    """Real Aliyun OSS object storage provider.

    Reads ``aliyun_oss_access_key``, ``aliyun_oss_secret_key``,
    ``aliyun_oss_bucket``, ``aliyun_oss_endpoint`` from settings.

    Phase 1: validates configuration; concrete upload/signed-url/delete
    implementations will be added once ``oss2`` SDK integration is wired.
    """

    def __init__(self) -> None:
        for key_name in (
            "aliyun_oss_access_key",
            "aliyun_oss_secret_key",
            "aliyun_oss_bucket",
            "aliyun_oss_endpoint",
        ):
            _require_api_key(key_name, "aliyun-oss")

    async def upload(self, request: StorageUploadRequest) -> StorageUploadResponse:  # pragma: no cover
        """Phase 1: validate request, raise NotImplementedError."""
        _validate_storage_request(request)
        raise NotImplementedError(
            "Aliyun OSS upload not yet implemented. Use FakeObjectStorageProvider for local development."
        )

    async def get_signed_url(self, asset_id: str, expires_seconds: int = 3600) -> str:  # pragma: no cover
        """Phase 1: raise NotImplementedError."""
        raise NotImplementedError(
            "Aliyun OSS signed URL not yet implemented. Use FakeObjectStorageProvider for local development."
        )

    async def delete(self, asset_id: str) -> None:  # pragma: no cover
        """Phase 1: raise NotImplementedError."""
        raise NotImplementedError(
            "Aliyun OSS delete not yet implemented. Use FakeObjectStorageProvider for local development."
        )


def _validate_storage_request(request: StorageUploadRequest) -> None:
    """Validate storage upload request parameters."""
    if not request.file_bytes:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="file_bytes must not be empty",
            provider="tos",
            retryable=False,
        )
    if not request.file_name.strip():
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="file_name must not be empty",
            provider="tos",
            retryable=False,
        )
    if not request.project_id.strip():
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message="project_id must not be empty",
            provider="tos",
            retryable=False,
        )


# =============================================================================
# Real Vision Quality Provider
# =============================================================================


class RealVisionQualityProvider(VisionQualityProvider):
    """Vision quality provider using OpenAI-compatible multimodal chat."""

    def __init__(self) -> None:
        provider = _vision_provider_adapter_id(settings.vision_quality_provider)
        config = _select_vision_provider_config(provider)
        self._api_key = config.get("api_key", "")
        if not self._api_key:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message="[vision-quality] Missing API key. Save it in local_config/model-providers.json.",
                provider="vision-quality",
                retryable=False,
            )
        self._provider = provider
        self._model = settings.vision_quality_model_name or config.get("model", "") or settings.seedream_model_name
        self._base_url = (config.get("base_url", "") or settings.seedream_base_url or _DEFAULT_ARK_BASE_URL).rstrip("/")
        self._adapter = get_adapter_registry().get(self._provider)
        self._auth_value: str | None = None

    @property
    def provider_id(self) -> str:
        return _public_vision_provider_id(self._provider)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _resolve_auth(self) -> str:
        if self._auth_value is None:
            self._auth_value = await self._adapter.authenticate(self._api_key)
        return self._auth_value

    async def check_quality(self, request: VisionQualityRequest) -> VisionQualityResponse:
        if not request.image:
            raise ProviderError(
                code=ProviderErrorCode.INVALID_REQUEST,
                message="image must be provided",
                provider="vision-quality",
                retryable=False,
            )

        start = time.perf_counter()
        auth_value = await self._resolve_auth()
        url, headers, payload = _build_vision_quality_http_request(
            provider=self._provider,
            base_url=self._base_url,
            model=self._model,
            auth_value=auth_value,
            adapter=self._adapter,
            request=request,
        )

        try:
            async with httpx.AsyncClient(timeout=request.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            await _log_vision_quality_call(
                request=request,
                provider=self.provider_id,
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=ProviderErrorCode.TIMEOUT.value,
            )
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message="[vision-quality] request timed out",
                provider="vision-quality",
                raw_error=_sanitize_error(str(exc)),
            ) from exc
        except httpx.RequestError as exc:
            await _log_vision_quality_call(
                request=request,
                provider=self.provider_id,
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=ProviderErrorCode.PROVIDER_UNAVAILABLE.value,
            )
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message="[vision-quality] request failed",
                provider="vision-quality",
                raw_error=_sanitize_error(str(exc)),
            ) from exc

        if response.status_code >= 400:
            await _log_vision_quality_call(
                request=request,
                provider=self.provider_id,
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=str(response.status_code),
            )
            raise _http_error(response, provider="vision-quality")

        try:
            data = response.json()
            content = _extract_vision_quality_content(data, provider=self._provider)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            await _log_vision_quality_call(
                request=request,
                provider=self.provider_id,
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=ProviderErrorCode.UNEXPECTED.value,
            )
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[vision-quality] unexpected response shape",
                provider="vision-quality",
                raw_error=_sanitize_error(str(exc)),
            ) from exc

        parsed = _parse_json_object_silent(content)
        if parsed is None:
            await _log_vision_quality_call(
                request=request,
                provider=self.provider_id,
                model=self._model,
                latency_ms=int((time.perf_counter() - start) * 1000),
                status="error",
                error_code=ProviderErrorCode.UNEXPECTED.value,
            )
            raise ProviderError(
                code=ProviderErrorCode.UNEXPECTED,
                message="[vision-quality] response content was not valid JSON",
                provider="vision-quality",
                retryable=True,
            )

        result = _vision_quality_response_from_json(parsed)
        await _log_vision_quality_call(
            request=request,
            provider=self.provider_id,
            model=self._model,
            latency_ms=int((time.perf_counter() - start) * 1000),
            status="success",
        )
        return result


def _vision_provider_adapter_id(provider: str) -> str:
    mapping = {
        "doubao": "doubao_seedream",
        "gemini": "google_gemini",
        "openai": "openai",
    }
    return mapping.get(provider, provider)


def _public_vision_provider_id(provider: str) -> str:
    mapping = {
        "doubao_seedream": "doubao",
        "google_gemini": "gemini",
    }
    return mapping.get(provider, provider)


def _select_vision_provider_config(provider: str) -> dict[str, str]:
    config = get_model_config_service().load_secret_config()
    for candidate in (config.text, config.image):
        if candidate.provider_id == provider:
            return {
                "provider_id": candidate.provider_id,
                "model": candidate.model,
                "base_url": candidate.base_url,
                "api_key": candidate.api_key,
            }
    if provider == "doubao_seedream":
        return {
            "provider_id": provider,
            "model": settings.vision_quality_model_name or settings.seedream_model_name,
            "base_url": settings.seedream_base_url or _DEFAULT_ARK_BASE_URL,
            "api_key": settings.seedream_api_key,
        }
    return {"provider_id": provider, "model": settings.vision_quality_model_name, "base_url": "", "api_key": ""}


def _build_vision_quality_http_request(
    *,
    provider: str,
    base_url: str,
    model: str,
    auth_value: str,
    adapter: Any,
    request: VisionQualityRequest,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    if provider == "google_gemini":
        url = f"{base_url.rstrip('/')}/models/{model}:generateContent?key={auth_value}"
        return (
            url,
            {"Content-Type": "application/json"},
            {
                "contents": [{"role": "user", "parts": _build_gemini_vision_parts(request)}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 1200,
                    "responseMimeType": "application/json",
                },
            },
        )

    headers = {
        "Content-Type": "application/json",
        **adapter.build_auth_headers(auth_value),
    }
    payload = adapter.sanitize_payload(
        {
            "model": model,
            "messages": _build_vision_quality_messages(request),
            "temperature": 0,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }
    )
    return adapter.build_chat_url(base_url), headers, payload


def _build_gemini_vision_parts(request: VisionQualityRequest) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"text": _vision_quality_prompt(request)}]
    parts.append(_gemini_image_part(request.image or b""))
    for image in request.reference_character_images:
        parts.append({"text": "Reference character image."})
        parts.append(_gemini_image_part(image))
    if request.reference_scene_image:
        parts.append({"text": "Reference scene image."})
        parts.append(_gemini_image_part(request.reference_scene_image))
    return parts


def _gemini_image_part(image: bytes) -> dict[str, Any]:
    return {
        "inline_data": {
            "mime_type": "image/png",
            "data": base64.b64encode(image).decode("ascii"),
        }
    }


def _extract_vision_quality_content(data: Any, *, provider: str) -> str:
    if not isinstance(data, dict):
        raise ValueError("response is not a JSON object")
    if provider == "google_gemini":
        candidates = data.get("candidates", [])
        content = candidates[0].get("content", {}) if candidates and isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        first = parts[0] if parts and isinstance(parts[0], dict) else {}
        return str(first.get("text", ""))
    choices = data.get("choices", [])
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    return str(message.get("content", ""))


async def _log_vision_quality_call(
    *,
    request: VisionQualityRequest,
    provider: str,
    model: str,
    latency_ms: int,
    status: str,
    error_code: str | None = None,
) -> None:
    metadata = request.metadata
    await log_provider_call(
        logger=structured_logger,
        provider=provider,
        model_name=model,
        latency_ms=latency_ms,
        status=status,
        error_code=error_code,
        project_id=metadata.get("project_id"),
        task_id=metadata.get("task_id"),
        module_id="vision_quality",
        stage="vision_qa",
        asset_type=metadata.get("asset_type"),
        input_chars=len(request.prompt) + len(request.negative_prompt),
        retry_count=_int_or_none(metadata.get("retry_count")),
    )


def _build_vision_quality_messages(request: VisionQualityRequest) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": _vision_quality_prompt(request),
        },
        {
            "type": "image_url",
            "image_url": {"url": _image_data_url(request.image or b"")},
        },
    ]
    for index, image in enumerate(request.reference_character_images, start=1):
        content.append({"type": "text", "text": f"Reference character image {index}."})
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(image)}})
    if request.reference_scene_image:
        content.append({"type": "text", "text": "Reference scene image."})
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(request.reference_scene_image)}})

    return [
        {
            "role": "system",
            "content": (
                "You are a strict visual asset QA reviewer. Return one JSON object only, "
                "without markdown or prose."
            ),
        },
        {"role": "user", "content": content},
    ]


def _vision_quality_prompt(request: VisionQualityRequest) -> str:
    context: dict[str, Any] = {
        "check_dimensions": request.check_dimensions,
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "asset_bible": request.asset_bible,
        "style_keywords": request.style_keywords,
        "expected_props": request.expected_props,
        "retry_history": request.retry_history,
    }
    return (
        "Inspect the generated image for story asset production readiness. "
        "Compare against any reference images and context. Return JSON with exactly these fields: "
        "passed boolean; scores object with consistency, art_quality, reusability numeric scores; "
        "total_score numeric; issues array; prompt_patch string. "
        "Scores may be 0-1 or 0-100. prompt_patch should be a concise generation prompt fix when failed.\n"
        f"Context JSON: {json.dumps(context, ensure_ascii=False)}"
    )


def _image_data_url(image: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(image).decode('ascii')}"


def _vision_quality_response_from_json(data: dict[str, Any]) -> VisionQualityResponse:
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    consistency = _score_0_to_1(scores.get("consistency"))
    art_quality = _score_0_to_1(scores.get("art_quality"))
    reusability = _score_0_to_1(scores.get("reusability"))
    total_score = _score_0_to_1(data.get("total_score"))
    if total_score is None:
        total_score = _average_scores([consistency, art_quality, reusability])

    passed = _parse_quality_passed(data.get("passed"))
    prompt_patch = _prompt_patch_to_text(data.get("prompt_patch"))
    return VisionQualityResponse(
        quality_score=total_score or 0.0,
        face_consistency_score=consistency,
        outfit_consistency_score=consistency,
        scene_consistency_score=consistency,
        prop_presence_score=consistency,
        composition_score=art_quality if art_quality is not None else reusability,
        issues=_normalize_vision_issues(data.get("issues")),
        retry_required=not passed,
        retry_prompt_patch=prompt_patch if not passed else "",
        prompt_patch=prompt_patch,
    )


def _score_0_to_1(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score > 1:
        score = score / 100
    return max(0.0, min(1.0, score))


def _average_scores(scores: list[float | None]) -> float | None:
    values = [score for score in scores if score is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _prompt_patch_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


def _parse_quality_passed(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "pass", "passed", "1"}:
            return True
        if normalized in {"false", "no", "fail", "failed", "0"}:
            return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise ProviderError(
        code=ProviderErrorCode.UNEXPECTED,
        message="[vision-quality] response field 'passed' must be a boolean",
        provider="vision-quality",
        retryable=True,
    )


def _parse_json_object_silent(text: str) -> dict[str, Any] | None:
    """Parse provider JSON without logging raw visual prompt or bible content."""
    candidates = [_strip_json_fences(text)]
    candidates.extend(_json_code_blocks(text))
    candidates.extend(_balanced_json_objects(text))

    for candidate in candidates:
        parsed = _loads_json_object(candidate)
        if parsed is not None:
            return parsed
    logger.warning("Vision quality JSON parse failed. text_len=%d candidates=%d", len(text), len(candidates))
    return None


def _normalize_vision_issues(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    issues: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            issues.append(item)
        elif isinstance(item, str) and item.strip():
            issues.append({"description": item.strip()})
    return issues
