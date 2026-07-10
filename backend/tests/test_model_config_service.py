"""Tests for the local model provider configuration service.

The service was refactored to delegate provider-specific auth / model-list
retrieval to adapters in ``app.modules.model_config.adapters``. These tests
exercise the service via its public API and stub adapters via the shared
adapter registry.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from app.modules.model_config.adapters.registry import get_adapter_registry
from app.modules.model_config.schemas import ModelOption
from app.modules.model_config.service import ModelConfigService


class _StubAdapter:
    """Minimal adapter that exposes just the surface the service consumes."""

    auth_label = "API Key"

    def __init__(
        self,
        *,
        auth_result: str | Exception = "",
        list_result: list[ModelOption] | Exception | None = None,
        test_result: tuple[bool, str] = (True, "ok"),
    ) -> None:
        self._auth_result = auth_result
        self._list_result = list_result if list_result is not None else []
        self._test_result = test_result
        self.authenticate_calls: list[str] = []
        self.list_models_calls: list[tuple[str, str]] = []

    async def authenticate(self, api_key: str) -> str:
        self.authenticate_calls.append(api_key)
        if isinstance(self._auth_result, Exception):
            raise self._auth_result
        return self._auth_result or api_key.strip()

    async def list_models(self, base_url: str, auth_value: str) -> list[ModelOption]:
        self.list_models_calls.append((base_url, auth_value))
        if isinstance(self._list_result, Exception):
            raise self._list_result
        return list(self._list_result)

    async def test_connection(self, base_url: str, auth_value: str) -> tuple[bool, str]:  # noqa: ARG002
        return self._test_result


def _stub_registry(monkeypatch: pytest.MonkeyPatch, provider_id: str, adapter: _StubAdapter) -> None:
    """Force ``get_adapter_registry().get(provider_id)`` to return *adapter*."""
    real_registry = get_adapter_registry()

    original_get = real_registry.get

    def patched_get(pid: str):
        if pid == provider_id:
            return adapter
        return original_get(pid)

    monkeypatch.setattr(real_registry, "get", patched_get)


# ── static config surface ────────────────────────────────────────────


def test_default_config_is_unconfigured_and_has_provider_presets(tmp_path, monkeypatch):
    # Ensure a fresh install (no .env-provided keys) presents as unconfigured.
    from app.modules.model_config import service as service_module

    monkeypatch.setattr(service_module.settings, "deepseek_api_key", "")
    monkeypatch.setattr(service_module.settings, "seedream_api_key", "")

    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    public_config = service.get_public_config()
    presets = service.get_presets()

    assert public_config.configured is False
    assert public_config.text.api_key_set is False
    assert public_config.image.provider_id == "doubao_seedream"
    assert {provider.provider_id for provider in presets.text_providers} >= {
        "deepseek",
        "aliyun_bailian",
        "baidu_qianfan",
        "tencent_hunyuan",
        "moonshot_kimi",
        "zhipu_bigmodel",
        "volcengine_ark",
    }
    assert {provider.provider_id for provider in presets.image_providers} >= {
        "doubao_seedream",
        "replicate",
        "google_imagen",
        "openai",
    }


def test_seedream_image_preset_uses_current_5_0_model_ids(tmp_path):
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    seedream_preset = next(
        provider for provider in service.get_presets().image_providers
        if provider.provider_id == "doubao_seedream"
    )

    assert seedream_preset.default_model == "doubao-seedream-5-0-lite-260128"
    assert {
        "doubao-seedream-5-0-260128",
        "doubao-seedream-5-0-lite-260128",
        "doubao-seedream-5-0-pro-260628",
    } <= {model.value for model in seedream_preset.models}


def test_tracked_config_examples_and_default_docs_do_not_use_legacy_seedream_lite_id():
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "grep",
            "-n",
            "--fixed-strings",
            "doubao-seedream-5.0-lite",
            "--",
            "local_config.example.json",
            ".env.example",
            "README.md",
            "docs",
            "backend/app/config.py",
            "backend/app/modules/model_config/presets.py",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode in (0, 1), result.stderr
    assert result.stdout == ""


def test_save_masks_keys_publicly_but_keeps_them_on_disk(tmp_path):
    config_path = tmp_path / "model-providers.json"
    service = ModelConfigService(config_path=config_path)

    public_config = service.save_config(
        {
            "text": {
                "provider_id": "moonshot_kimi",
                "model": "kimi-k2.6",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key": "sk-test-text",
            },
            "image": {
                "provider_id": "doubao_seedream",
                "model": "doubao-seedream-5.0-lite",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key": "sk-test-image",
            },
        }
    )

    assert public_config.configured is True
    assert public_config.text.api_key_set is True
    assert public_config.text.api_key_preview == "sk-t...text"
    assert public_config.image.api_key_preview == "sk-t...mage"

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw["text"]["api_key"] == "sk-test-text"
    assert raw["image"]["api_key"] == "sk-test-image"


def test_empty_key_on_update_keeps_existing_secret(tmp_path):
    config_path = tmp_path / "model-providers.json"
    service = ModelConfigService(config_path=config_path)
    service.save_config(
        {
            "text": {
                "provider_id": "deepseek",
                "model": "deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-original",
            }
        }
    )

    public_config = service.save_config(
        {
            "text": {
                "provider_id": "deepseek",
                "model": "deepseek-v4-pro",
                "base_url": "https://api.deepseek.com",
                "api_key": "",
            }
        }
    )

    assert public_config.text.model == "deepseek-v4-pro"
    assert public_config.text.api_key_preview == "sk-o...inal"
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw["text"]["api_key"] == "sk-original"


def test_empty_key_on_provider_change_clears_existing_secret(tmp_path):
    config_path = tmp_path / "model-providers.json"
    service = ModelConfigService(config_path=config_path)
    service.save_config(
        {
            "text": {
                "provider_id": "deepseek",
                "model": "deepseek-v4-flash",
                "base_url": "https://api.deepseek.com",
                "api_key": "sk-original",
            }
        }
    )

    public_config = service.save_config(
        {
            "text": {
                "provider_id": "moonshot_kimi",
                "model": "kimi-k2.6",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key": "",
            }
        }
    )

    assert public_config.text.provider_id == "moonshot_kimi"
    assert public_config.text.api_key_set is False
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    assert raw["text"]["api_key"] == ""


def test_load_secret_config_normalizes_legacy_bearer_api_keys(tmp_path):
    config_path = tmp_path / "model-providers.json"
    config_path.write_text(
        json.dumps(
            {
                "text": {
                    "provider_id": "moonshot_kimi",
                    "model": "kimi-k2.6",
                    "base_url": "https://api.moonshot.ai/v1",
                    "api_key": "Authorization: Bearer sk-text",
                },
                "image": {
                    "provider_id": "doubao_seedream",
                    "model": "doubao-seedream-5.0-lite",
                    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                    "api_key": "Bearer ark-image",
                },
            }
        ),
        encoding="utf-8",
    )
    service = ModelConfigService(config_path=config_path)

    config = service.load_secret_config()

    assert config.text.api_key == "sk-text"
    assert config.image.api_key == "ark-image"


# ── list_provider_models ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_provider_models_delegates_to_adapter(monkeypatch, tmp_path):
    adapter = _StubAdapter(
        list_result=[ModelOption(value="deepseek-v4-flash", label="DeepSeek V4 Flash")],
    )
    _stub_registry(monkeypatch, "deepseek", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-live",
        }
    )

    assert result.source == "remote"
    assert [m.value for m in result.models] == ["deepseek-v4-flash"]
    assert result.error_message == ""
    assert adapter.authenticate_calls == ["sk-live"]
    assert adapter.list_models_calls == [("https://api.deepseek.com", "sk-live")]


@pytest.mark.asyncio
async def test_list_provider_models_without_key_uses_presets_without_remote(monkeypatch, tmp_path):
    adapter = _StubAdapter(list_result=AssertionError("adapter must not be called without API key"))
    _stub_registry(monkeypatch, "moonshot_kimi", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "moonshot_kimi",
            "base_url": "https://api.moonshot.ai/v1",
            "api_key": "",
        }
    )

    assert result.source == "preset"
    assert "API Key" in result.error_message
    assert adapter.list_models_calls == []
    assert [model.value for model in result.models] == [
        "kimi-k2.6",
        "moonshot-v1-128k",
        "moonshot-v1-32k",
    ]


@pytest.mark.asyncio
async def test_list_provider_models_falls_back_for_incomplete_base_url(tmp_path):
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "aliyun_bailian",
            "base_url": "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            "api_key": "",
        }
    )

    assert result.source == "preset"
    assert "Base URL" in result.error_message


@pytest.mark.asyncio
async def test_list_provider_models_falls_back_on_401(monkeypatch, tmp_path):
    request = httpx.Request("GET", "https://api.deepseek.com/v1/models")
    error = httpx.HTTPStatusError(
        "bad key",
        request=request,
        response=httpx.Response(401, request=request),
    )
    adapter = _StubAdapter(list_result=error)
    _stub_registry(monkeypatch, "deepseek", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-invalid",
        }
    )

    assert result.source == "preset"
    assert "API Key" in result.error_message
    assert [m.value for m in result.models][:2] == ["deepseek-v4-flash", "deepseek-v4-pro"]


@pytest.mark.asyncio
async def test_list_provider_models_falls_back_on_network_error(monkeypatch, tmp_path):
    adapter = _StubAdapter(list_result=httpx.ConnectError("dns"))
    _stub_registry(monkeypatch, "deepseek", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-live",
        }
    )

    assert result.source == "preset"
    assert "Base URL" in result.error_message or "网络" in result.error_message


@pytest.mark.asyncio
async def test_list_provider_models_normalizes_pasted_bearer_api_key(monkeypatch, tmp_path):
    adapter = _StubAdapter(list_result=[ModelOption(value="kimi-k2.6", label="Kimi K2.6")])
    _stub_registry(monkeypatch, "moonshot_kimi", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "moonshot_kimi",
            "base_url": "https://api.moonshot.ai/v1",
            "api_key": "Authorization: Bearer sk-live",
        }
    )

    assert result.source == "remote"
    # The Authorization / Bearer prefixes should have been stripped before
    # reaching the adapter.
    assert adapter.authenticate_calls == ["sk-live"]


@pytest.mark.asyncio
async def test_seedream_remote_models_are_filtered_to_seedream_only(monkeypatch, tmp_path):
    adapter = _StubAdapter(
        list_result=[
            ModelOption(value="doubao-seedream-5.0-lite", label="Seedream 5.0 Lite"),
            ModelOption(value="doubao-1-5-pro-32k-250115", label="Doubao 1.5 Pro 32K"),
        ]
    )
    _stub_registry(monkeypatch, "doubao_seedream", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "image",
            "provider_id": "doubao_seedream",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "sk-live",
        }
    )

    assert result.source == "remote"
    assert [m.value for m in result.models] == ["doubao-seedream-5.0-lite"]


@pytest.mark.asyncio
async def test_list_provider_models_reports_authenticate_errors_as_preset_fallback(
    monkeypatch, tmp_path
):
    adapter = _StubAdapter(auth_result=ValueError("API Key 格式无效，应该是 key_id.key_secret"))
    _stub_registry(monkeypatch, "zhipu_bigmodel", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    result = await service.list_provider_models(
        {
            "kind": "text",
            "provider_id": "zhipu_bigmodel",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "not-a-valid-zhipu-key",
        }
    )

    assert result.source == "preset"
    assert "key_id.key_secret" in result.error_message


# ── test_connection ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_test_connection_delegates_to_adapter(monkeypatch, tmp_path):
    adapter = _StubAdapter(test_result=(True, "连接成功，获取到 6 个模型"))
    _stub_registry(monkeypatch, "deepseek", adapter)
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    response = await service.test_connection(
        {
            "kind": "text",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-live",
        }
    )

    assert response.success is True
    assert "连接成功" in response.message


@pytest.mark.asyncio
async def test_test_connection_reports_missing_key(tmp_path):
    service = ModelConfigService(config_path=tmp_path / "model-providers.json")

    response = await service.test_connection(
        {
            "kind": "text",
            "provider_id": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "",
        }
    )

    assert response.success is False
    assert "API Key" in response.message
