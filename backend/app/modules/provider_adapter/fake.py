"""Fake provider implementations for local development and testing.

Each fake provider returns deterministic, lightweight responses and can be
configured to simulate specific faults (timeout, rate-limit, auth failure)
for testing retry and error-handling logic.
"""

from __future__ import annotations

import base64
import json as _json
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

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

# ---------------------------------------------------------------------------
# Minimal valid media fixtures (embedded bytes)
# ---------------------------------------------------------------------------

# 1x1 transparent PNG (67 bytes)
_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQImWP4//8/AwAI/AL+hc2V/AAAAABJRU5ErkJggg=="
)

def _now_iso() -> str:
    """Return current time as ISO 8601 string."""
    import datetime as _dt

    return (_dt.datetime.now(_dt.UTC) + _dt.timedelta(hours=1)).isoformat()


# ---------------------------------------------------------------------------
# Pre-canned JSON fixtures for FakeDeepSeekProvider
# ---------------------------------------------------------------------------

_CHARACTER_FIXTURE: dict[str, Any] = {
    "characters": [
        {
            "character_id": "CH_001",
            "name": "苏晚晴",
            "aliases": ["晚晴", "苏小姐"],
            "role_type": "主角",
            "gender": "女",
            "age": "24岁",
            "height": "168cm",
            "body_type": "纤细",
            "face_shape": "鹅蛋脸",
            "facial_bone_structure": "柔和",
            "skin_tone": "白皙",
            "eyes": "杏仁眼，深棕色",
            "eyebrows": "柳叶眉",
            "nose": "小巧挺拔",
            "mouth": "樱桃小嘴",
            "hair_color": "黑色",
            "hair_style": "及腰长发，刘海偏分",
            "default_outfit": "白色连衣裙",
            "outfit_details": "简约收腰设计，领口蕾丝点缀",
            "personality": "温柔坚韧，内敛深情",
            "emotion_pack": ["温柔", "坚定", "悲伤", "喜悦"],
            "forbidden_changes": ["脸型", "眼睛", "发型"],
        }
    ]
}

_SCENE_FIXTURE: dict[str, Any] = {
    "scenes": [
        {
            "scene_id": "SC_001",
            "scene_name": "冷白灯豪宅客厅",
            "scene_type": "室内",
            "time_of_day": "夜晚",
            "weather": "晴朗",
            "lighting": "冷白色顶灯与窗外蓝色夜景混合",
            "mood": "冷清孤寂",
            "color_palette": ["黑色", "白色", "银色", "冷蓝色"],
            "fixed_anchors": [
                "黑色大理石地面",
                "右侧落地窗",
                "中央低矮茶几",
                "白色弧形沙发",
                "窗外城市夜景",
            ],
        }
    ]
}

_PROP_FIXTURE: dict[str, Any] = {
    "props": [
        {
            "prop_id": "PR_001",
            "name": "旧怀表",
            "aliases": ["怀表", "旧表"],
            "owner_character_id": "CH_001",
            "first_appearance": "第2幕",
            "visual_features": "金色表壳，表面有划痕，表链断裂",
            "material": "镀金铜",
            "color": "金色",
            "size": "直径3cm",
            "function_in_story": "男主遗物，贯穿全文的情感信物",
            "state_timeline": [
                "第2幕：男主握在掌心",
                "第4幕：掉落在雨水中",
                "第7幕：女主捡起后打开",
                "第9幕：表盖内露出旧照片",
            ],
        }
    ]
}

_STYLE_FIXTURE: dict[str, Any] = {
    "detected_genre": "都市言情",
    "confidence": 0.86,
    "reason": "文本包含总裁、宴会厅、豪门、合同、情感拉扯等元素",
    "recommended_visual_style": "现代都市写实插画风格",
    "fallback_styles": ["真人电影级", "豪门复仇"],
}

_STORY_BIBLE_FIXTURE: dict[str, Any] = {
    "project_id": "",
    "title": "旧怀表",
    "genre": "都市言情",
    "visual_style": "现代都市写实插画风格",
    "aspect_ratio": "9:16",
    "story_summary": "一个关于旧怀表的感情故事",
    "main_conflict": "女主在寻找怀表主人的过程中发现了自己的身世秘密",
    "emotional_tone": "深情忧伤",
}

_DEFAULT_FIXTURE: dict[str, Any] = {"text": "系统已根据输入文本生成了视觉资产分析结果。"}

# ---------------------------------------------------------------------------
# Fault configuration
# ---------------------------------------------------------------------------


class FaultType(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILED = "auth_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


@dataclass
class FaultConfig:
    """Injectable fault simulation for fake providers.

    Set ``fault`` on a fake provider instance to simulate specific errors.
    """

    fault: FaultType = FaultType.NONE
    fail_count: int = 1  # number of consecutive calls to fail
    _remaining: int = field(default=1, init=False)

    def __post_init__(self) -> None:
        self._remaining = self.fail_count

    def maybe_raise(self, provider_name: str) -> None:
        """Raise a ProviderError if a fault is configured and still active."""
        if self.fault == FaultType.NONE:
            return
        if self._remaining <= 0:
            return

        self._remaining -= 1
        if self.fault == FaultType.TIMEOUT:
            raise ProviderError(
                code=ProviderErrorCode.TIMEOUT,
                message=f"[fake] {provider_name} simulated timeout",
                provider=provider_name,
                raw_error="simulated timeout",
            )
        elif self.fault == FaultType.RATE_LIMIT:
            raise ProviderError(
                code=ProviderErrorCode.RATE_LIMITED,
                message=f"[fake] {provider_name} simulated rate limit",
                provider=provider_name,
                raw_error="simulated rate limit",
            )
        elif self.fault == FaultType.AUTH_FAILED:
            raise ProviderError(
                code=ProviderErrorCode.AUTH_FAILED,
                message=f"[fake] {provider_name} simulated auth failure",
                provider=provider_name,
                raw_error="simulated auth failure",
            )
        elif self.fault == FaultType.PROVIDER_UNAVAILABLE:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER_UNAVAILABLE,
                message=f"[fake] {provider_name} simulated provider unavailable",
                provider=provider_name,
                raw_error="simulated provider unavailable",
            )


# =============================================================================
# FakeDeepSeekProvider
# =============================================================================


class FakeDeepSeekProvider(TextGenerationProvider):
    """Fake text-generation provider returning canned JSON fixtures.

    Keyword matching rules (case-insensitive):
    - "character" -> character JSON
    - "scene"     -> scene JSON
    - "prop"      -> prop JSON
    - "style" or "genre" -> style detection JSON
    - "bible" or "story"  -> story bible JSON
    - Otherwise   -> default text response
    """

    def __init__(self, fault: FaultType = FaultType.NONE) -> None:
        self._fault_config = FaultConfig(fault=fault)

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        self._fault_config.maybe_raise("deepseek")

        start = time.perf_counter()
        prompt_lower = request.prompt.lower()

        if "character" in prompt_lower:
            fixture = _CHARACTER_FIXTURE
        elif "scene" in prompt_lower:
            fixture = _SCENE_FIXTURE
        elif "prop" in prompt_lower:
            fixture = _PROP_FIXTURE
        elif "style" in prompt_lower or "genre" in prompt_lower:
            fixture = _STYLE_FIXTURE
        elif "bible" in prompt_lower or "story" in prompt_lower:
            fixture = _STORY_BIBLE_FIXTURE
        else:
            fixture = _DEFAULT_FIXTURE

        latency = int((time.perf_counter() - start) * 1000)

        return TextGenerationResponse(
            text=_json.dumps(fixture, ensure_ascii=False, indent=2),
            json_data=fixture,
            model=request.model or "fake-deepseek",
            latency_ms=latency,
            provider_request_id=f"fake-deepseek-{uuid.uuid4().hex[:8]}",
        )

    def configure_fault(self, fault_type: FaultType, fail_count: int = 1) -> None:
        self._fault_config = FaultConfig(fault=fault_type, fail_count=fail_count)


# =============================================================================
# FakeSeedreamProvider
# =============================================================================


class FakeSeedreamProvider(ImageGenerationProvider):
    """Fake image-generation provider returning a 1x1 transparent PNG."""

    def __init__(self, fault: FaultType = FaultType.NONE) -> None:
        self._fault_config = FaultConfig(fault=fault)

    @property
    def provider_id(self) -> str:
        return "fake-seedream"

    @property
    def model_name(self) -> str:
        return "fake-seedream"

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        self._fault_config.maybe_raise("seedream")

        start = time.perf_counter()
        latency = int((time.perf_counter() - start) * 1000)

        return ImageGenerationResponse(
            images=[_ONE_PIXEL_PNG],
            image_urls=["file:///fake/seedream/output.png"],
            model="fake-seedream",
            latency_ms=latency,
            provider_task_id=f"fake-seedream-{uuid.uuid4().hex[:8]}",
        )

    def configure_fault(self, fault_type: FaultType, fail_count: int = 1) -> None:
        self._fault_config = FaultConfig(fault=fault_type, fail_count=fail_count)


# =============================================================================
# FakeObjectStorageProvider
# =============================================================================


class FakeObjectStorageProvider(ObjectStorageProvider):
    """In-memory object storage provider for development and testing.

    Uploaded files are stored in memory (dict) and served via local file:// URLs.
    """

    def __init__(self, fault: FaultType = FaultType.NONE) -> None:
        self._fault_config = FaultConfig(fault=fault)
        self._store: dict[str, StorageUploadRequest] = {}

    async def upload(self, request: StorageUploadRequest) -> StorageUploadResponse:
        self._fault_config.maybe_raise("tos")

        asset_id = f"fake-asset-{uuid.uuid4().hex}"
        self._store[asset_id] = request
        url = f"file:///fake/storage/{request.project_id}/{request.file_name}"

        return StorageUploadResponse(
            asset_id=asset_id,
            url=url,
            signed_url=f"{url}?signature=fake-signed&expires=3600",
            expires_at=_now_iso(),
        )

    async def get_signed_url(self, asset_id: str, expires_seconds: int = 3600) -> str:
        if asset_id not in self._store:
            return f"file:///fake/storage/unknown/{asset_id}?signature=fake"
        req = self._store[asset_id]
        return f"file:///fake/storage/{req.project_id}/{req.file_name}?signature=fake-signed&expires={expires_seconds}"

    async def delete(self, asset_id: str) -> None:
        self._store.pop(asset_id, None)

    def configure_fault(self, fault_type: FaultType, fail_count: int = 1) -> None:
        self._fault_config = FaultConfig(fault=fault_type, fail_count=fail_count)


# =============================================================================
# FakeVisionQualityProvider
# =============================================================================


class FakeVisionQualityProvider(VisionQualityProvider):
    """Fake quality-check provider returning high pass scores with no issues."""

    def __init__(self, fault: FaultType = FaultType.NONE) -> None:
        self._fault_config = FaultConfig(fault=fault)

    async def check_quality(self, request: VisionQualityRequest) -> VisionQualityResponse:
        self._fault_config.maybe_raise("vision-quality")

        return VisionQualityResponse(
            quality_score=0.95,
            face_consistency_score=0.92,
            outfit_consistency_score=0.88,
            scene_consistency_score=0.90,
            prop_presence_score=1.0,
            composition_score=0.85,
            issues=[],
            retry_required=False,
            retry_prompt_patch="",
        )

    def configure_fault(self, fault_type: FaultType, fail_count: int = 1) -> None:
        self._fault_config = FaultConfig(fault=fault_type, fail_count=fail_count)
