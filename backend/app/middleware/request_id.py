"""请求 ID 中间件。

为每个请求注入唯一 request_id 和 trace context，
并将 request_id 注入 structlog 上下文。
"""

from __future__ import annotations

import re
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 X-Request-ID header，并绑定到 structlog 上下文。"""

    _REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = (
            incoming_request_id
            if incoming_request_id and self._REQUEST_ID_RE.fullmatch(incoming_request_id)
            else str(uuid.uuid4())
        )
        request.state.request_id = request_id

        # 将 request_id 注入 structlog 上下文，使得该请求内的所有日志自动携带
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 请求结束后清理上下文，防止跨请求污染
            structlog.contextvars.unbind_contextvars("request_id")
