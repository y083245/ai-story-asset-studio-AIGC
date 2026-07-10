"""Observability 模块敏感字段脱敏。

集成 M17 的 sanitize.py，为 observability 层提供统一的脱敏入口。
确保 API key、签名密钥、access token 等不会被写入日志。
"""

from __future__ import annotations

from typing import Any

from app.modules.provider_adapter.sanitize import sanitize_log


def sanitize_log_context(log_data: dict[str, Any]) -> dict[str, Any]:
    """对日志数据进行敏感字段脱敏。

    调用 M17 的 sanitize_log 函数，将敏感字段替换为 ***REDACTED***。
    适用于所有需要写入日志的字典数据。

    Args:
        log_data: 待脱敏的日志数据字典。

    Returns:
        脱敏后的字典副本。
    """
    return sanitize_log(log_data)
