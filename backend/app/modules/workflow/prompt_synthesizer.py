"""Second-stage natural-language prompt synthesis."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from typing import Any

from app.config import settings
from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.template_style.style_master import StyleMasterProfile
from app.modules.workflow.prompt_composer import (
    compose_character_front,
    compose_character_turnaround,
    compose_prop_product,
    compose_scene_empty,
)

_JSON_MARKERS = ("{", "}", '"')
_WRAPPER_MARKERS = ("```", "###")
_SECTION_HEADING_PATTERN = re.compile(r"(?i)(^|\s)(negative\s+prompt|prompt)(\s*[：:]|\s|$)")


class PromptSynthesizer:
    """Use the text provider to synthesize complete image prompts."""

    def __init__(self, provider: TextGenerationProvider | None = None) -> None:
        self._provider = provider

    async def synthesize_character_front(
        self, character: dict[str, Any], style: StyleMasterProfile, story_context: str = ""
    ) -> str:
        return await self._synthesize(
            asset_type="character_front",
            style=style,
            template=style.character_prompt_template,
            example=style.character_example,
            prompt=_character_front_prompt(character, story_context),
            fallback=lambda: compose_character_front(character, style),
        )

    async def synthesize_character_turnaround(self, character: dict[str, Any], style: StyleMasterProfile) -> str:
        return await self._synthesize(
            asset_type="character_turnaround",
            style=style,
            template=style.character_turnaround_template,
            example=style.character_example,
            prompt=_character_turnaround_prompt(character),
            fallback=lambda: compose_character_turnaround(character, style),
        )

    async def synthesize_scene_empty(self, scene: dict[str, Any], style: StyleMasterProfile) -> str:
        return await self._synthesize(
            asset_type="scene_empty",
            style=style,
            template=style.scene_prompt_template,
            example=style.scene_example,
            prompt=_scene_prompt(scene),
            fallback=lambda: compose_scene_empty(scene, style),
        )

    async def synthesize_prop_product(self, prop: dict[str, Any], style: StyleMasterProfile) -> str:
        return await self._synthesize(
            asset_type="prop_product",
            style=style,
            template=style.prop_prompt_template,
            example=style.prop_example,
            prompt=_prop_prompt(prop),
            fallback=lambda: compose_prop_product(prop, style),
        )

    async def _synthesize(
        self,
        *,
        asset_type: str,
        style: StyleMasterProfile,
        template: str,
        example: str,
        prompt: str,
        fallback: Callable[[], str],
    ) -> str:
        request = TextGenerationRequest(
            system_prompt=_system_prompt(style, template, example),
            prompt=prompt,
            temperature=settings.prompt_synthesizer_temperature,
            max_tokens=settings.prompt_synthesizer_max_tokens,
            timeout_seconds=settings.prompt_synthesizer_timeout_seconds,
            metadata={
                "module_id": "prompt_synthesizer",
                "stage": "synth",
                "style_id": style.style_id,
                "asset_type": _asset_category(asset_type),
            },
        )
        try:
            response = await asyncio.wait_for(
                self._get_provider().generate(request),
                timeout=settings.prompt_synthesizer_timeout_seconds,
            )
            text = _clean_response(response.text)
            if _valid_prompt(text):
                return text
        except Exception:
            return fallback()
        return fallback()

    def _get_provider(self) -> TextGenerationProvider:
        if self._provider is not None:
            return self._provider
        return ProviderRegistry().get_text_generator()


def _system_prompt(style: StyleMasterProfile, template: str, example: str) -> str:
    bilingual_instruction = ""
    if settings.bilingual_keywords_enabled:
        bilingual_instruction = (
            "在自然语言中少量加入有效的双语视觉术语，使用中文描述加英文括注，优先覆盖镜头、光影、材质，"
            "例如：柔和轮廓光 (soft rim light)，85mm 浅景深 (shallow depth of field)，"
            "真实布料纤维 (photorealistic fabric texture)。只加入对画面生成有帮助的术语，避免关键词堆砌。\n"
        )
    return (
        f"你是{style.style_name}风格的资产图 prompt 合成专家。请仔细阅读下面的风格母版和资产数据，"
        "按母版的示范格式输出一段完整的中文自然语言 prompt（不要输出 JSON、不要输出 Markdown、"
        "不要输出多个候选、只输出一段可以直接送入 Diffusion 模型的 prompt）。\n\n"
        f"{bilingual_instruction}"
        "【风格母版关键段落】\n"
        f"视觉关键词：{'，'.join(style.visual_keywords)}\n"
        f"色彩与光影规则：{style.color_light_rules}\n"
        f"材质与细节规则：{style.material_rules}\n"
        f"镜头与构图规则：{style.composition_rules}\n"
        f"本风格禁忌：{'，'.join(style.style_taboos)}\n\n"
        "【示范格式】\n"
        f"{template}\n\n"
        "【示范输出】\n"
        f"{example}"
    )


def _character_front_prompt(character: dict[str, Any], story_context: str) -> str:
    lines = [
        "角色数据：",
        _line("名字", _value(character, "name")),
        _line("年龄", _first(_value(character, "age"), _value(character, "age_range"))),
        _line("性别", _value(character, "gender")),
        _line("身高", _value(character, "height")),
        _line("体型", _value(character, "body_type")),
        _line("脸型", _value(character, "face_shape")),
        _line("脸部特征", _first(_value(character, "facial_features"), _value(character, "face_features"))),
        _line("发型/发色", _join_pair(_value(character, "hair_style"), _value(character, "hair_color"))),
        _line("眼睛", _value(character, "eyes")),
        _line("肤色", _value(character, "skin_tone")),
        _line("身份", _first(_value(character, "identity"), _value(character, "role"))),
        _line("性格", _first(_value(character, "personality"), _value(character, "description"))),
        _line("默认服装", _first(_value(character, "default_outfit"), _value(character, "outfit"))),
        _line("服装细节", _value(character, "outfit_details")),
        _line("鞋子", _value(character, "shoes")),
        _line("配饰", _value(character, "accessories")),
        _line("故事上下文", story_context),
        "",
        "请按示范格式合成一段完整的角色正面全身资产图 prompt。",
    ]
    return "\n".join(line for line in lines if line)


def _character_turnaround_prompt(character: dict[str, Any]) -> str:
    lines = [
        "角色数据：",
        _line("名字", _value(character, "name")),
        _line("视觉设定", _character_summary(character)),
        "",
        "请按示范格式合成一段完整的角色三视图资产图 prompt。",
    ]
    return "\n".join(line for line in lines if line)


def _scene_prompt(scene: dict[str, Any]) -> str:
    lines = [
        "场景数据：",
        _line("场景名称", _first(_value(scene, "scene_name"), _value(scene, "name"))),
        _line("环境类型", _first(_value(scene, "environment_type"), _value(scene, "scene_type"))),
        _line("具体时间", _first(_value(scene, "time_of_day"), _value(scene, "time"))),
        _line("天气与光线", _join_list([_value(scene, "weather"), _value(scene, "lighting")])),
        _line("空间氛围", _first(_value(scene, "mood"), _value(scene, "description"))),
        _line("前景", _list_text(scene.get("foreground_elements"))),
        _line("中景", _list_text(scene.get("midground_elements"))),
        _line("远景", _list_text(scene.get("background_elements"))),
        _line("固定锚点", _list_text(scene.get("fixed_anchors") or scene.get("anchors"))),
        "",
        "请按示范格式合成一段完整的无人纯场景资产图 prompt。",
    ]
    return "\n".join(line for line in lines if line)


def _prop_prompt(prop: dict[str, Any]) -> str:
    lines = [
        "道具数据：",
        _line("道具名称", _first(_value(prop, "prop_name"), _value(prop, "name"))),
        _line("别名", _list_text(prop.get("aliases"))),
        _line("用途", _first(_value(prop, "prop_function"), _value(prop, "plot_function"), _value(prop, "function"))),
        _line("材质", _first(_value(prop, "prop_material"), _value(prop, "material"))),
        _line("颜色", _first(_value(prop, "prop_color"), _value(prop, "color"))),
        _line("造型/视觉特征", _first(_value(prop, "prop_shape"), _value(prop, "visual_features"), _value(prop, "description"))),
        _line("尺寸", _value(prop, "size")),
        _line("状态", _list_text(prop.get("state_timeline"))),
        "",
        "请按示范格式合成一段完整的单一道具资产图 prompt。",
    ]
    return "\n".join(line for line in lines if line)


def _valid_prompt(text: str) -> bool:
    length = len(text)
    if length < 80 or length > 1500:
        return False
    if any(marker in text for marker in _JSON_MARKERS):
        return False
    if any(marker in text for marker in _WRAPPER_MARKERS):
        return False
    if _SECTION_HEADING_PATTERN.search(text):
        return False
    return not re.search(r"(^|\s)[-*]\s+", text)


def _asset_category(asset_type: str) -> str:
    if asset_type.startswith("character_"):
        return "character"
    if asset_type.startswith("scene_"):
        return "scene"
    if asset_type.startswith("prop_"):
        return "prop"
    return asset_type


def _clean_response(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _line(label: str, value: str) -> str:
    return f"{label}：{value}" if value else ""


def _value(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _first(*values: str) -> str:
    return next((value for value in values if value), "")


def _join_pair(left: str, right: str) -> str:
    return " / ".join(value for value in (left, right) if value)


def _join_list(values: list[str]) -> str:
    return "，".join(value for value in values if value)


def _list_text(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("description") or item.get("state") or "").strip())
            else:
                parts.append(str(item or "").strip())
        return "、".join(part for part in parts if part)
    return str(value or "").strip()


def _character_summary(character: dict[str, Any]) -> str:
    keys = (
        "name",
        "age",
        "age_range",
        "gender",
        "height",
        "body_type",
        "face_shape",
        "facial_features",
        "hair_style",
        "hair_color",
        "eyes",
        "identity",
        "personality",
        "default_outfit",
        "outfit_details",
        "shoes",
        "accessories",
    )
    return "，".join(_value(character, key) for key in keys if _value(character, key))
