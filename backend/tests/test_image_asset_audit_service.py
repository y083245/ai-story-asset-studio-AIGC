from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import Table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.modules.project.models import Project


def _require_module(module_name: str) -> Any:
    assert importlib.util.find_spec(module_name) is not None, f"missing module: {module_name}"
    return importlib.import_module(module_name)


@pytest.fixture
async def audit_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    audit_models = _require_module("app.modules.image_asset.audit_models")
    project_table = cast(Table, Project.__table__)
    audit_table = cast(Table, audit_models.ImageAssetAuditLog.__table__)
    schema_name = f"test_image_asset_audit_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url)
    engine = create_async_engine(
        settings.database_url,
        connect_args={"server_settings": {"search_path": schema_name}},
    )

    def _create_tables(sync_conn: Any) -> None:
        project_table.create(sync_conn, checkfirst=True)
        audit_table.create(sync_conn, checkfirst=True)

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


async def _insert_project(session: AsyncSession, *, project_id: uuid.UUID, user_id: str, title: str) -> None:
    session.add(Project(id=project_id, user_id=user_id, title=title))
    await session.commit()


@pytest.mark.asyncio
async def test_audit_route_is_registered_before_dynamic_asset_route() -> None:
    from app.modules.image_asset.router import router

    route_paths = [route.path for route in router.routes if isinstance(route, APIRoute)]

    assert "/api/image-asset/audit-logs" in route_paths
    assert "/api/image-asset/{asset_id}" in route_paths
    assert route_paths.index("/api/image-asset/audit-logs") < route_paths.index("/api/image-asset/{asset_id}")


@pytest.mark.asyncio
async def test_record_persists_hashed_storage_path_and_sanitized_details(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_models = _require_module("app.modules.image_asset.audit_models")
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    service = audit_service_module.ImageAssetAuditService
    project_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    raw_storage_path = "projects/demo/asset-secret.png"

    async with audit_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="Project One")

    async with audit_session_factory() as session:
        await service.record(
            session,
            project_id=project_id,
            asset_id=asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason="manual",
            asset_type="character_front",
            related_id="CH_001",
            storage_path=raw_storage_path,
            details={
                "asset_id": str(asset_id),
                "asset_type": "character_front",
                "related_id": "CH_001",
                "prompt": "must be removed",
                "negative_prompt": "must be removed",
                "asset_url": "https://example.com/full.png",
                "thumbnail_url": "https://example.com/thumb.png",
                "storage_path": raw_storage_path,
                "api_key": "fixture-redacted-token",
                "novel_body": "这里是小说正文",
                "generation_task_summary": {
                    "generation_task_id": str(uuid.uuid4()),
                    "provider": "doubao_seedream",
                    "model_name": "doubao-seedream-5.0-lite",
                    "status": "success",
                    "quality_status": "passed",
                    "prompt": "nested prompt",
                    "asset_url": "https://example.com/nested.png",
                },
            },
        )
        await session.commit()

    async with audit_session_factory() as session:
        rows = (
            await session.execute(text("SELECT storage_path_hash, details::text FROM image_asset_audit_logs"))
        ).all()
        assert len(rows) == 1
        assert rows[0][0] == hashlib.sha256(raw_storage_path.encode("utf-8")).hexdigest()
        assert raw_storage_path not in rows[0][1]
        assert "https://example.com" not in rows[0][1]
        assert "fixture-redacted-token" not in rows[0][1]
        assert "这里是小说正文" not in rows[0][1]

        log = (await session.execute(text("SELECT id FROM image_asset_audit_logs"))).scalar_one()
        stored = await session.get(audit_models.ImageAssetAuditLog, log)

    assert stored is not None
    assert stored.storage_path_hash == hashlib.sha256(raw_storage_path.encode("utf-8")).hexdigest()
    assert stored.details["generation_task_summary"]["provider"] == "doubao_seedream"
    assert "prompt" not in stored.details
    assert "negative_prompt" not in stored.details
    assert "asset_url" not in stored.details
    assert "thumbnail_url" not in stored.details
    assert "storage_path" not in stored.details
    assert "api_key" not in stored.details
    assert "novel_body" not in stored.details
    assert "prompt" not in stored.details["generation_task_summary"]
    assert "asset_url" not in stored.details["generation_task_summary"]


@pytest.mark.asyncio
async def test_record_drops_neutral_key_sensitive_values_from_db_and_list_logs_response(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    service = audit_service_module.ImageAssetAuditService
    project_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    sensitive_url = "https://example.com/a.png"
    sensitive_storage_path = "projects/demo/raw.png"
    sensitive_token = "provider-secret"
    sensitive_excerpt = "这是小说正文片段，包含角色秘密与关键剧情。"

    async with audit_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="Project One")

    async with audit_session_factory() as session:
        await service.record(
            session,
            project_id=project_id,
            asset_id=asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason="manual",
            asset_type="character_front",
            related_id="CH_001",
            storage_path="projects/demo/audit-asset.png",
            details={
                "asset_id": str(asset_id),
                "asset_type": "character_front",
                "related_id": "CH_001",
                "reason": "manual",
                "generation_task_summary": {
                    "generation_task_id": str(uuid.uuid4()),
                    "provider": "doubao_seedream",
                    "model_name": "doubao-seedream-5.0-lite",
                    "status": "success",
                    "quality_status": "passed",
                },
                "note": sensitive_url,
                "message": sensitive_storage_path,
                "token": sensitive_token,
                "body_excerpt": sensitive_excerpt,
            },
        )
        await session.commit()

    async with audit_session_factory() as session:
        details_text = (
            await session.execute(
                text("SELECT details::text FROM image_asset_audit_logs WHERE asset_id = :asset_id"),
                {"asset_id": asset_id},
            )
        ).scalar_one()
        response = await service.list_logs(
            session,
            user_id="user-1",
            project_id=project_id,
            asset_id=asset_id,
            page=1,
            page_size=10,
        )

    response_json = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)

    for sensitive_value in (sensitive_url, sensitive_storage_path, sensitive_token, sensitive_excerpt):
        assert sensitive_value not in details_text
        assert sensitive_value not in response_json

    assert len(response.items) == 1
    assert response.items[0].details["generation_task_summary"]["provider"] == "doubao_seedream"
    assert "note" not in response.items[0].details
    assert "message" not in response.items[0].details
    assert "token" not in response.items[0].details
    assert "body_excerpt" not in response.items[0].details


@pytest.mark.asyncio
async def test_record_sanitizes_top_level_fields_before_db_write_and_list_logs_response(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    service = audit_service_module.ImageAssetAuditService
    project_id = uuid.uuid4()
    sensitive_asset_id = uuid.uuid4()
    safe_asset_id = uuid.uuid4()
    sensitive_url = "https://x.y/z"
    sensitive_storage_path = "projects/raw.png"
    sensitive_token = "api-key-demo-123"
    sensitive_excerpt = "这是小说正文片段包含角色秘密和关键剧情原文"

    async with audit_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="Project One")

    async with audit_session_factory() as session:
        await service.record(
            session,
            project_id=project_id,
            asset_id=sensitive_asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason=sensitive_url,
            asset_type=sensitive_storage_path,
            related_id=sensitive_token,
            storage_path="projects/demo/audit-asset.png",
            details={"asset_id": str(sensitive_asset_id)},
        )
        await service.record(
            session,
            project_id=project_id,
            asset_id=safe_asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
            reason="manual",
            asset_type="character_front",
            related_id="CH_001",
            storage_path="projects/demo/safe-asset.png",
            details={"asset_id": str(safe_asset_id)},
        )
        await service.record(
            session,
            project_id=project_id,
            asset_id=uuid.uuid4(),
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
            reason=sensitive_excerpt,
            asset_type="character_front",
            related_id="CH_002",
            storage_path="projects/demo/chinese-asset.png",
            details={"asset_id": str(uuid.uuid4())},
        )
        await session.commit()

    async with audit_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT reason, asset_type, related_id
                    FROM image_asset_audit_logs
                    WHERE project_id = :project_id
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"project_id": project_id},
            )
        ).all()
        response = await service.list_logs(
            session,
            user_id="user-1",
            project_id=project_id,
            asset_id=None,
            page=1,
            page_size=10,
        )

    response_json = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
    db_text = json.dumps([tuple(row) for row in rows], ensure_ascii=False)

    for sensitive_value in (sensitive_url, sensitive_storage_path, sensitive_token, sensitive_excerpt):
        assert sensitive_value not in db_text
        assert sensitive_value not in response_json

    assert ("manual", "character_front", "CH_001") in [tuple(row) for row in rows]
    assert any(
        item.reason == "manual" and item.asset_type == "character_front" and item.related_id == "CH_001"
        for item in response.items
    )


@pytest.mark.asyncio
async def test_record_applies_field_whitelists_to_reviewer_bypass_values(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    service = audit_service_module.ImageAssetAuditService
    project_id = uuid.uuid4()
    invalid_asset_id = uuid.uuid4()
    safe_asset_id = uuid.uuid4()
    invalid_file_url = "file:///Users/example/story-asset-studio/local_storage/projects/demo/raw.png"
    invalid_s3_url = "s3://bucket/projects/demo/raw.png"
    invalid_local_storage_path = "/Users/example/story-asset-studio/local_storage/projects/demo/raw.png"
    invalid_story_excerpt = "她推开门看见血迹"

    async with audit_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="Project One")

    async with audit_session_factory() as session:
        await service.record(
            session,
            project_id=project_id,
            asset_id=invalid_asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason=invalid_file_url,
            asset_type=invalid_story_excerpt,
            related_id=invalid_s3_url,
            storage_path="projects/demo/invalid-asset.png",
            details={
                "asset_id": str(invalid_asset_id),
                "reason": invalid_local_storage_path,
                "asset_type": "character_front",
                "related_id": "CH_999",
                "generation_task_summary": {
                    "generation_task_id": str(uuid.uuid4()),
                    "provider": invalid_file_url,
                    "model_name": invalid_local_storage_path,
                    "status": invalid_s3_url,
                    "quality_status": invalid_story_excerpt,
                },
            },
        )
        await service.record(
            session,
            project_id=project_id,
            asset_id=safe_asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
            reason="manual",
            asset_type="character_front",
            related_id="CH_001",
            storage_path="projects/demo/safe-asset.png",
            details={
                "asset_id": str(safe_asset_id),
                "reason": "manual",
                "asset_type": "character_front",
                "related_id": "CH_001",
                "generation_task_summary": {
                    "generation_task_id": str(uuid.uuid4()),
                    "provider": "doubao_seedream",
                    "model_name": "doubao-seedream-5.0-lite",
                    "status": "success",
                    "quality_status": "passed",
                },
            },
        )
        await session.commit()

    async with audit_session_factory() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT reason, asset_type, related_id, details::text
                    FROM image_asset_audit_logs
                    WHERE project_id = :project_id
                    ORDER BY created_at ASC, id ASC
                    """
                ),
                {"project_id": project_id},
            )
        ).all()
        response = await service.list_logs(
            session,
            user_id="user-1",
            project_id=project_id,
            asset_id=None,
            page=1,
            page_size=10,
        )

    db_text = json.dumps([tuple(row) for row in rows], ensure_ascii=False)
    response_json = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)

    for sensitive_value in (
        invalid_file_url,
        invalid_s3_url,
        invalid_local_storage_path,
        invalid_story_excerpt,
    ):
        assert sensitive_value not in db_text
        assert sensitive_value not in response_json

    assert ("manual", "character_front", "CH_001") in [(row[0], row[1], row[2]) for row in rows]
    assert any(
        item.reason == "manual" and item.asset_type == "character_front" and item.related_id == "CH_001"
        for item in response.items
    )
    assert any(item.details.get("reason") == "manual" for item in response.items)
    assert any(
        item.details.get("generation_task_summary", {}).get("provider") == "doubao_seedream" for item in response.items
    )


@pytest.mark.asyncio
async def test_list_logs_returns_persisted_actions_with_user_scope_and_filters(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    audit_service_module = _require_module("app.modules.image_asset.audit_service")
    schemas_module = _require_module("app.modules.image_asset.schemas")
    service = audit_service_module.ImageAssetAuditService
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    other_asset_id = uuid.uuid4()

    async with audit_session_factory() as session:
        await _insert_project(session, project_id=project_id, user_id="user-1", title="Project One")
        await _insert_project(session, project_id=other_project_id, user_id="user-2", title="Project Two")

    async with audit_session_factory() as session:
        for action in (
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
        ):
            await service.record(
                session,
                project_id=project_id,
                asset_id=asset_id,
                user_id="user-1",
                action=action,
                reason="manual",
                asset_type="character_front",
                related_id="CH_001",
                storage_path=f"{action}.png",
                details={"asset_id": str(asset_id), "reason": "manual"},
            )
        await service.record(
            session,
            project_id=project_id,
            asset_id=other_asset_id,
            user_id="user-1",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason="manual",
            asset_type="prop_product",
            related_id="PR_001",
            storage_path="other-asset.png",
            details={"asset_id": str(other_asset_id)},
        )
        await service.record(
            session,
            project_id=other_project_id,
            asset_id=uuid.uuid4(),
            user_id="user-2",
            action=audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            reason="manual",
            asset_type="scene_empty",
            related_id="SC_001",
            storage_path="other-project.png",
            details={"asset_id": str(uuid.uuid4())},
        )
        await session.commit()

    async with audit_session_factory() as session:
        first_page = await service.list_logs(
            session,
            user_id="user-1",
            project_id=project_id,
            asset_id=asset_id,
            page=1,
            page_size=2,
        )

    assert isinstance(first_page, schemas_module.ImageAssetAuditLogResponse)
    assert first_page.total == 4
    assert len(first_page.items) == 2
    assert {item.action for item in first_page.items}.issubset(
        {
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_DELETE_TO_TRASH,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_RESTORE_FROM_TRASH,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PERMANENT_DELETE,
            audit_service_module.IMAGE_ASSET_AUDIT_ACTION_PURGE_EXPIRED,
        }
    )
    assert all(item.project_id == project_id for item in first_page.items)
    assert all(item.asset_id == asset_id for item in first_page.items)
    assert all("prompt" not in item.details for item in first_page.items)

    async with audit_session_factory() as session:
        second_page = await service.list_logs(
            session,
            user_id="user-1",
            project_id=project_id,
            asset_id=asset_id,
            page=2,
            page_size=2,
        )
        foreign_logs = await service.list_logs(
            session,
            user_id="user-1",
            project_id=other_project_id,
            asset_id=None,
            page=1,
            page_size=50,
        )

    assert second_page.total == 4
    assert len(second_page.items) == 2
    assert foreign_logs.total == 0
    assert foreign_logs.items == []
