from __future__ import annotations

from typing import Any

import pytest

from app.modules.provider_adapter.base import VisionQualityProvider, VisionQualityRequest, VisionQualityResponse
from app.modules.quality_retry.image_quality import check_image_quality


class _RecordingVisionProvider(VisionQualityProvider):
    def __init__(self) -> None:
        self.requests: list[VisionQualityRequest] = []

    async def check_quality(self, request: VisionQualityRequest) -> VisionQualityResponse:
        self.requests.append(request)
        return VisionQualityResponse(
            quality_score=0.95,
            face_consistency_score=0.95,
            outfit_consistency_score=0.95,
            scene_consistency_score=0.95,
            prop_presence_score=0.95,
            composition_score=0.95,
            issues=[],
            retry_required=False,
        )


@pytest.mark.asyncio
async def test_check_image_quality_forwards_generation_context_to_provider() -> None:
    provider = _RecordingVisionProvider()
    retry_history: list[dict[str, Any]] = [{"attempt": 1, "prompt_patch": "make the watch visible"}]

    await check_image_quality(
        image_bytes=b"generated",
        reference_character_images=[b"character-ref"],
        reference_scene_image=b"scene-ref",
        expected_props=["旧怀表"],
        vision_provider=provider,
        check_dimensions=["prop", "composition"],
        prompt="positive generation prompt",
        negative_prompt="avoid blur",
        asset_bible={"title": "旧怀表", "summary": "A story bible snapshot"},
        style_keywords=["cinematic", "写实"],
        retry_history=retry_history,
        metadata={"project_id": "project-1", "asset_type": "prop_usage"},
    )

    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.prompt == "positive generation prompt"
    assert request.negative_prompt == "avoid blur"
    assert request.asset_bible == {"title": "旧怀表", "summary": "A story bible snapshot"}
    assert request.style_keywords == ["cinematic", "写实"]
    assert request.expected_props == ["旧怀表"]
    assert request.retry_history == retry_history
    assert request.metadata == {"project_id": "project-1", "asset_type": "prop_usage"}
