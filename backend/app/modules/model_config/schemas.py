"""Schemas for local model provider configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModelOption(BaseModel):
    value: str
    label: str


class ProviderPreset(BaseModel):
    provider_id: str
    label: str
    base_url: str
    default_model: str
    models: list[ModelOption]
    docs_url: str
    note: str = ""
    auth_label: str = "API Key"


class ProviderPresetResponse(BaseModel):
    text_providers: list[ProviderPreset]
    image_providers: list[ProviderPreset]


class ProviderModelListRequest(BaseModel):
    kind: Literal["text", "image"]
    provider_id: str
    base_url: str = ""
    api_key: str = Field(default="", repr=False)
    is_full_url: bool = False
    models_url: str = ""
    custom_user_agent: str = ""


class ProviderModelListResponse(BaseModel):
    provider_id: str
    models: list[ModelOption]
    source: Literal["remote", "preset"]
    error_message: str = ""


class ModelProviderPublicConfig(BaseModel):
    provider_id: str
    model: str
    base_url: str
    api_key_set: bool = False
    api_key_preview: str = ""


class LocalModelPublicConfig(BaseModel):
    configured: bool
    config_path: str
    text: ModelProviderPublicConfig
    image: ModelProviderPublicConfig


class ModelProviderConfigInput(BaseModel):
    provider_id: str
    model: str
    base_url: str
    api_key: str = Field(default="", repr=False)


class LocalModelConfigInput(BaseModel):
    text: ModelProviderConfigInput | None = None
    image: ModelProviderConfigInput | None = None


class ModelProviderSecretConfig(ModelProviderConfigInput):
    api_key: str = Field(default="", repr=False)


class LocalModelSecretConfig(BaseModel):
    text: ModelProviderSecretConfig
    image: ModelProviderSecretConfig


class TestConnectionRequest(BaseModel):
    kind: Literal["text", "image"]
    provider_id: str
    base_url: str = ""
    api_key: str = Field(default="", repr=False)


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
