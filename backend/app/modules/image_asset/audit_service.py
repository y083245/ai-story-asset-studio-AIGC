from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.image_asset.audit_models import ImageAssetAuditLog
from app.modules.image_asset.lifecycle import CHARACTER_ASSET_TYPES, PROP_ASSET_TYPES, SCENE_ASSET_TYPES
from app.modules.image_asset.schemas import ImageAssetAuditLogItem, ImageAssetAuditLogResponse
from app.modules.project.models import Project

IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH = "delete_image_asset_to_trash"
IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH = "restore_image_asset_from_trash"
IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE = "permanent_delete_image_asset"
IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED = "purge_expired_image_asset"

_ALLOWED_ACTIONS = {
    IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
    IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
    IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
    IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
}
_REDACTED = "***REDACTED***"
_UUID_RULE = "uuid"
_ASSET_TYPE_RULE = "asset_type"
_RELATED_ID_RULE = "related_id"
_REASON_RULE = "reason"
_CODE_RULE = "code"
_MODEL_NAME_RULE = "model_name"
_STATUS_RULE = "status"
_QUALITY_STATUS_RULE = "quality_status"
_HASH_RULE = "hash"
_ALLOWED_ASSET_TYPES = CHARACTER_ASSET_TYPES | PROP_ASSET_TYPES | SCENE_ASSET_TYPES
_STATUS_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,19}$")
_QUALITY_STATUS_VALUES = {"pending", "passed", "needs_retry", "needs_manual_review", "failed", "skipped"}
_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,49}$")
_SAFE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,49}$")
_FORBIDDEN_CODE_MARKER_PATTERN = re.compile(
    r"(?:^|[-_.])(api[-_]?key|secret|token|password|bearer|sk)(?:$|[-_.])", re.IGNORECASE
)
_ALLOWED_DETAIL_SCHEMA: dict[str, Any] = {
    "asset_id": _UUID_RULE,
    "asset_type": _ASSET_TYPE_RULE,
    "related_id": _RELATED_ID_RULE,
    "reason": _REASON_RULE,
    "storage_path_hash": _HASH_RULE,
    "generation_task_summary": {
        "generation_task_id": _UUID_RULE,
        "provider": _CODE_RULE,
        "model_name": _MODEL_NAME_RULE,
        "status": _STATUS_RULE,
        "quality_status": _QUALITY_STATUS_RULE,
    },
}


def _sanitize_uuid_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return _REDACTED


def _sanitize_asset_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped if stripped in _ALLOWED_ASSET_TYPES else _REDACTED


def _sanitize_reason(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped if _REASON_PATTERN.fullmatch(stripped) else _REDACTED


def _sanitize_related_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        return str(uuid.UUID(stripped))
    except ValueError:
        if _FORBIDDEN_CODE_MARKER_PATTERN.search(stripped):
            return _REDACTED
        return stripped if _SAFE_IDENTIFIER_PATTERN.fullmatch(stripped) else _REDACTED


def _sanitize_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    if _FORBIDDEN_CODE_MARKER_PATTERN.search(stripped):
        return _REDACTED
    return stripped if _SAFE_CODE_PATTERN.fullmatch(stripped) else _REDACTED


def _sanitize_model_name(value: Any) -> str | None:
    return _sanitize_code(value)


def _sanitize_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped if _STATUS_PATTERN.fullmatch(stripped) else _REDACTED


def _sanitize_quality_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return ""
    return stripped if stripped in _QUALITY_STATUS_VALUES else _REDACTED


def _sanitize_hash_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{8,64}", stripped):
        return stripped
    if not stripped:
        return ""
    return _REDACTED


def _sanitize_detail_value(value: Any, schema: Any) -> Any:
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            return {}
        sanitized: dict[str, Any] = {}
        for key, nested_schema in schema.items():
            if key not in value:
                continue
            sanitized_value = _sanitize_detail_value(value[key], nested_schema)
            if sanitized_value in (None, {}, []):
                continue
            sanitized[key] = sanitized_value
        return sanitized
    if schema == _UUID_RULE:
        return _sanitize_uuid_string(value)
    if schema == _HASH_RULE:
        return _sanitize_hash_text(value)
    if schema == _ASSET_TYPE_RULE:
        return _sanitize_asset_type(value)
    if schema == _RELATED_ID_RULE:
        return _sanitize_related_id(value)
    if schema == _REASON_RULE:
        return _sanitize_reason(value)
    if schema == _CODE_RULE:
        return _sanitize_code(value)
    if schema == _MODEL_NAME_RULE:
        return _sanitize_model_name(value)
    if schema == _STATUS_RULE:
        return _sanitize_status(value)
    if schema == _QUALITY_STATUS_RULE:
        return _sanitize_quality_status(value)
    return None


def _sanitize_details_payload(details: dict[str, object] | None) -> dict[str, Any]:
    payload = _sanitize_detail_value(details or {}, _ALLOWED_DETAIL_SCHEMA)
    return payload if isinstance(payload, dict) else {}


def _build_audit_log_item(row: ImageAssetAuditLog) -> ImageAssetAuditLogItem:
    return ImageAssetAuditLogItem(
        audit_id=row.id,
        project_id=row.project_id,
        asset_id=row.asset_id,
        user_id=row.user_id,
        action=row.action,
        reason=_sanitize_reason(row.reason),
        asset_type=_sanitize_asset_type(row.asset_type),
        related_id=_sanitize_related_id(row.related_id),
        storage_path_hash=row.storage_path_hash,
        details=_sanitize_details_payload(getattr(row, "details", None) or {}),
        created_at=row.created_at,
    )


class ImageAssetAuditService:
    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        project_id: uuid.UUID,
        asset_id: uuid.UUID | None,
        user_id: str,
        action: str,
        reason: str | None,
        asset_type: str | None,
        related_id: str | None,
        storage_path: str | None,
        details: dict[str, object] | None = None,
    ) -> None:
        if action not in _ALLOWED_ACTIONS:
            raise ValueError(f"Unsupported image asset audit action: {action}")

        log = ImageAssetAuditLog(
            project_id=project_id,
            asset_id=asset_id,
            user_id=user_id,
            action=action,
            reason=_sanitize_reason(reason),
            asset_type=_sanitize_asset_type(asset_type),
            related_id=_sanitize_related_id(related_id),
            storage_path_hash=hashlib.sha256(storage_path.encode("utf-8")).hexdigest() if storage_path else None,
            details=_sanitize_details_payload(details),
        )
        session.add(log)
        await session.flush()

    @staticmethod
    async def list_logs(
        session: AsyncSession,
        *,
        user_id: str,
        project_id: uuid.UUID | None,
        asset_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> ImageAssetAuditLogResponse:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        filters = [Project.user_id == user_id]
        if project_id is not None:
            filters.append(ImageAssetAuditLog.project_id == project_id)
        if asset_id is not None:
            filters.append(ImageAssetAuditLog.asset_id == asset_id)

        base_stmt = (
            select(ImageAssetAuditLog).join(Project, Project.id == ImageAssetAuditLog.project_id).where(*filters)
        )
        total_stmt = select(func.count()).select_from(base_stmt.order_by(None).subquery())
        total = int((await session.execute(total_stmt)).scalar_one())

        stmt = (
            base_stmt.order_by(ImageAssetAuditLog.created_at.desc(), ImageAssetAuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(stmt)).scalars().all()

        return ImageAssetAuditLogResponse(
            items=[_build_audit_log_item(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
