from __future__ import annotations

import importlib
import importlib.util
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.contracts.enums import ProjectStatus
from app.modules.character_library.models import Character
from app.modules.image_asset.audit_models import ImageAssetAuditLog
from app.modules.image_asset.models import ImageAsset, ImageGenerationTask
from app.modules.project.models import Project
from app.modules.prop_library.models import Prop
from app.modules.scene_library.models import Scene
from app.modules.storage.service import StorageService


def _require_module(module_name: str) -> Any:
    assert importlib.util.find_spec(module_name) is not None, f"missing module: {module_name}"
    return importlib.import_module(module_name)


def _freeze_service_now(monkeypatch: pytest.MonkeyPatch, library_module: Any, now: datetime) -> None:
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> _FrozenDateTime:
            value = now if tz is None else now.astimezone(tz)
            return cls.fromtimestamp(value.timestamp(), tz=value.tzinfo or UTC)

    monkeypatch.setattr(library_module, "datetime", _FrozenDateTime)


@pytest.fixture
async def library_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    schema_name = f"test_image_asset_library_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url)
    engine = create_async_engine(
        settings.database_url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )
    tables = [
        cast(Table, Project.__table__),
        cast(Table, Character.__table__),
        cast(Table, Scene.__table__),
        cast(Table, Prop.__table__),
        cast(Table, ImageAsset.__table__),
        cast(Table, ImageGenerationTask.__table__),
        cast(Table, ImageAssetAuditLog.__table__),
    ]

    def _create_tables(sync_conn: Any) -> None:
        for table in tables:
            table.create(sync_conn, checkfirst=True)

    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))

        async with engine.begin() as conn:
            await conn.run_sync(_create_tables)

        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await admin_engine.dispose()


async def _insert_project(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    user_id: str,
    title: str,
    status: ProjectStatus = ProjectStatus.DRAFT,
    deleted_at: datetime | None = None,
) -> None:
    session.add(
        Project(
            id=project_id,
            user_id=user_id,
            title=title,
            status=status,
            deleted_at=deleted_at,
            purge_after=deleted_at + timedelta(days=30) if deleted_at else None,
        )
    )
    await session.commit()


async def _insert_character(session: AsyncSession, *, project_id: uuid.UUID, character_id: str, name: str) -> None:
    session.add(Character(project_id=project_id, character_id=character_id, name=name))
    await session.commit()


async def _insert_scene(session: AsyncSession, *, project_id: uuid.UUID, scene_id: str, scene_name: str) -> None:
    session.add(
        Scene(project_id=project_id, scene_id=scene_id, scene_name=scene_name, fixed_anchors=["门", "窗", "桌"])
    )
    await session.commit()


async def _insert_prop(session: AsyncSession, *, project_id: uuid.UUID, prop_id: str, name: str) -> None:
    session.add(Prop(project_id=project_id, prop_id=prop_id, name=name, state_timeline=[]))
    await session.commit()


async def _insert_asset(
    session: AsyncSession,
    *,
    asset_id: uuid.UUID,
    project_id: uuid.UUID,
    asset_type: str,
    related_id: str | None,
    created_at: datetime,
    prompt: str,
    deleted_at: datetime | None = None,
    expires_at: datetime | None = None,
    generation_task_id: uuid.UUID | None = None,
) -> None:
    session.add(
        ImageAsset(
            id=asset_id,
            project_id=project_id,
            asset_type=asset_type,
            related_id=related_id,
            asset_url=f"https://example.com/{asset_id}.png",
            thumbnail_url=f"https://example.com/{asset_id}-thumb.png",
            storage_path=f"projects/{project_id}/{asset_id}.png",
            prompt=prompt,
            negative_prompt="",
            model_name="seedream-v1",
            provider_task_id=f"provider-{asset_id.hex[:8]}",
            generation_task_id=generation_task_id,
            width=1080,
            height=1920,
            reference_asset_ids=[],
            status="completed",
            created_at=created_at,
            updated_at=created_at,
            deleted_at=deleted_at,
            deleted_by="user-1" if deleted_at else None,
            purge_after=deleted_at + timedelta(days=30) if deleted_at else None,
            expires_at=expires_at or (created_at + timedelta(days=180)),
            delete_reason="manual" if deleted_at else None,
        )
    )
    await session.commit()


async def _insert_generation_task(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    project_id: uuid.UUID,
    asset_type: str,
    related_id: str | None,
    quality_status: str | None,
    created_at: datetime,
) -> None:
    session.add(
        ImageGenerationTask(
            id=task_id,
            project_id=project_id,
            asset_type=asset_type,
            related_id=related_id,
            provider="seedream",
            model_name="seedream-v1",
            request_json={},
            response_json={},
            status="success",
            retry_count=0,
            max_retries=3,
            error_message=None,
            quality_status=quality_status,
            quality_report_id=None,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    await session.commit()


class _StorageServiceSpy:
    def __init__(self, *, delete_error: Exception | None = None) -> None:
        self.delete_error = delete_error
        self.delete_calls: list[str] = []

    async def delete(self, asset_id: str) -> None:
        self.delete_calls.append(asset_id)
        if self.delete_error is not None:
            raise self.delete_error


@pytest.mark.asyncio
async def test_library_route_is_registered_before_dynamic_asset_route() -> None:
    from app.modules.image_asset.router import router

    route_paths = [route.path for route in router.routes if isinstance(route, APIRoute)]

    assert "/api/image-asset/library" in route_paths
    assert "/api/image-asset/{asset_id}" in route_paths
    assert route_paths.index("/api/image-asset/library") < route_paths.index("/api/image-asset/{asset_id}")


@pytest.mark.asyncio
async def test_trash_operation_routes_are_registered_before_dynamic_asset_route() -> None:
    from app.modules.image_asset.router import router

    route_paths = [route.path for route in router.routes if isinstance(route, APIRoute)]

    for path in (
        "/api/image-asset/trash",
        "/api/image-asset/batch-delete",
        "/api/image-asset/batch-restore",
        "/api/image-asset/batch-permanent-delete",
        "/api/image-asset/{asset_id}/restore",
        "/api/image-asset/{asset_id}/permanent",
        "/api/image-asset/{asset_id}",
    ):
        assert path in route_paths

    assert route_paths.index("/api/image-asset/trash") < route_paths.index("/api/image-asset/{asset_id}")
    assert route_paths.index("/api/image-asset/batch-delete") < route_paths.index("/api/image-asset/{asset_id}")
    assert route_paths.index("/api/image-asset/batch-restore") < route_paths.index("/api/image-asset/{asset_id}")
    assert route_paths.index("/api/image-asset/batch-permanent-delete") < route_paths.index(
        "/api/image-asset/{asset_id}"
    )


@pytest.mark.asyncio
async def test_list_library_groups_assets_and_excludes_trashed_expired_and_other_user_assets(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(StorageService.create())

    user_project_id = uuid.uuid4()
    archived_project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)
    archived_deleted_at = now - timedelta(days=2)
    char_task_id = uuid.uuid4()
    prop_task_id = uuid.uuid4()
    scene_task_id = uuid.uuid4()
    missing_task_id = uuid.uuid4()
    char_asset_id = uuid.uuid4()
    prop_asset_id = uuid.uuid4()
    scene_asset_id = uuid.uuid4()
    archived_asset_id = uuid.uuid4()

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=user_project_id, user_id="user-1", title="主项目")
        await _insert_project(
            session,
            project_id=archived_project_id,
            user_id="user-1",
            title="回收站项目",
            status=ProjectStatus.ARCHIVED,
            deleted_at=archived_deleted_at,
        )
        await _insert_project(session, project_id=other_project_id, user_id="user-2", title="其他人的项目")

        await _insert_character(session, project_id=user_project_id, character_id="CH_001", name="林小雨")
        await _insert_scene(session, project_id=user_project_id, scene_id="SC_001", scene_name="天台夜景")
        await _insert_prop(session, project_id=user_project_id, prop_id="PR_001", name="青铜钥匙")

        await _insert_generation_task(
            session,
            task_id=char_task_id,
            project_id=user_project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now - timedelta(minutes=1),
        )
        await _insert_generation_task(
            session,
            task_id=prop_task_id,
            project_id=user_project_id,
            asset_type="prop_product",
            related_id="PR_001",
            quality_status="needs_manual_review",
            created_at=now - timedelta(minutes=2),
        )
        await _insert_generation_task(
            session,
            task_id=scene_task_id,
            project_id=user_project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            quality_status="skipped",
            created_at=now - timedelta(days=1),
        )
        await _insert_generation_task(
            session,
            task_id=missing_task_id,
            project_id=archived_project_id,
            asset_type="character_expression",
            related_id="CH_999",
            quality_status="passed",
            created_at=now - timedelta(days=1, minutes=5),
        )

        await _insert_asset(
            session,
            asset_id=char_asset_id,
            project_id=user_project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(minutes=1),
            prompt="角色正面图 prompt " + ("A" * 140),
            generation_task_id=char_task_id,
            expires_at=now + timedelta(days=40),
        )
        await _insert_asset(
            session,
            asset_id=prop_asset_id,
            project_id=user_project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(minutes=2),
            prompt="道具单品图 prompt",
            generation_task_id=prop_task_id,
            expires_at=now + timedelta(days=5),
        )
        await _insert_asset(
            session,
            asset_id=scene_asset_id,
            project_id=user_project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(days=1),
            prompt="纯场景图 prompt",
            generation_task_id=scene_task_id,
            expires_at=now + timedelta(days=31),
        )
        await _insert_asset(
            session,
            asset_id=archived_asset_id,
            project_id=archived_project_id,
            asset_type="character_expression",
            related_id="CH_999",
            created_at=now - timedelta(days=1, minutes=5),
            prompt="已删除项目下的表情图 prompt",
            generation_task_id=missing_task_id,
            expires_at=now + timedelta(days=2),
        )

        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=user_project_id,
            asset_type="character_turnaround",
            related_id="CH_001",
            created_at=now - timedelta(minutes=3),
            prompt="图片回收站里的图片",
            deleted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=20),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=user_project_id,
            asset_type="scene_with_atmosphere",
            related_id="SC_001",
            created_at=now - timedelta(minutes=4),
            prompt="已过期图片",
            expires_at=now - timedelta(seconds=1),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=other_project_id,
            asset_type="prop_usage",
            related_id="PR_404",
            created_at=now - timedelta(minutes=5),
            prompt="其他用户图片",
            expires_at=now + timedelta(days=10),
        )

        response = await service.list_library(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetLibraryQuery(page=1, page_size=20),
        )

    assert response.total == 4
    assert [group.date for group in response.groups] == [date(2026, 7, 8), date(2026, 7, 7)]
    assert response.groups[0].project_count == 1
    assert response.groups[0].projects[0].project_id == user_project_id
    assert list(response.groups[0].projects[0].categories.keys()) == ["character", "prop", "scene"]
    assert [item.asset_id for item in response.groups[0].projects[0].categories["character"]] == [char_asset_id]
    assert [item.asset_id for item in response.groups[0].projects[0].categories["prop"]] == [prop_asset_id]
    assert [item.asset_id for item in response.groups[0].projects[0].categories["scene"]] == [scene_asset_id]
    assert response.groups[1].project_count == 1
    assert response.groups[1].projects[0].project_id == archived_project_id
    assert response.groups[1].projects[0].is_project_in_trash is True
    assert response.groups[1].projects[0].project_deleted_at == archived_deleted_at
    archived_item = response.groups[1].projects[0].categories["character"][0]
    assert archived_item.display_name == "CH_999"
    assert archived_item.related_name is None
    assert archived_item.quality_status == "passed"
    assert archived_item.project_status == ProjectStatus.ARCHIVED
    assert archived_item.prompt.startswith("已删除项目下的表情图")
    assert archived_item.prompt_summary.startswith("已删除项目下的表情图")
    assert archived_item.remaining_retention_days == 2
    assert archived_item.is_expiring_soon is True
    visible_item = response.groups[0].projects[0].categories["character"][0]
    assert visible_item.display_name == "林小雨"
    assert visible_item.related_name == "林小雨"
    assert visible_item.quality_status == "passed"
    assert visible_item.asset_type_label == "角色正面图"
    assert visible_item.project_title == "主项目"
    assert visible_item.storage_path.endswith(".png")
    assert visible_item.remaining_retention_days == 40
    assert visible_item.is_expiring_soon is False
    assert [option.project_id for option in response.available_projects] == [user_project_id, archived_project_id]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("keyword", "expected_related_name"),
    [
        ("项目甲", "林小雨"),
        ("CH_001", "林小雨"),
        ("林小雨", "林小雨"),
        ("天台夜景", "天台夜景"),
        ("青铜钥匙", "青铜钥匙"),
    ],
)
async def test_list_library_keyword_matches_project_related_id_and_related_names(
    library_session_factory: async_sessionmaker[AsyncSession],
    keyword: str,
    expected_related_name: str,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(StorageService.create())
    project_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="项目甲")
        await _insert_character(session, project_id=project_id, character_id="CH_001", name="林小雨")
        await _insert_scene(session, project_id=project_id, scene_id="SC_001", scene_name="天台夜景")
        await _insert_prop(session, project_id=project_id, prop_id="PR_001", name="青铜钥匙")

        char_task_id = uuid.uuid4()
        scene_task_id = uuid.uuid4()
        prop_task_id = uuid.uuid4()
        await _insert_generation_task(
            session,
            task_id=char_task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now,
        )
        await _insert_generation_task(
            session,
            task_id=scene_task_id,
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            quality_status="passed",
            created_at=now - timedelta(minutes=1),
        )
        await _insert_generation_task(
            session,
            task_id=prop_task_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            quality_status="passed",
            created_at=now - timedelta(minutes=2),
        )

        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now,
            prompt="角色 prompt",
            generation_task_id=char_task_id,
            expires_at=now + timedelta(days=10),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(minutes=1),
            prompt="场景 prompt",
            generation_task_id=scene_task_id,
            expires_at=now + timedelta(days=10),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(minutes=2),
            prompt="道具 prompt",
            generation_task_id=prop_task_id,
            expires_at=now + timedelta(days=10),
        )

        response = await service.list_library(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetLibraryQuery(keyword=keyword, page=1, page_size=20),
        )

    items = [
        item
        for group in response.groups
        for project in group.projects
        for category_items in project.categories.values()
        for item in category_items
    ]
    assert len(items) >= 1
    assert expected_related_name in {item.related_name for item in items}


@pytest.mark.asyncio
async def test_list_library_paginates_by_image_rows_and_available_projects_only_uses_current_page(
    library_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(StorageService.create())
    first_project_id = uuid.uuid4()
    second_project_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=first_project_id, user_id="user-1", title="第一页项目")
        await _insert_project(session, project_id=second_project_id, user_id="user-1", title="第二页项目")

        for index, project_id in enumerate((first_project_id, first_project_id, second_project_id), start=1):
            task_id = uuid.uuid4()
            related_id = f"CH_{index:03d}"
            await _insert_character(session, project_id=project_id, character_id=related_id, name=f"角色{index}")
            await _insert_generation_task(
                session,
                task_id=task_id,
                project_id=project_id,
                asset_type="character_front",
                related_id=related_id,
                quality_status="passed",
                created_at=now - timedelta(minutes=index),
            )
            await _insert_asset(
                session,
                asset_id=uuid.uuid4(),
                project_id=project_id,
                asset_type="character_front",
                related_id=related_id,
                created_at=now - timedelta(minutes=index),
                prompt=f"prompt {index}",
                generation_task_id=task_id,
                expires_at=now + timedelta(days=10),
            )

        response = await service.list_library(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetLibraryQuery(page=1, page_size=2),
        )

    items = [
        item
        for group in response.groups
        for project in group.projects
        for category_items in project.categories.values()
        for item in category_items
    ]
    assert response.total == 3
    assert len(items) == 2
    assert {item.project_id for item in items} == {first_project_id}
    assert [option.project_id for option in response.available_projects] == [first_project_id]


@pytest.mark.asyncio
async def test_list_library_date_filter_uses_asia_shanghai_archive_day_boundaries(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(StorageService.create())
    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
    created_at = datetime(2026, 7, 7, 16, 30, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="跨时区项目")
        await _insert_character(session, project_id=project_id, character_id="CH_001", name="时区角色")
        await _insert_generation_task(
            session,
            task_id=task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=created_at,
        )
        await _insert_asset(
            session,
            asset_id=asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=created_at,
            prompt="跨 UTC 边界图片",
            generation_task_id=task_id,
            expires_at=now + timedelta(days=10),
        )

        response = await service.list_library(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetLibraryQuery(
                date_from=date(2026, 7, 8),
                date_to=date(2026, 7, 8),
                page=1,
                page_size=20,
            ),
        )

    items = [
        item
        for group in response.groups
        for project in group.projects
        for category_items in project.categories.values()
        for item in category_items
    ]
    assert response.total == 1
    assert [group.date for group in response.groups] == [date(2026, 7, 8)]
    assert [item.asset_id for item in items] == [asset_id]


@pytest.mark.asyncio
async def test_list_trash_returns_only_current_user_assets_sorted_by_deleted_at(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(_StorageServiceSpy())
    project_id = uuid.uuid4()
    archived_project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)
    latest_asset_id = uuid.uuid4()
    older_asset_id = uuid.uuid4()

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="正常项目")
        await _insert_project(
            session,
            project_id=archived_project_id,
            user_id="user-1",
            title="回收站项目",
            status=ProjectStatus.ARCHIVED,
            deleted_at=now - timedelta(days=3),
        )
        await _insert_project(session, project_id=other_project_id, user_id="user-2", title="他人项目")

        await _insert_asset(
            session,
            asset_id=latest_asset_id,
            project_id=archived_project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=10),
            prompt="archived trash asset",
            deleted_at=now - timedelta(hours=3),
            expires_at=now + timedelta(days=90),
        )
        await _insert_asset(
            session,
            asset_id=older_asset_id,
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(days=9),
            prompt="older trash asset",
            deleted_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=15),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(days=8),
            prompt="expired trash asset",
            deleted_at=now - timedelta(hours=2),
            expires_at=now - timedelta(seconds=1),
        )
        await _insert_asset(
            session,
            asset_id=uuid.uuid4(),
            project_id=other_project_id,
            asset_type="prop_usage",
            related_id="PR_404",
            created_at=now - timedelta(days=8),
            prompt="other user trash asset",
            deleted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=20),
        )

        response = await service.list_trash(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetTrashQuery(page=1, page_size=20),
        )

    assert response.total == 2
    assert [item.asset_id for item in response.items] == [latest_asset_id, older_asset_id]
    assert [item.project_id for item in response.available_projects] == [archived_project_id, project_id]
    assert response.items[0].remaining_cleanup_days == 30
    assert response.items[0].can_restore is True
    assert response.items[0].display_name == "CH_001"
    assert response.items[0].project_status == ProjectStatus.ARCHIVED
    assert response.items[0].project_deleted_at == now - timedelta(days=3)
    assert response.items[0].created_at == now - timedelta(days=10)
    assert response.items[0].quality_status is None
    assert response.items[0].prompt == "archived trash asset"
    assert response.items[0].prompt_summary == "archived trash asset"
    assert response.items[1].remaining_cleanup_days == 29
    assert response.items[1].display_name == "SC_001"


@pytest.mark.asyncio
async def test_list_trash_date_filter_uses_deleted_at_local_day_boundaries(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(_StorageServiceSpy())
    project_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
    task_id = uuid.uuid4()
    in_range_asset_id = uuid.uuid4()
    out_of_range_asset_id = uuid.uuid4()
    deleted_at_in_range = datetime(2026, 7, 7, 16, 30, tzinfo=UTC)
    deleted_at_out_of_range = datetime(2026, 7, 8, 16, 30, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="回收站日期筛选项目")
        await _insert_character(session, project_id=project_id, character_id="CH_001", name="时区角色")
        await _insert_generation_task(
            session,
            task_id=task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now - timedelta(days=1),
        )
        await _insert_asset(
            session,
            asset_id=in_range_asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=2),
            prompt="命中删除日期范围",
            deleted_at=deleted_at_in_range,
            expires_at=now + timedelta(days=20),
            generation_task_id=task_id,
        )
        await _insert_asset(
            session,
            asset_id=out_of_range_asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=3),
            prompt="不命中删除日期范围",
            deleted_at=deleted_at_out_of_range,
            expires_at=now + timedelta(days=20),
            generation_task_id=task_id,
        )

        response = await service.list_trash(
            session,
            user_id="user-1",
            filters=schemas_module.ImageAssetTrashQuery(
                date_from=date(2026, 7, 8),
                date_to=date(2026, 7, 8),
                page=1,
                page_size=20,
            ),
        )

    assert response.total == 1
    assert [item.asset_id for item in response.items] == [in_range_asset_id]


@pytest.mark.asyncio
async def test_soft_delete_asset_sets_trash_fields_is_idempotent_and_keeps_generation_task(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    storage_spy = _StorageServiceSpy()
    service = library_module.ImageAssetLibraryService(storage_spy)
    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="删除项目")
        await _insert_generation_task(
            session,
            task_id=task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now - timedelta(minutes=1),
        )
        await _insert_asset(
            session,
            asset_id=asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(minutes=1),
            prompt="delete me",
            generation_task_id=task_id,
            expires_at=now + timedelta(days=50),
        )

        first = await service.soft_delete_asset(session, asset_id=asset_id, user_id="user-1")
        second = await service.soft_delete_asset(session, asset_id=asset_id, user_id="user-1")

        stored_asset = await session.get(ImageAsset, asset_id)
        stored_task = await session.get(ImageGenerationTask, task_id)
        audit_actions = (
            (
                await session.execute(
                    text("SELECT action FROM image_asset_audit_logs WHERE asset_id = :asset_id"), {"asset_id": asset_id}
                )
            )
            .scalars()
            .all()
        )

    assert first.status == "success"
    assert first.code == "IMAGE_ASSET_TRASHED"
    assert second.status == "success"
    assert second.code == "IMAGE_ASSET_ALREADY_TRASHED"
    assert stored_asset is not None
    assert stored_asset.deleted_at == now
    assert stored_asset.deleted_by == "user-1"
    assert stored_asset.purge_after == now + timedelta(days=30)
    assert stored_asset.delete_reason == "manual"
    assert stored_task is not None
    assert storage_spy.delete_calls == []
    assert audit_actions == [audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH]


@pytest.mark.asyncio
async def test_soft_delete_asset_system_user_still_cannot_bypass_project_ownership(
    library_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    service = library_module.ImageAssetLibraryService(_StorageServiceSpy())
    project_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="owner-user", title="他人项目")
        await _insert_asset(
            session,
            asset_id=asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now,
            prompt="foreign asset",
            expires_at=now + timedelta(days=30),
        )

        with pytest.raises(ValueError, match="IMAGE_ASSET_FORBIDDEN"):
            await service.soft_delete_asset(session, asset_id=asset_id, user_id="system")


@pytest.mark.asyncio
async def test_restore_asset_clears_trash_fields_without_restoring_project_and_blocks_expired_assets(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    service = library_module.ImageAssetLibraryService(_StorageServiceSpy())
    archived_project_id = uuid.uuid4()
    restore_asset_id = uuid.uuid4()
    expired_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(
            session,
            project_id=archived_project_id,
            user_id="user-1",
            title="已删除项目",
            status=ProjectStatus.ARCHIVED,
            deleted_at=now - timedelta(days=3),
        )
        await _insert_asset(
            session,
            asset_id=restore_asset_id,
            project_id=archived_project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=10),
            prompt="restore me",
            deleted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=10),
        )
        await _insert_asset(
            session,
            asset_id=expired_asset_id,
            project_id=archived_project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(days=20),
            prompt="expired restore",
            deleted_at=now - timedelta(hours=2),
            expires_at=now,
        )

        result = await service.restore_asset(session, asset_id=restore_asset_id, user_id="user-1")
        with pytest.raises(ValueError, match="IMAGE_ASSET_EXPIRED"):
            await service.restore_asset(session, asset_id=expired_asset_id, user_id="user-1")

        restored_asset = await session.get(ImageAsset, restore_asset_id)
        restored_project = await session.get(Project, archived_project_id)
        audit_actions = (
            (
                await session.execute(
                    text("SELECT action FROM image_asset_audit_logs WHERE asset_id = :asset_id"),
                    {"asset_id": restore_asset_id},
                )
            )
            .scalars()
            .all()
        )

    assert result.status == "success"
    assert result.code == "IMAGE_ASSET_RESTORED"
    assert restored_asset is not None
    assert restored_asset.deleted_at is None
    assert restored_asset.deleted_by is None
    assert restored_asset.purge_after is None
    assert restored_asset.delete_reason is None
    assert restored_project is not None
    assert restored_project.deleted_at == now - timedelta(days=3)
    assert restored_project.status == ProjectStatus.ARCHIVED
    assert audit_actions == [audit_service_module.IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH]


@pytest.mark.asyncio
async def test_permanent_delete_asset_deletes_storage_then_generation_task_and_asset_and_writes_audit(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    storage_spy = _StorageServiceSpy()
    service = library_module.ImageAssetLibraryService(storage_spy)
    project_id = uuid.uuid4()
    task_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="永久删除项目")
        await _insert_generation_task(
            session,
            task_id=task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now - timedelta(minutes=1),
        )
        await _insert_asset(
            session,
            asset_id=asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(minutes=1),
            prompt="sensitive prompt",
            generation_task_id=task_id,
            deleted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=5),
        )

        result = await service.permanent_delete_asset(
            session,
            asset_id=asset_id,
            user_id="user-1",
            reason="manual_permanent",
        )

        deleted_asset = await session.get(ImageAsset, asset_id)
        deleted_task = await session.get(ImageGenerationTask, task_id)
        audit_row = (
            await session.execute(
                text("SELECT action, details::text FROM image_asset_audit_logs WHERE asset_id = :asset_id"),
                {"asset_id": asset_id},
            )
        ).one()

    assert result.status == "success"
    assert result.code == "IMAGE_ASSET_PERMANENTLY_DELETED"
    assert storage_spy.delete_calls == [f"projects/{project_id}/{asset_id}.png"]
    assert deleted_asset is None
    assert deleted_task is None
    assert audit_row[0] == audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE
    assert "generation_task_summary" in audit_row[1]
    assert "sensitive prompt" not in audit_row[1]
    assert "https://example.com" not in audit_row[1]
    assert f"projects/{project_id}/{asset_id}.png" not in audit_row[1]


@pytest.mark.asyncio
async def test_permanent_delete_asset_keeps_db_records_when_storage_delete_fails_but_allows_missing_file(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    project_id = uuid.uuid4()
    failed_asset_id = uuid.uuid4()
    missing_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="存储失败项目")
        await _insert_asset(
            session,
            asset_id=failed_asset_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(minutes=2),
            prompt="keep db record",
            deleted_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=3),
        )
        await _insert_asset(
            session,
            asset_id=missing_asset_id,
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(minutes=3),
            prompt="missing file delete",
            deleted_at=now - timedelta(hours=2),
            expires_at=now + timedelta(days=3),
        )

        failing_service = library_module.ImageAssetLibraryService(
            _StorageServiceSpy(delete_error=PermissionError("denied"))
        )
        with pytest.raises(ValueError, match="IMAGE_ASSET_STORAGE_DELETE_FAILED"):
            await failing_service.permanent_delete_asset(
                session,
                asset_id=failed_asset_id,
                user_id="user-1",
                reason="manual_permanent",
            )

        missing_file_service = library_module.ImageAssetLibraryService(
            _StorageServiceSpy(delete_error=FileNotFoundError("missing"))
        )
        result = await missing_file_service.permanent_delete_asset(
            session,
            asset_id=missing_asset_id,
            user_id="user-1",
            reason="manual_permanent",
        )

        failed_asset = await session.get(ImageAsset, failed_asset_id)
        deleted_missing_asset = await session.get(ImageAsset, missing_asset_id)

    assert failed_asset is not None
    assert result.code == "IMAGE_ASSET_PERMANENTLY_DELETED"
    assert deleted_missing_asset is None


@pytest.mark.asyncio
async def test_batch_trash_restore_and_permanent_delete_return_partial_failures(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = library_module.ImageAssetLibraryService(_StorageServiceSpy())
    user_project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    deletable_asset_id = uuid.uuid4()
    other_user_asset_id = uuid.uuid4()
    restore_ok_asset_id = uuid.uuid4()
    restore_expired_asset_id = uuid.uuid4()
    delete_ok_asset_id = uuid.uuid4()
    delete_forbidden_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=user_project_id, user_id="user-1", title="我的项目")
        await _insert_project(session, project_id=other_project_id, user_id="user-2", title="其他项目")
        for asset_id, project_id, deleted_at, expires_at in (
            (deletable_asset_id, user_project_id, None, now + timedelta(days=30)),
            (other_user_asset_id, other_project_id, None, now + timedelta(days=30)),
            (restore_ok_asset_id, user_project_id, now - timedelta(hours=1), now + timedelta(days=30)),
            (restore_expired_asset_id, user_project_id, now - timedelta(hours=2), now),
            (delete_ok_asset_id, user_project_id, now - timedelta(hours=3), now + timedelta(days=30)),
            (delete_forbidden_asset_id, other_project_id, now - timedelta(hours=4), now + timedelta(days=30)),
        ):
            await _insert_asset(
                session,
                asset_id=asset_id,
                project_id=project_id,
                asset_type="character_front",
                related_id="CH_001",
                created_at=now - timedelta(days=1),
                prompt="batch asset",
                deleted_at=deleted_at,
                expires_at=expires_at,
            )

        delete_response = await service.batch_soft_delete_assets(
            session,
            user_id="user-1",
            asset_ids=[deletable_asset_id, other_user_asset_id],
        )
        restore_response = await service.batch_restore_assets(
            session,
            user_id="user-1",
            asset_ids=[restore_ok_asset_id, restore_expired_asset_id],
        )
        permanent_response = await service.batch_permanent_delete_assets(
            session,
            user_id="user-1",
            requests=[
                schemas_module.ImageAssetPermanentDeleteRequest(asset_id=delete_ok_asset_id, reason="manual_permanent"),
                schemas_module.ImageAssetPermanentDeleteRequest(
                    asset_id=delete_forbidden_asset_id,
                    reason="manual_permanent",
                ),
            ],
        )

    assert delete_response.total == 2
    assert delete_response.succeeded == 1
    assert delete_response.failed == 1
    assert [result.code for result in delete_response.results] == ["IMAGE_ASSET_TRASHED", "IMAGE_ASSET_FORBIDDEN"]

    assert restore_response.total == 2
    assert restore_response.succeeded == 1
    assert restore_response.failed == 1
    assert [result.code for result in restore_response.results] == ["IMAGE_ASSET_RESTORED", "IMAGE_ASSET_EXPIRED"]

    assert permanent_response.total == 2
    assert permanent_response.succeeded == 1
    assert permanent_response.failed == 1
    assert [result.code for result in permanent_response.results] == [
        "IMAGE_ASSET_PERMANENTLY_DELETED",
        "IMAGE_ASSET_FORBIDDEN",
    ]


@pytest.mark.asyncio
async def test_purge_expired_assets_dry_run_counts_candidates_without_deleting_or_auditing(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    storage_spy = _StorageServiceSpy()
    service = library_module.ImageAssetLibraryService(storage_spy)
    project_id = uuid.uuid4()
    trashed_asset_id = uuid.uuid4()
    retained_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="清理项目")
        await _insert_asset(
            session,
            asset_id=trashed_asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=120),
            prompt="trash expired",
            deleted_at=now - timedelta(days=40),
            expires_at=now + timedelta(days=20),
        )
        await _insert_asset(
            session,
            asset_id=retained_asset_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(days=190),
            prompt="retention expired",
            expires_at=now - timedelta(seconds=1),
        )

        result = await service.purge_expired_assets(session, limit=10, dry_run=True)
        stored_trashed_asset = await session.get(ImageAsset, trashed_asset_id)
        stored_retained_asset = await session.get(ImageAsset, retained_asset_id)
        audit_actions = (
            (
                await session.execute(
                    text("SELECT action FROM image_asset_audit_logs ORDER BY created_at ASC"),
                )
            )
            .scalars()
            .all()
        )

    assert result.trash_expired_count == 1
    assert result.retention_expired_count == 1
    assert result.storage_failed_count == 0
    assert result.deleted_count == 0
    assert storage_spy.delete_calls == []
    assert stored_trashed_asset is not None
    assert stored_retained_asset is not None
    assert audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED not in audit_actions


@pytest.mark.asyncio
async def test_purge_expired_assets_deletes_expired_assets_uses_earliest_deadline_and_writes_audit(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    storage_spy = _StorageServiceSpy()
    service = library_module.ImageAssetLibraryService(storage_spy)
    project_id = uuid.uuid4()
    trash_task_id = uuid.uuid4()
    trash_asset_id = uuid.uuid4()
    retention_task_id = uuid.uuid4()
    retention_asset_id = uuid.uuid4()
    future_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="自动清理项目")
        await _insert_generation_task(
            session,
            task_id=trash_task_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            quality_status="passed",
            created_at=now - timedelta(days=200),
        )
        await _insert_generation_task(
            session,
            task_id=retention_task_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            quality_status="passed",
            created_at=now - timedelta(days=220),
        )
        await _insert_asset(
            session,
            asset_id=trash_asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=200),
            prompt="trash purge first",
            generation_task_id=trash_task_id,
            deleted_at=now - timedelta(days=31),
            expires_at=now + timedelta(days=20),
        )
        await _insert_asset(
            session,
            asset_id=retention_asset_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(days=220),
            prompt="retention purge",
            generation_task_id=retention_task_id,
            expires_at=now - timedelta(seconds=2),
        )
        await _insert_asset(
            session,
            asset_id=future_asset_id,
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(days=20),
            prompt="keep future asset",
            deleted_at=now - timedelta(days=5),
            expires_at=now + timedelta(days=20),
        )

        result = await service.purge_expired_assets(session, limit=10, dry_run=False)
        deleted_trash_asset = await session.get(ImageAsset, trash_asset_id)
        deleted_retention_asset = await session.get(ImageAsset, retention_asset_id)
        retained_future_asset = await session.get(ImageAsset, future_asset_id)
        deleted_trash_task = await session.get(ImageGenerationTask, trash_task_id)
        deleted_retention_task = await session.get(ImageGenerationTask, retention_task_id)
        audit_rows = (
            await session.execute(
                text(
                    "SELECT asset_id, user_id, action, reason FROM image_asset_audit_logs "
                    "WHERE action = :action ORDER BY reason ASC, created_at ASC"
                ),
                {"action": audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED},
            )
        ).all()

    assert result.trash_expired_count == 1
    assert result.retention_expired_count == 1
    assert result.storage_failed_count == 0
    assert result.deleted_count == 2
    assert storage_spy.delete_calls == [
        f"projects/{project_id}/{trash_asset_id}.png",
        f"projects/{project_id}/{retention_asset_id}.png",
    ]
    assert deleted_trash_asset is None
    assert deleted_retention_asset is None
    assert retained_future_asset is not None
    assert deleted_trash_task is None
    assert deleted_retention_task is None
    assert [(row[0], row[1], row[2], row[3]) for row in audit_rows] == [
        (
            retention_asset_id,
            "system",
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
            "retention_expired",
        ),
        (
            trash_asset_id,
            "system",
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
            "trash_expired",
        ),
    ]


@pytest.mark.asyncio
async def test_purge_expired_assets_respects_limit_and_keeps_records_when_storage_delete_fails(
    library_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library_module = _require_module("app.modules.image_asset.library_service")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    project_id = uuid.uuid4()
    failed_asset_id = uuid.uuid4()
    deleted_asset_id = uuid.uuid4()
    skipped_asset_id = uuid.uuid4()
    now = datetime(2026, 7, 8, 16, 0, tzinfo=UTC)

    _freeze_service_now(monkeypatch, library_module, now)

    class _ConditionalStorageSpy:
        def __init__(self, failing_path: str) -> None:
            self.failing_path = failing_path
            self.delete_calls: list[str] = []

        async def delete(self, asset_id: str) -> None:
            self.delete_calls.append(asset_id)
            if asset_id == self.failing_path:
                raise PermissionError("denied")

    failing_path = f"projects/{project_id}/{failed_asset_id}.png"
    storage_spy = _ConditionalStorageSpy(failing_path)
    service = library_module.ImageAssetLibraryService(storage_spy)

    async with library_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="限流清理项目")
        await _insert_asset(
            session,
            asset_id=failed_asset_id,
            project_id=project_id,
            asset_type="character_front",
            related_id="CH_001",
            created_at=now - timedelta(days=200),
            prompt="storage failure",
            deleted_at=now - timedelta(days=31),
            expires_at=now + timedelta(days=10),
        )
        await _insert_asset(
            session,
            asset_id=deleted_asset_id,
            project_id=project_id,
            asset_type="prop_product",
            related_id="PR_001",
            created_at=now - timedelta(days=210),
            prompt="delete succeeds",
            expires_at=now - timedelta(days=2),
        )
        await _insert_asset(
            session,
            asset_id=skipped_asset_id,
            project_id=project_id,
            asset_type="scene_empty",
            related_id="SC_001",
            created_at=now - timedelta(days=220),
            prompt="skip by limit",
            deleted_at=now - timedelta(days=30, hours=1),
            expires_at=now + timedelta(days=5),
        )

        result = await service.purge_expired_assets(session, limit=2, dry_run=False)
        kept_failed_asset = await session.get(ImageAsset, failed_asset_id)
        deleted_asset = await session.get(ImageAsset, deleted_asset_id)
        skipped_asset = await session.get(ImageAsset, skipped_asset_id)
        purge_logs = (
            await session.execute(
                text(
                    "SELECT asset_id, reason FROM image_asset_audit_logs "
                    "WHERE action = :action ORDER BY created_at ASC"
                ),
                {"action": audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED},
            )
        ).all()

    assert result.trash_expired_count == 1
    assert result.retention_expired_count == 1
    assert result.storage_failed_count == 1
    assert result.deleted_count == 1
    assert set(storage_spy.delete_calls) == {
        f"projects/{project_id}/{deleted_asset_id}.png",
        failing_path,
    }
    assert kept_failed_asset is not None
    assert deleted_asset is None
    assert skipped_asset is not None
    assert purge_logs == [(deleted_asset_id, "retention_expired")]


class _FailingLibraryService:
    def __init__(self, error_message: str) -> None:
        self.error_message = error_message

    async def soft_delete_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> Any:
        raise ValueError(self.error_message)

    async def restore_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
    ) -> Any:
        raise ValueError(self.error_message)

    async def permanent_delete_asset(
        self,
        session: AsyncSession,
        *,
        asset_id: uuid.UUID,
        user_id: str,
        reason: str,
    ) -> Any:
        raise ValueError(self.error_message)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("route_name", "error_message", "expected_code"),
    [
        ("restore_asset_from_trash", "IMAGE_ASSET_EXPIRED: asset already expired", "IMAGE_ASSET_EXPIRED"),
        (
            "permanent_delete_asset",
            "IMAGE_ASSET_STORAGE_DELETE_FAILED: failed to delete asset from storage",
            "IMAGE_ASSET_STORAGE_DELETE_FAILED",
        ),
    ],
)
async def test_single_asset_routes_preserve_business_error_code(
    route_name: str,
    error_message: str,
    expected_code: str,
) -> None:
    router_module = _require_module("app.modules.image_asset.router")
    route_handler = getattr(router_module, route_name)

    with pytest.raises(HTTPException) as exc_info:
        await route_handler(
            asset_id=uuid.uuid4(),
            session=cast(AsyncSession, object()),
            user_id="user-1",
            service=_FailingLibraryService(error_message),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == expected_code
    assert exc_info.value.detail["message"] == error_message
