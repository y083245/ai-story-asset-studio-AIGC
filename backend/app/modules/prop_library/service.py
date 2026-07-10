"""Business logic for the Prop Library module.

All database access goes through a single SQLAlchemy AsyncSession.
LLM calls go through the provider adapter.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.id_factory import generate_prop_id, reset_counters
from app.modules.prop_library.alias_merger import merge_prop_aliases
from app.modules.prop_library.models import GenerationTask, Prop, PropVersion
from app.modules.prop_library.prompt_builder import (
    build_prop_prompt,
    build_usage_prompt,
    classify_importance,
    infer_visual_details,
)
from app.modules.prop_library.schemas import (
    CandidatePropInput,
    ExtractedProp,
    ExtractedPropsResponse,
    PropUpdateRequest,
    StateTimelineItem,
)
from app.modules.prop_library.state_timeline import (
    generate_state_timeline,
    validate_timeline_for_importance,
)
from app.modules.provider_adapter.base import TextGenerationProvider

# Fields that can trigger a version snapshot on update
_VERSIONED_FIELDS: set[str] = {
    "name",
    "aliases",
    "importance",
    "category",
    "owner_character_id",
    "visual_features",
    "material",
    "color",
    "size",
    "first_appearance",
    "plot_function",
    "state_timeline",
    "prop_prompt",
    "usage_prompt",
    "canonical_asset_id",
    "reference_assets",
}


class PropLibraryService:
    """Stateless prop management service.

    All methods receive an open AsyncSession and a provider instance.
    Callers (router layer) are responsible for converting to Pydantic
    response schemas.
    """

    # ------------------------------------------------------------------
    # Character ID lookup helper
    # ------------------------------------------------------------------

    @staticmethod
    async def _validate_owner_character_id(
        session: AsyncSession,
        project_id: uuid.UUID,
        owner_character_id: str | None,
    ) -> list[str]:
        """Validate that owner_character_id, if set, references an existing character.

        Returns a list of error messages (empty if valid).
        """
        if not owner_character_id:
            return []

        # Import Character model lazily to avoid circular imports
        from app.modules.character_library.models import Character

        stmt = select(Character).where(
            Character.character_id == owner_character_id,
            Character.project_id == project_id,
        )
        result = await session.execute(stmt)
        char = result.scalar_one_or_none()

        if char is None:
            return [
                f"Owner character '{owner_character_id}' not found in project {project_id}. "
                "The owner_character_id must reference an existing character or be empty."
            ]
        return []

    # ------------------------------------------------------------------
    # Extraction pipeline
    # ------------------------------------------------------------------

    @staticmethod
    async def extract_props(
        session: AsyncSession,
        provider: TextGenerationProvider,
        project_id: str,
        candidates: list[CandidatePropInput],
        character_ids: list[str] | None = None,
        chapter_text: list[str] | None = None,
        use_llm: bool = True,
    ) -> ExtractedPropsResponse:
        """Run the full extraction pipeline for a project.

        1. Merge aliases (dedup)
        2. Assign prop IDs
        3. Classify importance
        4. Infer visual details
        5. Generate state timeline
        6. Build prop_prompt and usage_prompt
        7. Validate owner character references
        8. Persist to database
        """
        total_candidates = len(candidates)
        blocking_errors: list[str] = []

        # Step 1: Merge aliases
        merged = await merge_prop_aliases(provider, candidates)
        merged_count = total_candidates - len(merged)

        # Step 2: Reset prop ID counters for this project, then assign
        reset_counters(project_id)

        # Sort by importance: core first, then supporting, then minor
        extracted: list[ExtractedProp] = []

        # First pass: classify and generate data for each candidate
        prop_data: list[dict[str, Any]] = []
        for candidate in merged:
            importance = classify_importance(candidate)
            visual_features, material, color, size = infer_visual_details(candidate)
            timeline = generate_state_timeline(candidate, chapter_text)

            # Validate timeline for core props
            timeline_errors = validate_timeline_for_importance(importance, timeline, candidate.name)
            blocking_errors.extend(timeline_errors)

            prop_prompt = build_prop_prompt(candidate, visual_features, material, color, size)
            usage_prompt = build_usage_prompt(
                candidate, timeline, owner_name=candidate.owner_name, first_appearance=candidate.first_appearance
            )

            prop_data.append(
                {
                    "candidate": candidate,
                    "importance": importance,
                    "visual_features": visual_features,
                    "material": material,
                    "color": color,
                    "size": size,
                    "timeline": timeline,
                    "prop_prompt": prop_prompt,
                    "usage_prompt": usage_prompt,
                }
            )

        # Sort by importance priority
        def _importance_priority(d: dict[str, Any]) -> int:
            imp = d["importance"]
            if imp == "core":
                return 0
            if imp == "supporting":
                return 1
            return 2

        prop_data.sort(key=_importance_priority)

        # Build character ID lookup map from owner_name to character_id
        char_name_to_id: dict[str, str] = {}
        if character_ids:
            # Query character names from the database
            from app.modules.character_library.models import Character

            for char_id in character_ids:
                stmt = select(Character).where(
                    Character.character_id == char_id,
                    Character.project_id == uuid.UUID(project_id),
                )
                result = await session.execute(stmt)
                char = result.scalar_one_or_none()
                if char:
                    char_name_to_id[char.name] = char_id
                    # Also map aliases
                    if char.aliases:
                        for alias in char.aliases:
                            char_name_to_id[alias] = char_id

        # Second pass: assign IDs and persist
        for data in prop_data:
            cand: CandidatePropInput = data["candidate"]
            prop_id = generate_prop_id(project_id)

            # Resolve owner_character_id from owner_name
            owner_character_id: str | None = None
            if cand.owner_name and cand.owner_name in char_name_to_id:
                owner_character_id = char_name_to_id[cand.owner_name]

            # Validate owner if set
            owner_errors = await PropLibraryService._validate_owner_character_id(
                session, uuid.UUID(project_id), owner_character_id
            )
            blocking_errors.extend(owner_errors)

            # Persist Prop row
            prop = Prop(
                project_id=uuid.UUID(project_id),
                prop_id=prop_id,
                name=cand.name,
                aliases=cand.aliases if cand.aliases else None,
                importance=data["importance"],
                category=None,
                owner_character_id=owner_character_id,
                visual_features=data["visual_features"] or None,
                material=data["material"] or None,
                color=data["color"] or None,
                size=data["size"] or None,
                first_appearance=cand.first_appearance or None,
                plot_function=cand.function_hint or None,
                state_timeline=[item.model_dump() for item in data["timeline"]],
                prop_prompt=data["prop_prompt"],
                usage_prompt=data["usage_prompt"],
                reference_assets=None,
            )
            session.add(prop)

            extracted.append(
                ExtractedProp(
                    prop_id=prop_id,
                    name=cand.name,
                    aliases=cand.aliases if cand.aliases else [],
                    importance=data["importance"],
                    owner_character_id=owner_character_id,
                    visual_features=data["visual_features"] or None,
                    material=data["material"] or None,
                    color=data["color"] or None,
                    size=data["size"] or None,
                    first_appearance=cand.first_appearance or None,
                    plot_function=cand.function_hint or None,
                    state_timeline=data["timeline"],
                    prop_prompt=data["prop_prompt"],
                    usage_prompt=data["usage_prompt"],
                    reference_assets=[],
                )
            )

        await session.flush()

        return ExtractedPropsResponse(
            project_id=project_id,
            props=extracted,
            merged_count=merged_count,
            total_candidates=total_candidates,
            blocking_errors=blocking_errors,
        )

    # ------------------------------------------------------------------
    # List props for a project
    # ------------------------------------------------------------------

    @staticmethod
    async def list_props(
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> tuple[list[Prop], int]:
        """Return all props for a project, sorted by importance priority then name."""
        count_stmt = select(func.count()).select_from(Prop).where(Prop.project_id == project_id)
        total = (await session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Prop)
            .where(Prop.project_id == project_id)
            .order_by(
                # Sort by importance: core first, then supporting, then minor
                case(
                    (Prop.importance == "core", 0),
                    (Prop.importance == "supporting", 1),
                    else_=2,
                ),
                Prop.name,
            )
        )
        items = (await session.execute(stmt)).scalars().all()

        return list(items), total

    # ------------------------------------------------------------------
    # Get single prop
    # ------------------------------------------------------------------

    @staticmethod
    async def get_prop(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_id: str,
    ) -> Prop | None:
        """Return a single prop by project_id and prop_id, or None."""
        stmt = select(Prop).where(Prop.project_id == project_id, Prop.prop_id == prop_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Update prop (with version snapshot)
    # ------------------------------------------------------------------

    @staticmethod
    async def update_prop(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_id: str,
        data: PropUpdateRequest,
    ) -> Prop:
        """Partial update of a prop. Creates a version snapshot first.

        Only fields that are actually changed (and are in _VERSIONED_FIELDS)
        trigger a version snapshot.
        """
        prop = await PropLibraryService._require_prop(session, project_id, prop_id)

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return prop

        # If owner_character_id is being set, validate it
        if "owner_character_id" in updates and updates["owner_character_id"]:
            owner_errors = await PropLibraryService._validate_owner_character_id(
                session, prop.project_id, updates["owner_character_id"]
            )
            if owner_errors:
                raise ValueError(owner_errors[0])

        # If importance is changing to core, validate state_timeline
        new_importance = updates.get("importance", prop.importance)
        if new_importance == "core":
            # Get timeline (either from updates or existing)
            timeline_raw = updates.get("state_timeline", prop.state_timeline)
            timeline_items: list[StateTimelineItem] = []
            for item in timeline_raw:
                if isinstance(item, dict):
                    timeline_items.append(
                        StateTimelineItem(
                            step_index=int(item.get("step_index", 1)),
                            state=str(item.get("state", "")),
                            description=str(item.get("description", "")),
                        )
                    )
            timeline_errors = validate_timeline_for_importance(
                new_importance, timeline_items, updates.get("name", prop.name)
            )
            if timeline_errors:
                raise ValueError(timeline_errors[0])

        # Determine which fields actually changed
        changed: list[str] = []
        previous: dict[str, Any] = {}

        for key, new_value in updates.items():
            if key not in _VERSIONED_FIELDS:
                continue
            old_value = getattr(prop, key, None)
            if old_value != new_value:
                changed.append(key)
                previous[key] = old_value

        if changed:
            # Determine next version number
            version_stmt = select(func.max(PropVersion.version_number)).where(
                PropVersion.project_id == project_id,
                PropVersion.prop_id == prop_id,
            )
            max_ver = (await session.execute(version_stmt)).scalar_one_or_none()
            next_version = (max_ver or 0) + 1

            # Save version snapshot
            version = PropVersion(
                project_id=project_id,
                prop_id=prop_id,
                version_number=next_version,
                changed_fields=changed,
                previous_values=previous,
            )
            session.add(version)

        # Apply updates
        for key, value in updates.items():
            if hasattr(prop, key):
                setattr(prop, key, value)

        await session.flush()
        return prop

    # ------------------------------------------------------------------
    # Regenerate prop (create task, don't call M11)
    # ------------------------------------------------------------------

    @staticmethod
    async def regenerate_prop(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_id: str,
    ) -> GenerationTask:
        """Create a pending regeneration task for a prop.

        The actual work is dispatched by the Workflow module.
        """
        prop = await PropLibraryService._require_prop(session, project_id, prop_id)

        task = GenerationTask(
            project_id=project_id,
            task_type="prop_regenerate",
            target_id=prop_id,
            status="pending",
            payload={
                "prop_id": prop_id,
                "prop_name": prop.name,
                "prop_prompt": prop.prop_prompt,
                "usage_prompt": prop.usage_prompt,
            },
        )
        session.add(task)
        await session.flush()

        return task

    # ------------------------------------------------------------------
    # Delete a prop
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_prop(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_id: str,
    ) -> None:
        """Delete a prop and all its versions."""
        prop = await PropLibraryService._require_prop(session, project_id, prop_id)
        await session.delete(prop)
        await session.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_prop(
        session: AsyncSession,
        project_id: uuid.UUID,
        prop_id: str,
    ) -> Prop:
        """Fetch a prop or raise ValueError."""
        p = await PropLibraryService.get_prop(session, project_id, prop_id)
        if p is None:
            raise ValueError(f"Prop {prop_id!r} not found")
        return p
