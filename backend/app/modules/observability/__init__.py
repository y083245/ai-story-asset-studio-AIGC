"""M19 Observability 模块。

提供结构化日志、指标、审计和错误展示能力。
"""

from __future__ import annotations

from app.modules.observability.audit import AuditLogger, audit_logger
from app.modules.observability.context import LogContext
from app.modules.observability.error_display import normalize_error_for_display
from app.modules.observability.logger import get_logger
from app.modules.observability.metrics import METRICS, MetricsRecorder, metrics_recorder
from app.modules.observability.provider_log import log_provider_call
from app.modules.observability.sanitize import sanitize_log_context
from app.modules.observability.workflow import bind_workflow_context

__all__ = [
    "get_logger",
    "LogContext",
    "sanitize_log_context",
    "log_provider_call",
    "bind_workflow_context",
    "METRICS",
    "MetricsRecorder",
    "metrics_recorder",
    "AuditLogger",
    "audit_logger",
    "normalize_error_for_display",
]
