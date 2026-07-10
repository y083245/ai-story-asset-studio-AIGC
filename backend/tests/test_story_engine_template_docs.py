from __future__ import annotations

import pytest

from app.modules.template_style.story_engine_docs import (
    STYLE_DOC_ROOT_RELATIVE,
    STYLE_DOCS,
    StoryEngineTemplateRegistry,
    _resolve_repo_root,
)
from app.modules.template_style.style_alias import SUPPORTED_STYLE_IDS, normalize_style_id
from app.modules.template_style.style_pack import REQUIRED_STYLE_PACK_MODULES, StylePackRegistry


def test_repo_root_resolution_handles_container_app_layout(tmp_path):
    repo_root = tmp_path / "app"
    docs_root = repo_root / "docs"
    docs_root.mkdir(parents=True)
    for filename in (
        "现实类/中国古风_高质量提示词模板.txt",
        "现实类/古风仙侠类_高质量提示词模板.txt",
        "现实类/未来科幻电影类_高质量提示词模板.txt",
        "现实类/真人电影级_高质量提示词模板.txt",
        "现实类/赛博朋克类_高质量提示词模板.txt",
        "现实类/都市剧情类真人写实风_高质量提示词模板.txt",
        "3D动漫类/3D都市剧情类动漫风_高质量提示词模板.txt",
        "3D动漫类/中国古风_3D动漫版_高质量提示词模板.txt",
        "3D动漫类/古风仙侠类_3D动漫版_高质量提示词模板.txt",
        "3D动漫类/未来科幻电影类_3D动漫版_高质量提示词模板.txt",
        "3D动漫类/真人电影级_3D动漫版_高质量提示词模板.txt",
        "3D动漫类/赛博朋克类_3D动漫版_高质量提示词模板.txt",
    ):
        path = docs_root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("template", encoding="utf-8")
    module_file = repo_root / "app" / "modules" / "template_style" / "story_engine_docs.py"
    module_file.parent.mkdir(parents=True)
    module_file.touch()

    assert _resolve_repo_root(None, module_file) == repo_root


def test_contract_loads_top_level_doc_for_legacy_style_id():
    registry = StoryEngineTemplateRegistry()

    contract = registry.get_contract("cyberpunk", "character_extractor")

    assert contract.style_id == "cyberpunk"
    assert contract.style_folder == "赛博朋克类"
    assert "风格 ID：cyberpunk_neon_noir" in contract.content
    assert "九、图片质检与失败重试" in contract.content
    assert contract.source_files == ("docs/现实类/赛博朋克类_高质量提示词模板.txt",)


def test_contract_accepts_new_style_id_and_chinese_alias():
    registry = StoryEngineTemplateRegistry()

    new_id_contract = registry.get_contract("future_sci_fi_cinema", "scene_extractor")
    alias_contract = registry.get_contract("中国古风", "prop_extractor")

    assert new_id_contract.style_id == "sci_fi"
    assert new_id_contract.source_files == ("docs/现实类/未来科幻电影类_高质量提示词模板.txt",)
    assert "风格名称：未来科幻电影类" in new_id_contract.content
    assert alias_contract.style_id == "chinese_ancient"
    assert alias_contract.source_files == ("docs/现实类/中国古风_高质量提示词模板.txt",)
    assert "风格名称：中国古风" in alias_contract.content


def test_contract_loads_urban_drama_realistic_doc_not_generic_cinematic_doc():
    registry = StoryEngineTemplateRegistry()

    contract = registry.get_contract("urban_drama", "genre_detector")

    assert contract.style_id == "urban_drama"
    assert contract.style_folder == "都市剧情类真人写实风"
    assert contract.source_files == ("docs/现实类/都市剧情类真人写实风_高质量提示词模板.txt",)
    assert "风格 ID：urban_drama_live_action_realistic" in contract.content
    assert "输出目标是真人质感，不是 3D 动漫" in contract.content


def test_style_catalog_exposes_all_supported_style_rules_for_genre_detection():
    registry = StoryEngineTemplateRegistry()

    catalog = registry.get_style_catalog()

    assert "## 现实类｜style_family=realistic" in catalog
    assert "## 3D动漫类｜style_family=3d_anime" in catalog
    assert "style_id=urban_drama｜都市剧情类真人写实风" in catalog
    assert "style_id=chinese_ancient｜中国古风" in catalog
    assert "style_id=xianxia｜古风仙侠类" in catalog
    assert "style_id=sci_fi｜未来科幻电影类" in catalog
    assert "style_id=cinematic_realistic｜真人电影级" in catalog
    assert "style_id=cyberpunk｜赛博朋克类" in catalog
    assert "style_id=live_action_cinematic｜真人电影级" not in catalog
    assert "style_id=urban_drama_live_action_realistic｜" not in catalog
    assert "来源：docs/现实类/真人电影级_高质量提示词模板.txt" in catalog
    assert "图片质检与失败重试" in catalog


def test_all_runtime_style_docs_have_unique_source_files():
    assert len(STYLE_DOCS) == 12
    assert set(STYLE_DOCS) == set(SUPPORTED_STYLE_IDS)
    source_files = [style_doc.relative_file for style_doc in STYLE_DOCS.values()]
    assert len(source_files) == len(set(source_files))


def test_all_runtime_style_docs_exist_under_docs_root():
    repo_root = _resolve_repo_root(None)
    docs_root = repo_root / STYLE_DOC_ROOT_RELATIVE

    missing = [style_doc.relative_file for style_doc in STYLE_DOCS.values() if not (docs_root / style_doc.relative_file).is_file()]

    assert missing == []


@pytest.mark.parametrize(
    ("style_id", "style_name", "source_file"),
    [
        ("urban_drama_3d_anime", "3D都市剧情类动漫风", "docs/3D动漫类/3D都市剧情类动漫风_高质量提示词模板.txt"),
        ("chinese_historical_3d_anime", "中国古风_3D动漫版", "docs/3D动漫类/中国古风_3D动漫版_高质量提示词模板.txt"),
        ("xianxia_3d_anime", "古风仙侠类_3D动漫版", "docs/3D动漫类/古风仙侠类_3D动漫版_高质量提示词模板.txt"),
        ("future_scifi_movie_3d_anime", "未来科幻电影类_3D动漫版", "docs/3D动漫类/未来科幻电影类_3D动漫版_高质量提示词模板.txt"),
        ("cinematic_live_action_3d_anime", "真人电影级_3D动漫版", "docs/3D动漫类/真人电影级_3D动漫版_高质量提示词模板.txt"),
        ("cyberpunk_3d_anime", "赛博朋克类_3D动漫版", "docs/3D动漫类/赛博朋克类_3D动漫版_高质量提示词模板.txt"),
    ],
)
def test_contract_loads_3d_anime_style_docs(style_id: str, style_name: str, source_file: str):
    registry = StoryEngineTemplateRegistry()

    contract = registry.get_contract(style_id, "character_extractor")

    assert contract.style_id == style_id
    assert contract.style_folder == style_name
    assert contract.source_files == (source_file,)
    assert f"风格 ID：{style_id}" in contract.content
    assert "模块 02｜角色提取模板｜extract_characters" in contract.content
    assert "模块 05｜场景提取模板｜extract_scenes" in contract.content
    assert "模块 07｜道具提取模板｜extract_props" in contract.content


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("3D动漫", "urban_drama_3d_anime"),
        ("3D都市剧情类动漫风", "urban_drama_3d_anime"),
        ("中国古风3D动漫", "chinese_historical_3d_anime"),
        ("古风仙侠3D动漫", "xianxia_3d_anime"),
        ("未来科幻3D动漫", "future_scifi_movie_3d_anime"),
        ("真人电影级3D动漫", "cinematic_live_action_3d_anime"),
        ("赛博朋克3D动漫", "cyberpunk_3d_anime"),
    ],
)
def test_normalize_style_id_accepts_3d_anime_aliases(alias: str, expected: str):
    assert normalize_style_id(alias) == expected


def test_normalize_style_id_accepts_docs_internal_urban_drama_realistic_id():
    assert normalize_style_id("urban_drama_live_action_realistic") == "urban_drama"
    assert normalize_style_id("都市剧情类真人写实风") == "urban_drama"


def test_style_catalog_exposes_3d_anime_rules_for_genre_detection():
    registry = StoryEngineTemplateRegistry()

    catalog = registry.get_style_catalog()

    assert "style_id=urban_drama_3d_anime｜3D都市剧情类动漫风" in catalog
    assert "style_id=chinese_historical_3d_anime｜中国古风_3D动漫版" in catalog
    assert "style_id=xianxia_3d_anime｜古风仙侠类_3D动漫版" in catalog
    assert "style_id=future_scifi_movie_3d_anime｜未来科幻电影类_3D动漫版" in catalog
    assert "style_id=cinematic_live_action_3d_anime｜真人电影级_3D动漫版" in catalog
    assert "style_id=cyberpunk_3d_anime｜赛博朋克类_3D动漫版" in catalog


@pytest.mark.parametrize(
    "style_id",
    [
        "urban_drama_3d_anime",
        "chinese_historical_3d_anime",
        "xianxia_3d_anime",
        "future_scifi_movie_3d_anime",
        "cinematic_live_action_3d_anime",
        "cyberpunk_3d_anime",
    ],
)
def test_style_pack_registry_loads_3d_anime_required_modules(style_id: str):
    registry = StylePackRegistry()
    registry.load_all()

    modules = registry.list_modules(style_id)

    assert modules == sorted(REQUIRED_STYLE_PACK_MODULES)
