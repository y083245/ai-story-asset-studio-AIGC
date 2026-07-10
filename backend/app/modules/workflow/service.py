"""WorkflowService — business logic layer for workflow API endpoints.

Manages workflow state in the database and delegates orchestration
to the FakeWorkflowRunner.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.modules.workflow.models import WorkflowState
from app.modules.workflow.normalizers.genre import normalize_confidence
from app.modules.workflow.publication import AnalysisPublicationService
from app.modules.workflow.runner import (
    ActivityRecord,
    FakeWorkflowRunner,
    WorkflowCancelledError,
    activity_input_hash,
)
from app.modules.workflow.schemas import (
    ActivityState,
    WorkflowContext,
    WorkflowStatusResponse,
)
from app.modules.workflow.workflows import (
    AssetGenerationWorkflow,
    ProjectAnalyzeWorkflow,
    ProjectFullGenerationWorkflow,
)

logger = logging.getLogger("storyasset.workflow")


class WorkflowAnalysisNotReadyError(ValueError):
    """Raised when analysis exists but is not ready for consumption."""


class WorkflowAnalysisFailedError(ValueError):
    """Raised when analysis workflow failed before producing a result."""


class WorkflowService:
    """Stateless service for managing workflow execution.

    Each method receives a session and returns domain objects or dicts.
    The router layer converts to Pydantic response schemas.
    """

    # Map workflow type → workflow class
    _WORKFLOW_CLASSES: dict[str, type] = {
        "analyze": ProjectAnalyzeWorkflow,
        "asset": AssetGenerationWorkflow,
        "full": ProjectFullGenerationWorkflow,
    }
    _ORPHANED_RUNNING_TIMEOUT_SECONDS = 300
    _ORPHANED_RUNNING_ERROR = "工作流运行中断，请重新开始分析"

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    @staticmethod
    async def get_or_create_state(session: AsyncSession, project_id: uuid.UUID, workflow_type: str) -> WorkflowState:
        """Get existing workflow state or create a new one.

        Uses SELECT-then-INSERT with IntegrityError handling to avoid
        UniqueViolationError when two requests race on the same project_id.
        """
        # Fast path: already exists in this session
        stmt = select(WorkflowState).where(WorkflowState.project_id == project_id)
        result = await session.execute(stmt)
        state = result.scalar_one_or_none()
        if state is not None:
            return state

        # Slow path: create new state, handling concurrent inserts
        state = WorkflowState(
            project_id=project_id,
            workflow_type=workflow_type,
            current_stage="idle",
            progress=0.0,
            message="",
            status="pending",
        )
        session.add(state)
        try:
            await session.flush()
        except IntegrityError:
            # Another request created the state between our SELECT and INSERT.
            # Rollback the failed insert and reload the winner.
            await session.rollback()
            stmt2 = select(WorkflowState).where(WorkflowState.project_id == project_id)
            result2 = await session.execute(stmt2)
            state = result2.scalar_one()
            logger.info(
                "Detected concurrent insert for project_id=%s, reusing existing state",
                str(project_id),
            )
        return state

    @staticmethod
    async def get_state(session: AsyncSession, project_id: uuid.UUID) -> WorkflowState | None:
        """Get the workflow state for a project, if it exists."""
        stmt = select(WorkflowState).where(WorkflowState.project_id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_state(
        session: AsyncSession,
        project_id: uuid.UUID,
        *,
        current_stage: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        status: str | None = None,
        error: str | None = None,
        error_stage: str | None = None,
    ) -> WorkflowState:
        """Update fields on an existing workflow state."""
        state = await WorkflowService._require_state(session, project_id)

        if current_stage is not None:
            state.current_stage = current_stage
        if progress is not None:
            state.progress = progress
        if message is not None:
            state.message = message
        if status is not None:
            state.status = status
        if error is not None:
            state.error = error
        if error_stage is not None:
            state.error_stage = error_stage

        await session.flush()
        return state

    # ------------------------------------------------------------------
    # Workflow execution
    # ------------------------------------------------------------------

    @staticmethod
    async def start_workflow(
        session: AsyncSession,
        project_id: uuid.UUID,
        workflow_type: str,
        context: WorkflowContext,
        activities: dict[str, Any] | None = None,
    ) -> WorkflowState:
        """Start a workflow and return the initial state.

        Workflows run through the local FakeWorkflowRunner in the default
        development and Docker setup.
        """
        workflow_cls = WorkflowService._WORKFLOW_CLASSES.get(workflow_type)
        if workflow_cls is None:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        state = await WorkflowService.get_or_create_state(session, project_id, workflow_type)
        resumable_task_states = WorkflowService.prepare_task_states_for_start(workflow_type, state.task_states)
        state.workflow_type = workflow_type
        state.status = "running"
        state.current_stage = "starting"
        state.progress = 0.0
        state.message = f"Starting {workflow_type} workflow..."
        state.task_states = resumable_task_states
        state.error = None
        state.error_stage = None
        state.awaiting_signal = None
        state.signal_data = None
        await session.flush()
        await session.commit()
        template_fingerprint = _analysis_template_fingerprint() if workflow_type == "analyze" else ""

        runner = FakeWorkflowRunner(activities)
        replay_history = _activity_history_from_task_states(resumable_task_states)
        if replay_history:
            runner.enable_replay(replay_history)
        WorkflowService._active_runners[project_id] = runner

        # Progress callback that writes to DB via an independent session so
        # polling requests can see real-time progress immediately.
        async def on_progress(stage: str, progress: float, message: str) -> None:
            async with async_session_factory() as prog_session:
                try:
                    await WorkflowService.update_state(
                        prog_session,
                        project_id,
                        current_stage=stage,
                        progress=progress,
                        message=message,
                    )
                    await prog_session.commit()
                except Exception:
                    await prog_session.rollback()

        runner.set_progress_callback(on_progress)

        async def on_activity(
            activity_name: str,
            status: str,
            attempt: int,
            result: dict[str, Any] | None,
            error: str | None,
            input_hash: str,
        ) -> None:
            async with async_session_factory() as activity_session:
                try:
                    activity_state = await WorkflowService._require_state(activity_session, project_id)
                    task_states = dict(activity_state.task_states or {})
                    entry = {
                        "status": status,
                        "attempt": attempt,
                        "error": error,
                        "input_hash": input_hash,
                    }
                    if template_fingerprint:
                        entry["template_fingerprint"] = template_fingerprint
                    if status == "success" and result is not None:
                        entry["result"] = result
                    result_summary = _activity_result_summary(result)
                    if result_summary is not None:
                        entry["result_summary"] = result_summary
                    task_states[activity_name] = entry
                    activity_state.task_states = task_states
                    await activity_session.flush()
                    await activity_session.commit()
                except Exception:
                    await activity_session.rollback()

        if hasattr(runner, "set_activity_callback"):
            runner.set_activity_callback(on_activity)

        workflow = workflow_cls()

        try:
            final_context = await runner.execute_workflow(workflow, context)
            task_states = dict(state.task_states or {})
            for record in runner.get_history():
                input_hash = str(record.input_params.get("__input_hash") or activity_input_hash(record.input_params))
                entry: dict[str, Any] = {
                    "status": "success" if record.error is None else "failed",
                    "attempt": record.attempts,
                    "result": record.result,
                    "error": record.error,
                    "input_hash": input_hash,
                }
                if template_fingerprint:
                    entry["template_fingerprint"] = template_fingerprint
                task_states[record.activity_name] = {
                    **entry,
                }
            if workflow_type in {"analyze", "full"}:
                publish_summary = await AnalysisPublicationService.publish(
                    session,
                    project_id,
                    final_context,
                    generate_images=False,
                )
                task_states["publish_analysis"] = {
                    "status": "success",
                    "attempt": 1,
                    "result": publish_summary,
                    "error": None,
                }
            task_states["_context"] = {
                "status": "success",
                "attempt": 1,
                "result": final_context,
            }
            state.task_states = task_states
            await WorkflowService.update_state(
                session,
                project_id,
                current_stage="completed",
                status="completed",
                progress=1.0,
                message="工作流已完成",
            )
        except WorkflowCancelledError:
            logger.info("Workflow cancelled for project_id=%s", str(project_id))
            await WorkflowService.update_state(
                session,
                project_id,
                status="cancelled",
                message="工作流已取消",
            )
        except Exception as exc:
            failed_stage = str(state.__dict__.get("current_stage") or "unknown")
            logger.exception(
                "Workflow failed for project_id=%s at stage=%s: %s",
                str(project_id),
                failed_stage,
                exc,
            )
            with contextlib.suppress(Exception):
                await session.rollback()
            state = await WorkflowService.get_or_create_state(session, project_id, workflow_type)
            if failed_stage == "unknown":
                failed_stage = state.current_stage
            public_error = _public_workflow_error(str(exc))
            await WorkflowService.update_state(
                session,
                project_id,
                status="failed",
                error=public_error,
                error_stage=failed_stage,
                message=f"工作流失败: {public_error}",
            )
        finally:
            WorkflowService._active_runners.pop(project_id, None)

        await session.refresh(state)
        return state

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    _active_runners: dict[uuid.UUID, FakeWorkflowRunner] = {}

    @staticmethod
    async def cancel_workflow(
        session: AsyncSession, project_id: uuid.UUID, reason: str = "user_cancelled"
    ) -> WorkflowState:
        """Cancel a running workflow (M15-13)."""
        state = await WorkflowService._require_state(session, project_id)

        if state.status not in ("pending", "running"):
            raise ValueError(f"Cannot cancel workflow in status '{state.status}'")

        # Signal the runner if it's active
        runner = WorkflowService._active_runners.pop(project_id, None)
        if runner is not None:
            runner.cancel(reason)

        state.status = "cancelled"
        state.message = "工作流已取消"
        state.error = reason
        await session.flush()
        return state

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    @staticmethod
    async def send_signal(
        session: AsyncSession,
        project_id: uuid.UUID,
        signal_name: str,
        data: dict[str, Any],
    ) -> WorkflowState:
        """Send a signal to a waiting workflow (M15-05)."""
        state = await WorkflowService._require_state(session, project_id)

        runner = WorkflowService._active_runners.get(project_id)
        if runner is not None:
            runner.send_signal(signal_name, data)

        state.awaiting_signal = None
        state.signal_data = data
        await session.flush()
        return state

    # ------------------------------------------------------------------
    # Status query
    # ------------------------------------------------------------------

    @staticmethod
    async def get_workflow_status(session: AsyncSession, project_id: uuid.UUID) -> WorkflowStatusResponse:
        """Build a full workflow status response."""
        state = await WorkflowService._require_state(session, project_id)
        await WorkflowService._mark_orphaned_running_state(session, state)

        activities: list[ActivityState] = [
            ActivityState(
                activity_name=name,
                status=entry.get("status", "unknown"),
                attempt=entry.get("attempt", 0),
                error=entry.get("error"),
                result_summary=entry.get("result_summary"),
            )
            for name, entry in state.task_states.items()
        ]

        return WorkflowStatusResponse(
            project_id=str(state.project_id),
            workflow_type=state.workflow_type,
            status=state.status,
            current_stage=state.current_stage,
            progress=state.progress,
            message=state.message,
            awaiting_signal=state.awaiting_signal,
            error=state.error,
            error_stage=state.error_stage,
            activities=activities,
        )

    @staticmethod
    async def get_analysis(session: AsyncSession, project_id: uuid.UUID) -> dict[str, Any]:
        """Build frontend analysis data from the completed analyze workflow context."""
        state = await WorkflowService._require_state(session, project_id)
        context = _analysis_context_from_state(state)
        if context is not None:
            return _analysis_response_from_context(project_id, context)

        saved_analysis = await _analysis_response_from_story_bible(session, project_id)
        if saved_analysis is not None:
            return saved_analysis

        if state.status == "failed":
            raise WorkflowAnalysisFailedError(_public_analysis_error(state.error or state.message))
        if state.status != "completed":
            raise WorkflowAnalysisNotReadyError("故事分析尚未完成，请稍后重试")
        raise WorkflowAnalysisNotReadyError("故事分析结果尚未生成，请重新开始分析")

    @staticmethod
    def has_saved_analysis_result(state: WorkflowState) -> bool:
        """Return True when workflow state still carries a completed analysis context."""
        return _analysis_context_from_state(state) is not None

    @staticmethod
    async def has_persisted_analysis_result(session: AsyncSession, project_id: uuid.UUID) -> bool:
        """Return True when completed analysis has been published into business tables."""
        return await _analysis_response_from_story_bible(session, project_id) is not None

    @staticmethod
    def prepare_task_states_for_start(workflow_type: str, task_states: dict[str, Any] | None) -> dict[str, Any]:
        """Keep only completed analysis activity results that can be replayed after interruption."""
        if workflow_type != "analyze":
            return {}
        return _resumable_analysis_task_states(task_states)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_state(session: AsyncSession, project_id: uuid.UUID) -> WorkflowState:
        """Fetch workflow state or raise ValueError."""
        state = await WorkflowService.get_state(session, project_id)
        if state is None:
            raise ValueError(f"No workflow state found for project {project_id!s}")
        return state

    @staticmethod
    async def _mark_orphaned_running_state(session: AsyncSession, state: WorkflowState) -> None:
        """Fail a stale running state when its in-memory runner no longer exists."""
        if state.status != "running":
            return
        if state.project_id in WorkflowService._active_runners:
            return
        updated_at = state.updated_at
        if updated_at is None:
            return
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
        if age_seconds < WorkflowService._ORPHANED_RUNNING_TIMEOUT_SECONDS:
            return

        state.status = "failed"
        state.error = WorkflowService._ORPHANED_RUNNING_ERROR
        state.error_stage = state.current_stage
        state.message = WorkflowService._ORPHANED_RUNNING_ERROR
        await session.flush()


def _analysis_context_from_state(state: WorkflowState) -> dict[str, Any] | None:
    task_states = state.task_states if isinstance(getattr(state, "task_states", None), dict) else {}
    context_entry = task_states.get("_context", {})
    if not isinstance(context_entry, dict):
        return None
    context = context_entry.get("result")
    if isinstance(context, dict) and context:
        return context
    return None


def _resumable_analysis_task_states(task_states: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(task_states, dict):
        return {}
    current_template_fingerprint = _analysis_template_fingerprint()
    resumable: dict[str, Any] = {}
    for activity_name, raw_entry in task_states.items():
        if activity_name.startswith("_") or activity_name == "publish_analysis":
            continue
        if not isinstance(raw_entry, dict) or raw_entry.get("status") != "success":
            continue
        result = raw_entry.get("result")
        if not isinstance(result, dict):
            continue
        input_hash = raw_entry.get("input_hash")
        if not isinstance(input_hash, str) or not input_hash:
            continue
        if raw_entry.get("template_fingerprint") != current_template_fingerprint:
            continue
        entry: dict[str, Any] = {
            "status": "success",
            "attempt": _int_value(raw_entry.get("attempt"), 1),
            "result": result,
            "error": None,
            "input_hash": input_hash,
            "template_fingerprint": current_template_fingerprint,
        }
        summary = raw_entry.get("result_summary")
        entry["result_summary"] = summary if isinstance(summary, dict) else _activity_result_summary(result)
        resumable[activity_name] = entry
    return resumable


def _activity_history_from_task_states(task_states: dict[str, Any]) -> list[ActivityRecord]:
    history: list[ActivityRecord] = []
    for activity_name, raw_entry in task_states.items():
        if not isinstance(raw_entry, dict) or raw_entry.get("status") != "success":
            continue
        result = raw_entry.get("result")
        if not isinstance(result, dict):
            continue
        input_hash = raw_entry.get("input_hash")
        if not isinstance(input_hash, str) or not input_hash:
            continue
        history.append(
            ActivityRecord(
                activity_name=activity_name,
                input_params={"__input_hash": input_hash},
                result=result,
                attempts=_int_value(raw_entry.get("attempt"), 1),
            )
        )
    return history


def _analysis_template_fingerprint() -> str:
    current = Path(__file__).resolve()
    style_root: Path | None = None
    docs_root: Path | None = None
    for parent in current.parents:
        candidate = parent / "templates" / "style_packs"
        if candidate.exists():
            style_root = candidate
        docs_candidate = parent / "docs"
        if docs_candidate.exists():
            docs_root = docs_candidate
        if style_root is not None and docs_root is not None:
            break
    if style_root is None and docs_root is None:
        fallback = current.parents[4]
        return hashlib.sha256(str(fallback).encode("utf-8")).hexdigest()

    payload: list[dict[str, str]] = []
    if style_root is not None:
        for path in sorted(style_root.glob("*/*.json")):
            payload.append(
                {
                    "root": "templates/style_packs",
                    "path": str(path.relative_to(style_root)),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
    if docs_root is not None:
        for path in sorted(docs_root.glob("*/*_高质量提示词模板.txt")):
            payload.append(
                {
                    "root": "docs",
                    "path": str(path.relative_to(docs_root)),
                    "content": path.read_text(encoding="utf-8"),
                }
            )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _analysis_response_from_story_bible(session: AsyncSession, project_id: uuid.UUID) -> dict[str, Any] | None:
    from app.modules.story_bible.service import StoryBibleService

    bible = await StoryBibleService.get_bible(session, project_id)
    if bible is None:
        return None

    story_bible = {
        "story_summary": str(getattr(bible, "story_summary", "") or "故事分析已完成"),
        "main_conflict": str(getattr(bible, "main_conflict", "") or "待从故事设定中确认"),
        "emotional_tone": str(getattr(bible, "emotional_tone", "") or "剧情向"),
        "world_setting": str(getattr(bible, "world_setting", "") or "待确认"),
        "time_period": str(getattr(bible, "time_period", "") or "现代"),
        "color_palette": list(getattr(bible, "color_palette", None) or []),
        "composition_language": list(getattr(bible, "composition_language", None) or []),
    }
    return _analysis_response_from_parts(
        project_id=project_id,
        genre=str(getattr(bible, "genre", "") or ""),
        visual_style=str(getattr(bible, "visual_style", "") or "智能识别风格"),
        style_confidence=1.0,
        story_bible=story_bible,
        characters=_as_list(getattr(bible, "characters", None)),
        scenes=_as_list(getattr(bible, "scenes", None)),
        props=_as_list(getattr(bible, "props", None)),
    )


def _analysis_response_from_context(project_id: uuid.UUID, context: dict[str, Any]) -> dict[str, Any]:
    genre_result = context.get("genre_result", {}) if isinstance(context.get("genre_result"), dict) else {}
    story_bible = context.get("story_bible", {}) if isinstance(context.get("story_bible"), dict) else {}
    return _analysis_response_from_parts(
        project_id=project_id,
        genre=str(genre_result.get("genre", "")),
        visual_style=" / ".join(str(tag) for tag in _as_list(genre_result.get("style_tags"))) or "智能识别风格",
        style_confidence=normalize_confidence(genre_result.get("confidence")),
        story_bible=story_bible,
        characters=_as_list(context.get("characters")),
        scenes=_as_list(context.get("scenes")),
        props=_as_list(context.get("props")),
    )


def _analysis_response_from_parts(
    *,
    project_id: uuid.UUID,
    genre: str,
    visual_style: str,
    style_confidence: float,
    story_bible: dict[str, Any],
    characters: list[Any],
    scenes: list[Any],
    props: list[Any],
) -> dict[str, Any]:
    character_refs = [_character_ref(item, index + 1) for index, item in enumerate(characters)]
    scene_refs = [_scene_ref(item, index + 1) for index, item in enumerate(scenes)]
    prop_refs = [_prop_ref(item, index + 1) for index, item in enumerate(props)]

    return {
        "project_id": str(project_id),
        "genre": genre,
        "visual_style": visual_style,
        "style_confidence": normalize_confidence(style_confidence),
        "story_summary": str(story_bible.get("story_summary", "故事分析已完成")),
        "main_conflict": str(story_bible.get("main_conflict", "待从故事设定中确认")),
        "protagonist": character_refs[0] if character_refs else _character_ref({}, 1),
        "emotional_tone": str(story_bible.get("emotional_tone", "剧情向")),
        "world_setting": str(story_bible.get("world_setting", "待确认")),
        "time_period": str(story_bible.get("time_period", "现代")),
        "characters": character_refs,
        "scenes": scene_refs,
        "props": prop_refs,
        "color_palette": _as_string_list(story_bible.get("color_palette")) or ["#1f2937", "#2563eb", "#f8fafc"],
        "composition_language": _as_string_list(story_bible.get("composition_language")) or ["正面参考", "空场景", "单品图"],
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value)]


def _public_analysis_error(message: str | None) -> str:
    if not message:
        return "故事分析失败，请重新开始分析"
    if "JSON" in message or "json" in message or "DeepSeek did not return" in message:
        return "AI 故事分析返回不完整结果，请重新开始分析"
    return message


def _public_workflow_error(message: str | None) -> str:
    if not message:
        return "工作流失败，请重新开始"
    if "INSERT INTO" in message or "parameters" in message or "asyncpg" in message or "DataError" in message:
        return "分析结果写入失败，请重新开始分析"
    if "JSON" in message or "json" in message or "DeepSeek did not return" in message:
        return "AI 故事分析返回不完整结果，请重新开始分析"
    return message[:300]


def _activity_result_summary(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    summary: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, list):
            summary[key] = len(value)
        elif isinstance(value, dict):
            summary[key] = sorted(str(item) for item in value)[:12]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            summary[key] = value if not isinstance(value, str) else value[:120]
    return summary


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _character_ref(item: Any, index: int) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {}
    traits = "、".join(str(trait) for trait in _as_list(data.get("traits")))
    return {
        "character_id": str(data.get("character_id") or f"CH_{index:03d}"),
        "name": str(data.get("name") or "未命名角色"),
        "description": str(data.get("description") or traits or data.get("role") or "角色描述待完善"),
        "role": str(data.get("role") or "supporting"),
        "gender": data.get("gender"),
        "age_range": str(data.get("age_range") or data.get("age") or ""),
    }


def _scene_ref(item: Any, index: int) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {}
    fixed_anchors = _as_string_list(data.get("fixed_anchors")) or [
        str(value) for value in (data.get("type"), data.get("time")) if value
    ]
    return {
        "scene_id": str(data.get("scene_id") or f"SC_{index:03d}"),
        "name": str(data.get("name") or data.get("scene_name") or "未命名场景"),
        "description": str(data.get("description") or data.get("type") or "场景描述待完善"),
        "time_period": str(data.get("time") or ""),
        "mood": str(data.get("mood") or ""),
        "fixed_anchors": fixed_anchors,
    }


def _prop_ref(item: Any, index: int) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {}
    return {
        "prop_id": str(data.get("prop_id") or f"PR_{index:03d}"),
        "name": str(data.get("name") or "未命名道具"),
        "description": str(data.get("description") or "道具描述待完善"),
        "function": str(data.get("function") or data.get("importance") or data.get("type") or "关键道具"),
        "state_timeline": _as_string_list(data.get("state_timeline")),
    }
