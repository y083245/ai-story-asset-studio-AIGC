"""Reference integrity validator for the Story Bible.

Validates that all character_id, scene_id, and prop_id references
in the Story Bible correspond to actual records in their respective tables.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.character_library.models import Character
from app.modules.prop_library.models import Prop
from app.modules.scene_library.models import Scene
from app.modules.story_bible.schemas import ReferenceValidationError


class ReferenceValidator:
    """Validates reference integrity of Story Bible content against source tables."""

    @staticmethod
    async def validate(
        session: AsyncSession,
        project_id: uuid.UUID,
        characters: list[dict[str, str]],
        scenes: list[dict[str, str]],
        props: list[dict[str, str]],
    ) -> list[ReferenceValidationError]:
        """Validate all character, scene, and prop references.

        Args:
            session: Active database session.
            project_id: The project to scope validation to.
            characters: Bible character references (list of dicts with character_id).
            scenes: Bible scene references (list of dicts with scene_id).
            props: Bible prop references (list of dicts with prop_id).

        Returns:
            List of validation errors (empty if all references are valid).
        """
        errors: list[ReferenceValidationError] = []

        # Validate character references
        char_ids = [c["character_id"] for c in characters if "character_id" in c]
        missing_chars = await ReferenceValidator._check_character_ids(session, project_id, char_ids)
        if missing_chars:
            errors.append(ReferenceValidationError(entity_type="character", missing_ids=missing_chars))

        # Validate scene references
        scene_ids = [s["scene_id"] for s in scenes if "scene_id" in s]
        missing_scenes = await ReferenceValidator._check_scene_ids(session, project_id, scene_ids)
        if missing_scenes:
            errors.append(ReferenceValidationError(entity_type="scene", missing_ids=missing_scenes))

        # Validate prop references
        prop_ids = [p["prop_id"] for p in props if "prop_id" in p]
        missing_props = await ReferenceValidator._check_prop_ids(session, project_id, prop_ids)
        if missing_props:
            errors.append(ReferenceValidationError(entity_type="prop", missing_ids=missing_props))

        # Validate prop owner_character_id references
        owner_errors = await ReferenceValidator._validate_prop_owners(session, project_id, props)
        errors.extend(owner_errors)

        return errors

    @staticmethod
    async def _check_character_ids(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_ids: list[str],
    ) -> list[str]:
        """Return character_ids that do NOT exist in the characters table."""
        if not character_ids:
            return []

        stmt = select(Character.character_id).where(
            Character.project_id == project_id,
            Character.character_id.in_(character_ids),
        )
        result = await session.execute(stmt)
        existing_ids: set[str] = {row[0] for row in result.all()}

        return [cid for cid in character_ids if cid not in existing_ids]

    @staticmethod
    async def _check_scene_ids(
        session: AsyncSession,
        project_id: uuid.UUID,
        scene_ids: list[str],
    ) -> list[str]:
        """Return scene_ids that do NOT exist in the scenes table."""
        if not scene_ids:
            return []

        stmt = select(Scene.scene_id).where(
            Scene.project_id == project_id,
            Scene.scene_id.in_(scene_ids),
        )
        result = await session.execute(stmt)
        existing_ids: set[str] = {row[0] for row in result.all()}

        return [sid for sid in scene_ids if sid not in existing_ids]

    @staticmethod
    async def _check_prop_ids(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_ids: list[str],
    ) -> list[str]:
        """Return prop_ids that do NOT exist in the props table."""
        if not prop_ids:
            return []

        stmt = select(Prop.prop_id).where(
            Prop.project_id == project_id,
            Prop.prop_id.in_(prop_ids),
        )
        result = await session.execute(stmt)
        existing_ids: set[str] = {row[0] for row in result.all()}

        return [pid for pid in prop_ids if pid not in existing_ids]

    @staticmethod
    async def _validate_prop_owners(
        session: AsyncSession,
        project_id: uuid.UUID,
        props: list[dict[str, str]],
    ) -> list[ReferenceValidationError]:
        """Validate that prop owner_character_id references, if present, are valid."""
        owner_ids: set[str] = set()
        for prop_dict in props:
            owner = prop_dict.get("owner_character_id", "")
            if owner:
                owner_ids.add(owner)

        if not owner_ids:
            return []

        stmt = select(Character.character_id).where(
            Character.project_id == project_id,
            Character.character_id.in_(list(owner_ids)),
        )
        result = await session.execute(stmt)
        existing_ids: set[str] = {row[0] for row in result.all()}

        missing = sorted(owner_ids - existing_ids)
        if missing:
            return [
                ReferenceValidationError(
                    entity_type="prop_owner",
                    missing_ids=missing,
                )
            ]
        return []
