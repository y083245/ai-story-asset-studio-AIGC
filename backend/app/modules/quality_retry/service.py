"""Image quality inspection and retry decisions."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.contracts.errors import NEEDS_REVIEW, NOT_FOUND
from app.modules.provider_adapter.base import VisionQualityProvider
from app.modules.quality_retry.image_quality import check_image_quality
from app.modules.quality_retry.models import QualityReport, RetryDecision
from app.modules.quality_retry.retry_patches import build_retry_patches
from app.modules.quality_retry.schemas import (
    ImageQualityRequest,
    IssueItem,
    QualityReportResponse,
    RetryDecisionResponse,
    RetryExecuteRequest,
    RetryExecuteResponse,
)

MAX_AUTO_FIXES = 2


def _build_issue_items(issues: list[dict[str, Any]]) -> list[IssueItem]:
    return [
        IssueItem(
            code=str(issue.get("code", "")),
            dimension=str(issue.get("dimension", "unknown")),
            description=str(issue.get("description", "")),
            score=issue.get("score"),
            threshold=issue.get("threshold"),
            severity=str(issue.get("severity", "warning")),
        )
        for issue in issues
    ]


async def _get_existing_retry_count(db: AsyncSession, generation_task_id: uuid.UUID) -> int:
    result = await db.execute(
        text("SELECT retry_count FROM image_generation_tasks WHERE id = :tid"),
        {"tid": generation_task_id},
    )
    row = result.fetchone()
    return int(row[0]) if row is not None else 0


async def _update_task_retry_count(db: AsyncSession, task_id: uuid.UUID, retry_count: int) -> None:
    await db.execute(
        text("UPDATE image_generation_tasks SET retry_count = :rc WHERE id = :tid"),
        {"rc": retry_count, "tid": task_id},
    )


def _build_report_response(report: QualityReport) -> QualityReportResponse:
    return QualityReportResponse(
        report_id=report.id,
        project_id=report.project_id,
        related_id=report.related_id,
        asset_id=report.asset_id,
        asset_type=report.asset_type,
        generation_task_id=report.generation_task_id,
        quality_score=report.quality_score,
        face_consistency_score=report.face_consistency_score,
        outfit_consistency_score=report.outfit_consistency_score,
        scene_consistency_score=report.scene_consistency_score,
        prop_presence_score=report.prop_presence_score,
        composition_score=report.composition_score,
        issues=_build_issue_items(report.issues),
        retry_required=report.retry_required,
        retry_prompt_patch=report.retry_prompt_patch,
        needs_review=report.needs_review,
        retry_decision_id=None,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


class QualityRetryService:
    """Service for image quality inspection and retry decision management."""

    def __init__(self, vision_provider: VisionQualityProvider | None = None) -> None:
        self._vision_provider = vision_provider

    async def _get_or_default_provider(self) -> VisionQualityProvider:
        if self._vision_provider is not None:
            return self._vision_provider
        from app.modules.provider_adapter.registry import ProviderRegistry

        return ProviderRegistry().get_vision_quality()

    async def inspect_image(self, request: ImageQualityRequest, db: AsyncSession) -> QualityReportResponse:
        provider = await self._get_or_default_provider()
        result = await check_image_quality(
            image_bytes=request.image_bytes or b"",
            reference_character_images=[],
            reference_scene_image=None,
            expected_props=request.expected_props,
            vision_provider=provider,
            check_dimensions=request.check_dimensions,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            asset_bible=request.asset_bible,
            style_keywords=request.style_keywords,
            retry_history=request.retry_history,
            metadata={
                "project_id": str(request.project_id),
                "asset_id": str(request.asset_id),
                "task_id": str(request.generation_task_id or ""),
            },
        )

        return await self._process_quality_result(
            project_id=request.project_id,
            related_id=request.related_id,
            asset_id=request.asset_id,
            generation_task_id=request.generation_task_id,
            result=result,
            db=db,
        )

    async def _process_quality_result(
        self,
        *,
        project_id: uuid.UUID,
        related_id: str | None,
        asset_id: uuid.UUID | None,
        generation_task_id: uuid.UUID | None,
        result: dict[str, Any],
        db: AsyncSession,
    ) -> QualityReportResponse:
        report_json = {
            "related_id": related_id,
            "quality_score": result["quality_score"],
            "face_consistency_score": result["face_consistency_score"],
            "outfit_consistency_score": result["outfit_consistency_score"],
            "scene_consistency_score": result["scene_consistency_score"],
            "prop_presence_score": result["prop_presence_score"],
            "composition_score": result.get("composition_score"),
            "issues": result["issues"],
            "retry_required": result["retry_required"],
            "retry_prompt_patch": result.get("retry_prompt_patch", ""),
        }

        retry_decision_id: uuid.UUID | None = None
        retry_prompt_patch: str | None = None
        needs_review = False
        retry_decision: RetryDecision | None = None

        if result["retry_required"]:
            patches = build_retry_patches(result["issues"], {"related_id": related_id or ""})
            combined_patch = "\n".join(patches) if patches else result.get("retry_prompt_patch", "")
            existing_retry_count = (
                await _get_existing_retry_count(db, generation_task_id) if generation_task_id else 0
            )
            max_retries = settings.vision_quality_max_retries
            needs_review = existing_retry_count >= max_retries

            retry_decision = RetryDecision(
                project_id=project_id,
                generation_task_id=generation_task_id,
                related_id=related_id,
                asset_type="image",
                retry_count=existing_retry_count + 1,
                max_retries=max_retries,
                max_auto_fixes=MAX_AUTO_FIXES,
                auto_fix_count=0,
                action="needs_review" if needs_review else "retry",
                retry_prompt_patch=combined_patch or None,
                previous_prompt=None,
                quality_report_id=None,
                outcome="pending",
            )
            db.add(retry_decision)
            await db.flush()
            retry_decision_id = retry_decision.id
            retry_prompt_patch = combined_patch or None

        quality_report = QualityReport(
            project_id=project_id,
            related_id=related_id,
            asset_id=asset_id,
            asset_type="image",
            generation_task_id=generation_task_id,
            quality_score=result["quality_score"],
            face_consistency_score=result["face_consistency_score"],
            outfit_consistency_score=result["outfit_consistency_score"],
            scene_consistency_score=result["scene_consistency_score"],
            prop_presence_score=result["prop_presence_score"],
            composition_score=result.get("composition_score"),
            issues=result["issues"],
            retry_required=result["retry_required"],
            retry_prompt_patch=retry_prompt_patch,
            needs_review=needs_review,
            report_json=report_json,
        )
        db.add(quality_report)
        await db.flush()

        if retry_decision is not None:
            retry_decision.quality_report_id = quality_report.id
            db.add(retry_decision)

        await db.commit()

        response = _build_report_response(quality_report)
        response.retry_decision_id = retry_decision_id
        return response

    async def get_report(self, report_id: uuid.UUID, db: AsyncSession) -> QualityReportResponse:
        result = await db.execute(select(QualityReport).where(QualityReport.id == report_id))
        report = result.scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": NOT_FOUND.code,
                    "message": f"QualityReport {report_id} not found",
                    "retryable": NOT_FOUND.retryable,
                },
            )
        return _build_report_response(report)

    async def list_reports(self, project_id: uuid.UUID, db: AsyncSession) -> list[QualityReportResponse]:
        result = await db.execute(
            select(QualityReport)
            .where(QualityReport.project_id == project_id)
            .order_by(QualityReport.created_at.desc())
        )
        return [_build_report_response(report) for report in result.scalars().all()]

    async def get_retry_decision(self, decision_id: uuid.UUID, db: AsyncSession) -> RetryDecisionResponse:
        result = await db.execute(select(RetryDecision).where(RetryDecision.id == decision_id))
        decision = result.scalar_one_or_none()
        if decision is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": NOT_FOUND.code,
                    "message": f"RetryDecision {decision_id} not found",
                    "retryable": NOT_FOUND.retryable,
                },
            )
        return RetryDecisionResponse(
            decision_id=decision.id,
            project_id=decision.project_id,
            generation_task_id=decision.generation_task_id,
            related_id=decision.related_id,
            asset_type=decision.asset_type,
            retry_count=decision.retry_count,
            max_retries=decision.max_retries,
            max_auto_fixes=decision.max_auto_fixes,
            auto_fix_count=decision.auto_fix_count,
            action=decision.action,
            retry_prompt_patch=decision.retry_prompt_patch,
            previous_prompt=decision.previous_prompt,
            quality_report_id=decision.quality_report_id,
            outcome=decision.outcome,
            created_at=decision.created_at,
            updated_at=decision.updated_at,
        )

    async def execute_retry_decision(
        self,
        request: RetryExecuteRequest,
        db: AsyncSession,
    ) -> RetryExecuteResponse:
        result = await db.execute(select(RetryDecision).where(RetryDecision.id == request.decision_id))
        decision = result.scalar_one_or_none()
        if decision is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": NOT_FOUND.code,
                    "message": f"RetryDecision {request.decision_id} not found",
                    "retryable": NOT_FOUND.retryable,
                },
            )

        if decision.action == "passed":
            decision.outcome = "success"
            db.add(decision)
            await db.commit()
            return RetryExecuteResponse(
                decision_id=decision.id,
                success=True,
                action=decision.action,
                message="Quality check passed; no retry needed.",
                updated_task_retry_count=None,
            )

        if decision.action == "needs_review":
            decision.outcome = "pending"
            db.add(decision)
            await db.commit()
            return RetryExecuteResponse(
                decision_id=decision.id,
                success=False,
                action=decision.action,
                message=NEEDS_REVIEW.message,
                updated_task_retry_count=decision.retry_count,
            )

        if decision.generation_task_id:
            await _update_task_retry_count(db, decision.generation_task_id, decision.retry_count)

        decision.outcome = "success"
        db.add(decision)
        await db.commit()
        return RetryExecuteResponse(
            decision_id=decision.id,
            success=True,
            action=decision.action,
            message=f"Retry #{decision.retry_count} initiated with prompt patch.",
            updated_task_retry_count=decision.retry_count,
        )
