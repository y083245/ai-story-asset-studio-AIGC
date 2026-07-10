"""Style pack registry for high-quality staged analysis templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

REQUIRED_STYLE_PACK_MODULES: tuple[str, ...] = (
    "genre_detector",
    "character_extractor",
    "character_turnaround_prompt",
    "scene_extractor",
    "prop_extractor",
)


class StylePackTemplate(BaseModel):
    """A style-specific module prompt converted from the master templates."""

    style_id: str
    style_name: str
    module_id: str
    source_master: str
    template_version: str = "2.0.0"
    system_prompt: str
    user_prompt_template: str
    output_schema: dict[str, Any] = Field(default_factory=dict)
    quality_rules: list[str] = Field(default_factory=list)
    negative_rules: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class StylePackRegistry:
    """Loads style-pack JSON templates from ``templates/style_packs``."""

    def __init__(self, style_packs_root: str | None = None) -> None:
        if style_packs_root is None:
            current = Path(__file__).resolve()
            for parent in current.parents:
                candidate = parent / "templates" / "style_packs"
                if candidate.exists():
                    style_packs_root = str(candidate)
                    break
            else:
                style_packs_root = str(current.parents[4] / "templates" / "style_packs")
        self._style_packs_root = Path(style_packs_root)
        self._packs: dict[str, dict[str, StylePackTemplate]] = {}
        self._loaded = False

    @property
    def style_packs_root(self) -> Path:
        return self._style_packs_root

    def load_all(self) -> None:
        """Load all style packs and validate each pack has required modules."""
        if self._loaded:
            return
        if not self._style_packs_root.exists():
            raise RuntimeError(f"Style packs root does not exist: {self._style_packs_root}")

        for style_dir in sorted(path for path in self._style_packs_root.iterdir() if path.is_dir()):
            modules: dict[str, StylePackTemplate] = {}
            for json_file in sorted(style_dir.glob("*.json")):
                template = self._load_template(json_file)
                if template.style_id != style_dir.name:
                    raise ValueError(
                        f"Style pack file {json_file} has style_id={template.style_id}, expected {style_dir.name}"
                    )
                modules[template.module_id] = template
            missing = set(REQUIRED_STYLE_PACK_MODULES) - set(modules)
            if missing:
                raise ValueError(f"Style pack {style_dir.name} missing modules: {sorted(missing)}")
            self._packs[style_dir.name] = modules

        self._loaded = True

    def list_styles(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._packs)

    def list_modules(self, style_id: str) -> list[str]:
        self._ensure_loaded()
        return sorted(self._get_pack(style_id))

    def get_template(self, style_id: str, module_id: str) -> StylePackTemplate:
        self._ensure_loaded()
        pack = self._get_pack(style_id)
        if module_id not in pack:
            raise KeyError(f"Module '{module_id}' not found in style pack '{style_id}'")
        return pack[module_id]

    def get_pack(self, style_id: str) -> dict[str, StylePackTemplate]:
        self._ensure_loaded()
        return dict(self._get_pack(style_id))

    def _load_template(self, path: Path) -> StylePackTemplate:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
        template = StylePackTemplate.model_validate(data)
        if not template.system_prompt.strip():
            raise ValueError(f"Style pack template {path} has empty system_prompt")
        if not template.user_prompt_template.strip():
            raise ValueError(f"Style pack template {path} has empty user_prompt_template")
        return template

    def _get_pack(self, style_id: str) -> dict[str, StylePackTemplate]:
        if style_id not in self._packs:
            raise KeyError(f"Style pack '{style_id}' not found")
        return self._packs[style_id]

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError("StylePackRegistry not loaded. Call load_all() before querying templates.")
