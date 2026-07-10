"""FastAPI dependency injection helpers for the Workflow module."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND
from app.db.session import get_session
from app.modules.project.schemas import ErrorDetail, ErrorResponse
from app.modules.project.service import ProjectService
from app.security.auth import require_current_user_id as get_current_user_id

__all__ = ["get_current_user_id", "get_project_id", "verify_project_ownership"]


async def get_project_id(project_id: Annotated[uuid.UUID, Path(description="项目ID")]) -> uuid.UUID:
    """Extract project_id from the URL path."""
    return project_id


async def verify_project_ownership(
    project_id: Annotated[uuid.UUID, Depends(get_project_id)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> uuid.UUID:
    """Verify the user owns the project, then return the project_id.

    Raises 404 if the project does not exist, 403 if the user is not the owner.
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
    return project_id
