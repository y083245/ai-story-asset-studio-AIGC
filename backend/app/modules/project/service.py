"""Business logic for the Project module.

All database access goes through a single SQLAlchemy AsyncSession.
External SDK calls are forbidden here.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.enums import ProjectStatus
from app.db.base import Base
from app.modules.character_library import models as _character_models  # noqa: F401
from app.modules.image_asset import models as _image_asset_models  # noqa: F401
from app.modules.novel_intake import models as _novel_models  # noqa: F401
from app.modules.project.models import Project, ProjectSettings, ProjectStatusSnapshot
from app.modules.project.schemas import (
    ProgressInfo,
    ProjectCreateRequest,
    ProjectStatusResponse,
    ProjectUpdateRequest,
)
from app.modules.prop_library import models as _prop_models  # noqa: F401
from app.modules.quality_retry import models as _quality_models  # noqa: F401
from app.modules.scene_library import models as _scene_models  # noqa: F401
from app.modules.story_bible import models as _story_bible_models  # noqa: F401
from app.modules.workflow import models as _workflow_models  # noqa: F401

# States during which critical generation parameters must not be changed.
_LOCKED_STATES: set[ProjectStatus] = {
    ProjectStatus.ANALYZING,
    ProjectStatus.GENERATING_ASSETS,
}

# Sensitive fields that are locked during active generation.
_LOCKED_FIELDS: set[str] = {
    "aspect_ratio",
    "style_mode",
    "generation_mode",
}

RECYCLE_RETENTION_DAYS = 30


class ProjectService:
    """Stateless project lifecycle service.

    All methods receive an open AsyncSession and return domain objects
    or dictionaries.  Callers (router layer) are responsible for
    converting to Pydantic response schemas.
    """

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    @staticmethod
    async def create_project(session: AsyncSession, user_id: str, data: ProjectCreateRequest) -> Project:
        """Create a new project in DRAFT status."""
        project = Project(
            user_id=user_id,
            title=data.title.strip(),
            aspect_ratio=data.aspect_ratio.value,
            style_mode=data.style_mode,
            manual_style=data.manual_style,
            generation_mode=data.generation_mode,
            status=ProjectStatus.DRAFT,
        )
        session.add(project)
        await session.flush()

        # Record the initial status snapshot
        snapshot = ProjectStatusSnapshot(
            project_id=project.id,
            stage=ProjectStatus.DRAFT.value,
            message="项目已创建",
        )
        session.add(snapshot)
        await session.commit()
        await session.refresh(project)

        return project

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    async def get_project(session: AsyncSession, project_id: uuid.UUID) -> Project | None:
        """Return a single project by ID, or None."""
        stmt = select(Project).where(Project.id == project_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_projects(
        session: AsyncSession,
        user_id: str,
        include_archived: bool = False,
        only_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """Return projects owned by *user_id* with an optional archived filter.

        Returns (items, total_count).
        """
        await ProjectService.purge_expired_recycle_bin_projects(session)

        # Count
        count_stmt = select(func.count()).select_from(Project).where(Project.user_id == user_id)
        if only_archived:
            count_stmt = count_stmt.where(Project.status == ProjectStatus.ARCHIVED)
        elif not include_archived:
            count_stmt = count_stmt.where(Project.status != ProjectStatus.ARCHIVED)
        total = (await session.execute(count_stmt)).scalar_one()

        # Items
        items_stmt = (
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if only_archived:
            items_stmt = items_stmt.where(Project.status == ProjectStatus.ARCHIVED)
        elif not include_archived:
            items_stmt = items_stmt.where(Project.status != ProjectStatus.ARCHIVED)

        items = (await session.execute(items_stmt)).scalars().all()
        return list(items), total

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    @staticmethod
    async def update_project(
        session: AsyncSession,
        project_id: uuid.UUID,
        data: ProjectUpdateRequest,
    ) -> Project:
        """Partial update of a project. Raises on locked fields."""
        project = await ProjectService._require_project(session, project_id)

        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return project  # nothing to change

        # Block locked fields when project is in a locked state
        if project.status in _LOCKED_STATES:
            blocked = _LOCKED_FIELDS & set(updates.keys())
            if blocked:
                raise ValueError(
                    f"Fields {sorted(blocked)} cannot be modified when project status is '{project.status.value}'"
                )

        # Apply updates directly to the ORM object
        for key, value in updates.items():
            setattr(project, key, value)

        await session.flush()
        return project

    # ------------------------------------------------------------------
    # Soft-delete
    # ------------------------------------------------------------------

    @staticmethod
    async def soft_delete_project(session: AsyncSession, project_id: uuid.UUID) -> None:
        """Move the project to recycle bin for 30 days."""
        project = await ProjectService._require_project(session, project_id)

        if project.status == ProjectStatus.ARCHIVED:
            return  # idempotent

        deleted_at = datetime.now(UTC)
        project.status = ProjectStatus.ARCHIVED
        project.deleted_at = deleted_at
        project.purge_after = deleted_at + timedelta(days=RECYCLE_RETENTION_DAYS)

        snapshot = ProjectStatusSnapshot(
            project_id=project.id,
            stage=ProjectStatus.ARCHIVED.value,
            message="项目已移入回收站，30天后自动删除",
        )
        session.add(snapshot)
        await session.flush()

    @staticmethod
    async def restore_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
        """Restore a project from recycle bin to draft status."""
        project = await ProjectService._require_project(session, project_id)

        if project.status != ProjectStatus.ARCHIVED:
            return project

        project.status = ProjectStatus.DRAFT
        project.deleted_at = None
        project.purge_after = None
        session.add(
            ProjectStatusSnapshot(
                project_id=project.id,
                stage=ProjectStatus.DRAFT.value,
                message="项目已从回收站恢复",
            )
        )
        await session.flush()
        return project

    @staticmethod
    async def purge_expired_recycle_bin_projects(session: AsyncSession) -> int:
        """Permanently delete recycle-bin projects after the retention window."""
        now = datetime.now(UTC)
        result = await session.execute(
            select(Project.id).where(Project.status == ProjectStatus.ARCHIVED, Project.purge_after <= now)
        )
        project_ids = list(result.scalars().all())
        if not project_ids:
            return 0

        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Project.__tablename__:
                continue
            if "project_id" in table.c:
                await session.execute(delete(table).where(table.c.project_id.in_(project_ids)))

        await session.execute(delete(Project).where(Project.id.in_(project_ids)))
        await session.flush()
        return len(project_ids)

    # ------------------------------------------------------------------
    # Copy
    # ------------------------------------------------------------------

    @staticmethod
    async def copy_project(
        session: AsyncSession,
        project_id: uuid.UUID,
        new_user_id: str | None = None,
    ) -> Project:
        """Create a shallow copy of a project.

        Copies title, settings and asset-generation params.  The copy is always
        DRAFT.  If *new_user_id* is omitted the copy belongs to the
        original owner.
        """
        original = await ProjectService._require_project(session, project_id)

        new_project = Project(
            user_id=new_user_id if new_user_id else original.user_id,
            title=f"{original.title} (副本)",
            aspect_ratio=original.aspect_ratio,
            style_mode=original.style_mode,
            manual_style=original.manual_style,
            generation_mode=original.generation_mode,
            status=ProjectStatus.DRAFT,
        )
        session.add(new_project)
        await session.flush()

        # Copy settings rows
        settings_stmt = select(ProjectSettings).where(ProjectSettings.project_id == original.id)
        settings_result = await session.execute(settings_stmt)
        for setting in settings_result.scalars().all():
            session.add(
                ProjectSettings(
                    project_id=new_project.id,
                    key=setting.key,
                    value=setting.value,
                )
            )

        # Snapshot
        snapshot = ProjectStatusSnapshot(
            project_id=new_project.id,
            stage=ProjectStatus.DRAFT.value,
            message=f"从项目 {original.id!s} 复制创建",
        )
        session.add(snapshot)

        return new_project

    # ------------------------------------------------------------------
    # Permanent delete
    # ------------------------------------------------------------------

    @staticmethod
    async def permanent_delete_project(session: AsyncSession, project_id: uuid.UUID) -> None:
        """Permanently delete a project and all its related data from the database.

        This iterates through all tables that have a ``project_id`` column and
        removes every row associated with the project, then removes the project
        itself.  This is NOT reversible.
        """
        await ProjectService._require_project(session, project_id)

        # Delete from every table that references project_id (except the project table itself)
        for table in reversed(Base.metadata.sorted_tables):
            if table.name == Project.__tablename__:
                continue
            if "project_id" in table.columns:
                await session.execute(delete(table).where(table.c.project_id == project_id))

        # Delete project settings
        await session.execute(delete(ProjectSettings).where(ProjectSettings.project_id == project_id))
        # Delete status snapshots
        await session.execute(delete(ProjectStatusSnapshot).where(ProjectStatusSnapshot.project_id == project_id))
        # Finally delete the project itself
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.flush()

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    @staticmethod
    async def archive_project(session: AsyncSession, project_id: uuid.UUID) -> None:
        """Explicitly archive a project — moves it to recycle bin."""
        await ProjectService.soft_delete_project(session, project_id)

    # ------------------------------------------------------------------
    # Status aggregation
    # ------------------------------------------------------------------

    @staticmethod
    async def get_project_status(session: AsyncSession, project_id: uuid.UUID) -> ProjectStatusResponse:
        """Build an aggregated status view for a project.

        Phase 1: derives current_stage from project.status and reads
        progress from project.progress_json.  Future phases will also
        read related task tables.
        """
        project = await ProjectService._require_project(session, project_id)

        # Derive current_stage and message
        stage_map: dict[ProjectStatus, str] = {
            ProjectStatus.DRAFT: "草稿",
            ProjectStatus.UPLOADED: "已上传",
            ProjectStatus.ANALYZING: "分析中",
            ProjectStatus.GENERATING_ASSETS: "生成素材中",
            ProjectStatus.COMPLETED: "已完成",
            ProjectStatus.FAILED: "失败",
            ProjectStatus.ARCHIVED: "已归档",
        }
        status = _coerce_project_status(project.status)
        status_value = status.value if isinstance(status, ProjectStatus) else str(status)
        current_stage = stage_map.get(status, status_value) if isinstance(status, ProjectStatus) else status_value

        # Progress
        if project.progress_json:
            progress = ProgressInfo(
                completed=project.progress_json.get("completed", 0),
                total=project.progress_json.get("total", 0),
                percentage=project.progress_json.get("percentage", 0),
            )
            # Recalculate percentage to keep it honest
            if progress.total > 0:
                progress.percentage = math.floor((progress.completed / progress.total) * 100)
        else:
            progress = ProgressInfo(completed=0, total=0, percentage=0)

        # Default message
        message_map: dict[ProjectStatus, str] = {
            ProjectStatus.DRAFT: "项目已创建，等待上传",
            ProjectStatus.UPLOADED: "素材已上传，等待分析",
            ProjectStatus.ANALYZING: "正在分析项目素材...",
            ProjectStatus.GENERATING_ASSETS: "正在生成素材...",
            ProjectStatus.COMPLETED: "项目已完成",
            ProjectStatus.FAILED: "项目处理失败",
            ProjectStatus.ARCHIVED: "项目已归档",
        }
        message = message_map.get(status, "") if isinstance(status, ProjectStatus) else ""

        return ProjectStatusResponse(
            project_id=project.id,
            current_stage=current_stage,
            progress=progress,
            message=message,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _require_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
        """Fetch a project or raise ValueError with NOT_FOUND details."""
        project = await ProjectService.get_project(session, project_id)
        if project is None:
            raise ValueError(f"Project {project_id!s} not found")
        return project


def _coerce_project_status(value: object) -> ProjectStatus | str:
    """Return a ProjectStatus when possible, otherwise preserve the raw status string."""
    if isinstance(value, ProjectStatus):
        return value
    try:
        return ProjectStatus(str(value))
    except ValueError:
        return str(value)
