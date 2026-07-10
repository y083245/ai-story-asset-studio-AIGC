"""FastAPI router for the Scene Library module.

Prefix: /api
All endpoints require X-User-ID header (inherited from M01 pattern).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND, VALIDATION_ERROR
from app.db.session import get_session
from app.modules.project.models import Project
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.scene_library.deps import get_current_user_id
from app.modules.scene_library.schemas import (
    ErrorResponse,
    ExtractedScenesRequest,
    ExtractedScenesResponse,
    SceneListResponse,
    SceneRegenerateResponse,
    SceneResponse,
    SceneUpdateRequest,
)
from app.modules.scene_library.service import SceneLibraryService

router = APIRouter(prefix="/api", tags=["scene-library"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_provider() -> ProviderRegistry:
    """Return a ProviderRegistry for the current environment."""
    return ProviderRegistry()


# ---------------------------------------------------------------------------
# Ownership check helper
# ---------------------------------------------------------------------------


async def _check_project_ownership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: str,
) -> Project:
    """Verify project exists and is owned by the current user.

    Raises 404 if not found, 403 if wrong user.
    """
    from sqlalchemy import select as _select

    stmt = _select(Project).where(Project.id == project_id)
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Project {project_id} not found",
                "retryable": False,
            },
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": FORBIDDEN.code,
                "message": "You do not have access to this project",
                "retryable": False,
            },
        )
    return project


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/scenes/extract
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/scenes/extract",
    response_model=ExtractedScenesResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def extract_scenes(
    project_id: uuid.UUID,
    body: ExtractedScenesRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    registry: Annotated[ProviderRegistry, Depends(_get_provider)],
) -> ExtractedScenesResponse:
    """Extract, deduplicate, and formalise scene profiles from M05 candidates.

    Expects the output of M05 Text Understanding's StoryStructureAgent
    as input. Runs the full pipeline:
    1. Scene alias merging (exact match + LLM-assisted semantic merge)
    2. Scene name validation and expansion (>= 4 Chinese characters)
    3. Fixed anchor generation (>= 3 anchors)
    4. Spatial layering (foreground/midground/background)
    5. Composition angle assignment
    6. Scene prompt and empty-scene prompt generation
    7. Scene ID assignment (SC_001, SC_002, ...)
    8. Persistence to database
    """
    await _check_project_ownership(session, project_id, user_id)

    provider = registry.get_text_generator()

    try:
        result = await SceneLibraryService.extract_scenes(
            session=session,
            provider=provider,
            project_id=str(project_id),
            candidates=body.candidates,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return result


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/scenes
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/scenes",
    response_model=SceneListResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_scenes(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> SceneListResponse:
    """List all scenes belonging to a project."""
    await _check_project_ownership(session, project_id, user_id)

    items, total = await SceneLibraryService.list_scenes(session, project_id)

    return SceneListResponse(
        project_id=project_id,
        scenes=[SceneResponse.model_validate(s) for s in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/scenes/{scene_id}
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/scenes/{scene_id}",
    response_model=SceneResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_scene(
    project_id: uuid.UUID,
    scene_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> SceneResponse:
    """Get a single scene by project and scene_id."""
    await _check_project_ownership(session, project_id, user_id)

    scene = await SceneLibraryService.get_scene(session, project_id, scene_id)
    if scene is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Scene {scene_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    return SceneResponse.model_validate(scene)


# ---------------------------------------------------------------------------
# PATCH /api/projects/{project_id}/scenes/{scene_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/projects/{project_id}/scenes/{scene_id}",
    response_model=SceneResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def update_scene(
    project_id: uuid.UUID,
    scene_id: str,
    body: SceneUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> SceneResponse:
    """Partial update of a scene. Creates a version snapshot before mutating.

    Only supplied fields are updated. The previous values are stored
    in a SceneVersion row so history is never lost.
    """
    await _check_project_ownership(session, project_id, user_id)

    # Verify scene exists and belongs to this project
    existing = await SceneLibraryService.get_scene(session, project_id, scene_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Scene {scene_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    try:
        updated = await SceneLibraryService.update_scene(session, project_id, scene_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return SceneResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/scenes/{scene_id}/regenerate
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/scenes/{scene_id}/regenerate",
    response_model=SceneRegenerateResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def regenerate_scene(
    project_id: uuid.UUID,
    scene_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> SceneRegenerateResponse:
    """Request regeneration of scene reference assets.

    This endpoint creates a pending generation_task record.
    The actual image generation is dispatched by the Workflow module
    calling M11 Image Asset — this module does NOT generate images.
    """
    await _check_project_ownership(session, project_id, user_id)

    task = await SceneLibraryService.regenerate_scene(session, project_id, scene_id)

    return SceneRegenerateResponse(
        task_id=task.id,
        scene_id=scene_id,
        status=task.status,
    )


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id}/scenes/{scene_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}/scenes/{scene_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def delete_scene(
    project_id: uuid.UUID,
    scene_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Delete a scene and its version history."""
    await _check_project_ownership(session, project_id, user_id)

    existing = await SceneLibraryService.get_scene(session, project_id, scene_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Scene {scene_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    await SceneLibraryService.delete_scene(session, project_id, scene_id)
