"""Normalized provider errors for M17 Provider Adapter.

Every provider error — regardless of its origin (DeepSeek, Seedream, TOS, etc.)
— is mapped to a canonical ProviderError with a stable error code and a
retryable flag. Business modules catch ProviderError and decide whether to
retry, fail the task, or escalate for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderErrorCode(StrEnum):
    """Canonical error codes for all external providers."""

    TIMEOUT = "provider_timeout"
    RATE_LIMITED = "provider_rate_limited"
    AUTH_FAILED = "provider_auth_failed"
    INVALID_REQUEST = "provider_invalid_request"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNEXPECTED = "provider_unexpected"


# Retryable flags by error code
_RETRYABLE: dict[ProviderErrorCode, bool] = {
    ProviderErrorCode.TIMEOUT: True,
    ProviderErrorCode.RATE_LIMITED: True,
    ProviderErrorCode.AUTH_FAILED: False,
    ProviderErrorCode.INVALID_REQUEST: False,
    ProviderErrorCode.PROVIDER_UNAVAILABLE: True,
    ProviderErrorCode.UNEXPECTED: True,
}


@dataclass
class ProviderError(Exception):
    """Normalized provider error raised by any provider adapter.

    Attributes:
        code: Canonical error code.
        message: Human-readable description.
        provider: Provider name ("deepseek", "seedream", etc.).
        retryable: Whether the caller should retry after this error.
        raw_error: The original provider error message (sanitized).
    """

    code: ProviderErrorCode
    message: str
    provider: str
    retryable: bool = True
    raw_error: str = ""

    def __post_init__(self) -> None:
        super().__init__(self.message)
        # If retryable was not explicitly set, derive from code
        if self.retryable is True and self.code in _RETRYABLE:
            self.retryable = _RETRYABLE[self.code]


def is_retryable(code: ProviderErrorCode) -> bool:
    """Return True if the given error code indicates the operation can be retried."""
    return _RETRYABLE.get(code, True)
