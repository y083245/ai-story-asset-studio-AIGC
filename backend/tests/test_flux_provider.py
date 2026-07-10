from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import flux_pro as flux_module
from app.modules.provider_adapter.base import ImageGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FakeFluxResponse:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        status_code: int = 200,
        content: bytes = b"",
    ) -> None:
        self._payload = payload or {}
        self.status_code = status_code
        self.content = content
        self.text = json.dumps(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    response_payload: dict[str, Any] = {}
    requests: list[dict[str, Any]] = []

    def __init__(self, timeout: int | float) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> _FakeFluxResponse:
        self.requests.append({"method": "POST", "url": url, "headers": headers, "json": json})
        return _FakeFluxResponse(self.response_payload)

    async def get(self, url: str, headers: dict[str, str] | None = None) -> _FakeFluxResponse:
        self.requests.append({"method": "GET", "url": url, "headers": headers or {}})
        return _FakeFluxResponse(content=b"flux-image")


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.requests = []


def _service(tmp_path, *, api_key: str = "r8_live_image_token") -> ModelConfigService:
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "base_url": "https://api.deepseek.com",
                    "api_key": "sk-text",
                },
                "image": {
                    "provider_id": "replicate",
                    "model": "black-forest-labs/flux-pro",
                    "base_url": "https://api.replicate.com/v1",
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigService(config_path=config_path)


@pytest.mark.asyncio
async def test_flux_provider_generates_image_from_prediction_url(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(flux_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(flux_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "pred-123",
        "status": "succeeded",
        "output": ["https://replicate.delivery/output.png"],
    }

    response = await flux_module.FluxProProvider().generate(
        ImageGenerationRequest(
            prompt="场景资产图",
            negative_prompt="人物",
            width=1080,
            height=1920,
            timeout_seconds=30,
        )
    )

    assert response.images == [b"flux-image"]
    assert response.image_urls == ["https://replicate.delivery/output.png"]
    assert response.model == "black-forest-labs/flux-pro"
    assert response.provider_task_id == "pred-123"

    create_request = _FakeAsyncClient.requests[0]
    assert create_request["url"] == "https://api.replicate.com/v1/models/black-forest-labs/flux-pro/predictions"
    assert create_request["headers"]["Authorization"] == "Bearer r8_live_image_token"
    assert create_request["headers"]["Prefer"] == "wait"
    assert create_request["json"]["input"]["aspect_ratio"] == "9:16"
    assert "避免出现：人物" in create_request["json"]["input"]["prompt"]


def test_flux_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path, api_key="dummy-replicate-key")
    monkeypatch.setattr(flux_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        flux_module.FluxProProvider()

    assert exc_info.value.code == ProviderErrorCode.AUTH_FAILED


@pytest.mark.asyncio
async def test_flux_provider_rejects_tiny_dimensions(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(flux_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        await flux_module.FluxProProvider().generate(ImageGenerationRequest(prompt="asset", width=32, height=32))

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST
