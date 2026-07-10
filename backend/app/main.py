"""Story Asset Studio FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.middleware.cors import setup_cors
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理。"""
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    app = FastAPI(
        title="Story Asset Studio",
        description="Novel-to-visual-asset pipeline",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 中间件（添加顺序 = 执行顺序，先添加的先执行）
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestIDMiddleware)
    setup_cors(app)

    # 注册路由
    from app.health.router import router as health_router
    from app.modules.asset_workbench.router import router as asset_workbench_router
    from app.modules.character_library.router import router as character_library_router
    from app.modules.image_asset.router import router as image_asset_router
    from app.modules.model_config.router import router as model_config_router
    from app.modules.novel_intake.router import router as novel_intake_router
    from app.modules.project.router import router as project_router
    from app.modules.prop_library.router import router as prop_library_router
    from app.modules.quality_retry.router import router as quality_retry_router
    from app.modules.scene_library.router import router as scene_library_router
    from app.modules.story_bible.router import router as story_bible_router
    from app.modules.workflow.router import router as workflow_router

    app.include_router(health_router)
    app.include_router(model_config_router)
    app.include_router(project_router)
    app.include_router(novel_intake_router)
    app.include_router(asset_workbench_router)
    app.include_router(character_library_router)
    app.include_router(scene_library_router)
    app.include_router(prop_library_router)
    app.include_router(story_bible_router)
    app.include_router(image_asset_router)
    app.include_router(quality_retry_router)
    app.include_router(workflow_router)

    if settings.app_env != "production":
        app.mount("/local-storage", StaticFiles(directory="local_storage", check_dir=False), name="local-storage")

    return app


app = create_app()
