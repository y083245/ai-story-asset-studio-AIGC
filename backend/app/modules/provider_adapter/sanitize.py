"""Log sanitization for M17 Provider Adapter.

Removes sensitive fields (API keys, tokens, signatures) from log data
before it reaches the observability layer. Every provider adapter MUST
call `sanitize_log` before emitting log records that contain provider
request/response payloads.
"""

from __future__ import annotations

from typing import Any

# Keys that must never appear in logs — these are matched case-insensitively
# and matched as substrings (e.g. "x-api-key" matches).
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "apikey",
        "secretkey",
        "accesskey",
        "accesstoken",
        "signature",
        "authorization",
        "xapikey",
        "xauthtoken",
        "bearer",
    }
)

# Prefix used when masking a value whose parent key looks sensitive
_MASK_VALUE: str = "***REDACTED***"


def _is_sensitive(key: str) -> bool:
    """Return True if *key* looks like a sensitive field name."""
    normalized = key.strip().lower().replace("_", "").replace("-", "")
    return normalized in _SENSITIVE_KEYS


def _mask_dict(data: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Recursively mask sensitive values in a dictionary."""
    if depth > 10:  # safety limit
        return data

    result: dict[str, Any] = {}
    for k, v in data.items():
        if _is_sensitive(k):
            result[k] = _MASK_VALUE
        elif isinstance(v, dict):
            result[k] = _mask_dict(dict(v), depth + 1)
        elif isinstance(v, list):
            result[k] = [_mask_dict(dict(item), depth + 1) if isinstance(item, dict) else item for item in v]
        else:
            result[k] = v
    return result


def sanitize_log(log_data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *log_data* with all sensitive fields masked.

    Typical usage::

        logger.info("provider response", extra={"data": sanitize_log(raw)})
    """
    return _mask_dict(dict(log_data))
