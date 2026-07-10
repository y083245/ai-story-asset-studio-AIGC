from __future__ import annotations

import re

import pytest

from app.modules.provider_adapter.base import TextGenerationRequest, TextGenerationResponse
from app.modules.template_style.style_pack import StylePackTemplate
from app.modules.workflow import analysis_activities


class _StubTextProvider:
    pass


class _StubProviderRegistry:
    def get_text_generator(self) -> _StubTextProvider:
        return _StubTextProvider()


class _CapturingTextProvider:
    def __init__(self) -> None:
        self.requests: list[TextGenerationRequest] = []

    async def generate_json(self, request: TextGenerationRequest) -> TextGenerationResponse:
        self.requests.append(request)
        return TextGenerationResponse(text='{"ok": true}', json_data={"ok": True}, model=request.model)


def test_create_analysis_activities_uses_local_model_config_provider_in_auto_mode(monkeypatch):
    monkeypatch.setattr(analysis_activities.settings, "provider_mode", "auto")
    monkeypatch.setattr(analysis_activities.settings, "deepseek_api_key", "")
    monkeypatch.setattr(analysis_activities, "ProviderRegistry", lambda: _StubProviderRegistry(), raising=False)

    activities = analysis_activities.create_analysis_activities()

    assert activities["detect_genre"].__self__._provider is None


def test_provider_user_id_uses_provider_safe_charset():
    user_id = analysis_activities._provider_user_id("project:996735e4-b8f4-45fb-a679-9c504419fee3")

    assert user_id == "project-project-996735e4-b8f4-45fb-a679-9c504419fee3"
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id)


def test_analysis_normalizes_docs_style_ids_to_runtime_style_packs():
    assert analysis_activities._normalize_style_id("live_action_cinematic") == "cinematic_realistic"
    assert analysis_activities._normalize_style_id("traditional_chinese_period") == "chinese_ancient"
    assert analysis_activities._normalize_style_id("xianxia_high_cg") == "xianxia"
    assert analysis_activities._normalize_style_id("future_sci_fi_cinema") == "sci_fi"
    assert analysis_activities._normalize_style_id("cyberpunk_neon_noir") == "cyberpunk"


@pytest.mark.asyncio
async def test_analysis_template_uses_configured_provider_default_model(monkeypatch):
    monkeypatch.setattr(analysis_activities.settings, "deepseek_fast_model_name", "deepseek-fast-from-env")
    monkeypatch.setattr(analysis_activities.settings, "deepseek_model_name", "deepseek-default-from-env")
    provider = _CapturingTextProvider()
    activities = analysis_activities.DeepSeekAnalysisActivities(provider)
    template = StylePackTemplate(
        style_id="urban_drama",
        style_name="都市短剧类",
        module_id="character_extractor",
        source_master="test",
        system_prompt="system",
        user_prompt_template="{{ text }} {{ style_name }} {{ context_json }}",
    )

    result = await activities._run_template(
        "project-1",
        "character_extractor",
        "urban_drama",
        template,
        "story text",
    )

    assert result == {"ok": True}
    assert provider.requests[0].model == ""
