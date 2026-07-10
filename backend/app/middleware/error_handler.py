"""全局异常处理中间件。

将所有未捕获异常转换为统一 JSON 响应格式。
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """捕获未处理异常，返回统一错误 JSON。

    响应格式:
        {"error": {"code": "INTERNAL_ERROR", "message": "...", "retryable": false}}
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            request_id = getattr(request.state, "request_id", None)
            message = str(exc) if settings.app_env != "production" else "Internal server error"
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": message,
                        "request_id": request_id,
                        "retryable": False,
                    }
                },
            )
