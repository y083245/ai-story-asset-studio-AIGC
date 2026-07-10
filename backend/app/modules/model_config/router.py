"""Routes for local model provider configuration."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.model_config.schemas import (
    LocalModelConfigInput,
    LocalModelPublicConfig,
    ProviderModelListRequest,
    ProviderModelListResponse,
    ProviderPresetResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from app.modules.model_config.service import get_model_config_service

router = APIRouter(prefix="/api/model-config", tags=["model-config"])


@router.get("/presets", response_model=ProviderPresetResponse)
async def get_model_provider_presets() -> ProviderPresetResponse:
    return get_model_config_service().get_presets()


@router.post("/models", response_model=ProviderModelListResponse)
async def list_model_provider_models(payload: ProviderModelListRequest) -> ProviderModelListResponse:
    return await get_model_config_service().list_provider_models(payload)


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_model_connection(payload: TestConnectionRequest) -> TestConnectionResponse:
    return await get_model_config_service().test_connection(payload)


@router.get("", response_model=LocalModelPublicConfig)
async def get_model_config() -> LocalModelPublicConfig:
    return get_model_config_service().get_public_config()


@router.put("", response_model=LocalModelPublicConfig)
async def save_model_config(payload: LocalModelConfigInput) -> LocalModelPublicConfig:
    return get_model_config_service().save_config(payload)
