"""Structured access to high-quality style master prompt documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.modules.template_style.style_alias import normalize_style_id as _alias_normalize_style_id

STYLE_DOC_ROOT_RELATIVE = Path("docs")

STYLE_MASTER_DOCS: dict[str, tuple[str, str]] = {
    "urban_drama": ("都市剧情类真人写实风", "现实类/都市剧情类真人写实风_高质量提示词模板.txt"),
    "xianxia": ("古风仙侠类", "现实类/古风仙侠类_高质量提示词模板.txt"),
    "cyberpunk": ("赛博朋克类", "现实类/赛博朋克类_高质量提示词模板.txt"),
    "sci_fi": ("未来科幻电影类", "现实类/未来科幻电影类_高质量提示词模板.txt"),
    "cinematic_realistic": ("真人电影级", "现实类/真人电影级_高质量提示词模板.txt"),
    "chinese_ancient": ("中国古风", "现实类/中国古风_高质量提示词模板.txt"),
    "urban_drama_3d_anime": ("3D都市剧情类动漫风", "3D动漫类/3D都市剧情类动漫风_style_master.txt"),
    "chinese_historical_3d_anime": ("中国古风_3D动漫版", "3D动漫类/中国古风_3D动漫版_style_master.txt"),
    "xianxia_3d_anime": ("古风仙侠类_3D动漫版", "3D动漫类/古风仙侠类_3D动漫版_style_master.txt"),
    "future_scifi_movie_3d_anime": ("未来科幻电影类_3D动漫版", "3D动漫类/未来科幻电影类_3D动漫版_style_master.txt"),
    "cinematic_live_action_3d_anime": ("真人电影级_3D动漫版", "3D动漫类/真人电影级_3D动漫版_style_master.txt"),
    "cyberpunk_3d_anime": ("赛博朋克类_3D动漫版", "3D动漫类/赛博朋克类_3D动漫版_style_master.txt"),
}

_LABEL_PATTERN = re.compile(
    r"^【(?P<label>[^】\n]+)】[：:]?(?P<body>.*?)(?=^【[^】\n]+】[：:]?|^=+\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_SECTION_PATTERN = re.compile(
    r"^=+\s*\n(?P<title>.*?)\n=+\s*\n(?P<body>.*?)(?=^=+\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_NEGATIVE_PATTERN = re.compile(
    r"Negative Prompt[：:]\s*(?P<body>.*?)(?=^【(?!通用负面提示词】)[^】\n]+】[：:]?|^=+\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_LABELED_NEGATIVE_PATTERN = re.compile(
    r"^【[^】\n]*负面提示词】[：:]?\s*(?P<body>.*?)(?=^【[^】\n]+】[：:]?|^=+\s*$|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True)
class StyleMasterProfile:
    style_id: str
    style_name: str
    visual_keywords: list[str]
    color_light_rules: str
    material_rules: str
    composition_rules: str
    style_taboos: list[str]
    negative_prompt_universal: str
    negative_prompt_style_specific: str
    character_prompt_template: str
    character_expression_template: str
    character_turnaround_template: str
    scene_prompt_template: str
    prop_prompt_template: str
    character_example: str
    scene_example: str
    prop_example: str


@lru_cache(maxsize=64)
def load_style_master(style_id: str) -> StyleMasterProfile:
    normalized_style_id = _normalize_style_id(style_id)
    style_name, filename = STYLE_MASTER_DOCS[normalized_style_id]
    text = _read_style_doc(filename)
    labels = _extract_labeled_blocks(text)
    sections = _extract_sections(text)
    negative_labels = _extract_negative_labels(text, labels)

    return StyleMasterProfile(
        style_id=normalized_style_id,
        style_name=_extract_style_name(text) or style_name,
        visual_keywords=_split_terms(_require_label_any(labels, ("视觉关键词", "画质关键词", "画面核心"))),
        color_light_rules=_require_label_any(labels, ("色彩与光影规则", "色彩系统", "光影系统")),
        material_rules=_require_label_any(labels, ("材质与细节规则", "材质系统")),
        composition_rules=_require_label_any(labels, ("镜头与构图规则", "镜头与构图")),
        style_taboos=_split_terms(_require_label_any(labels, ("本风格禁忌", "必须避免", "角色图负面提示词"))),
        negative_prompt_universal=_require_label(negative_labels, "通用负面提示词"),
        negative_prompt_style_specific=_require_label(negative_labels, "本风格专属负面词"),
        character_prompt_template=_require_block_any(sections, labels, ("角色资产图总模板", "三、", "角色生图模板")),
        character_expression_template=_optional_label_any(labels, ("角色半身情绪图模板",))
        or _require_block_any(sections, labels, ("角色资产图总模板", "三、", "角色生图模板")),
        character_turnaround_template=_require_block_any(sections, labels, ("四、", "角色三视图模板")),
        scene_prompt_template=_require_block_any(sections, labels, ("场景资产图总模板", "六、", "场景生图模板")),
        prop_prompt_template=_require_block_any(sections, labels, ("道具资产图总模板", "八、", "道具生图模板")),
        character_example=_require_label_any(labels, ("角色示例", "女角色示例 Prompt", "男角色示例 Prompt")),
        scene_example=_require_label_any(labels, ("场景示例", "场景示例 Prompt")),
        prop_example=_require_label_any(labels, ("道具示例", "道具示例 Prompt")),
    )


@lru_cache(maxsize=256)
def get_negative_prompt(style_id: str, asset_type: str) -> str:
    """Return universal, style-specific, and asset-specific negative prompts."""
    profile = load_style_master(style_id)
    asset_negative = _asset_negative_prompt(profile, asset_type)
    return _join_prompt_parts(
        [
            profile.negative_prompt_universal,
            profile.negative_prompt_style_specific,
            asset_negative,
        ]
    )


def _normalize_style_id(style_id: str) -> str:
    return _alias_normalize_style_id(style_id)


@lru_cache(maxsize=16)
def _read_style_doc(filename: str) -> str:
    path = _resolve_docs_root() / filename
    if not path.exists():
        raise FileNotFoundError(f"Style master template file does not exist: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030")


@lru_cache(maxsize=1)
def _resolve_docs_root() -> Path:
    module_path = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    candidates = [*module_path.parents, cwd, *cwd.parents]
    required_files = {filename for _, filename in STYLE_MASTER_DOCS.values()}

    for candidate in candidates:
        docs_root = candidate / STYLE_DOC_ROOT_RELATIVE
        if docs_root.is_dir() and all((docs_root / filename).is_file() for filename in required_files):
            return docs_root

    return module_path.parents[4] / STYLE_DOC_ROOT_RELATIVE


def _extract_style_name(text: str) -> str:
    match = re.search(r"^风格名称[：:](?P<name>.+?)\s*$", text, re.MULTILINE)
    return _clean_text(match.group("name")) if match else ""


def _extract_labeled_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    for match in _LABEL_PATTERN.finditer(text):
        label = _clean_text(match.group("label")).strip("：:")
        body = _clean_text(match.group("body"))
        if label and body:
            blocks[label] = body
    return blocks


def _extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for match in _SECTION_PATTERN.finditer(text):
        title = _clean_text(match.group("title"))
        body = _clean_block(match.group("body"))
        if title and body:
            sections[title] = f"{title}\n{body}".strip()
    return sections


def _extract_section_labels(text: str, title_prefix: str) -> dict[str, str]:
    for match in _SECTION_PATTERN.finditer(text):
        title = _clean_text(match.group("title"))
        if title.startswith(title_prefix):
            return _extract_labeled_blocks(match.group("body"))
    raise ValueError(f"Style master missing section: {title_prefix}")


def _extract_negative_labels(text: str, labels: dict[str, str]) -> dict[str, str]:
    try:
        return _extract_section_labels(text, "十、")
    except ValueError:
        sections = _extract_sections(text)
        universal = _optional_block_any(sections, labels, ("模块 11｜统一负面提示词",))
        style_specific = labels.get("角色图负面提示词", "")
        if universal:
            return {
                "通用负面提示词": universal,
                "本风格专属负面词": style_specific or universal,
            }
        raise


def _require_label(labels: dict[str, str], label: str) -> str:
    value = labels.get(label, "")
    if not value:
        raise ValueError(f"Style master missing labeled block: {label}")
    return value


def _optional_label_any(labels: dict[str, str], candidates: tuple[str, ...]) -> str:
    for label in candidates:
        value = labels.get(label, "")
        if value:
            return value
    return ""


def _require_label_any(labels: dict[str, str], candidates: tuple[str, ...]) -> str:
    value = _optional_label_any(labels, candidates)
    if value:
        return value
    raise ValueError(f"Style master missing labeled block: {' / '.join(candidates)}")


def _require_section(sections: dict[str, str], title_prefix: str) -> str:
    for title, body in sections.items():
        if title.startswith(title_prefix):
            return body
    raise ValueError(f"Style master missing section: {title_prefix}")


def _require_section_any(sections: dict[str, str], candidates: tuple[str, ...]) -> str:
    value = _optional_block_any(sections, {}, candidates)
    if value:
        return value
    raise ValueError(f"Style master missing section: {' / '.join(candidates)}")


def _optional_block_any(sections: dict[str, str], labels: dict[str, str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        for title, body in sections.items():
            if title.startswith(candidate) or candidate in title:
                return body
        for label, body in labels.items():
            if label.startswith(candidate) or candidate in label:
                return body
    return ""


def _require_block_any(sections: dict[str, str], labels: dict[str, str], candidates: tuple[str, ...]) -> str:
    value = _optional_block_any(sections, labels, candidates)
    if value:
        return value
    raise ValueError(f"Style master missing section: {' / '.join(candidates)}")


def _split_terms(text: str) -> list[str]:
    return [
        term
        for term in (_clean_text(item).strip("，,、；;。") for item in re.split(r"[，,、；;。]", text))
        if term
    ]


def _asset_negative_prompt(profile: StyleMasterProfile, asset_type: str) -> str:
    template = _asset_template(profile, asset_type)
    match = _NEGATIVE_PATTERN.search(template)
    if not match:
        match = _LABELED_NEGATIVE_PATTERN.search(template)
    if not match:
        return ""

    negative = _clean_text(match.group("body")).replace("【通用负面提示词】", "")
    negative = _clean_text(negative)
    universal = _clean_text(profile.negative_prompt_universal).rstrip("，,。")
    if negative.startswith(universal):
        negative = negative[len(universal) :]
    return _clean_text(negative).strip("，,。")


def _asset_template(profile: StyleMasterProfile, asset_type: str) -> str:
    normalized = asset_type.strip().lower().replace("-", "_")
    if normalized in {
        "character",
        "character_front",
        "character_full",
        "character_bible_sheet",
        "bible_sheet",
        "front",
        "character_expression",
    }:
        return profile.character_prompt_template
    if normalized in {"turnaround", "character_turnaround", "character_reference"}:
        return profile.character_turnaround_template
    if normalized in {"scene", "scene_empty", "empty_scene", "scene_with_atmosphere"}:
        return profile.scene_prompt_template
    if normalized in {"prop", "prop_product", "product", "prop_usage"}:
        return profile.prop_prompt_template
    return ""


def _join_prompt_parts(parts: list[str]) -> str:
    joined_terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for term in _split_terms(part):
            if term not in seen:
                joined_terms.append(term)
                seen.add(term)
    return "，".join(joined_terms)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_block(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)
