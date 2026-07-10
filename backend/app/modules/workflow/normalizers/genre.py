"""Genre-detector output normalizer."""

from __future__ import annotations

from typing import Any

from app.modules.template_style.style_alias import DEFAULT_STYLE_ID, normalize_style_id_for_family
from app.modules.workflow.normalizers.common import string_list


def normalize_genre(data: dict[str, Any]) -> dict[str, Any]:
    style_family = str(data.get("style_family") or "")
    style_id = normalize_style_id_for_family(
        str(data.get("style_id") or data.get("genre") or DEFAULT_STYLE_ID),
        style_family,
    )
    return {
        "genre": str(data.get("genre") or data.get("detected_genre") or style_id),
        "style_family": style_family,
        "style_id": style_id,
        "confidence": normalize_confidence(data.get("confidence")),
        "sub_genres": string_list(data.get("sub_genres")),
        "style_tags": string_list(data.get("style_tags")),
        "fallback_styles": string_list(data.get("fallback_styles")),
        "evidence": string_list(data.get("evidence")),
        "risk": str(data.get("risk") or ""),
        "reason": str(data.get("reason") or ""),
    }


def normalize_confidence(value: Any) -> float:
    """Normalize model confidence into the public 0..1 contract."""
    if value is None:
        return 0.0
    has_percent_sign = False
    if isinstance(value, str):
        text = value.strip()
        has_percent_sign = "%" in text
        text = text.replace("%", "")
    else:
        text = value
    try:
        confidence = float(text)
    except (TypeError, ValueError):
        return 0.0
    if has_percent_sign or confidence > 10:
        confidence = confidence / 100
    return min(max(confidence, 0.0), 1.0)
