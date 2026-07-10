"""FastAPI router for the merged asset workbench."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.asset_workbench.schemas import (
    GenerateAssetWorkbenchRequest,
    GenerateAssetWorkbenchResponse,
    PreviewAssetWorkbenchPromptsRequest,
    PreviewAssetWorkbenchPromptsResponse,
)
from app.modules.asset_workbench.service import AssetWorkbenchService
from app.modules.image_asset.service import ImageAssetService
from app.modules.provider_adapter.fake import FakeSeedreamProvider
from app.modules.provider_adapter.registry import ProviderRegistry
from app.modules.storage.service import StorageService
from app.modules.workflow.deps import verify_project_ownership

router = APIRouter(prefix="/api", tags=["asset-workbench"])


def _get_asset_workbench_service() -> AssetWorkbenchService:
    registry = ProviderRegistry()
    try:
        image_provider = registry.get_image_generator()
    except Exception:
        image_provider = None
    if image_provider is None:
        image_provider = FakeSeedreamProvider()
    image_asset_service = ImageAssetService(
        image_provider=image_provider,
        storage_service=StorageService.create(),
    )
    return AssetWorkbenchService(image_asset_service)


@router.post(
    "/projects/{project_id}/asset-workbench/generate",
    response_model=GenerateAssetWorkbenchResponse,
)
async def generate_asset_workbench(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: GenerateAssetWorkbenchRequest,
    service: Annotated[AssetWorkbenchService, Depends(_get_asset_workbench_service)],
) -> GenerateAssetWorkbenchResponse:
    """Generate character three-views, empty scenes, and prop images in one flow."""
    return await service.generate_reference_assets(session, project_id, body)


@router.post(
    "/projects/{project_id}/asset-workbench/prompts/preview",
    response_model=PreviewAssetWorkbenchPromptsResponse,
)
async def preview_asset_workbench_prompts(
    project_id: Annotated[uuid.UUID, Depends(verify_project_ownership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    body: PreviewAssetWorkbenchPromptsRequest,
    service: Annotated[AssetWorkbenchService, Depends(_get_asset_workbench_service)],
) -> PreviewAssetWorkbenchPromptsResponse:
    """Build final image prompts for workbench display without generating assets."""
    return await service.preview_prompts(session, project_id, body)
