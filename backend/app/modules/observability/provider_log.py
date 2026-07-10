"""Provider 调用日志。

记录 provider 调用的关键信息：provider、model、耗时、状态、错误码。
绝不记录 API key。
"""

from __future__ import annotations

import structlog

from app.modules.observability.context import LogContext


async def log_provider_call(
    logger: structlog.BoundLogger,
    provider: str,
    model_name: str,
    latency_ms: int,
    status: str,
    error_code: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    image_count: int | None = None,
    request_id: str | None = None,
    project_id: str | None = None,
    workflow_id: str | None = None,
    task_id: str | None = None,
    module_id: str | None = None,
    chunk_index: int | None = None,
    chunk_count: int | None = None,
    stage: str | None = None,
    asset_type: str | None = None,
    thinking: str | None = None,
    input_chars: int | None = None,
    output_chars: int | None = None,
    prompt_cache_hit_tokens: int | None = None,
    prompt_cache_miss_tokens: int | None = None,
    finish_reason: str | None = None,
    retry_count: int | None = None,
) -> None:
    """记录一次 provider 调用。

    所有敏感字段已由调用方在传入前脱敏。
    绝不记录 API key、签名密钥等。

    Args:
        logger: 结构化 logger。
        provider: provider 名称（例如 "deepseek"、"seedream"）。
        model_name: 模型名称。
        latency_ms: 调用耗时（毫秒）。
        status: 调用状态（"success", "error"）。
        error_code: 错误码（status="error" 时）。
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        image_count: 生成图片数量。
        request_id: 请求 ID。
        project_id: 项目 ID。
        workflow_id: workflow ID。
        task_id: 任务 ID。
    """
    extra = {
        key: value
        for key, value in {
            "module_id": module_id,
            "chunk_index": chunk_index,
            "chunk_count": chunk_count,
            "stage": stage,
            "asset_type": asset_type,
            "thinking": thinking,
            "input_chars": input_chars,
            "output_chars": output_chars,
            "prompt_cache_hit_tokens": prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": prompt_cache_miss_tokens,
            "finish_reason": finish_reason,
            "retry_count": retry_count,
        }.items()
        if value is not None
    }
    ctx = LogContext(
        module="provider_call",
        provider=provider,
        model_name=model_name,
        latency_ms=latency_ms,
        status=status,
        error_code=error_code,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        image_count=image_count,
        request_id=request_id,
        project_id=project_id,
        workflow_id=workflow_id,
        task_id=task_id,
        extra=extra,
    )

    if status == "error":
        logger.error(
            "provider call failed",
            **ctx.to_dict(),
        )
    else:
        logger.info(
            "provider call completed",
            **ctx.to_dict(),
        )
