"""日志上下文字段定义。

所有结构化日志的字段约束都在这里定义。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogContext:
    """结构化日志上下文字段。

    每个核心模块输出日志时必须包含 module 字段。
    其他字段按业务阶段按需填充。
    """

    module: str
    request_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    provider: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    status: str | None = None  # "success" | "error" | "pending"
    error_code: str | None = None

    # M19-12 成本记录字段
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    image_count: int | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为字典，排除 None 值（module 除外）。"""
        result: dict[str, Any] = {"module": self.module}
        for field_name in (
            "request_id",
            "user_id",
            "project_id",
            "workflow_id",
            "task_id",
            "provider",
            "model_name",
            "latency_ms",
            "status",
            "error_code",
            "prompt_tokens",
            "completion_tokens",
            "image_count",
        ):
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        if self.extra:
            result["extra"] = self.extra
        return result
