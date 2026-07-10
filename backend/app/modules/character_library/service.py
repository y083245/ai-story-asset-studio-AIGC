"""Business logic for the Character Library module.

All database access goes through a single SQLAlchemy AsyncSession.
LLM calls go through the provider adapter.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.id_factory import generate_character_id, reset_counters
from app.modules.character_library.alias_merger import merge_aliases
from app.modules.character_library.consistency import generate_consistency
from app.modules.character_library.image_plan import generate_image_plan
from app.modules.character_library.models import Character, CharacterVersion, GenerationTask
from app.modules.character_library.schemas import (
    CandidateCharacterInput,
    CharacterUpdateRequest,
    ExtractedCharacter,
    ExtractedCharactersResponse,
    ReferenceImagePlanItem,
)
from app.modules.provider_adapter.base import TextGenerationProvider

# Fields that can trigger a version snapshot on update
_VERSIONED_FIELDS: set[str] = {
    "name",
    "aliases",
    "role_type",
    "gender",
    "age",
    "height",
    "body_type",
    "face_shape",
    "facial_bone_structure",
    "skin_tone",
    "eyes",
    "eyebrows",
    "nose",
    "mouth",
    "hair_color",
    "hair_style",
    "default_outfit",
    "outfit_details",
    "shoes",
    "accessories",
    "identity",
    "personality",
    "relationship_to_others",
    "first_appearance",
    "emotion_pack",
    "consistency_tag",
    "forbidden_changes",
    "reference_image_plan",
    "canonical_asset_id",
}


class CharacterLibraryService:
    """Stateless character management service.

    All methods receive an open AsyncSession and a provider instance.
    Callers (router layer) are responsible for converting to Pydantic
    response schemas.
    """

    # ------------------------------------------------------------------
    # Extraction pipeline
    # ------------------------------------------------------------------

    @staticmethod
    async def extract_characters(
        session: AsyncSession,
        provider: TextGenerationProvider,
        project_id: str,
        candidates: list[CandidateCharacterInput],
        use_llm: bool = True,
    ) -> ExtractedCharactersResponse:
        """Run the full extraction pipeline for a project.

        1. Merge aliases (dedup)
        2. Assign character IDs
        3. Generate consistency tags, forbidden changes, image plans
        4. Persist to database
        """
        total_candidates = len(candidates)

        # Step 1: Merge aliases
        merged = await merge_aliases(provider, candidates)
        merged_count = total_candidates - len(merged)

        # Step 2: Reset character ID counters for this project, then assign
        reset_counters(project_id)

        # Sort by role priority: 主角 first, then others
        def _role_priority(c: CandidateCharacterInput) -> int:
            if "主角" in c.role:
                return 0
            if "反派" in c.role:
                return 1
            if "配角" in c.role:
                return 2
            return 3

        merged_sorted = sorted(merged, key=_role_priority)

        extracted: list[ExtractedCharacter] = []

        for order, candidate in enumerate(merged_sorted):
            char_id = generate_character_id(project_id)

            # Build profile dict for consistency & image plan
            profile: dict[str, Any] = {
                "name": candidate.name,
                "role_type": candidate.role if candidate.role else "配角",
                "gender": "",
                "age": "",
                "traits": candidate.traits,
                "personality": "",
                "description": candidate.description,
            }

            # Generate consistency controls
            consistency_tag, forbidden_changes = await generate_consistency(provider, profile, use_llm=use_llm)

            # Generate image plan
            image_plan = await generate_image_plan(provider, profile, role_type=candidate.role, use_llm=use_llm)

            # Persist Character row
            character = Character(
                project_id=uuid.UUID(project_id),
                character_id=char_id,
                name=candidate.name,
                aliases=None,
                role_type=candidate.role if candidate.role else "配角",
                sort_order=order,
                first_appearance=candidate.first_appearance or None,
                personality="; ".join(candidate.traits) if candidate.traits else None,
                consistency_tag=consistency_tag,
                forbidden_changes=forbidden_changes,
                reference_image_plan=[
                    {"category": ip["category"], "description": ip["description"], "priority": ip["priority"]}
                    for ip in image_plan
                ],
                reference_assets=None,
            )
            session.add(character)

            extracted.append(
                ExtractedCharacter(
                    character_id=char_id,
                    name=candidate.name,
                    aliases=[],
                    role_type=candidate.role,
                    first_appearance=candidate.first_appearance or None,
                    personality="; ".join(candidate.traits) if candidate.traits else None,
                    consistency_tag=consistency_tag,
                    forbidden_changes=forbidden_changes,
                    reference_image_plan=[
                        ReferenceImagePlanItem(
                            category=ip["category"],
                            description=ip["description"],
                            priority=ip.get("priority", "required"),
                        )
                        for ip in image_plan
                    ],
                )
            )

        await session.flush()

        return ExtractedCharactersResponse(
            project_id=project_id,
            characters=extracted,
            merged_count=merged_count,
            total_candidates=total_candidates,
        )

    # ------------------------------------------------------------------
    # List characters for a project
    # ------------------------------------------------------------------

    @staticmethod
    async def list_characters(
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> tuple[list[Character], int]:
        """Return all characters for a project, sorted by sort_order."""
        count_stmt = select(func.count()).select_from(Character).where(Character.project_id == project_id)
        total = (await session.execute(count_stmt)).scalar_one()

        stmt = select(Character).where(Character.project_id == project_id).order_by(Character.sort_order)
        items = (await session.execute(stmt)).scalars().all()

        return list(items), total

    # ------------------------------------------------------------------
    # Get single character
    # ------------------------------------------------------------------

    @staticmethod
    async def get_character(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_id: str,
    ) -> Character | None:
        """Return a single character by project_id and character_id, or None."""
        stmt = select(Character).where(Character.project_id == project_id, Character.character_id == character_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Update character (with version snapshot)
    # ------------------------------------------------------------------

    @staticmethod
    async def update_character(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_id: str,
        data: CharacterUpdateRequest,
    ) -> Character:
        """Partial update of a character. Creates a version snapshot first.

        Only fields that are actually changed (and are in _VERSIONED_FIELDS)
        trigger a version snapshot.
        """
        character = await CharacterLibraryService._require_character(session, project_id, character_id)

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return character

        # Determine which fields actually changed
        changed: list[str] = []
        previous: dict[str, Any] = {}

        for key, new_value in updates.items():
            if key not in _VERSIONED_FIELDS:
                continue
            old_value = getattr(character, key, None)
            if old_value != new_value:
                changed.append(key)
                previous[key] = old_value

        if changed:
            # Determine next version number
            version_stmt = select(func.max(CharacterVersion.version_number)).where(
                CharacterVersion.project_id == project_id,
                CharacterVersion.character_id == character_id,
            )
            max_ver = (await session.execute(version_stmt)).scalar_one_or_none()
            next_version = (max_ver or 0) + 1

            # Save version snapshot
            version = CharacterVersion(
                project_id=project_id,
                character_id=character_id,
                version_number=next_version,
                changed_fields=changed,
                previous_values=previous,
            )
            session.add(version)

        # Apply updates
        for key, value in updates.items():
            if key == "sort_order":
                continue  # sort_order is managed internally
            if hasattr(character, key):
                setattr(character, key, value)

        await session.flush()
        return character

    # ------------------------------------------------------------------
    # Regenerate character (create task, don't call M11)
    # ------------------------------------------------------------------

    @staticmethod
    async def regenerate_character(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_id: str,
    ) -> GenerationTask:
        """Create a pending regeneration task for a character.

        The actual work is dispatched by the Workflow module.
        """
        character = await CharacterLibraryService._require_character(session, project_id, character_id)

        task = GenerationTask(
            project_id=project_id,
            task_type="character_regenerate",
            target_id=character_id,
            status="pending",
            payload={
                "character_id": character_id,
                "character_name": character.name,
                "current_image_plan": character.reference_image_plan,
            },
        )
        session.add(task)
        await session.flush()

        return task

    # ------------------------------------------------------------------
    # Delete a character
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_character(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_id: str,
    ) -> None:
        """Delete a character and all its versions."""
        character = await CharacterLibraryService._require_character(session, project_id, character_id)
        await session.delete(character)
        await session.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_character(
        session: AsyncSession,
        project_id: uuid.UUID,
        character_id: str,
    ) -> Character:
        """Fetch a character or raise ValueError."""
        c = await CharacterLibraryService.get_character(session, project_id, character_id)
        if c is None:
            raise ValueError(f"Character {character_id!r} not found")
        return c
