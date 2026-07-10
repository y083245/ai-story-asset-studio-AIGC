"""Story Asset Studio configuration.

所有配置通过环境变量注入，本地开发使用 .env 文件。
生产环境密钥不允许默认值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"
    admin_api_key: str = ""
    user_auth_mode: Literal["dev-header", "signed-header"] = "dev-header"
    user_auth_shared_secret: str = ""
    user_auth_signature_ttl_seconds: int = 300
    provider_mode: Literal["auto", "fake", "real"] = "auto"
    cors_allowed_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
    )

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://storyasset:storyasset@localhost:5432/storyasset"
    database_url_sync: str = "postgresql://storyasset:storyasset@localhost:5432/storyasset"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object Storage
    object_storage_provider: Literal["local", "volcengine", "aliyun"] = "local"

    # TOS (生产环境使用火山引擎 TOS)
    tos_access_key: str = ""
    tos_secret_key: str = ""
    tos_bucket: str = ""
    tos_region: str = ""
    tos_endpoint: str = ""

    # Aliyun OSS (阿里云对象存储)
    aliyun_oss_access_key: str = ""
    aliyun_oss_secret_key: str = ""
    aliyun_oss_bucket: str = ""
    aliyun_oss_region: str = ""
    aliyun_oss_endpoint: str = ""

    # CDN / 公网资产访问基础 URL
    cdn_base_url: str = ""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_name: str = "deepseek-v4-flash"
    deepseek_fast_model_name: str = "deepseek-v4-flash"
    deepseek_strong_model_name: str = "deepseek-v4-pro"
    deepseek_default_thinking: Literal["enabled", "disabled"] = "disabled"

    # Analysis performance
    analysis_chunk_concurrency: int = 3
    analysis_chunk_retry_limit: int = 1
    analysis_chunk_result_cache: bool = True
    deepseek_flash_concurrency: int = 20
    deepseek_pro_concurrency: int = 10

    # Prompt engine
    prompt_engine_mode: Literal["legacy", "staged"] = "staged"
    prompt_synthesizer_concurrency: int = 5
    prompt_synthesizer_temperature: float = 0.55
    prompt_synthesizer_max_tokens: int = 1500
    prompt_synthesizer_timeout_seconds: int = 60
    bilingual_keywords_enabled: bool = True

    # Reference chain
    reference_chain_enabled: bool = True
    canonical_bible_sheet_timeout_seconds: int = 240
    canonical_bible_sheet_dimensions: str = "1440x2560"

    # Seedream (火山引擎 Ark)
    seedream_api_key: str = ""
    seedream_base_url: str = ""
    seedream_model_name: str = "doubao-seedream-5-0-lite-260128"

    # Vision Quality
    vision_quality_enabled: bool = True
    vision_quality_provider: Literal["openai", "gemini", "doubao"] = "doubao"
    vision_quality_model_name: str = "doubao-vision-quality"
    vision_quality_pass_threshold: int = 60
    vision_quality_max_retries: int = 3


# 全局单例，模块导入时创建
settings = Settings()
