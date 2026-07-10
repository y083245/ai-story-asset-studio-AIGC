from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import dalle as dalle_module
from app.modules.provider_adapter.base import ImageGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FakeImageResponse:
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

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> _FakeImageResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return _FakeImageResponse(self.response_payload)

    async def get(self, url: str) -> _FakeImageResponse:
        self.requests.append({"url": url})
        return _FakeImageResponse(content=b"downloaded-openai-image")


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.requests = []


def _service(tmp_path, *, api_key: str = "sk-live-image") -> ModelConfigService:
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
                    "provider_id": "openai",
                    "model": "dall-e-3",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigService(config_path=config_path)


@pytest.mark.asyncio
async def test_dalle_provider_generates_base64_image(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(dalle_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(dalle_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "id": "img-openai-123",
        "model": "dall-e-3",
        "data": [{"b64_json": base64.b64encode(b"openai-image").decode("ascii")}],
    }

    response = await dalle_module.DalleProvider().generate(
        ImageGenerationRequest(
            prompt="角色正面资产图",
            negative_prompt="低质量",
            width=1080,
            height=1920,
            timeout_seconds=30,
        )
    )

    assert response.images == [b"openai-image"]
    assert response.model == "dall-e-3"
    assert response.provider_task_id == "img-openai-123"

    request = _FakeAsyncClient.requests[0]
    assert request["url"] == "https://api.openai.com/v1/images/generations"
    assert request["headers"]["Authorization"] == "Bearer sk-live-image"
    assert request["json"]["model"] == "dall-e-3"
    assert request["json"]["size"] == "1024x1792"
    assert request["json"]["response_format"] == "b64_json"
    assert "避免出现：低质量" in request["json"]["prompt"]


def test_dalle_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path, api_key="your-api-key")
    monkeypatch.setattr(dalle_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        dalle_module.DalleProvider()

    assert exc_info.value.code == ProviderErrorCode.AUTH_FAILED


@pytest.mark.asyncio
async def test_dalle_provider_rejects_empty_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(dalle_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        await dalle_module.DalleProvider().generate(ImageGenerationRequest(prompt=" "))

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST
