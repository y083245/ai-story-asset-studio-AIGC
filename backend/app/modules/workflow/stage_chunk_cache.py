"""Persistent cache for DeepSeek analysis stage chunks."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import async_session_factory
from app.modules.workflow.models import AnalysisStageChunk

logger = logging.getLogger("storyasset.stage_chunk_cache")


def build_stage_chunk_hash(
    *,
    chunk_text: str,
    style_id: str,
    module_id: str,
    template_text: str,
    json_contract: str,
    context: dict[str, Any] | None,
) -> str:
    payload = {
        "chunk_text": chunk_text,
        "style_id": style_id,
        "module_id": module_id,
        "template_text": template_text,
        "json_contract": json_contract,
        "context": context or {},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def load_stage_chunk_success(
    *,
    project_id: str | uuid.UUID,
    style_id: str,
    module_id: str,
    chunk_hash: str,
) -> dict[str, Any] | list[Any] | None:
    project_uuid = _coerce_project_uuid(project_id)
    if project_uuid is None:
        return None

    async with async_session_factory() as session:
        try:
            stmt = select(AnalysisStageChunk).where(
                AnalysisStageChunk.project_id == project_uuid,
                AnalysisStageChunk.style_id == style_id,
                AnalysisStageChunk.module_id == module_id,
                AnalysisStageChunk.chunk_hash == chunk_hash,
                AnalysisStageChunk.status == "success",
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.result_json if row is not None else None
        except SQLAlchemyError as exc:
            logger.warning(
                "Unable to read analysis stage chunk cache",
                extra={"project_id": str(project_id), "module_id": module_id, "error": str(exc)},
            )
            return None


async def save_stage_chunk_success(
    *,
    project_id: str | uuid.UUID,
    style_id: str,
    module_id: str,
    model_tier: str,
    chunk_index: int,
    chunk_hash: str,
    result: dict[str, Any] | list[Any],
    attempt: int,
) -> None:
    await _save_stage_chunk(
        project_id=project_id,
        style_id=style_id,
        module_id=module_id,
        model_tier=model_tier,
        chunk_index=chunk_index,
        chunk_hash=chunk_hash,
        status="success",
        result=result,
        error=None,
        attempt=attempt,
    )


async def save_stage_chunk_failure(
    *,
    project_id: str | uuid.UUID,
    style_id: str,
    module_id: str,
    model_tier: str,
    chunk_index: int,
    chunk_hash: str,
    error: str,
    attempt: int,
) -> None:
    await _save_stage_chunk(
        project_id=project_id,
        style_id=style_id,
        module_id=module_id,
        model_tier=model_tier,
        chunk_index=chunk_index,
        chunk_hash=chunk_hash,
        status="failed",
        result=None,
        error=error,
        attempt=attempt,
    )


async def _save_stage_chunk(
    *,
    project_id: str | uuid.UUID,
    style_id: str,
    module_id: str,
    model_tier: str,
    chunk_index: int,
    chunk_hash: str,
    status: str,
    result: dict[str, Any] | list[Any] | None,
    error: str | None,
    attempt: int,
) -> None:
    project_uuid = _coerce_project_uuid(project_id)
    if project_uuid is None:
        return

    async with async_session_factory() as session:
        try:
            stmt = select(AnalysisStageChunk).where(
                AnalysisStageChunk.project_id == project_uuid,
                AnalysisStageChunk.style_id == style_id,
                AnalysisStageChunk.module_id == module_id,
                AnalysisStageChunk.chunk_hash == chunk_hash,
            )
            query_result = await session.execute(stmt)
            row = query_result.scalar_one_or_none()
            if row is None:
                row = AnalysisStageChunk(
                    project_id=project_uuid,
                    style_id=style_id,
                    module_id=module_id,
                    model_tier=model_tier,
                    chunk_index=chunk_index,
                    chunk_hash=chunk_hash,
                )
                session.add(row)
            row.model_tier = model_tier
            row.chunk_index = chunk_index
            row.status = status
            row.result_json = result
            row.error = error
            row.attempt = attempt
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.warning(
                "Unable to write analysis stage chunk cache",
                extra={"project_id": str(project_id), "module_id": module_id, "error": str(exc)},
            )


def _coerce_project_uuid(value: str | uuid.UUID) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
