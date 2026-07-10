from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.workflow import publication
from app.modules.workflow.publication import (
    _character_image_plan,
    _generate_reference_assets,
    _normalize_state_timeline,
    _publication_style_id,
)


class _FakeSession:
    async def flush(self) -> None:
        return None


def test_character_image_plan_builds_turnaround_from_fallback_description():
    plan = _character_image_plan(
        name="苏晚晴",
        role="主角",
        gender="女",
        age="24岁",
        description="旧钟楼旁的调查者，手持金色旧怀表",
        outfit="白色连衣裙和深色长外套",
        front_prompt=None,
        turnaround_prompt=None,
        style_id="cinematic_realistic",
    )

    assert [item["category"] for item in plan] == ["正面全身", "三视图"]
    assert "苏晚晴" in plan[1]["description"]
    assert "金色旧怀表" in plan[1]["description"]


def test_publication_normalizes_string_prop_state_timeline_items():
    timeline = _normalize_state_timeline(["初始状态：常温，无发光", {"state": "激活状态", "description": "蓝白色光闪烁"}])

    assert timeline == [
        {"step_index": 1, "state": "初始状态：常温，无发光", "description": "初始状态：常温，无发光"},
        {"step_index": 2, "state": "激活状态", "description": "蓝白色光闪烁"},
    ]


def test_publication_normalizes_docs_style_ids_to_runtime_style_packs():
    assert _publication_style_id({"style_id": "live_action_cinematic"}, {}) == "cinematic_realistic"
    assert _publication_style_id({"style_id": "traditional_chinese_period"}, {}) == "chinese_ancient"
    assert _publication_style_id({"style_id": "xianxia_high_cg"}, {}) == "xianxia"
    assert _publication_style_id({"style_id": "future_sci_fi_cinema"}, {}) == "sci_fi"
    assert _publication_style_id({"style_id": "cyberpunk_neon_noir"}, {}) == "cyberpunk"


@pytest.mark.asyncio
async def test_generate_reference_assets_uses_reference_chain(monkeypatch):
    project_id = uuid.uuid4()
    character = SimpleNamespace(character_id="CH_001", reference_assets=[], canonical_asset_id=None)
    scene = SimpleNamespace(scene_id="SC_001", reference_assets=[], canonical_asset_id=None)
    prop = SimpleNamespace(
        prop_id="PR_001",
        owner_character_id="CH_001",
        reference_assets=[],
        canonical_asset_id=None,
    )
    calls: list[Any] = []

    class FakeImageAssetService:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def generate_asset(self, request: Any, _session: Any) -> Any:
            calls.append(request)
            return SimpleNamespace(storage_path=f"{request.asset_type}:{request.related_id}")

    monkeypatch.setattr(publication, "ImageAssetService", FakeImageAssetService)
    monkeypatch.setattr(publication.ProviderRegistry, "get_image_generator", lambda self: object())
    monkeypatch.setattr(publication.StorageService, "create", staticmethod(lambda: object()))
    monkeypatch.setattr(publication.settings, "reference_chain_enabled", True)

    summary = await _generate_reference_assets(
        session=_FakeSession(),  # type: ignore[arg-type]
        project_id=project_id,
        characters=[character],  # type: ignore[list-item]
        scenes=[scene],  # type: ignore[list-item]
        props=[prop],  # type: ignore[list-item]
    )

    assert summary == {"assets": 8, "asset_errors": []}
    assert [call.asset_type for call in calls] == [
        "character_bible_sheet",
        "character_front",
        "character_turnaround",
        "character_expression",
        "scene_empty",
        "scene_with_atmosphere",
        "prop_product",
        "prop_usage",
    ]
    assert calls[1].reference_asset_ids == ["character_bible_sheet:CH_001"]
    assert calls[2].reference_asset_ids == ["character_bible_sheet:CH_001"]
    assert calls[3].reference_asset_ids == ["character_bible_sheet:CH_001"]
    assert calls[5].reference_asset_ids == ["scene_empty:SC_001"]
    assert calls[7].reference_asset_ids == ["prop_product:PR_001", "character_bible_sheet:CH_001"]
    assert character.canonical_asset_id == "character_bible_sheet:CH_001"
    assert scene.canonical_asset_id == "scene_empty:SC_001"
    assert prop.canonical_asset_id == "prop_product:PR_001"


@pytest.mark.asyncio
async def test_generate_reference_assets_can_fall_back_to_legacy_sequence(monkeypatch):
    project_id = uuid.uuid4()
    character = SimpleNamespace(character_id="CH_001", reference_assets=[], canonical_asset_id=None)
    scene = SimpleNamespace(scene_id="SC_001", reference_assets=[], canonical_asset_id=None)
    prop = SimpleNamespace(prop_id="PR_001", reference_assets=[], canonical_asset_id=None)
    calls: list[Any] = []

    class FakeImageAssetService:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def generate_asset(self, request: Any, _session: Any) -> Any:
            calls.append(request)
            return SimpleNamespace(storage_path=f"{request.asset_type}:{request.related_id}")

    monkeypatch.setattr(publication, "ImageAssetService", FakeImageAssetService)
    monkeypatch.setattr(publication.ProviderRegistry, "get_image_generator", lambda self: object())
    monkeypatch.setattr(publication.StorageService, "create", staticmethod(lambda: object()))
    monkeypatch.setattr(publication.settings, "reference_chain_enabled", False)

    summary = await _generate_reference_assets(
        session=_FakeSession(),  # type: ignore[arg-type]
        project_id=project_id,
        characters=[character],  # type: ignore[list-item]
        scenes=[scene],  # type: ignore[list-item]
        props=[prop],  # type: ignore[list-item]
    )

    assert summary == {"assets": 4, "asset_errors": []}
    assert [call.asset_type for call in calls] == [
        "character_front",
        "character_turnaround",
        "scene_empty",
        "prop_product",
    ]
    assert calls[1].reference_asset_ids == ["character_front:CH_001"]
    assert character.canonical_asset_id is None
