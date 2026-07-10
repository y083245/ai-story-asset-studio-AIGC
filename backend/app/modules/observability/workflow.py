"""Workflow 日志上下文绑定。

用于 workflow activity 调用时自动绑定 workflow_id 和 task_id。
"""

from __future__ import annotations

import structlog


def bind_workflow_context(
    workflow_id: str,
    task_id: str,
    project_id: str | None = None,
    user_id: str | None = None,
) -> structlog.BoundLogger:
    """绑定 workflow 上下文字段到 structlog logger。

    在 workflow activity 开始时调用，后续该 activity 的所有日志
    自动携带 workflow_id、task_id 等信息。

    Args:
        workflow_id: workflow ID。
        task_id: 当前 activity task ID。
        project_id: 可选的项目 ID。
        user_id: 可选的用户 ID。

    Returns:
        绑定了 workflow 上下文的 structlog BoundLogger。
    """
    logger = structlog.get_logger().bind(
        workflow_id=workflow_id,
        task_id=task_id,
        module="workflow",
    )
    if project_id:
        logger = logger.bind(project_id=project_id)
    if user_id:
        logger = logger.bind(user_id=user_id)
    return logger  # type: ignore[no-any-return]
