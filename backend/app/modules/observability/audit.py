"""审计日志。

审计日志只写不改（不可变）。一期使用内存列表存储。
"""

from __future__ import annotations

import time
from typing import Any


class AuditLogger:
    """审计日志记录器。

    规则：
    - 审计日志只写不改（不可变）。
    - 记录用户操作：编辑 Story Bible、角色、场景、道具、重生成等。
    - 一期使用内存列表存储。
    """

    def __init__(self) -> None:
        self._logs: list[dict[str, Any]] = []
        self._seq: int = 0

    def log_user_action(
        self,
        user_id: str,
        project_id: str,
        action: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        """记录一条用户操作审计日志。

        Args:
            user_id: 操作用户 ID。
            project_id: 所在项目 ID。
            action: 操作类型，例如 "edit_story_bible"、"edit_character"、
                    "regenerate_asset" 等。
            details: 操作的附加详情。
            request_id: 关联的请求 ID。
        """
        self._seq += 1
        entry: dict[str, Any] = {
            "timestamp": time.time(),
            "seq": self._seq,
            "user_id": user_id,
            "project_id": project_id,
            "action": action,
            "details": details or {},
        }
        if request_id:
            entry["request_id"] = request_id
        self._logs.append(entry)

    def get_audit_logs(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """按项目查询审计日志。

        Args:
            project_id: 项目 ID。
            limit: 返回条数上限。

        Returns:
            该项目的审计日志列表（按时间倒序，同时使用序号打破平局）。
        """
        project_logs = [log for log in self._logs if log["project_id"] == project_id]
        project_logs.sort(key=lambda x: (x["timestamp"], x["seq"]), reverse=True)
        return project_logs[:limit]

    def reset(self) -> None:
        """清空所有审计日志（仅用于测试）。"""
        self._logs.clear()


# 全局单例
audit_logger = AuditLogger()
