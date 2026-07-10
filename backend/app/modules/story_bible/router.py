"""Story Bible API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND
from app.db.session import get_session
from app.modules.project.models import Project
from app.modules.story_bible.deps import get_current_user_id
from app.modules.story_bible.schemas import (
    CharacterReference,
    NegativePromptRule,
    PropReference,
    SceneReference,
    StoryBibleData,
    StoryBibleErrorResponse,
    StoryBiblePatchRequest,
    StoryBibleResponse,
    StoryBibleVersionItem,
    StoryBibleVersionListResponse,
    StoryBibleVersionSnapshot,
)
from app.modules.story_bible.service import StoryBibleService

router = APIRouter(prefix="/api", tags=["story-bible"])


async def _require_project(session: AsyncSession, project_id: uuid.UUID, user_id: str) -> Project:
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=StoryBibleErrorResponse(
                code=NOT_FOUND.code,
                message=f"Project {project_id} not found",
                retryable=False,
            ).model_dump(),
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=StoryBibleErrorResponse(
                code=FORBIDDEN.code,
                message="You do not have access to this project",
                retryable=False,
            ).model_dump(),
        )
    return project


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in _list(value) if isinstance(item, dict)]


def _bible_to_response(bible: Any) -> StoryBibleResponse:
    return StoryBibleResponse(
        project_id=bible.project_id,
        version=bible.version,
        title=str(bible.title or ""),
        genre=str(bible.genre or ""),
        visual_style=str(bible.visual_style or ""),
        aspect_ratio=str(bible.aspect_ratio or "9:16"),
        story_summary=str(bible.story_summary or ""),
        main_conflict=str(bible.main_conflict or ""),
        emotional_tone=str(bible.emotional_tone or ""),
        world_setting=str(bible.world_setting or ""),
        time_period=str(bible.time_period or ""),
        color_palette=[str(item) for item in _list(bible.color_palette)],
        composition_language=[str(item) for item in _list(bible.composition_language)],
        characters=[CharacterReference(**item) for item in _dicts(bible.characters)],
        scenes=[SceneReference(**item) for item in _dicts(bible.scenes)],
        props=[PropReference(**item) for item in _dicts(bible.props)],
        negative_prompt_rules=[NegativePromptRule(**item) for item in _dicts(bible.negative_prompt_rules)],
        created_at=bible.created_at,
        updated_at=bible.updated_at,
    )


@router.get(
    "/projects/{project_id}/story-bible",
    response_model=StoryBibleResponse,
    responses={404: {"model": StoryBibleErrorResponse}},
)
async def get_story_bible(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    version: Annotated[int | None, Query(ge=1, description="指定版本号，默认返回最新")] = None,
) -> StoryBibleResponse:
    await _require_project(session, project_id, user_id)
    bible = await StoryBibleService.get_bible(session, project_id, version=version)
    if bible is None:
        raise HTTPException(
            status_code=404,
            detail=StoryBibleErrorResponse(
                code=NOT_FOUND.code,
                message=f"No Story Bible found for project {project_id}",
                retryable=False,
            ).model_dump(),
        )
    return _bible_to_response(bible)


@router.patch(
    "/projects/{project_id}/story-bible",
    response_model=StoryBibleResponse,
    responses={404: {"model": StoryBibleErrorResponse}},
)
async def patch_story_bible(
    project_id: uuid.UUID,
    body: StoryBiblePatchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> StoryBibleResponse:
    await _require_project(session, project_id, user_id)
    try:
        bible = await StoryBibleService.patch_bible(session, project_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=StoryBibleErrorResponse(
                code=NOT_FOUND.code,
                message=str(exc),
                retryable=False,
            ).model_dump(),
        ) from exc
    return _bible_to_response(bible)


@router.get(
    "/projects/{project_id}/story-bible/versions",
    response_model=StoryBibleVersionListResponse,
    responses={404: {"model": StoryBibleErrorResponse}},
)
async def list_story_bible_versions(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> StoryBibleVersionListResponse:
    await _require_project(session, project_id, user_id)
    versions = await StoryBibleService.list_versions(session, project_id)
    items = [
        StoryBibleVersionItem(
            version=item.version,
            created_at=item.created_at,
            title=str(item.snapshot.get("title", "")) if isinstance(item.snapshot, dict) else "",
        )
        for item in versions
    ]
    return StoryBibleVersionListResponse(project_id=project_id, versions=items)


@router.get(
    "/projects/{project_id}/story-bible/versions/{version}",
    response_model=StoryBibleVersionSnapshot,
    responses={404: {"model": StoryBibleErrorResponse}},
)
async def get_story_bible_version_snapshot(
    project_id: uuid.UUID,
    version: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> StoryBibleVersionSnapshot:
    await _require_project(session, project_id, user_id)
    snapshot = await StoryBibleService.get_version_snapshot(session, project_id, version)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=StoryBibleErrorResponse(
                code=NOT_FOUND.code,
                message=f"Version {version} not found for project {project_id}",
                retryable=False,
            ).model_dump(),
        )
    created_at = datetime.now(UTC)
    for item in await StoryBibleService.list_versions(session, project_id):
        if item.version == version:
            created_at = item.created_at
            break
    return StoryBibleVersionSnapshot(
        project_id=project_id,
        version=version,
        created_at=created_at,
        data=StoryBibleData(
            project_id=project_id,
            version=int(snapshot.get("version", version)),
            title=str(snapshot.get("title", "")),
            genre=str(snapshot.get("genre", "")),
            visual_style=str(snapshot.get("visual_style", "")),
            aspect_ratio=str(snapshot.get("aspect_ratio", "9:16")),
            story_summary=str(snapshot.get("story_summary", "")),
            main_conflict=str(snapshot.get("main_conflict", "")),
            emotional_tone=str(snapshot.get("emotional_tone", "")),
            world_setting=str(snapshot.get("world_setting", "")),
            time_period=str(snapshot.get("time_period", "")),
            color_palette=[str(item) for item in _list(snapshot.get("color_palette"))],
            composition_language=[str(item) for item in _list(snapshot.get("composition_language"))],
            characters=[CharacterReference(**item) for item in _dicts(snapshot.get("characters"))],
            scenes=[SceneReference(**item) for item in _dicts(snapshot.get("scenes"))],
            props=[PropReference(**item) for item in _dicts(snapshot.get("props"))],
            negative_prompt_rules=[
                NegativePromptRule(**item) for item in _dicts(snapshot.get("negative_prompt_rules"))
            ],
        ),
    )
