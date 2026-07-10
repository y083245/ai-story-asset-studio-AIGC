from __future__ import annotations

import re

import pytest

from app.config import settings
from app.modules.provider_adapter.base import TextGenerationProvider, TextGenerationRequest, TextGenerationResponse
from app.modules.template_style.style_master import load_style_master
from app.modules.workflow.prompt_synthesizer import PromptSynthesizer


class _CapturingPromptProvider(TextGenerationProvider):
    def __init__(self, text: str = "") -> None:
        self.text = text or _good_prompt("合成结果")
        self.requests: list[TextGenerationRequest] = []

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        self.requests.append(request)
        return TextGenerationResponse(text=self.text, model=request.model or "fake")

    async def generate_json(self, request: TextGenerationRequest) -> TextGenerationResponse:
        raise AssertionError("PromptSynthesizer must call generate(), not generate_json()")


class _FailingPromptProvider(TextGenerationProvider):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:  # noqa: ARG002
        raise RuntimeError("simulated provider failure")

    async def generate_json(self, request: TextGenerationRequest) -> TextGenerationResponse:  # noqa: ARG002
        raise AssertionError("PromptSynthesizer must call generate(), not generate_json()")


@pytest.mark.asyncio
async def test_synthesize_character_front_builds_style_master_request_without_json_mode():
    provider = _CapturingPromptProvider(_good_prompt("苏晚晴"))
    style = load_style_master("cinematic_realistic")

    prompt = await PromptSynthesizer(provider).synthesize_character_front(
        {
            "name": "苏晚晴",
            "age": "28岁",
            "gender": "女性",
            "height": "168cm",
            "body_type": "高挑匀称",
            "facial_features": "鹅蛋脸，柳叶眉，丹凤眼",
            "hair_style": "长直发",
            "hair_color": "深棕色",
            "eyes": "自然棕色",
            "skin_tone": "白皙",
            "identity": "都市商战女主",
            "personality": "冷静克制",
            "default_outfit": "米白色羊毛大衣",
            "outfit_details": "浅蓝色棉质衬衫与深灰A字裙",
            "shoes": "黑色细跟短靴",
            "accessories": "银色小耳钉",
        },
        style,
        story_context="旧怀表牵出商战阴谋。",
    )

    request = provider.requests[0]
    assert prompt.startswith("苏晚晴")
    assert request.temperature == settings.prompt_synthesizer_temperature == 0.55
    assert request.max_tokens == settings.prompt_synthesizer_max_tokens == 1500
    assert request.timeout_seconds == settings.prompt_synthesizer_timeout_seconds == 60
    assert not hasattr(request, "response_format")
    assert "不要输出 JSON" in request.system_prompt
    assert _english_parenthetical_count(request.system_prompt) >= 3
    assert "避免关键词堆砌" in request.system_prompt
    assert "视觉关键词：" in request.system_prompt
    assert style.character_prompt_template in request.system_prompt
    assert style.character_example in request.system_prompt
    assert "故事上下文：旧怀表牵出商战阴谋。" in request.prompt
    assert "名字：苏晚晴" in request.prompt
    assert request.metadata["module_id"] == "prompt_synthesizer"
    assert request.metadata["stage"] == "synth"
    assert request.metadata["asset_type"] == "character"
    assert request.metadata["style_id"] == "cinematic_realistic"


@pytest.mark.asyncio
async def test_synthesize_character_turnaround_uses_turnaround_template():
    provider = _CapturingPromptProvider(_good_prompt("三视图"))
    style = load_style_master("xianxia")

    prompt = await PromptSynthesizer(provider).synthesize_character_turnaround({"name": "云澈"}, style)

    request = provider.requests[0]
    assert "三视图" in prompt
    assert style.character_turnaround_template in request.system_prompt
    assert "请按示范格式合成一段完整的角色三视图资产图 prompt" in request.prompt


@pytest.mark.asyncio
async def test_synthesize_scene_empty_uses_scene_template_and_data():
    provider = _CapturingPromptProvider(_good_prompt("场景"))
    style = load_style_master("cyberpunk")

    prompt = await PromptSynthesizer(provider).synthesize_scene_empty(
        {
            "name": "霓虹雨巷",
            "scene_type": "室外街巷",
            "time_of_day": "深夜",
            "weather": "雨后",
            "lighting": "粉蓝霓虹反射",
            "mood": "潮湿压抑",
            "fixed_anchors": ["湿润柏油路", "霓虹灯牌"],
        },
        style,
    )

    request = provider.requests[0]
    assert "场景" in prompt
    assert style.scene_prompt_template in request.system_prompt
    assert "场景名称：霓虹雨巷" in request.prompt
    assert "固定锚点：湿润柏油路、霓虹灯牌" in request.prompt
    assert request.metadata["stage"] == "synth"
    assert request.metadata["asset_type"] == "scene"


@pytest.mark.asyncio
async def test_synthesize_prop_product_uses_prop_template_and_data():
    provider = _CapturingPromptProvider(_good_prompt("道具"))
    style = load_style_master("sci_fi")

    prompt = await PromptSynthesizer(provider).synthesize_prop_product(
        {
            "name": "量子密钥",
            "aliases": ["银色芯片", "密钥"],
            "plot_function": "开启轨道电梯权限",
            "material": "钛合金与透明晶体",
            "color": "银白色",
            "visual_features": "六边形薄片，边缘有蓝色光带",
        },
        style,
    )

    request = provider.requests[0]
    assert "道具" in prompt
    assert style.prop_prompt_template in request.system_prompt
    assert "道具名称：量子密钥" in request.prompt
    assert "别名：银色芯片、密钥" in request.prompt


@pytest.mark.asyncio
async def test_synthesizer_falls_back_to_local_composer_for_invalid_model_output():
    provider = _CapturingPromptProvider('{"prompt": "too short"}')
    style = load_style_master("chinese_ancient")

    prompt = await PromptSynthesizer(provider).synthesize_character_front({"name": "沈清辞"}, style)

    assert len(prompt) > 200
    assert "沈清辞" in prompt
    assert "中国古风" in prompt
    assert not prompt.strip().startswith("{")


@pytest.mark.asyncio
async def test_synthesizer_disabled_bilingual_flag_omits_keyword_instruction(monkeypatch):
    monkeypatch.setattr(settings, "bilingual_keywords_enabled", False)
    provider = _CapturingPromptProvider(_good_prompt("苏晚晴"))
    style = load_style_master("cinematic_realistic")

    await PromptSynthesizer(provider).synthesize_character_front({"name": "苏晚晴"}, style)

    request = provider.requests[0]
    assert "柔和轮廓光 (soft rim light)" not in request.system_prompt
    assert "85mm 浅景深 (shallow depth of field)" not in request.system_prompt
    assert "真实布料纤维 (photorealistic fabric texture)" not in request.system_prompt
    assert "双语视觉术语" not in request.system_prompt
    assert "避免关键词堆砌" not in request.system_prompt


@pytest.mark.asyncio
async def test_synthesizer_falls_back_for_markdown_or_sectioned_output():
    provider = _CapturingPromptProvider(
        """
```markdown
### Prompt
霓虹雨巷，横向16:9电影级纯净场景设定图，环境类型为室外街巷，具体时间深夜，
天气与光线雨后霓虹反射，空间氛围潮湿压抑，前景积水路面，中景自动售卖机，
远景高楼投影屏，核心材质湿润柏油路与金属灯牌，画面完整清晰，风格统一。
镜头低机位透视，雨滴反光清楚，霓虹灯牌边缘锐利，街巷纵深明确，材质层次稳定，
没有人物和人影，主体空间干净，适合作为资产库可复用的纯场景图。

Negative Prompt:
文字，水印
```
""".strip()
    )
    style = load_style_master("cyberpunk")

    prompt = await PromptSynthesizer(provider).synthesize_scene_empty({"name": "霓虹雨巷"}, style)

    assert len(prompt) > 200
    assert "霓虹雨巷" in prompt
    assert "```" not in prompt
    assert "Negative Prompt" not in prompt


@pytest.mark.asyncio
async def test_synthesizer_falls_back_for_unfenced_prompt_negative_sections():
    provider = _CapturingPromptProvider(
        """
Prompt
霓虹雨巷，横向16:9电影级纯净场景设定图，环境类型为室外街巷，具体时间深夜，
天气与光线雨后霓虹反射，空间氛围潮湿压抑，前景积水路面，中景自动售卖机，
远景高楼投影屏，核心材质湿润柏油路与金属灯牌，画面完整清晰，风格统一。
镜头低机位透视，雨滴反光清楚，霓虹灯牌边缘锐利，街巷纵深明确，材质层次稳定，
没有人物和人影，主体空间干净，适合作为资产库可复用的纯场景图。
Negative Prompt
文字，水印
""".strip()
    )
    style = load_style_master("cyberpunk")

    prompt = await PromptSynthesizer(provider).synthesize_scene_empty({"name": "霓虹雨巷"}, style)

    assert len(prompt) > 200
    assert "霓虹雨巷" in prompt
    assert "Prompt" not in prompt
    assert "Negative Prompt" not in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize("colon", [":", "："])
async def test_synthesizer_falls_back_for_colon_sections_without_spaces(colon: str):
    provider = _CapturingPromptProvider(
        f"""
Prompt{colon}霓虹雨巷，横向16:9电影级纯净场景设定图，环境类型为室外街巷，具体时间深夜，
天气与光线雨后霓虹反射，空间氛围潮湿压抑，前景积水路面，中景自动售卖机，
远景高楼投影屏，核心材质湿润柏油路与金属灯牌，画面完整清晰，风格统一。
镜头低机位透视，雨滴反光清楚，霓虹灯牌边缘锐利，街巷纵深明确，材质层次稳定，
没有人物和人影，主体空间干净，适合作为资产库可复用的纯场景图。
Negative Prompt{colon}文字，水印
""".strip()
    )
    style = load_style_master("cyberpunk")

    prompt = await PromptSynthesizer(provider).synthesize_scene_empty({"name": "霓虹雨巷"}, style)

    assert len(prompt) > 200
    assert "霓虹雨巷" in prompt
    assert f"Prompt{colon}" not in prompt
    assert f"Negative Prompt{colon}" not in prompt


@pytest.mark.asyncio
async def test_synthesizer_falls_back_to_local_composer_when_provider_fails():
    style = load_style_master("urban_drama")

    prompt = await PromptSynthesizer(_FailingPromptProvider()).synthesize_prop_product({"name": "旧怀表"}, style)

    assert len(prompt) > 200
    assert "旧怀表" in prompt
    assert "真人电影级" in prompt


@pytest.mark.asyncio
async def test_synthesizer_uses_configured_hard_timeout(monkeypatch):
    provider = _CapturingPromptProvider(_good_prompt("苏晚晴"))
    style = load_style_master("cinematic_realistic")
    captured: dict[str, float | None] = {}

    async def passthrough(awaitable, timeout=None):
        captured["timeout"] = timeout
        return await awaitable

    monkeypatch.setattr("app.modules.workflow.prompt_synthesizer.asyncio.wait_for", passthrough)

    await PromptSynthesizer(provider).synthesize_character_front({"name": "苏晚晴"}, style)

    assert captured["timeout"] == settings.prompt_synthesizer_timeout_seconds == 60


def _good_prompt(label: str) -> str:
    return (
        f"{label}，完整自然语言资产图 prompt，包含清晰主体、镜头构图、真实材质、光影层次、"
        "服装纹理、空间关系、风格关键词和一致性要求，画面干净，主体完整，细节可信，"
        "适合直接送入 Diffusion 模型生成高质量视觉资产图。"
    )


def _english_parenthetical_count(text: str) -> int:
    return len(re.findall(r"\([A-Za-z][A-Za-z0-9 ,./-]*[A-Za-z]\)", text))
