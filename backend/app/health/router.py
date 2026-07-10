"""健康检查路由。

提供 /health 端点供负载均衡和监控使用。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """基础健康检查。

    返回应用运行状态。后续 Phase 会加入 DB、Redis 连通性检查。
    """
    return {
        "status": "ok",
        "version": "0.1.0",
    }
