"""Load Story Engine style template documents for extraction prompts.

The JSON style packs define the API contract. The documents under ``docs/``
are the user-authored master instructions. Extraction prompts include the
relevant document text verbatim so the LLM works from the selected style's
source template instead of a backend summary.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

STYLE_DOC_ROOT_RELATIVE = Path("docs")

REALISTIC_FAMILY = "realistic"
ANIME_3D_FAMILY = "3d_anime"


@dataclass(frozen=True)
class StyleDoc:
    style_name: str
    relative_file: str
    family: str


STYLE_DOCS: dict[str, StyleDoc] = {
    "urban_drama": StyleDoc("都市剧情类真人写实风", "现实类/都市剧情类真人写实风_高质量提示词模板.txt", REALISTIC_FAMILY),
    "chinese_ancient": StyleDoc("中国古风", "现实类/中国古风_高质量提示词模板.txt", REALISTIC_FAMILY),
    "xianxia": StyleDoc("古风仙侠类", "现实类/古风仙侠类_高质量提示词模板.txt", REALISTIC_FAMILY),
    "sci_fi": StyleDoc("未来科幻电影类", "现实类/未来科幻电影类_高质量提示词模板.txt", REALISTIC_FAMILY),
    "cinematic_realistic": StyleDoc("真人电影级", "现实类/真人电影级_高质量提示词模板.txt", REALISTIC_FAMILY),
    "cyberpunk": StyleDoc("赛博朋克类", "现实类/赛博朋克类_高质量提示词模板.txt", REALISTIC_FAMILY),
    "urban_drama_3d_anime": StyleDoc(
        "3D都市剧情类动漫风", "3D动漫类/3D都市剧情类动漫风_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
    "chinese_historical_3d_anime": StyleDoc(
        "中国古风_3D动漫版", "3D动漫类/中国古风_3D动漫版_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
    "xianxia_3d_anime": StyleDoc(
        "古风仙侠类_3D动漫版", "3D动漫类/古风仙侠类_3D动漫版_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
    "future_scifi_movie_3d_anime": StyleDoc(
        "未来科幻电影类_3D动漫版", "3D动漫类/未来科幻电影类_3D动漫版_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
    "cinematic_live_action_3d_anime": StyleDoc(
        "真人电影级_3D动漫版", "3D动漫类/真人电影级_3D动漫版_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
    "cyberpunk_3d_anime": StyleDoc(
        "赛博朋克类_3D动漫版", "3D动漫类/赛博朋克类_3D动漫版_高质量提示词模板.txt", ANIME_3D_FAMILY
    ),
}


@dataclass(frozen=True)
class StoryEngineTemplateContract:
    """Document text used to constrain one extraction module."""

    style_id: str
    module_id: str
    style_folder: str
    source_files: tuple[str, ...]
    content: str


class StoryEngineTemplateRegistry:
    """Read style-specific Story Engine templates from ``docs``."""

    def __init__(self, repo_root: str | Path | None = None) -> None:
        self._repo_root = _resolve_repo_root(repo_root)
        self._style_root = self._repo_root / STYLE_DOC_ROOT_RELATIVE

    @property
    def style_root(self) -> Path:
        return self._style_root

    def get_contract(self, style_id: str, module_id: str) -> StoryEngineTemplateContract:
        """Return the exact style template document text for a module."""
        normalized_style_id = _normalize_style_id(style_id)
        style_doc = STYLE_DOCS[normalized_style_id]
        path = self._style_root / style_doc.relative_file
        text = _read_text(path)
        source_file = path.relative_to(self._repo_root).as_posix()

        return StoryEngineTemplateContract(
            style_id=normalized_style_id,
            module_id=module_id,
            style_folder=style_doc.style_name,
            source_files=(source_file,),
            content=f"### {source_file}\n{text.strip()}",
        )

    def get_style_catalog(self) -> str:
        """Return full style documents used before the final style is known."""
        sections: list[str] = [
            "【风格识别硬规则】",
            "1. 必须先判断 style_family，只能是 realistic 或 3d_anime。",
            "2. 第二步只能从同一 style_family 下选择 style_id，style_id 必须是下方列出的 runtime style id。",
            "3. confidence 必须是 0 到 1 的小数，不得输出 95、95% 这类百分制值。",
            "4. 输出 JSON 字段必须包含 genre、style_family、style_id、confidence、reason、style_tags、evidence、risk、fallback_styles。",
            "5. 如果现实真人写实与 3D 动漫都可用，优先根据文本目标画风、人物质感、材质描述和模板适配度判断，不要混用风格。",
        ]
        family_labels = ((REALISTIC_FAMILY, "现实类"), (ANIME_3D_FAMILY, "3D动漫类"))
        for family, label in family_labels:
            sections.append(f"## {label}｜style_family={family}")
            for style_id, style_doc in STYLE_DOCS.items():
                if style_doc.family != family:
                    continue
                path = self._style_root / style_doc.relative_file
                text = _read_text(path)
                sections.append(
                    f"### style_id={style_id}｜{style_doc.style_name}\n"
                    f"style_family={family}\n"
                    f"来源：{path.relative_to(self._repo_root).as_posix()}\n"
                    f"{text.strip()}"
                )
        return "\n\n".join(sections).strip()


@lru_cache(maxsize=64)
def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Story Engine template file does not exist: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gb18030")


def _resolve_repo_root(repo_root: str | Path | None, module_file: Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)

    module_path = Path(module_file) if module_file is not None else Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    candidates = [*module_path.parents, cwd, *cwd.parents]
    for candidate in candidates:
        docs_root = candidate / STYLE_DOC_ROOT_RELATIVE
        has_style_docs = all((docs_root / style_doc.relative_file).is_file() for style_doc in STYLE_DOCS.values())
        if docs_root.is_dir() and has_style_docs:
            return candidate

    # Preserve the old local-source fallback for clearer errors in incomplete installs.
    return module_path.parents[4]


def _normalize_style_id(style_id: str) -> str:
    text = str(style_id or "").strip()
    if text in STYLE_DOCS:
        return text
    lowered = text.lower()
    if lowered in STYLE_DOCS:
        return lowered
    aliases = {
        "traditional_chinese_period": "chinese_ancient",
        "古风": "chinese_ancient",
        "中国古风": "chinese_ancient",
        "xianxia_high_cg": "xianxia",
        "古风仙侠类": "xianxia",
        "古风仙侠": "xianxia",
        "仙侠": "xianxia",
        "future_sci_fi_cinema": "sci_fi",
        "未来科幻电影类": "sci_fi",
        "未来科幻": "sci_fi",
        "科幻": "sci_fi",
        "live_action_cinematic": "cinematic_realistic",
        "真人电影级": "cinematic_realistic",
        "电影写实": "cinematic_realistic",
        "urban_drama_live_action_realistic": "urban_drama",
        "都市剧情类真人写实风": "urban_drama",
        "都市写实": "urban_drama",
        "都市言情": "urban_drama",
        "都市爱情": "urban_drama",
        "都市短剧类": "urban_drama",
        "cyberpunk_neon_noir": "cyberpunk",
        "赛博朋克类": "cyberpunk",
        "赛博朋克": "cyberpunk",
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
    return aliases.get(text) or aliases.get(lowered) or "live_action_cinematic"
