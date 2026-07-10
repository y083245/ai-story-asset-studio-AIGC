"""Workflow API routes."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.errors import ANALYSIS_FAILED, ANALYSIS_NOT_READY, NOT_FOUND, PROJECT_LOCKED
from app.db.session import async_session_factory, get_session
from app.modules.novel_intake.service import NovelIntakeService
from app.modules.project.schemas import ErrorDetail, ErrorResponse
from app.modules.workflow.analysis_activities import create_analysis_activities
from app.modules.workflow.deps import get_current_user_id, verify_project_ownership
from app.modules.workflow.fake_activities import create_default_fake_activities
from app.modules.workflow.schemas import (
    CancelRequest,
    GenerateAssetsRequest,
    GenerateRequest,
    SignalRequest,
    WorkflowCancelledResponse,
    WorkflowContext,
    WorkflowStartedResponse,
    WorkflowStartRequest,
    WorkflowStatusResponse,
)
from app.modules.workflow.service import WorkflowAnalysisFailedError, WorkflowAnalysisNotReadyError, WorkflowService

router = APIRouter(prefix="/api", tags=["workflow"])
logger = logging.getLogger("storyasset.workflow.router")


def _error_response(code: Any, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(error=ErrorDetail(code=code.code, message=message, retryable=code.retryable)).model_dump()[
            "error"
        ],
    )


def _workflow_start_message(status: str, message: str) -> str:
    if status == "failed" and ("JSON" in message or "json" in message or "DeepSeek did not return" in message):
        return "AI 故事分析返回不完整结果，请重新开始分析"
    return message


@router.post(
    "/projects/{project_id}/analyze",
    response_model=WorkflowStartedResponse,
    status_code=202,
    responses={404: {"model": ErrorResponse}},
)
async def start_analyze(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    background_tasks: BackgroundTasks,
    body: WorkflowStartRequest | None = None,  # noqa: ARG001
) -> WorkflowStartedResponse:
    state = await WorkflowService.get_or_create_state(session, project_id, "analyze")
    if state.status == "completed" and (
        WorkflowService.has_saved_analysis_result(state)
        or await WorkflowService.has_persisted_analysis_result(session, project_id)
    ):
        return WorkflowStartedResponse(
            project_id=str(project_id),
            workflow_type="analyze",
            status=state.status,
            message=_workflow_start_message(state.status, state.message or "工作流已完成"),
        )
    if state.status == "running" and state.workflow_type == "analyze":
        return WorkflowStartedResponse(
            project_id=str(project_id),
            workflow_type="analyze",
            status=state.status,
            message=_workflow_start_message(state.status, state.message or "分析正在进行中"),
        )

    novel = await NovelIntakeService.get_novel_by_project(session, project_id)
    clean_text = novel.clean_text if novel is not None else ""

    state.workflow_type = "analyze"
    state.status = "running"
    state.current_stage = "starting"
    state.progress = 0.0
    state.message = "分析已开始"
    state.error = None
    state.error_stage = None
    state.task_states = WorkflowService.prepare_task_states_for_start("analyze", state.task_states)
    await session.flush()
    await session.commit()

    background_tasks.add_task(_run_analysis_workflow_background, project_id, user_id, clean_text)

    return WorkflowStartedResponse(
        project_id=str(project_id),
        workflow_type="analyze",
        status=state.status,
        message=_workflow_start_message(state.status, state.message),
    )


async def _run_analysis_workflow_background(project_id: uuid.UUID, user_id: str, novel_text: str) -> None:
    try:
        context = WorkflowContext(project_id=str(project_id), user_id=user_id, novel_text=novel_text)
        activities = create_analysis_activities()
        async with async_session_factory() as session:
            await WorkflowService.start_workflow(session, project_id, "analyze", context, activities)
            await session.commit()
    except Exception:
        logger.exception("Background analysis task crashed for project_id=%s", project_id)


@router.get(
    "/projects/{project_id}/analysis",
    response_model=dict[str, Any],
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def get_analysis(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    try:
        return await WorkflowService.get_analysis(session, project_id)
    except WorkflowAnalysisFailedError as exc:
        raise _error_response(ANALYSIS_FAILED, str(exc), 409) from exc
    except WorkflowAnalysisNotReadyError as exc:
        raise _error_response(ANALYSIS_NOT_READY, str(exc), 409) from exc
    except ValueError as exc:
        raise _error_response(NOT_FOUND, str(exc), 404) from exc


@router.post(
    "/projects/{project_id}/generate-assets",
    response_model=WorkflowStartedResponse,
    status_code=202,
    responses={404: {"model": ErrorResponse}},
)
async def start_generate_assets(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    body: GenerateAssetsRequest | None = None,  # noqa: ARG001
) -> WorkflowStartedResponse:
    state = await WorkflowService.get_or_create_state(session, project_id, "asset")
    context = WorkflowContext(
        project_id=str(project_id),
        user_id=user_id,
        characters=state.task_states.get("extract_characters", {}).get("result", {}).get("characters", []),
        scenes=state.task_states.get("extract_scenes", {}).get("result", {}).get("scenes", []),
        props=state.task_states.get("extract_props", {}).get("result", {}).get("props", []),
    )
    state = await WorkflowService.start_workflow(session, project_id, "asset", context, create_default_fake_activities())
    return WorkflowStartedResponse(
        project_id=str(project_id),
        workflow_type="asset",
        status=state.status,
        message=state.message,
    )


@router.post(
    "/projects/{project_id}/generate",
    response_model=WorkflowStartedResponse,
    status_code=202,
    responses={404: {"model": ErrorResponse}},
)
async def start_full_generation(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    body: GenerateRequest | None = None,  # noqa: ARG001
) -> WorkflowStartedResponse:
    novel = await NovelIntakeService.get_novel_by_project(session, project_id)
    clean_text = novel.clean_text if novel is not None else ""
    context = WorkflowContext(project_id=str(project_id), user_id=user_id, novel_text=clean_text)
    state = await WorkflowService.start_workflow(session, project_id, "full", context, create_default_fake_activities())
    return WorkflowStartedResponse(
        project_id=str(project_id),
        workflow_type="full",
        status=state.status,
        message=state.message,
    )


@router.post(
    "/projects/{project_id}/cancel",
    response_model=WorkflowCancelledResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def cancel_workflow(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: CancelRequest | None = None,
) -> WorkflowCancelledResponse:
    reason = body.reason if body else "user_cancelled"
    try:
        state = await WorkflowService.cancel_workflow(session, project_id, reason)
    except ValueError as exc:
        raise _error_response(PROJECT_LOCKED, str(exc), 409) from exc
    return WorkflowCancelledResponse(project_id=str(project_id), status=state.status, message=state.message)


@router.post(
    "/projects/{project_id}/signal",
    responses={404: {"model": ErrorResponse}},
)
async def send_signal(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: SignalRequest,
) -> dict[str, Any]:
    try:
        await WorkflowService.send_signal(session, project_id, body.signal_name, body.data)
    except ValueError as exc:
        raise _error_response(NOT_FOUND, str(exc), 404) from exc
    return {
        "project_id": str(project_id),
        "signal_name": body.signal_name,
        "received": True,
        "message": f"Signal '{body.signal_name}' sent successfully",
    }


@router.get(
    "/projects/{project_id}/workflow-status",
    response_model=WorkflowStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_workflow_status(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkflowStatusResponse:
    try:
        return await WorkflowService.get_workflow_status(session, project_id)
    except ValueError as exc:
        raise _error_response(NOT_FOUND, str(exc), 404) from exc
