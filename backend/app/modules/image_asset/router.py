"""FastAPI router for the Image Asset module.

Prefix: /api/image-asset
All endpoints require X-User-ID header.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import FORBIDDEN, NOT_FOUND, VALIDATION_ERROR
from app.db.session import get_session
from app.modules.image_asset.audit_service import ImageAssetAuditService
from app.modules.image_asset.deps import get_current_user_id
from app.modules.image_asset.library_service import ImageAssetLibraryService
from app.modules.image_asset.schemas import (
    BatchGenerateRequest,
    BatchGenerateResponse,
    ErrorResponse,
    GenerateAssetRequest,
    GenerateJobResponse,
    GenerationTaskResponse,
    ImageAssetAuditLogResponse,
    ImageAssetBatchOperationRequest,
    ImageAssetBatchOperationResponse,
    ImageAssetBatchPermanentDeleteRequest,
    ImageAssetLibraryQuery,
    ImageAssetLibraryResponse,
    ImageAssetOperationResult,
    ImageAssetResponse,
    ImageAssetTrashQuery,
    ImageAssetTrashResponse,
    QualityCallback,
)
from app.modules.image_asset.service import ImageAssetService, execute_generation_job
from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode
from app.modules.provider_adapter.fake import FakeSeedreamProvider
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.storage.service import StorageService

router = APIRouter(prefix="/api/image-asset", tags=["image-asset"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def _get_service() -> ImageAssetService:
    """Return an ImageAssetService wired to the configured providers."""
    registry = ProviderRegistry()
    try:
        image_provider = registry.get_image_generator()
    except Exception:
        # Fallback to fake for dev
        image_provider = FakeSeedreamProvider()
    if image_provider is None:
        image_provider = FakeSeedreamProvider()
    storage_service = StorageService.create()
    return ImageAssetService(
        image_provider=image_provider,
        storage_service=storage_service,
    )


def _get_library_service() -> ImageAssetLibraryService:
    return ImageAssetLibraryService(StorageService.create())


def _value_error_to_http_400(exc: ValueError) -> HTTPException:
    raw_message = str(exc.args[0])
    code, separator, _message = raw_message.partition(":")
    detail_code = code.strip() if separator else ""
    return HTTPException(
        status_code=400,
        detail={
            "code": detail_code or VALIDATION_ERROR.code,
            "message": raw_message,
            "retryable": False,
        },
    )


def _provider_error_to_http(exc: ProviderError) -> HTTPException:
    client_error_codes = {
        ProviderErrorCode.AUTH_FAILED,
        ProviderErrorCode.INVALID_REQUEST,
    }
    status_code = 400 if exc.code in client_error_codes else 502
    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code.value,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )


async def _check_project_ownership(
    session: AsyncSession,
    project_id: uuid.UUID,
    user_id: str,
) -> None:
    """Verify project exists and is owned by the current user."""
    from sqlalchemy import select as _select

    from app.modules.project.models import Project

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


# ---------------------------------------------------------------------------
# POST /api/image-asset/generate
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=ImageAssetResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def generate_asset(
    body: GenerateAssetRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> ImageAssetResponse:
    """Generate a single image asset.

    Supported asset types:
    - character_bible_sheet / character_front / character_turnaround / character_expression
    - scene_empty / scene_with_atmosphere
    - prop_product / prop_usage
    """
    await _check_project_ownership(session, body.project_id, user_id)

    try:
        result = await service.generate_asset(body, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc
    except ProviderError as exc:
        raise _provider_error_to_http(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "GENERATION_FAILED",
                "message": f"Image generation failed: {exc}",
                "retryable": True,
            },
        ) from exc

    return result


# ---------------------------------------------------------------------------
# POST /api/image-asset/generate-jobs
# ---------------------------------------------------------------------------


@router.post(
    "/generate-jobs",
    response_model=GenerateJobResponse,
    status_code=202,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_generation_job(
    body: GenerateAssetRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> GenerateJobResponse:
    """Create an async image generation job.

    Returns immediately with the task_id and a polling URL.
    The actual generation runs in the background.
    """
    await _check_project_ownership(session, body.project_id, user_id)

    try:
        task = await service.create_generation_job(body, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    task_id = task.id
    project_id = task.project_id
    await session.commit()

    # Schedule background execution — must NOT reuse the request's db session
    asyncio.create_task(execute_generation_job(str(task_id)))

    return GenerateJobResponse(
        task_id=task_id,
        project_id=project_id,
        status="pending",
        polling_url=f"/api/image-asset/tasks/{task_id}",
    )


# ---------------------------------------------------------------------------
# POST /api/image-asset/generate/batch
# ---------------------------------------------------------------------------


@router.post(
    "/generate/batch",
    response_model=BatchGenerateResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def generate_batch(
    body: BatchGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> BatchGenerateResponse:
    """Generate multiple image assets for a project.

    Each asset is generated independently. Partial failures are tolerated.
    """
    await _check_project_ownership(session, body.project_id, user_id)

    try:
        result = await service.generate_batch(body, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return result


# ---------------------------------------------------------------------------
# GET /api/image-asset/audit-logs
# ---------------------------------------------------------------------------


@router.get(
    "/audit-logs",
    response_model=ImageAssetAuditLogResponse,
    responses={
        400: {"model": ErrorResponse},
    },
)
async def list_image_asset_audit_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    project_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> ImageAssetAuditLogResponse:
    """List persisted image asset audit logs for the current user."""
    try:
        return await ImageAssetAuditService.list_logs(
            session,
            user_id=user_id,
            project_id=project_id,
            asset_id=asset_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc


# ---------------------------------------------------------------------------
# GET /api/image-asset/library
# ---------------------------------------------------------------------------


@router.get(
    "/library",
    response_model=ImageAssetLibraryResponse,
    responses={
        400: {"model": ErrorResponse},
    },
)
async def list_asset_library(
    filters: Annotated[ImageAssetLibraryQuery, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetLibraryResponse:
    try:
        return await service.list_library(session, user_id=user_id, filters=filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc


# ---------------------------------------------------------------------------
# GET /api/image-asset/trash
# ---------------------------------------------------------------------------


@router.get(
    "/trash",
    response_model=ImageAssetTrashResponse,
    responses={
        400: {"model": ErrorResponse},
    },
)
async def list_asset_trash(
    filters: Annotated[ImageAssetTrashQuery, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetTrashResponse:
    try:
        return await service.list_trash(session, user_id=user_id, filters=filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc


# ---------------------------------------------------------------------------
# POST /api/image-asset/batch-delete
# ---------------------------------------------------------------------------


@router.post("/batch-delete", response_model=ImageAssetBatchOperationResponse)
async def batch_delete_assets_to_trash(
    body: ImageAssetBatchOperationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetBatchOperationResponse:
    return await service.batch_soft_delete_assets(session, user_id=user_id, asset_ids=body.asset_ids)


# ---------------------------------------------------------------------------
# POST /api/image-asset/batch-restore
# ---------------------------------------------------------------------------


@router.post("/batch-restore", response_model=ImageAssetBatchOperationResponse)
async def batch_restore_assets_from_trash(
    body: ImageAssetBatchOperationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetBatchOperationResponse:
    return await service.batch_restore_assets(session, user_id=user_id, asset_ids=body.asset_ids)


# ---------------------------------------------------------------------------
# POST /api/image-asset/batch-permanent-delete
# ---------------------------------------------------------------------------


@router.post("/batch-permanent-delete", response_model=ImageAssetBatchOperationResponse)
async def batch_permanent_delete_assets(
    body: ImageAssetBatchPermanentDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetBatchOperationResponse:
    return await service.batch_permanent_delete_assets(session, user_id=user_id, requests=body.requests)


# ---------------------------------------------------------------------------
# DELETE /api/image-asset/{asset_id}
# ---------------------------------------------------------------------------


@router.delete("/{asset_id}", response_model=ImageAssetOperationResult)
async def delete_asset_to_trash(
    asset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetOperationResult:
    try:
        return await service.soft_delete_asset(session, asset_id=asset_id, user_id=user_id)
    except ValueError as exc:
        raise _value_error_to_http_400(exc) from exc


# ---------------------------------------------------------------------------
# POST /api/image-asset/{asset_id}/restore
# ---------------------------------------------------------------------------


@router.post("/{asset_id}/restore", response_model=ImageAssetOperationResult)
async def restore_asset_from_trash(
    asset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetOperationResult:
    try:
        return await service.restore_asset(session, asset_id=asset_id, user_id=user_id)
    except ValueError as exc:
        raise _value_error_to_http_400(exc) from exc


# ---------------------------------------------------------------------------
# DELETE /api/image-asset/{asset_id}/permanent
# ---------------------------------------------------------------------------


@router.delete("/{asset_id}/permanent", response_model=ImageAssetOperationResult)
async def permanent_delete_asset(
    asset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetLibraryService, Depends(_get_library_service)],
) -> ImageAssetOperationResult:
    try:
        return await service.permanent_delete_asset(
            session,
            asset_id=asset_id,
            user_id=user_id,
            reason="manual_permanent",
        )
    except ValueError as exc:
        raise _value_error_to_http_400(exc) from exc


# ---------------------------------------------------------------------------
# GET /api/image-asset/{asset_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{asset_id}",
    response_model=ImageAssetResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_asset(
    asset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> ImageAssetResponse:
    """Get asset details by ID."""
    try:
        return await service.get_asset(asset_id, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc


# ---------------------------------------------------------------------------
# GET /api/image-asset/tasks/{task_id}
# ---------------------------------------------------------------------------


@router.get(
    "/tasks/{task_id}",
    response_model=GenerationTaskResponse,
    responses={
        404: {"model": ErrorResponse},
    },
)
async def get_task(
    task_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> GenerationTaskResponse:
    """Get generation task status by ID."""
    try:
        response = await service.get_task(task_id, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc
    await _check_project_ownership(session, response.project_id, user_id)
    return response


# ---------------------------------------------------------------------------
# POST /api/image-asset/retry/{task_id}
# ---------------------------------------------------------------------------


@router.post(
    "/retry/{task_id}",
    response_model=ImageAssetResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def retry_task(
    task_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> ImageAssetResponse:
    """Retry a failed generation task (max 3 retries)."""
    try:
        task = await service.get_task(task_id, session)
        await _check_project_ownership(session, task.project_id, user_id)
        return await service.retry_task(task_id, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": VALIDATION_ERROR.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc
    except ProviderError as exc:
        raise _provider_error_to_http(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RETRY_FAILED",
                "message": f"Retry failed: {exc}",
                "retryable": True,
            },
        ) from exc


# ---------------------------------------------------------------------------
# POST /api/image-asset/quality-callback
# ---------------------------------------------------------------------------


@router.post(
    "/quality-callback",
    status_code=200,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def quality_callback(
    body: QualityCallback,
    session: Annotated[AsyncSession, Depends(get_session)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> dict[str, str]:
    """Receive quality results from M13 Vision Quality module.

    Marks generation tasks with quality status and triggers retry
    if M13 reports needs_retry.
    """
    try:
        await service.handle_quality_callback(body, session)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": NOT_FOUND.code,
                "message": str(exc.args[0]),
                "retryable": False,
            },
        ) from exc

    return {"status": "ok", "message": "Quality callback processed"}


# ---------------------------------------------------------------------------
# GET /api/image-asset/project/{project_id}
# ---------------------------------------------------------------------------


@router.get(
    "/project/{project_id}",
    response_model=list[ImageAssetResponse],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_project_assets(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
    asset_type: str | None = None,
) -> list[ImageAssetResponse]:
    """List all image assets for a project, optionally filtered by type."""
    await _check_project_ownership(session, project_id, user_id)

    return await service.list_project_assets(project_id, asset_type, session)


# ---------------------------------------------------------------------------
# GET /api/image-asset/project/{project_id}/by-type
# ---------------------------------------------------------------------------


@router.get(
    "/project/{project_id}/by-type",
    response_model=dict[str, list[ImageAssetResponse]],
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def list_assets_by_type(
    project_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    service: Annotated[ImageAssetService, Depends(_get_service)],
) -> dict[str, list[ImageAssetResponse]]:
    """List image assets grouped by asset_type."""
    await _check_project_ownership(session, project_id, user_id)

    all_assets = await service.list_project_assets(project_id, None, session)

    grouped: dict[str, list[ImageAssetResponse]] = {}
    for asset in all_assets:
        grouped.setdefault(asset.asset_type, []).append(asset)

    return grouped
