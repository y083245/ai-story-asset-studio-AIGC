"""Style-id aliases and normalization.

The analysis pipeline sees a handful of style names in Chinese, English,
and legacy style-pack IDs (``xianxia_high_cg`` etc).  This module keeps the
one canonical mapping and the ``SUPPORTED_STYLE_IDS`` set so
``analysis_activities`` and ``workflow.publication`` normalize identically.
"""

from __future__ import annotations

SUPPORTED_STYLE_IDS: frozenset[str] = frozenset(
    {
        "urban_drama",
        "xianxia",
        "cyberpunk",
        "sci_fi",
        "cinematic_realistic",
        "chinese_ancient",
        "urban_drama_3d_anime",
        "chinese_historical_3d_anime",
        "xianxia_3d_anime",
        "future_scifi_movie_3d_anime",
        "cinematic_live_action_3d_anime",
        "cyberpunk_3d_anime",
    }
)

DEFAULT_STYLE_ID = "cinematic_realistic"

REALISTIC_STYLE_IDS: frozenset[str] = frozenset(
    {
        "urban_drama",
        "xianxia",
        "cyberpunk",
        "sci_fi",
        "cinematic_realistic",
        "chinese_ancient",
    }
)

ANIME_3D_STYLE_IDS: frozenset[str] = frozenset(
    {
        "urban_drama_3d_anime",
        "chinese_historical_3d_anime",
        "xianxia_3d_anime",
        "future_scifi_movie_3d_anime",
        "cinematic_live_action_3d_anime",
        "cyberpunk_3d_anime",
    }
)

REALISTIC_TO_3D_STYLE_ID: dict[str, str] = {
    "urban_drama": "urban_drama_3d_anime",
    "chinese_ancient": "chinese_historical_3d_anime",
    "xianxia": "xianxia_3d_anime",
    "sci_fi": "future_scifi_movie_3d_anime",
    "cinematic_realistic": "cinematic_live_action_3d_anime",
    "cyberpunk": "cyberpunk_3d_anime",
}

ANIME_3D_TO_REALISTIC_STYLE_ID: dict[str, str] = {value: key for key, value in REALISTIC_TO_3D_STYLE_ID.items()}

STYLE_ID_ALIASES: dict[str, str] = {
    # 都市写实
    "都市写实": "urban_drama",
    "都市言情": "urban_drama",
    "都市爱情": "urban_drama",
    "都市剧情类真人写实风": "urban_drama",
    "urban_drama_live_action_realistic": "urban_drama",
    "urban_drama": "urban_drama",
    "urban_romance": "urban_drama",
    # 古风仙侠
    "古风仙侠类": "xianxia",
    "古风仙侠": "xianxia",
    "仙侠": "xianxia",
    "xianxia": "xianxia",
    "xianxia_high_cg": "xianxia",
    # 赛博朋克
    "赛博朋克类": "cyberpunk",
    "赛博朋克": "cyberpunk",
    "cyberpunk": "cyberpunk",
    "cyberpunk_neon_noir": "cyberpunk",
    # 科幻
    "未来科幻电影类": "sci_fi",
    "未来科幻": "sci_fi",
    "科幻": "sci_fi",
    "sci_fi": "sci_fi",
    "future_sci_fi_cinema": "sci_fi",
    # 电影写实
    "真人电影级": "cinematic_realistic",
    "电影写实": "cinematic_realistic",
    "cinematic_realistic": "cinematic_realistic",
    "live_action_cinematic": "cinematic_realistic",
    # 中国古风
    "古风": "chinese_ancient",
    "中国古风": "chinese_ancient",
    "chinese_ancient": "chinese_ancient",
    "traditional_chinese_period": "chinese_ancient",
    # 3D 动漫风格包
    "3D动漫": "urban_drama_3d_anime",
    "3d动漫": "urban_drama_3d_anime",
    "3d_anime": "urban_drama_3d_anime",
    "anime_3d": "urban_drama_3d_anime",
    "3D都市剧情类动漫风": "urban_drama_3d_anime",
    "都市剧情3D动漫": "urban_drama_3d_anime",
    "urban_drama_3d_anime": "urban_drama_3d_anime",
    "中国古风3D动漫": "chinese_historical_3d_anime",
    "中国古风_3D动漫版": "chinese_historical_3d_anime",
    "chinese_historical_3d_anime": "chinese_historical_3d_anime",
    "古风仙侠3D动漫": "xianxia_3d_anime",
    "古风仙侠类_3D动漫版": "xianxia_3d_anime",
    "xianxia_3d_anime": "xianxia_3d_anime",
    "未来科幻3D动漫": "future_scifi_movie_3d_anime",
    "未来科幻电影类_3D动漫版": "future_scifi_movie_3d_anime",
    "future_scifi_movie_3d_anime": "future_scifi_movie_3d_anime",
    "真人电影级3D动漫": "cinematic_live_action_3d_anime",
    "真人电影级_3D动漫版": "cinematic_live_action_3d_anime",
    "cinematic_live_action_3d_anime": "cinematic_live_action_3d_anime",
    "赛博朋克3D动漫": "cyberpunk_3d_anime",
    "赛博朋克类_3D动漫版": "cyberpunk_3d_anime",
    "cyberpunk_3d_anime": "cyberpunk_3d_anime",
}


def normalize_style_id(value: str | None) -> str:
    """Map an arbitrary genre / style label onto a supported style-pack id.

    Falls back to :data:`DEFAULT_STYLE_ID` if the input is empty or unknown.
    """
    text = (value or "").strip()
    if text in SUPPORTED_STYLE_IDS:
        return text
    lowered = text.lower()
    if lowered in SUPPORTED_STYLE_IDS:
        return lowered
    return STYLE_ID_ALIASES.get(text) or STYLE_ID_ALIASES.get(lowered) or DEFAULT_STYLE_ID


def normalize_style_id_for_family(value: str | None, style_family: str | None) -> str:
    """Normalize a style id while preserving an explicitly detected style family."""
    normalized = normalize_style_id(value)
    family = (style_family or "").strip().lower()
    if family == "3d_anime" and normalized in REALISTIC_TO_3D_STYLE_ID:
        return REALISTIC_TO_3D_STYLE_ID[normalized]
    if family == "realistic" and normalized in ANIME_3D_TO_REALISTIC_STYLE_ID:
        return ANIME_3D_TO_REALISTIC_STYLE_ID[normalized]
    return normalized
