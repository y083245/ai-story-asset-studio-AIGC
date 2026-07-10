"""Request authentication helpers.

Local development keeps the existing ``X-User-ID`` workflow so the current
single-user UI remains usable. Production is fail-closed and requires a
trusted upstream to sign the forwarded identity.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.config import settings

_USER_ID_RE = re.compile(r"^[A-Za-z0-9._:@-]{1,128}$")


async def require_current_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-ID", description="当前用户标识")] = None,
    x_user_signature: Annotated[str | None, Header(alias="X-User-Signature")] = None,
    x_user_timestamp: Annotated[str | None, Header(alias="X-User-Timestamp")] = None,
) -> str:
    """Resolve and validate the current user identity.

    In production, the caller must include:
    - ``X-User-ID``
    - ``X-User-Timestamp`` as Unix seconds
    - ``X-User-Signature`` as HMAC-SHA256 of ``"{timestamp}:{user_id}"``

    The HMAC key is ``USER_AUTH_SHARED_SECRET`` and should only be known by a
    trusted gateway or backend-for-frontend service.
    """
    user_id = _validate_user_id(x_user_id)
    if settings.app_env == "production" or settings.user_auth_mode == "signed-header":
        _verify_signed_user_header(user_id, x_user_timestamp, x_user_signature)
    return user_id


def _validate_user_id(x_user_id: str | None) -> str:
    user_id = (x_user_id or "").strip()
    if not user_id:
        _raise_auth_error(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED", "X-User-ID header is required")
    if not _USER_ID_RE.fullmatch(user_id):
        _raise_auth_error(status.HTTP_401_UNAUTHORIZED, "INVALID_USER_ID", "X-User-ID header is invalid")
    return user_id


def _verify_signed_user_header(user_id: str, timestamp_header: str | None, signature_header: str | None) -> None:
    secret = settings.user_auth_shared_secret.strip()
    if not secret:
        _raise_auth_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "USER_AUTH_NOT_CONFIGURED",
            "User authentication is not configured",
        )

    timestamp_value = (timestamp_header or "").strip()
    signature_value = (signature_header or "").strip()
    if not timestamp_value or not signature_value:
        _raise_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_SIGNATURE_REQUIRED",
            "Signed user headers are required",
        )

    try:
        timestamp = int(timestamp_value)
    except ValueError:
        _raise_auth_error(status.HTTP_401_UNAUTHORIZED, "AUTH_SIGNATURE_INVALID", "User signature is invalid")

    ttl = max(settings.user_auth_signature_ttl_seconds, 1)
    if abs(int(time.time()) - timestamp) > ttl:
        _raise_auth_error(status.HTTP_401_UNAUTHORIZED, "AUTH_SIGNATURE_EXPIRED", "User signature is expired")

    expected = hmac.new(secret.encode(), f"{timestamp}:{user_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature_value, expected):
        _raise_auth_error(status.HTTP_401_UNAUTHORIZED, "AUTH_SIGNATURE_INVALID", "User signature is invalid")


def _raise_auth_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "message": message,
            "retryable": False,
        },
    )
