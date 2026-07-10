from __future__ import annotations

import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.enums import ProjectStatus
from app.modules.character_library.models import Character
from app.modules.image_asset.audit_service import (
    IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
    IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
    IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
    IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
    ImageAssetAuditService,
)
from app.modules.image_asset.lifecycle import (
    CATEGORY_ORDER,
    CHARACTER_ASSET_TYPES,
    IMAGE_LIBRARY_TIMEZONE,
    PROP_ASSET_TYPES,
    SCENE_ASSET_TYPES,
    archive_date,
    asset_category,
    compute_purge_after,
    effective_permanent_delete_at,
    remaining_days,
)
from app.modules.image_asset.models import ImageAsset, ImageGenerationTask
from app.modules.image_asset.schemas import (
    ImageAssetBatchOperationResponse,
    ImageAssetCategory,
    ImageAssetDateGroup,
    ImageAssetLibraryItem,
    ImageAssetLibraryQuery,
    ImageAssetLibraryResponse,
    ImageAssetOperationResult,
    ImageAssetPermanentDeleteRequest,
    ImageAssetProjectGroup,
    ImageAssetProjectOption,
    ImageAssetTrashItem,
    ImageAssetTrashQuery,
    ImageAssetTrashResponse,
)
from app.modules.project.models import Project
from app.modules.prop_library.models import Prop
from app.modules.scene_library.models import Scene
from app.modules.storage.service import StorageService

_ASSET_TYPE_LABELS: dict[str, str] = {
    "character_bible_sheet": "角色设定图",
    "character_front": "角色正面图",
    "character_turnaround": "角色转身图",
    "character_expression": "角色表情图",
    "prop_product": "道具单品图",
    "prop_usage": "道具使用图",
    "scene_empty": "纯场景图",
    "scene_with_atmosphere": "氛围场景图",
}
_PROMPT_SUMMARY_LIMIT = 120
_EXPIRING_SOON_DAYS = 7
_PURGE_REASON_TRASH_EXPIRED = "trash_expired"
_PURGE_REASON_RETENTION_EXPIRED = "retention_expired"


@dataclass(slots=True)
class ImageAssetPurgeResult:
    trash_expired_count: int = 0
    retention_expired_count: int = 0
    storage_failed_count: int = 0
    deleted_count: int = 0


class ImageAssetLibraryService:
    def __init__(self, storage_service: StorageService) -> None:
        self._storage_service = storage_service

    async def list_library(
        self,
        session: AsyncSession,
        user_id: str,
        filters: ImageAssetLibraryQuery,
    ) -> ImageAssetLibraryResponse:
        now = datetime.now(UTC)
        base_stmt = self._base_statement(user_id=user_id, filters=filters, now=now)
        base_subquery = base_stmt.subquery()
        count_stmt = select(func.count()).select_from(base_subquery)
        total = int((await session.execute(count_stmt)).scalar_one())

        page_stmt = (
            base_stmt.order_by(ImageAsset.created_at.desc(), ImageAsset.id.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        rows = list((await session.execute(page_stmt)).mappings().all())
        groups, available_projects = self._build_groups(rows=rows, now=now)
        return ImageAssetLibraryResponse(
            groups=groups,
            available_projects=available_projects,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
        )

    async def list_trash(
        self,
        session: AsyncSession,
        user_id: str,
        filters: ImageAssetTrashQuery,
    ) -> ImageAssetTrashResponse:
        now = datetime.now(UTC)
        base_stmt = self._trash_statement(user_id=user_id, filters=filters, now=now)
        base_subquery = base_stmt.subquery()
        count_stmt = select(func.count()).select_from(base_subquery)
        total = int((await session.execute(count_stmt)).scalar_one())

        page_stmt = (
            base_stmt.order_by(ImageAsset.deleted_at.desc(), ImageAsset.id.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        rows = list((await session.execute(page_stmt)).mappings().all())
        items, available_projects = self._build_trash_items(rows=rows, now=now)
        return ImageAssetTrashResponse(
            items=items,
            available_projects=available_projects,
            page=filters.page,
            page_size=filters.page_size,
            total=total,
        )

    async def soft_delete_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> ImageAssetOperationResult:
        asset, _task, project = await self._get_asset_with_context(session, asset_id=asset_id, user_id=user_id)
        if asset.deleted_at is not None:
            return self._success_result(asset_id, "IMAGE_ASSET_ALREADY_TRASHED", "Asset already in trash")

        now = datetime.now(UTC)
        asset.deleted_at = now
        asset.deleted_by = user_id
        asset.purge_after = compute_purge_after(now)
        asset.delete_reason = "manual"
        await ImageAssetAuditService.record(
            session,
            project_id=project.id,
            asset_id=asset.id,
            user_id=user_id,
            action=IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason="manual",
            asset_type=asset.asset_type,
            related_id=asset.related_id,
            storage_path=asset.storage_path,
            details={
                "asset_id": str(asset.id),
                "asset_type": asset.asset_type,
                "related_id": asset.related_id,
                "reason": "manual",
            },
        )
        await session.commit()
        return self._success_result(asset_id, "IMAGE_ASSET_TRASHED", "Asset moved to trash")

    async def restore_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> ImageAssetOperationResult:
        asset, _task, project = await self._get_asset_with_context(session, asset_id=asset_id, user_id=user_id)
        if asset.deleted_at is None:
            return self._success_result(asset_id, "IMAGE_ASSET_NOT_TRASHED", "Asset is not in trash")

        now = datetime.now(UTC)
        if asset.expires_at is None or asset.expires_at <= now:
            raise ValueError("IMAGE_ASSET_EXPIRED: asset already expired")

        asset.deleted_at = None
        asset.deleted_by = None
        asset.purge_after = None
        asset.delete_reason = None
        await ImageAssetAuditService.record(
            session,
            project_id=project.id,
            asset_id=asset.id,
            user_id=user_id,
            action=IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
            reason="manual",
            asset_type=asset.asset_type,
            related_id=asset.related_id,
            storage_path=asset.storage_path,
            details={
                "asset_id": str(asset.id),
                "asset_type": asset.asset_type,
                "related_id": asset.related_id,
                "reason": "manual",
            },
        )
        await session.commit()
        return self._success_result(asset_id, "IMAGE_ASSET_RESTORED", "Asset restored from trash")

    async def permanent_delete_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
        reason: str,
    ) -> ImageAssetOperationResult:
        asset, generation_task, project = await self._get_asset_with_context(
            session, asset_id=asset_id, user_id=user_id
        )
        deleted = await self._permanently_delete_loaded_asset(
            session,
            asset=asset,
            generation_task=generation_task,
            project=project,
            user_id=user_id,
            action=IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
            reason=reason,
        )
        if not deleted:
            raise ValueError("IMAGE_ASSET_STORAGE_DELETE_FAILED: failed to delete asset from storage")
        await session.commit()
        return self._success_result(asset_id, "IMAGE_ASSET_PERMANENTLY_DELETED", "Asset permanently deleted")

    async def batch_soft_delete_assets(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        asset_ids: list[uuid.UUID],
    ) -> ImageAssetBatchOperationResponse:
        return await self._run_batch(
            session,
            items=asset_ids,
            operation=lambda asset_id: self.soft_delete_asset(session, asset_id=asset_id, user_id=user_id),
        )

    async def batch_restore_assets(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        asset_ids: list[uuid.UUID],
    ) -> ImageAssetBatchOperationResponse:
        return await self._run_batch(
            session,
            items=asset_ids,
            operation=lambda asset_id: self.restore_asset(session, asset_id=asset_id, user_id=user_id),
        )

    async def batch_permanent_delete_assets(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        requests: list[ImageAssetPermanentDeleteRequest],
    ) -> ImageAssetBatchOperationResponse:
        return await self._run_batch(
            session,
            items=requests,
            operation=lambda request: self.permanent_delete_asset(
                session,
                asset_id=request.asset_id,
                user_id=user_id,
                reason=request.reason,
            ),
        )

    async def purge_expired_assets(
        self,
        session: AsyncSession,
        *,
        limit: int,
        dry_run: bool,
    ) -> ImageAssetPurgeResult:
        if limit < 1:
            raise ValueError("limit must be >= 1")

        now = datetime.now(UTC)
        effective_delete_at = case(
            (
                and_(
                    ImageAsset.deleted_at.is_not(None),
                    ImageAsset.purge_after.is_not(None),
                    ImageAsset.purge_after < ImageAsset.expires_at,
                ),
                ImageAsset.purge_after,
            ),
            else_=ImageAsset.expires_at,
        )
        stmt = (
            select(ImageAsset, ImageGenerationTask, Project)
            .join(Project, Project.id == ImageAsset.project_id)
            .outerjoin(ImageGenerationTask, ImageGenerationTask.id == ImageAsset.generation_task_id)
            .where(
                or_(
                    and_(
                        ImageAsset.deleted_at.is_not(None),
                        ImageAsset.purge_after.is_not(None),
                        ImageAsset.purge_after <= now,
                    ),
                    ImageAsset.expires_at <= now,
                )
            )
            .order_by(effective_delete_at.asc(), ImageAsset.created_at.asc(), ImageAsset.id.asc())
            .limit(limit)
        )

        result = ImageAssetPurgeResult()
        rows = (await session.execute(stmt)).all()
        for asset, generation_task, project in rows:
            reason = self._purge_reason(asset=asset, now=now)
            if reason == _PURGE_REASON_TRASH_EXPIRED:
                result.trash_expired_count += 1
            else:
                result.retention_expired_count += 1

            if dry_run:
                continue

            deleted = await self._permanently_delete_loaded_asset(
                session,
                asset=asset,
                generation_task=generation_task,
                project=project,
                user_id="system",
                action=IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
                reason=reason,
            )
            if deleted:
                result.deleted_count += 1
            else:
                result.storage_failed_count += 1

        if not dry_run:
            await session.commit()
        return result

    def _base_statement(
        self,
        *,
        user_id: str,
        filters: ImageAssetLibraryQuery,
        now: datetime,
    ) -> Any:
        char_join = and_(
            Character.project_id == ImageAsset.project_id,
            Character.character_id == ImageAsset.related_id,
        )
        scene_join = and_(
            Scene.project_id == ImageAsset.project_id,
            Scene.scene_id == ImageAsset.related_id,
        )
        prop_join = and_(
            Prop.project_id == ImageAsset.project_id,
            Prop.prop_id == ImageAsset.related_id,
        )

        stmt = (
            select(
                ImageAsset.id.label("asset_id"),
                ImageAsset.project_id,
                ImageAsset.asset_type,
                ImageAsset.related_id,
                ImageAsset.asset_url,
                ImageAsset.thumbnail_url,
                ImageAsset.storage_path,
                ImageAsset.prompt,
                ImageAsset.model_name,
                ImageAsset.status,
                ImageAsset.width,
                ImageAsset.height,
                ImageAsset.created_at,
                ImageAsset.expires_at,
                Project.title.label("project_title"),
                Project.status.label("project_status"),
                Project.deleted_at.label("project_deleted_at"),
                ImageGenerationTask.quality_status.label("quality_status"),
                Character.name.label("character_name"),
                Scene.scene_name.label("scene_name"),
                Prop.name.label("prop_name"),
            )
            .join(Project, Project.id == ImageAsset.project_id)
            .outerjoin(ImageGenerationTask, ImageGenerationTask.id == ImageAsset.generation_task_id)
            .outerjoin(Character, char_join)
            .outerjoin(Scene, scene_join)
            .outerjoin(Prop, prop_join)
            .where(
                Project.user_id == user_id,
                ImageAsset.deleted_at.is_(None),
                ImageAsset.expires_at.is_not(None),
                ImageAsset.expires_at > now,
            )
        )

        if filters.date_from is not None:
            start_at = _local_day_start_to_utc(filters.date_from)
            stmt = stmt.where(ImageAsset.created_at >= start_at)
        if filters.date_to is not None:
            end_at = _local_day_start_to_utc(filters.date_to + timedelta(days=1))
            stmt = stmt.where(ImageAsset.created_at < end_at)
        if filters.project_id is not None:
            stmt = stmt.where(ImageAsset.project_id == filters.project_id)
        if filters.category is not None:
            stmt = stmt.where(ImageAsset.asset_type.in_(self._category_asset_types(filters.category)))
        if filters.asset_type is not None:
            stmt = stmt.where(ImageAsset.asset_type == filters.asset_type)
        if filters.keyword:
            keyword = f"%{filters.keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    Project.title.ilike(keyword),
                    ImageAsset.related_id.ilike(keyword),
                    Character.name.ilike(keyword),
                    Scene.scene_name.ilike(keyword),
                    Prop.name.ilike(keyword),
                )
            )
        return stmt

    def _trash_statement(
        self,
        *,
        user_id: str,
        filters: ImageAssetTrashQuery,
        now: datetime,
    ) -> Any:
        char_join = and_(
            Character.project_id == ImageAsset.project_id,
            Character.character_id == ImageAsset.related_id,
        )
        scene_join = and_(
            Scene.project_id == ImageAsset.project_id,
            Scene.scene_id == ImageAsset.related_id,
        )
        prop_join = and_(
            Prop.project_id == ImageAsset.project_id,
            Prop.prop_id == ImageAsset.related_id,
        )

        stmt = (
            select(
                ImageAsset.id.label("asset_id"),
                ImageAsset.project_id,
                ImageAsset.asset_type,
                ImageAsset.related_id,
                ImageAsset.asset_url,
                ImageAsset.thumbnail_url,
                ImageAsset.prompt,
                ImageAsset.model_name,
                ImageAsset.status,
                ImageAsset.created_at,
                ImageAsset.deleted_at,
                ImageAsset.purge_after,
                ImageAsset.expires_at,
                Project.title.label("project_title"),
                Project.status.label("project_status"),
                Project.deleted_at.label("project_deleted_at"),
                ImageGenerationTask.quality_status.label("quality_status"),
                Character.name.label("character_name"),
                Scene.scene_name.label("scene_name"),
                Prop.name.label("prop_name"),
            )
            .join(Project, Project.id == ImageAsset.project_id)
            .outerjoin(ImageGenerationTask, ImageGenerationTask.id == ImageAsset.generation_task_id)
            .outerjoin(Character, char_join)
            .outerjoin(Scene, scene_join)
            .outerjoin(Prop, prop_join)
            .where(
                Project.user_id == user_id,
                ImageAsset.deleted_at.is_not(None),
                ImageAsset.expires_at.is_not(None),
                ImageAsset.expires_at > now,
            )
        )

        if filters.project_id is not None:
            stmt = stmt.where(ImageAsset.project_id == filters.project_id)
        if filters.date_from is not None:
            start_at = _local_day_start_to_utc(filters.date_from)
            stmt = stmt.where(ImageAsset.deleted_at >= start_at)
        if filters.date_to is not None:
            end_at = _local_day_start_to_utc(filters.date_to + timedelta(days=1))
            stmt = stmt.where(ImageAsset.deleted_at < end_at)
        if filters.category is not None:
            stmt = stmt.where(ImageAsset.asset_type.in_(self._category_asset_types(filters.category)))
        if filters.asset_type is not None:
            stmt = stmt.where(ImageAsset.asset_type == filters.asset_type)
        if filters.keyword:
            keyword = f"%{filters.keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    Project.title.ilike(keyword),
                    ImageAsset.related_id.ilike(keyword),
                    Character.name.ilike(keyword),
                    Scene.scene_name.ilike(keyword),
                    Prop.name.ilike(keyword),
                )
            )
        return stmt

    def _build_groups(
        self,
        *,
        rows: list[Any],
        now: datetime,
    ) -> tuple[list[ImageAssetDateGroup], list[ImageAssetProjectOption]]:
        date_groups: OrderedDict[Any, dict[str, Any]] = OrderedDict()
        project_options: OrderedDict[uuid.UUID, ImageAssetProjectOption] = OrderedDict()

        for row in rows:
            created_at = row["created_at"]
            expires_at = row["expires_at"]
            category = asset_category(row["asset_type"])
            group_date = archive_date(created_at, IMAGE_LIBRARY_TIMEZONE)
            project_id = row["project_id"]
            project_deleted_at = row["project_deleted_at"]
            is_project_in_trash = project_deleted_at is not None or row["project_status"] == ProjectStatus.ARCHIVED

            item = ImageAssetLibraryItem(
                asset_id=row["asset_id"],
                display_name=_display_name(row),
                project_id=project_id,
                project_title=row["project_title"],
                project_status=_stringify_status(row["project_status"]),
                project_deleted_at=project_deleted_at,
                category=category,
                asset_type=row["asset_type"],
                asset_type_label=_ASSET_TYPE_LABELS.get(row["asset_type"], row["asset_type"]),
                related_id=row["related_id"],
                related_name=_related_name(row),
                asset_url=row["asset_url"],
                thumbnail_url=row["thumbnail_url"],
                storage_path=row["storage_path"],
                prompt_summary=_prompt_summary(row["prompt"]),
                prompt=row["prompt"],
                model_name=row["model_name"],
                status=row["status"],
                quality_status=row["quality_status"],
                width=row["width"],
                height=row["height"],
                created_at=created_at,
                expires_at=expires_at,
                remaining_retention_days=remaining_days(expires_at, now),
                is_expiring_soon=remaining_days(expires_at, now) < _EXPIRING_SOON_DAYS,
            )

            date_entry = date_groups.setdefault(
                group_date,
                {
                    "total": 0,
                    "projects": OrderedDict(),
                },
            )
            date_entry["total"] += 1
            projects = date_entry["projects"]
            project_entry = projects.setdefault(
                project_id,
                {
                    "project_id": project_id,
                    "project_title": row["project_title"],
                    "project_status": _stringify_status(row["project_status"]),
                    "project_deleted_at": project_deleted_at,
                    "is_project_in_trash": is_project_in_trash,
                    "total": 0,
                    "latest_created_at": created_at,
                    "categories": {category_key: [] for category_key in CATEGORY_ORDER},
                },
            )
            project_entry["total"] += 1
            if created_at > project_entry["latest_created_at"]:
                project_entry["latest_created_at"] = created_at
            project_entry["categories"][category].append(item)

            option = project_options.get(project_id)
            if option is None:
                project_options[project_id] = ImageAssetProjectOption(
                    project_id=project_id,
                    project_title=row["project_title"],
                    project_status=_stringify_status(row["project_status"]),
                    project_deleted_at=project_deleted_at,
                    is_project_in_trash=is_project_in_trash,
                    total=1,
                )
            else:
                option.total += 1

        groups: list[ImageAssetDateGroup] = []
        for group_date, date_entry in date_groups.items():
            sorted_projects = sorted(
                date_entry["projects"].values(),
                key=lambda project: project["latest_created_at"],
                reverse=True,
            )
            projects = [
                ImageAssetProjectGroup(
                    project_id=project["project_id"],
                    project_title=project["project_title"],
                    project_status=project["project_status"],
                    project_deleted_at=project["project_deleted_at"],
                    is_project_in_trash=project["is_project_in_trash"],
                    total=project["total"],
                    latest_created_at=project["latest_created_at"],
                    categories=project["categories"],
                )
                for project in sorted_projects
            ]
            groups.append(
                ImageAssetDateGroup(
                    date=group_date,
                    total=date_entry["total"],
                    project_count=len(projects),
                    projects=projects,
                )
            )

        return groups, list(project_options.values())

    def _build_trash_items(
        self,
        *,
        rows: list[Any],
        now: datetime,
    ) -> tuple[list[ImageAssetTrashItem], list[ImageAssetProjectOption]]:
        items: list[ImageAssetTrashItem] = []
        project_options: OrderedDict[uuid.UUID, ImageAssetProjectOption] = OrderedDict()

        for row in rows:
            project_id = row["project_id"]
            project_deleted_at = row["project_deleted_at"]
            is_project_in_trash = project_deleted_at is not None or row["project_status"] == ProjectStatus.ARCHIVED
            item = ImageAssetTrashItem(
                asset_id=row["asset_id"],
                display_name=_display_name(row),
                project_id=project_id,
                project_title=row["project_title"],
                project_status=_stringify_status(row["project_status"]),
                project_deleted_at=project_deleted_at,
                category=asset_category(row["asset_type"]),
                asset_type=row["asset_type"],
                asset_type_label=_ASSET_TYPE_LABELS.get(row["asset_type"], row["asset_type"]),
                related_id=row["related_id"],
                related_name=_related_name(row),
                asset_url=row["asset_url"],
                thumbnail_url=row["thumbnail_url"],
                prompt_summary=_prompt_summary(row["prompt"]),
                prompt=row["prompt"],
                model_name=row["model_name"],
                status=row["status"],
                quality_status=row["quality_status"],
                created_at=row["created_at"],
                deleted_at=row["deleted_at"],
                purge_after=row["purge_after"],
                expires_at=row["expires_at"],
                remaining_cleanup_days=remaining_days(row["purge_after"], now) if row["purge_after"] else 0,
                can_restore=row["expires_at"] > now,
            )
            items.append(item)

            option = project_options.get(project_id)
            if option is None:
                project_options[project_id] = ImageAssetProjectOption(
                    project_id=project_id,
                    project_title=row["project_title"],
                    project_status=_stringify_status(row["project_status"]),
                    project_deleted_at=project_deleted_at,
                    is_project_in_trash=is_project_in_trash,
                    total=1,
                )
            else:
                option.total += 1

        return items, list(project_options.values())

    @staticmethod
    def _category_asset_types(category: ImageAssetCategory) -> set[str]:
        if category == "character":
            return CHARACTER_ASSET_TYPES
        if category == "prop":
            return PROP_ASSET_TYPES
        return SCENE_ASSET_TYPES

    async def _get_asset_with_context(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> tuple[ImageAsset, ImageGenerationTask | None, Project]:
        stmt = (
            select(ImageAsset, ImageGenerationTask, Project)
            .join(Project, Project.id == ImageAsset.project_id)
            .outerjoin(ImageGenerationTask, ImageGenerationTask.id == ImageAsset.generation_task_id)
            .where(ImageAsset.id == asset_id)
        )
        row = (await session.execute(stmt)).one_or_none()
        if row is None:
            raise ValueError("IMAGE_ASSET_NOT_FOUND: image asset not found")

        asset, generation_task, project = row
        if project.user_id != user_id:
            raise ValueError("IMAGE_ASSET_FORBIDDEN: image asset does not belong to current user")
        return asset, generation_task, project

    async def _run_batch(
        self,
        session: AsyncSession,
        *,
        items: list[Any],
        operation: Any,
    ) -> ImageAssetBatchOperationResponse:
        results: list[ImageAssetOperationResult] = []
        succeeded = 0
        failed = 0

        for item in items:
            try:
                result = await operation(item)
            except ValueError as exc:
                result = self._failure_result(item, exc)
            if result.status == "success":
                succeeded += 1
            else:
                failed += 1
            results.append(result)

        return ImageAssetBatchOperationResponse(
            results=results,
            total=len(items),
            succeeded=succeeded,
            failed=failed,
        )

    @staticmethod
    def _permanent_delete_audit_details(
        *,
        asset: ImageAsset,
        generation_task: ImageGenerationTask | None,
        reason: str,
    ) -> dict[str, object]:
        details: dict[str, object] = {
            "asset_id": str(asset.id),
            "asset_type": asset.asset_type,
            "related_id": asset.related_id,
            "reason": reason,
        }
        if generation_task is not None:
            details["generation_task_summary"] = {
                "generation_task_id": str(generation_task.id),
                "provider": generation_task.provider,
                "model_name": generation_task.model_name,
                "status": generation_task.status,
                "quality_status": generation_task.quality_status,
            }
        return details

    async def _permanently_delete_loaded_asset(
        self,
        session: AsyncSession,
        *,
        asset: ImageAsset,
        generation_task: ImageGenerationTask | None,
        project: Project,
        user_id: str,
        action: str,
        reason: str,
    ) -> bool:
        audit_details = self._permanent_delete_audit_details(
            asset=asset,
            generation_task=generation_task,
            reason=reason,
        )
        try:
            await self._storage_service.delete(asset.storage_path)
        except FileNotFoundError:
            pass
        except Exception:
            return False

        if generation_task is not None:
            await session.delete(generation_task)
        await session.delete(asset)
        await ImageAssetAuditService.record(
            session,
            project_id=project.id,
            asset_id=asset.id,
            user_id=user_id,
            action=action,
            reason=reason,
            asset_type=asset.asset_type,
            related_id=asset.related_id,
            storage_path=asset.storage_path,
            details=audit_details,
        )
        await session.flush()
        return True

    @staticmethod
    def _purge_reason(*, asset: ImageAsset, now: datetime) -> str:
        effective_delete_at = effective_permanent_delete_at(asset)
        if (
            asset.deleted_at is not None
            and asset.purge_after is not None
            and effective_delete_at is not None
            and effective_delete_at <= now
            and asset.purge_after <= now
            and asset.purge_after <= (asset.expires_at or asset.purge_after)
        ):
            return _PURGE_REASON_TRASH_EXPIRED
        return _PURGE_REASON_RETENTION_EXPIRED

    @staticmethod
    def _success_result(asset_id: uuid.UUID, code: str, message: str) -> ImageAssetOperationResult:
        return ImageAssetOperationResult(asset_id=asset_id, status="success", code=code, message=message)

    @staticmethod
    def _failure_result(item: Any, exc: ValueError) -> ImageAssetOperationResult:
        code, _, message = str(exc).partition(":")
        asset_id = item.asset_id if hasattr(item, "asset_id") else item
        return ImageAssetOperationResult(
            asset_id=asset_id,
            status="failed",
            code=code.strip() or "IMAGE_ASSET_OPERATION_FAILED",
            message=(message.strip() or str(exc)),
        )


def _prompt_summary(prompt: str) -> str:
    normalized = " ".join(prompt.split())
    if len(normalized) <= _PROMPT_SUMMARY_LIMIT:
        return normalized
    return normalized[:_PROMPT_SUMMARY_LIMIT].rstrip()


def _related_name(row: Any) -> str | None:
    category = asset_category(row["asset_type"])
    if category == "character":
        return cast(str | None, row["character_name"])
    if category == "scene":
        return cast(str | None, row["scene_name"])
    return cast(str | None, row["prop_name"])


def _display_name(row: Any) -> str:
    related_name = _related_name(row)
    if related_name:
        return related_name
    if row["related_id"]:
        return cast(str, row["related_id"])
    if row["asset_type"]:
        return _ASSET_TYPE_LABELS.get(row["asset_type"], cast(str, row["asset_type"]))
    return str(row["asset_id"])


def _stringify_status(status: Any) -> str:
    if isinstance(status, ProjectStatus):
        return status.value
    return str(status)


def _local_day_start_to_utc(value: date) -> datetime:
    local_start = datetime.combine(value, time.min, tzinfo=ZoneInfo(IMAGE_LIBRARY_TIMEZONE))
    return local_start.astimezone(UTC)
