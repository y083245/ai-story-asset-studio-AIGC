"""FastAPI dependency injection helpers for the Scene Library module."""

from __future__ import annotations

from app.security.auth import require_current_user_id as get_current_user_id

__all__ = ["get_current_user_id"]
