from __future__ import annotations

import json
from typing import Any

import pytest

from app.modules.model_config.service import ModelConfigService
from app.modules.provider_adapter import real as real_provider_module
from app.modules.provider_adapter.base import VisionQualityRequest
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode


class _FakeVisionResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

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

    async def post(self, url: str, headers: dict[str, str], json: dict[str, Any]) -> _FakeVisionResponse:
        self.requests.append({"url": url, "headers": headers, "json": json})
        return _FakeVisionResponse(self.response_payload)


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.response_payload = {}
    _FakeAsyncClient.requests = []


@pytest.fixture
def vision_provider(monkeypatch: pytest.MonkeyPatch, tmp_path):
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
                    "provider_id": "doubao_seedream",
                    "model": "doubao-seedream-5.0-lite",
                    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                    "api_key": "sk-image",
                },
            }
        ),
        encoding="utf-8",
    )
    service = ModelConfigService(config_path=config_path)
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.settings, "vision_quality_provider", "doubao")
    monkeypatch.setattr(real_provider_module.settings, "vision_quality_model_name", "doubao-vision-quality")
    monkeypatch.setattr(real_provider_module.httpx, "AsyncClient", _FakeAsyncClient)
    return real_provider_module.RealVisionQualityProvider()


def _chat_response(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


@pytest.mark.asyncio
async def test_vision_quality_provider_parses_failed_result_with_prompt_patch(vision_provider) -> None:
    _FakeAsyncClient.response_payload = _chat_response(
        json.dumps(
            {
                "passed": False,
                "scores": {"consistency": 62, "art_quality": 71, "reusability": 0.58},
                "total_score": 64,
                "issues": [{"code": "FACE_CHANGED", "severity": "error"}],
                "prompt_patch": "Keep the character face closer to the reference.",
            }
        )
    )

    response = await vision_provider.check_quality(
        VisionQualityRequest(
            image=b"generated-image",
            reference_character_images=[b"reference-face"],
            prompt="portrait asset",
            style_keywords=["ink", "cinematic"],
        )
    )

    assert response.retry_required is True
    assert response.quality_score == pytest.approx(0.64)
    assert response.face_consistency_score == pytest.approx(0.62)
    assert response.outfit_consistency_score == pytest.approx(0.62)
    assert response.scene_consistency_score == pytest.approx(0.62)
    assert response.prop_presence_score == pytest.approx(0.62)
    assert response.composition_score == pytest.approx(0.71)
    assert response.issues == [{"code": "FACE_CHANGED", "severity": "error"}]
    assert response.prompt_patch == "Keep the character face closer to the reference."
    assert response.retry_prompt_patch == response.prompt_patch

    request_payload = _FakeAsyncClient.requests[0]["json"]
    assert request_payload["model"] == "doubao-vision-quality"
    content = request_payload["messages"][1]["content"]
    image_parts = [part for part in content if part.get("type") == "image_url"]
    assert len(image_parts) == 2
    assert image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_vision_quality_provider_uses_independent_provider_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "openai",
                    "model": "gpt-4o-mini",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-vision",
                },
                "image": {
                    "provider_id": "replicate",
                    "model": "black-forest-labs/flux-pro",
                    "base_url": "https://api.replicate.com/v1",
                    "api_key": "r8-image",
                },
            }
        ),
        encoding="utf-8",
    )
    service = ModelConfigService(config_path=config_path)
    monkeypatch.setattr(real_provider_module, "get_model_config_service", lambda: service)
    monkeypatch.setattr(real_provider_module.settings, "vision_quality_provider", "openai")
    monkeypatch.setattr(real_provider_module.settings, "vision_quality_model_name", "gpt-4o-mini")

    provider = real_provider_module.RealVisionQualityProvider()

    assert provider.provider_id == "openai"
    assert provider.model_name == "gpt-4o-mini"
    assert provider.base_url == "https://api.openai.com/v1"


@pytest.mark.asyncio
async def test_vision_quality_provider_parses_passed_result(vision_provider) -> None:
    _FakeAsyncClient.response_payload = _chat_response(
        json.dumps(
            {
                "passed": True,
                "scores": {"consistency": 0.94, "art_quality": 0.9, "reusability": 0.88},
                "total_score": 0.91,
                "issues": [],
                "prompt_patch": "",
            }
        )
    )

    response = await vision_provider.check_quality(VisionQualityRequest(image=b"generated-image"))

    assert response.retry_required is False
    assert response.quality_score == pytest.approx(0.91)
    assert response.face_consistency_score == pytest.approx(0.94)
    assert response.composition_score == pytest.approx(0.9)
    assert response.issues == []
    assert response.prompt_patch == ""
    assert response.retry_prompt_patch == ""


@pytest.mark.asyncio
async def test_vision_quality_provider_logs_vision_qa_call(
    vision_provider, monkeypatch: pytest.MonkeyPatch
) -> None:
    log_calls: list[dict[str, Any]] = []

    async def fake_log_provider_call(**kwargs: Any) -> None:
        log_calls.append(kwargs)

    monkeypatch.setattr(real_provider_module, "log_provider_call", fake_log_provider_call)
    _FakeAsyncClient.response_payload = _chat_response(
        json.dumps(
            {
                "passed": True,
                "scores": {"consistency": 0.94, "art_quality": 0.9, "reusability": 0.88},
                "total_score": 0.91,
                "issues": [],
                "prompt_patch": "",
            }
        )
    )

    await vision_provider.check_quality(
        VisionQualityRequest(
            image=b"generated-image",
            metadata={"project_id": "project-1", "asset_type": "character_front", "task_id": "task-1"},
        )
    )

    assert len(log_calls) == 1
    assert log_calls[0]["stage"] == "vision_qa"
    assert log_calls[0]["asset_type"] == "character_front"
    assert log_calls[0]["project_id"] == "project-1"
    assert log_calls[0]["task_id"] == "task-1"


@pytest.mark.asyncio
async def test_vision_quality_provider_parses_string_false_as_failed(vision_provider) -> None:
    _FakeAsyncClient.response_payload = _chat_response(
        json.dumps(
            {
                "passed": "false",
                "scores": {"consistency": 45, "art_quality": 60, "reusability": 55},
                "total_score": 53,
                "issues": ["background is cluttered"],
                "prompt_patch": "Use a clean white asset background.",
            }
        )
    )

    response = await vision_provider.check_quality(VisionQualityRequest(image=b"generated-image"))

    assert response.retry_required is True
    assert response.retry_prompt_patch == "Use a clean white asset background."
    assert response.issues == [{"description": "background is cluttered"}]


@pytest.mark.asyncio
async def test_vision_quality_provider_requires_image(vision_provider) -> None:
    with pytest.raises(ProviderError) as exc_info:
        await vision_provider.check_quality(VisionQualityRequest())

    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST


@pytest.mark.asyncio
async def test_vision_quality_provider_rejects_non_json_content(vision_provider) -> None:
    _FakeAsyncClient.response_payload = _chat_response("plain text, not json")

    with pytest.raises(ProviderError) as exc_info:
        await vision_provider.check_quality(VisionQualityRequest(image=b"generated-image"))

    assert exc_info.value.code == ProviderErrorCode.UNEXPECTED
