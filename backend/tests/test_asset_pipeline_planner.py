from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.workflow.asset_pipeline import AssetPipelinePlanner


def test_character_pipeline_builds_canonical_bible_sheet_before_derived_assets():
    planner = AssetPipelinePlanner()
    character = SimpleNamespace(character_id="char-001")

    plan = planner.plan_character_pipeline(character)

    assert plan.entity_id == "char-001"
    assert plan.entity_type == "character"
    assert [stage.stage_name for stage in plan.stages] == [
        "bible_sheet",
        "front",
        "turnaround",
        "expression",
    ]
    assert [stage.asset_type for stage in plan.stages] == [
        "character_bible_sheet",
        "character_front",
        "character_turnaround",
        "character_expression",
    ]
    assert plan.stages[0].reference_stages == []
    assert plan.stages[0].priority == 0
    for stage in plan.stages[1:]:
        assert stage.reference_stages == ["bible_sheet"]
        assert stage.priority == 1


def test_scene_pipeline_uses_empty_scene_as_atmosphere_reference():
    planner = AssetPipelinePlanner()
    scene = SimpleNamespace(scene_id="scene-001")

    plan = planner.plan_scene_pipeline(scene)

    assert plan.entity_id == "scene-001"
    assert plan.entity_type == "scene"
    assert [stage.stage_name for stage in plan.stages] == [
        "scene_empty",
        "scene_with_atmosphere",
    ]
    assert [stage.asset_type for stage in plan.stages] == [
        "scene_empty",
        "scene_with_atmosphere",
    ]
    assert plan.stages[0].reference_stages == []
    assert plan.stages[1].reference_stages == ["scene_empty"]


def test_prop_pipeline_keeps_owner_character_reference_out_of_planner():
    planner = AssetPipelinePlanner()
    prop = SimpleNamespace(prop_id="prop-001", owner_character_id="char-001")

    plan = planner.plan_prop_pipeline(prop)

    assert plan.entity_id == "prop-001"
    assert plan.entity_type == "prop"
    assert [stage.stage_name for stage in plan.stages] == [
        "prop_product",
        "prop_usage",
    ]
    assert [stage.asset_type for stage in plan.stages] == [
        "prop_product",
        "prop_usage",
    ]
    assert plan.stages[0].reference_stages == []
    assert plan.stages[1].reference_stages == ["prop_product"]


@pytest.mark.parametrize(
    ("method_name", "entity"),
    [
        ("plan_character_pipeline", SimpleNamespace(character_id="")),
        ("plan_scene_pipeline", SimpleNamespace(scene_id=None)),
        ("plan_prop_pipeline", SimpleNamespace()),
    ],
)
def test_pipeline_planner_rejects_empty_or_unknown_entity_ids(method_name, entity):
    planner = AssetPipelinePlanner()

    with pytest.raises(ValueError, match="entity id"):
        getattr(planner, method_name)(entity)
