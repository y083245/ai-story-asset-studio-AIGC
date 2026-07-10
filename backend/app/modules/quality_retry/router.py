"""FastAPI router for the Quality & Retry module.

Prefix: /api
All endpoints require X-User-ID header.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND
from app.db.session import get_session
from app.modules.project.models import Project
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.quality_retry.deps import get_current_user_id
from app.modules.quality_retry.schemas import (
    ErrorResponse,
    ImageQualityRequest,
    QualityReportResponse,
    RetryDecisionResponse,
    RetryExecuteRequest,
    RetryExecuteResponse,
)
from app.modules.quality_retry.service import QualityRetryService

router = APIRouter(prefix="/api", tags=["quality-retry"])


# ---------------------------------------------------------------------------
# Ownership check helper
# ---------------------------------------------------------------------------


async def _check_project_ownership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: str,
) -> Project:
    """Verify project exists and is owned by the current user."""
    stmt = select(Project).where(Project.id == project_id)
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
# Dependencies
# ---------------------------------------------------------------------------


def _get_service() -> QualityRetryService:
    """Return a QualityRetryService for the current environment."""
    registry = ProviderRegistry()
    return QualityRetryService(vision_provider=registry.get_vision_quality())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/quality-retry/inspect/image",
    response_model=QualityReportResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
    },
)
async def inspect_image(
    request: ImageQualityRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QualityRetryService, Depends(_get_service)],
) -> QualityReportResponse:
    """Inspect an image asset for quality issues.

    Runs face consistency, outfit consistency, scene consistency,
    prop presence, watermark, body deformation, and composition checks.
    """
    await _check_project_ownership(session, request.project_id, user_id)
    return await service.inspect_image(request, session)


@router.post(
    "/quality-retry/retry/execute",
    response_model=RetryExecuteResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
    },
)
async def execute_retry(
    request: RetryExecuteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QualityRetryService, Depends(_get_service)],
) -> RetryExecuteResponse:
    """Execute a retry decision.

    Updates generation task retry count.
    """
    await _check_project_ownership(session, request.project_id, user_id)
    return await service.execute_retry_decision(request, session)


@router.get(
    "/quality-retry/reports/{report_id}",
    response_model=QualityReportResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Report not found"},
    },
)
async def get_report(
    report_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QualityRetryService, Depends(_get_service)],
) -> QualityReportResponse:
    """Get a quality report by ID."""
    report = await service.get_report(report_id, session)
    await _check_project_ownership(session, report.project_id, user_id)
    return report


@router.get(
    "/quality-retry/reports/project/{project_id}",
    response_model=list[QualityReportResponse],
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
)
async def list_project_reports(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QualityRetryService, Depends(_get_service)],
) -> list[QualityReportResponse]:
    """List all quality reports for a project."""
    await _check_project_ownership(session, project_id, user_id)
    return await service.list_reports(project_id, session)


@router.get(
    "/quality-retry/decisions/{decision_id}",
    response_model=RetryDecisionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Decision not found"},
    },
)
async def get_decision(
    decision_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[QualityRetryService, Depends(_get_service)],
) -> RetryDecisionResponse:
    """Get a retry decision by ID."""
    decision = await service.get_retry_decision(decision_id, session)
    await _check_project_ownership(session, decision.project_id, user_id)
    return decision
