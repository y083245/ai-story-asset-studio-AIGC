"""核心指标定义与记录。

一期使用内存列表存储指标值，后续替换为真实 OpenTelemetry 导出。
"""

from __future__ import annotations

from typing import Any

# 指标名称与类型常量
METRICS: dict[str, str] = {
    "project_created_total": "counter",
    "analysis_success_total": "counter",
    "image_generation_success_total": "counter",
    "quality_check_failure_total": "counter",
    "auto_retry_total": "counter",
    "generation_latency_seconds": "histogram",
    "project_cost_estimate": "gauge",
}


class MetricsRecorder:
    """指标记录器。

    一期使用内存列表存储，后续替换为 OpenTelemetry MeterProvider。
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """记录 counter 指标。

        Args:
            name: 指标名称，必须在 METRICS 中定义为 counter。
            value: 增量值。
            labels: 可选的维度标签。

        Raises:
            ValueError: 指标名称未定义或类型不匹配。
        """
        self._validate_metric_type(name, "counter")
        self._records.append(
            {
                "type": "counter",
                "name": name,
                "value": value,
                "labels": labels or {},
            }
        )

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """记录 histogram 指标。

        Args:
            name: 指标名称，必须在 METRICS 中定义为 histogram。
            value: 观测值。
            labels: 可选的维度标签。

        Raises:
            ValueError: 指标名称未定义或类型不匹配。
        """
        self._validate_metric_type(name, "histogram")
        self._records.append(
            {
                "type": "histogram",
                "name": name,
                "value": value,
                "labels": labels or {},
            }
        )

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """记录 gauge 指标。

        Args:
            name: 指标名称，必须在 METRICS 中定义为 gauge。
            value: 当前值。
            labels: 可选的维度标签。

        Raises:
            ValueError: 指标名称未定义或类型不匹配。
        """
        self._validate_metric_type(name, "gauge")
        self._records.append(
            {
                "type": "gauge",
                "name": name,
                "value": value,
                "labels": labels or {},
            }
        )

    def get_records(self, name: str | None = None) -> list[dict[str, Any]]:
        """获取已记录的指标。

        Args:
            name: 按指标名称过滤，None 返回全部。

        Returns:
            匹配的指标记录列表。
        """
        if name is None:
            return list(self._records)
        return [r for r in self._records if r["name"] == name]

    def reset(self) -> None:
        """清空所有指标记录（仅用于测试）。"""
        self._records.clear()

    def _validate_metric_type(self, name: str, expected_type: str) -> None:
        """验证指标名称和类型是否匹配。"""
        if name not in METRICS:
            raise ValueError(f"Unknown metric: {name}")
        actual_type = METRICS[name]
        if actual_type != expected_type:
            raise ValueError(f"Metric {name} is defined as {actual_type}, but {expected_type} was requested")


# 全局单例
metrics_recorder = MetricsRecorder()
