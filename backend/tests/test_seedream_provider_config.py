from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import real as real_provider_module
from app.modules.provider_adapter.base import ImageGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FakeSeedreamResponse:
    def __init__(self, payload: dict[str, Any] | None = None, *, status_code: int = 200) -> None:
        self._payload = payload or {}
        self.status_code = status_code
        self.text = json.dumps(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    response_payload: dict[str, Any] = {}
    status_code: int = 200
    requests: list[dict[str, Any]] = []

    def __init__(self, timeout: int | float) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> _FakeSeedreamResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return _FakeSeedreamResponse(self.response_payload, status_code=self.status_code)


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.status_code = 200
    _FakeAsyncClient.requests = []


def _service(
    tmp_path,
    *,
    model: str = "doubao-seedream-5-0-lite-260128",
    api_key: str = "fixture-image-token",
) -> ModelConfigService:
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "base_url": "https://api.deepseek.com",
                    "api_key": "fixture-text-token",
                },
                "image": {
                    "provider_id": "doubao_seedream",
                    "model": model,
                    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigService(config_path=config_path)


@pytest.mark.parametrize("api_key", ["your-api-key", "test-key-456"])
def test_seedream_provider_rejects_placeholder_api_key(monkeypatch, tmp_path, api_key):
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "base_url": "https://api.deepseek.com",
                    "api_key": "fixture-text-token",
                },
                "image": {
                    "provider_id": "doubao_seedream",
                    "model": "doubao-seedream-5.0-lite",
                    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    service = ModelConfigService(config_path=config_path)
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.settings, "seedream_api_key", "")

    with pytest.raises(ProviderError) as exc_info:
        real_provider_module.SeedreamProvider()

    assert exc_info.value.code == ProviderErrorCode.AUTH_FAILED


@pytest.mark.asyncio
async def test_seedream_provider_sends_reference_images_as_data_url_image_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service = _service(tmp_path, model="doubao-seedream-5-0-lite-260128")
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "seedream-job-123",
        "model": "doubao-seedream-5-0-lite-260128",
        "data": [{"b64_json": base64.b64encode(b"seedream-image").decode("ascii")}],
    }
    png = b"\x89PNG\r\n\x1a\npng-data"
    jpeg = b"\xff\xd8\xff\xe0jpeg-data"
    webp = b"RIFF\x10\x00\x00\x00WEBPwebp-data"

    response = await real_provider_module.SeedreamProvider().generate(
        ImageGenerationRequest(
            prompt="角色资产图",
            negative_prompt="低质量",
            width=1440,
            height=2560,
            reference_images=[png, jpeg, webp],
            timeout_seconds=30,
        )
    )

    assert response.images == [b"seedream-image"]
    request = _FakeAsyncClient.requests[0]
    payload = request["json"]
    assert request["url"] == "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    assert request["headers"]["Authorization"] == "Bearer fixture-image-token"
    assert payload["model"] == "doubao-seedream-5-0-lite-260128"
    assert payload["size"] == "1440x2560"
    assert payload["response_format"] == "b64_json"
    assert "避免出现：低质量" in payload["prompt"]
    assert payload["watermark"] is False
    assert payload["image"] == [
        f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}",
        f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode('ascii')}",
        f"data:image/webp;base64,{base64.b64encode(webp).decode('ascii')}",
    ]
    assert "reference_images" not in payload
    assert "batch" not in payload
    assert "stream" not in payload
    assert payload["sequential_image_generation"] == "disabled"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "reference_count", "expected_limit"),
    [
        ("doubao-seedream-5-0-pro-260628", 11, 10),
        ("doubao-seedream-5-0-lite-260128", 15, 14),
        ("doubao-seedream-5-0-260128", 15, 14),
    ],
)
async def test_seedream_provider_rejects_reference_image_counts_over_model_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    model: str,
    reference_count: int,
    expected_limit: int,
) -> None:
    service = _service(tmp_path, model=model)
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(ProviderError) as exc_info:
        await real_provider_module.SeedreamProvider().generate(
            ImageGenerationRequest(
                prompt="角色资产图",
                reference_images=[b"\x89PNG\r\n\x1a\n"] * reference_count,
            )
        )

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST
    assert str(expected_limit) in exc_info.value.message
    assert not _FakeAsyncClient.requests


@pytest.mark.asyncio
async def test_seedream_provider_maps_upstream_validation_status_to_invalid_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.status_code = 422
    _FakeAsyncClient.response_payload = {"error": {"message": "invalid image payload"}}

    with pytest.raises(ProviderError) as exc_info:
        await real_provider_module.SeedreamProvider().generate(
            ImageGenerationRequest(
                prompt="角色资产图",
                reference_images=[b"\x89PNG\r\n\x1a\n"],
            )
        )

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST
    assert exc_info.value.retryable is False
    assert "invalid image payload" in exc_info.value.message


@pytest.mark.asyncio
async def test_seedream_5_pro_request_omits_unsupported_group_and_stream_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service = _service(tmp_path, model="doubao-seedream-5-0-pro-260628")
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "seedream-job-pro",
        "model": "doubao-seedream-5-0-pro-260628",
        "data": [{"b64_json": base64.b64encode(b"pro-image").decode("ascii")}],
    }

    await real_provider_module.SeedreamProvider().generate(
        ImageGenerationRequest(prompt="角色资产图", width=1440, height=2560)
    )

    payload = _FakeAsyncClient.requests[0]["json"]
    assert payload["model"] == "doubao-seedream-5-0-pro-260628"
    assert payload["size"] == "1440x2560"
    assert payload["response_format"] == "b64_json"
    assert payload["watermark"] is False
    assert "sequential_image_generation" not in payload
    assert "sequential_image_generation_options" not in payload
    assert "stream" not in payload
    assert "tools" not in payload


@pytest.mark.asyncio
async def test_seedream_45_request_uses_official_single_image_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service = _service(tmp_path, model="doubao-seedream-4-5-251128")
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "seedream-job-45",
        "model": "doubao-seedream-4-5-251128",
        "data": [{"b64_json": base64.b64encode(b"legacy-image").decode("ascii")}],
    }

    await real_provider_module.SeedreamProvider().generate(
        ImageGenerationRequest(prompt="场景资产图", width=2560, height=1440)
    )

    payload = _FakeAsyncClient.requests[0]["json"]
    assert payload["model"] == "doubao-seedream-4-5-251128"
    assert payload["size"] == "2560x1440"
    assert payload["response_format"] == "b64_json"
    assert payload["sequential_image_generation"] == "disabled"
    assert payload["watermark"] is False
    assert "output_format" not in payload
    assert "stream" not in payload


@pytest.mark.asyncio
async def test_seedream_provider_maps_item_level_error_to_provider_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    service = _service(tmp_path, model="doubao-seedream-4-5-251128")
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "seedream-job-error",
        "model": "doubao-seedream-4-5-251128",
        "data": [{"error": {"code": "InternalServiceError", "message": "internal service error"}}],
    }

    with pytest.raises(ProviderError) as exc_info:
        await real_provider_module.SeedreamProvider().generate(
            ImageGenerationRequest(prompt="场景资产图", width=2560, height=1440)
        )

    assert exc_info.value.code == ProviderErrorCode.PROVIDER_UNAVAILABLE
    assert exc_info.value.retryable is True
    assert "internal service error" in exc_info.value.message
