"""Image quality check rules (M13-06).

Defines issue codes, descriptions, and the check_image_quality function
that orchestrates visual quality inspection for generated image assets.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.modules.provider_adapter.base import (
    VisionQualityProvider,
    VisionQualityRequest,
    VisionQualityResponse,
)
from app.modules.quality_retry.thresholds import evaluate_thresholds

# Issue codes for image quality inspection
IMAGE_ISSUE_CODES: dict[str, str] = {
    "FACE_CHANGED": "角色面部与参考图不一致（变脸）",
    "OUTFIT_MISMATCH": "服装不一致",
    "EXTRA_CHARACTER": "画面中出现无关人物",
    "SCENE_MISMATCH": "场景与固定锚点不符",
    "PROP_MISSING": "关键道具缺失",
    "WATERMARK": "画面中存在文字水印或logo",
    "BODY_DEFORM": "肢体异常变形",
    "COMPOSITION_CROP": "构图裁切不当",
    "LOW_QUALITY": "画面整体质量过低",
}

# Mapping from issue code to check dimension name
ISSUE_CODE_TO_DIMENSION: dict[str, str] = {
    "FACE_CHANGED": "face",
    "OUTFIT_MISMATCH": "outfit",
    "EXTRA_CHARACTER": "extra_character",
    "SCENE_MISMATCH": "scene",
    "PROP_MISSING": "prop",
    "WATERMARK": "watermark",
    "BODY_DEFORM": "body",
    "COMPOSITION_CROP": "composition",
    "LOW_QUALITY": "quality",
}


async def check_image_quality(
    image_bytes: bytes,
    reference_character_images: list[bytes],
    reference_scene_image: bytes | None,
    expected_props: list[str],
    vision_provider: VisionQualityProvider,
    check_dimensions: list[str] | None = None,
    prompt: str = "",
    negative_prompt: str = "",
    asset_bible: dict[str, Any] | str | None = None,
    style_keywords: list[str] | None = None,
    retry_history: list[dict[str, Any]] | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run image quality checks and return issues + scores.

    Args:
        image_bytes: The generated image to inspect.
        reference_character_images: Reference images of characters expected in the asset.
        reference_scene_image: Reference image of the scene.
        expected_props: List of prop names expected in the image.
        vision_provider: Provider adapter for vision quality checks.
        check_dimensions: Specific dimensions to check; all if None.

    Returns:
        dict with keys: quality_score, face_consistency_score,
        outfit_consistency_score, scene_consistency_score,
        prop_presence_score, composition_score, issues, retry_required,
        retry_prompt_patch, needs_review.
    """
    if check_dimensions is None:
        check_dimensions = ["face", "outfit", "scene", "prop", "watermark", "body", "composition"]

    request = VisionQualityRequest(
        image=image_bytes,
        reference_character_images=reference_character_images,
        reference_scene_image=reference_scene_image,
        check_dimensions=check_dimensions,
        prompt=prompt,
        negative_prompt=negative_prompt,
        asset_bible=asset_bible,
        style_keywords=style_keywords or [],
        expected_props=expected_props,
        retry_history=retry_history or [],
        metadata=metadata or {},
    )

    response: VisionQualityResponse = await vision_provider.check_quality(request)

    # Collect issues into standardized format
    issues: list[dict[str, Any]] = []
    for issue in response.issues:
        issue_code = issue.get("code", "")
        issues.append(
            {
                "code": issue_code,
                "dimension": issue.get("dimension", ISSUE_CODE_TO_DIMENSION.get(issue_code, "unknown")),
                "description": issue.get("description", IMAGE_ISSUE_CODES.get(issue_code, "")),
                "score": issue.get("score"),
                "threshold": issue.get("threshold"),
                "severity": issue.get("severity", "warning"),
            }
        )

    # Build scores dict for threshold evaluation
    scores = {
        "quality_score": response.quality_score,
        "face_consistency": response.face_consistency_score,
        "outfit_consistency": response.outfit_consistency_score,
        "scene_consistency": response.scene_consistency_score,
        "prop_presence": response.prop_presence_score,
    }

    if settings.vision_quality_pass_threshold != 60:
        scores["quality_score"] = response.quality_score

    # Evaluate thresholds
    passed, failed_checks = evaluate_thresholds(scores, issues)
    configured_threshold = settings.vision_quality_pass_threshold / 100
    if response.quality_score < configured_threshold:
        passed = False
        failed_checks.append("quality_score_below_threshold")

    return {
        "quality_score": response.quality_score,
        "face_consistency_score": response.face_consistency_score,
        "outfit_consistency_score": response.outfit_consistency_score,
        "scene_consistency_score": response.scene_consistency_score,
        "prop_presence_score": response.prop_presence_score,
        "composition_score": response.composition_score,
        "issues": issues,
        "retry_required": not passed,
        "retry_prompt_patch": response.retry_prompt_patch or "",
        "needs_review": False,
    }
