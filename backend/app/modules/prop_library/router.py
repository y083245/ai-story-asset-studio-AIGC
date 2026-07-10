"""FastAPI router for the Prop Library module.

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
from app.modules.prop_library.deps import get_current_user_id
from app.modules.prop_library.schemas import (
    ErrorResponse,
    ExtractedPropsRequest,
    ExtractedPropsResponse,
    PropListResponse,
    PropRegenerateResponse,
    PropResponse,
    PropUpdateRequest,
)
from app.modules.prop_library.service import PropLibraryService
from app.modules.provider_adapter.registry import ProviderRegistry

router = APIRouter(prefix="/api", tags=["prop-library"])


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
# POST /api/projects/{project_id}/props/extract
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/props/extract",
    response_model=ExtractedPropsResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def extract_props(
    project_id: uuid.UUID,
    body: ExtractedPropsRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    registry: Annotated[ProviderRegistry, Depends(_get_provider)],
) -> ExtractedPropsResponse:
    """Extract, deduplicate, and formalise prop profiles from M05 candidates.

    Expects the output of M05 Text Understanding as input.
    Runs the full pipeline:
    1. Alias merging (exact match + LLM-assisted semantic merge)
    2. Prop ID assignment (PR_001, PR_002, ...)
    3. Importance classification (core/supporting/minor)
    4. Visual detail inference
    5. State timeline generation
    6. Prop prompt + usage prompt building
    7. Owner character validation
    8. Persistence to database
    """
    await _check_project_ownership(session, project_id, user_id)

    provider = registry.get_text_generator()

    try:
        result = await PropLibraryService.extract_props(
            session=session,
            provider=provider,
            project_id=str(project_id),
            candidates=body.candidates,
            character_ids=body.character_ids if body.character_ids else None,
            chapter_text=body.chapter_text if body.chapter_text else None,
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
# GET /api/projects/{project_id}/props
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/props",
    response_model=PropListResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_props(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> PropListResponse:
    """List all props belonging to a project."""
    await _check_project_ownership(session, project_id, user_id)

    items, total = await PropLibraryService.list_props(session, project_id)

    return PropListResponse(
        project_id=project_id,
        props=[PropResponse.model_validate(p) for p in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/props/{prop_id}
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/props/{prop_id}",
    response_model=PropResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def get_prop(
    project_id: uuid.UUID,
    prop_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> PropResponse:
    """Get a single prop by project and prop_id."""
    await _check_project_ownership(session, project_id, user_id)

    prop = await PropLibraryService.get_prop(session, project_id, prop_id)
    if prop is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Prop {prop_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    return PropResponse.model_validate(prop)


# ---------------------------------------------------------------------------
# PATCH /api/projects/{project_id}/props/{prop_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/projects/{project_id}/props/{prop_id}",
    response_model=PropResponse,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def update_prop(
    project_id: uuid.UUID,
    prop_id: str,
    body: PropUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> PropResponse:
    """Partial update of a prop. Creates a version snapshot before mutating.

    Only supplied fields are updated.  The previous values are stored
    in a PropVersion row so history is never lost.
    """
    await _check_project_ownership(session, project_id, user_id)

    # Verify prop exists and belongs to this project
    existing = await PropLibraryService.get_prop(session, project_id, prop_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Prop {prop_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    try:
        updated = await PropLibraryService.update_prop(session, project_id, prop_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return PropResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/props/{prop_id}/regenerate
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/props/{prop_id}/regenerate",
    response_model=PropRegenerateResponse,
    status_code=201,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def regenerate_prop(
    project_id: uuid.UUID,
    prop_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> PropRegenerateResponse:
    """Request regeneration of prop reference assets.

    This endpoint creates a pending generation_task record.
    The actual image generation is dispatched by the Workflow module
    calling M11 Image Asset — this module does NOT generate images.
    """
    await _check_project_ownership(session, project_id, user_id)

    task = await PropLibraryService.regenerate_prop(session, project_id, prop_id)

    return PropRegenerateResponse(
        task_id=task.id,
        prop_id=prop_id,
        status=task.status,
    )


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id}/props/{prop_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}/props/{prop_id}",
    status_code=204,
    responses={
        404: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def delete_prop(
    project_id: uuid.UUID,
    prop_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Delete a prop and its version history."""
    await _check_project_ownership(session, project_id, user_id)

    existing = await PropLibraryService.get_prop(session, project_id, prop_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": f"Prop {prop_id} not found in project {project_id}",
                "retryable": False,
            },
        )

    await PropLibraryService.delete_prop(session, project_id, prop_id)
