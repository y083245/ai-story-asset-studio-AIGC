"""CORS 中间件配置。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def setup_cors(app: FastAPI) -> None:
    """配置 CORS，开发环境允许 Next.js dev server。"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _allowed_origins() -> list[str]:
    return [origin.strip().rstrip("/") for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
