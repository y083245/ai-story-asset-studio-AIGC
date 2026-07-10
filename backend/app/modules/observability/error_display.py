"""错误归一化展示。

将 ProviderError 映射为用户可读的中文消息和运维消息。
"""

from __future__ import annotations

from app.modules.provider_adapter.errors import ProviderError, ProviderErrorCode

# ProviderErrorCode 到用户可读中文消息的映射
_USER_MESSAGES: dict[ProviderErrorCode, str] = {
    ProviderErrorCode.TIMEOUT: "生成超时，正在自动重试...",
    ProviderErrorCode.RATE_LIMITED: "请求繁忙，稍后自动重试...",
    ProviderErrorCode.AUTH_FAILED: "服务配置异常，请联系管理员",
    ProviderErrorCode.INVALID_REQUEST: "请求参数有误",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "AI 服务暂时不可用，稍后自动重试...",
    ProviderErrorCode.UNEXPECTED: "服务异常，正在自动重试...",
}


def normalize_error_for_display(error: Exception) -> dict[str, str]:
    """将 provider 错误映射为用户可读消息和运维消息。

    Args:
        error: 原始异常对象。

    Returns:
        包含 user_message、ops_message 和 code 的字典。
        - user_message: 面向用户的中文消息。
        - ops_message: 面向运维的技术消息。
        - code: 错误码。
    """
    if isinstance(error, ProviderError):
        code = error.code.value if isinstance(error.code, ProviderErrorCode) else str(error.code)
        user_message = _USER_MESSAGES.get(
            error.code if isinstance(error.code, ProviderErrorCode) else ProviderErrorCode.UNEXPECTED,
            "服务异常，稍后重试",
        )
        ops_message = error.message
    else:
        code = "unknown_error"
        user_message = "系统繁忙，请稍后重试"
        ops_message = str(error)

    return {
        "user_message": user_message,
        "ops_message": ops_message,
        "code": code,
    }
