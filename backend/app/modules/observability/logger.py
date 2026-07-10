"""结构化 Logger。

基于 structlog 实现，要求 module 字段必填。
输出 JSON 格式日志。
"""

from __future__ import annotations

import structlog


def get_logger(module: str) -> structlog.BoundLogger:
    """获取预配置的结构化 logger。

    Args:
        module: 模块名称，必填。

    Returns:
        绑定了 module 字段的 structlog BoundLogger。

    Raises:
        ValueError: module 为空。
    """
    if not module:
        raise ValueError("module is required for structured logging")
    return structlog.get_logger().bind(module=module)  # type: ignore[no-any-return]
