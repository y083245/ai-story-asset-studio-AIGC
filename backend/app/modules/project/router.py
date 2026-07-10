"""FastAPI router for the Project module.

Prefix: /api
All endpoints require X-User-ID header.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND, PROJECT_LOCKED
from app.db.session import get_session
from app.modules.project.deps import get_current_user_id
from app.modules.project.schemas import (
    ErrorDetail,
    ErrorResponse,
    ProjectCopyResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
    ProjectStatusResponse,
    ProjectUpdateRequest,
)
from app.modules.project.service import ProjectService

router = APIRouter(prefix="/api", tags=["project"])


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=201,
    responses={422: {"model": ErrorResponse}},
)
async def create_project(
    body: ProjectCreateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectResponse:
    """Create a new visual asset project."""
    try:
        project = await ProjectService.create_project(session, user_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=exc.args[0]) from exc
    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------


@router.get(
    "/projects",
    response_model=ProjectListResponse,
)
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    include_archived: Annotated[bool, Query(description="是否包含已归档项目")] = False,
    only_archived: Annotated[bool, Query(description="是否只返回回收站项目")] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectListResponse:
    """List projects belonging to the current user."""
    items, total = await ProjectService.list_projects(
        session,
        user_id,
        include_archived=include_archived,
        only_archived=only_archived,
        limit=limit,
        offset=offset,
    )
    return ProjectListResponse(
        items=[ProjectResponse.from_project(p) for p in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectResponse:
    """Get full project detail."""
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    # Ownership check
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# PATCH /api/projects/{project_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectResponse:
    """Partial update of a project.

    Fields aspect_ratio, style_mode, generation_mode
    are locked when the project is in an active generation state.
    """
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )

    try:
        updated = await ProjectService.update_project(session, project_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=PROJECT_LOCKED.code,
                    message=str(exc.args[0]),
                    retryable=False,
                )
            ).model_dump()["error"],
        ) from exc

    return ProjectResponse.from_project(updated)


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id}  (soft-delete)
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def delete_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Move a project to recycle bin. It is permanently deleted after 30 days."""
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    await ProjectService.soft_delete_project(session, project_id)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/restore
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/restore",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}},
)
async def restore_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectResponse:
    """Restore a project from recycle bin."""
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    restored = await ProjectService.restore_project(session, project_id)
    return ProjectResponse.from_project(restored)


# ---------------------------------------------------------------------------
# GET /api/projects/{project_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/status",
    response_model=ProjectStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_project_status(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectStatusResponse:
    """Get aggregated project status with progress."""
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    return await ProjectService.get_project_status(session, project_id)


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/copy
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/copy",
    response_model=ProjectCopyResponse,
    status_code=201,
    responses={404: {"model": ErrorResponse}},
)
async def copy_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ProjectCopyResponse:
    """Create a copy of an existing project.

    The new project starts in DRAFT status with the same title (副本) and settings.
    """
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )

    new_project = await ProjectService.copy_project(session, project_id, user_id)
    return ProjectCopyResponse(
        original_id=project_id,
        new_project=ProjectResponse.from_project(new_project),
    )


# ---------------------------------------------------------------------------
# POST /api/projects/{project_id}/archive
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/archive",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def archive_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Archive a project (sets status to archived)."""
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    await ProjectService.archive_project(session, project_id)


# ---------------------------------------------------------------------------
# DELETE /api/projects/{project_id}/permanent
# ---------------------------------------------------------------------------


@router.delete(
    "/projects/{project_id}/permanent",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
async def permanent_delete_project(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> None:
    """Permanently delete a project and all its related data.

    This is NOT reversible — the project and all associated data
    (workflow states, analysis results, generated assets, etc.)
    will be removed from the database.
    """
    project = await ProjectService.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=NOT_FOUND.code,
                    message=f"Project {project_id} not found",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    if project.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code=FORBIDDEN.code,
                    message="You do not have access to this project",
                    retryable=False,
                )
            ).model_dump()["error"],
        )
    await ProjectService.permanent_delete_project(session, project_id)
