from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import imagen as imagen_module
from app.modules.provider_adapter.base import ImageGenerationRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FakeImagenResponse:
    def __init__(self, payload: dict[str, Any] | None = None, *, status_code: int = 200) -> None:
        self._payload = payload or {}
        self.status_code = status_code
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

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> _FakeImagenResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return _FakeImagenResponse(self.response_payload)


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.requests = []


def _service(tmp_path, *, api_key: str = "gemini-live-image-key") -> ModelConfigService:
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
                    "provider_id": "google_imagen",
                    "model": "imagen-4.0-generate-001",
                    "base_url": "https://generativelanguage.googleapis.com/v1beta",
                    "api_key": api_key,
                },
            }
        ),
        encoding="utf-8",
    )
    return ModelConfigService(config_path=config_path)


@pytest.mark.asyncio
async def test_imagen_provider_generates_base64_image(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(imagen_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(imagen_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response_payload = {
        "metadata": {"predictionId": "imagen-pred-123"},
        "predictions": [
            {
                "bytesBase64Encoded": base64.b64encode(b"imagen-image").decode("ascii"),
                "mimeType": "image/png",
            }
        ],
    }

    response = await imagen_module.ImagenProvider().generate(
        ImageGenerationRequest(
            prompt="A cinematic character asset sheet",
            negative_prompt="low quality",
            width=1440,
            height=2560,
            timeout_seconds=30,
        )
    )

    assert response.images == [b"imagen-image"]
    assert response.model == "imagen-4.0-generate-001"
    assert response.provider_task_id == "imagen-pred-123"

    request = _FakeAsyncClient.requests[0]
    assert request["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"
    )
    assert request["headers"]["x-goog-api-key"] == "gemini-live-image-key"
    assert request["json"]["instances"][0]["prompt"].endswith("Avoid: low quality")
    assert request["json"]["parameters"]["sampleCount"] == 1
    assert request["json"]["parameters"]["aspectRatio"] == "9:16"
    assert request["json"]["parameters"]["personGeneration"] == "allow_adult"


def test_imagen_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path, api_key="example-google-key")
    monkeypatch.setattr(imagen_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        imagen_module.ImagenProvider()

    assert exc_info.value.code == ProviderErrorCode.AUTH_FAILED


@pytest.mark.asyncio
async def test_imagen_provider_rejects_empty_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    service = _service(tmp_path)
    monkeypatch.setattr(imagen_module, "get_model_config_service", lambda: service)

    with pytest.raises(ProviderError) as exc_info:
        await imagen_module.ImagenProvider().generate(ImageGenerationRequest(prompt=" "))

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST
