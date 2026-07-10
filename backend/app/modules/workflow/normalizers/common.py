"""Shared helpers for the analysis normalizers."""

from __future__ import annotations

from typing import Any


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    return [str(item) for item in as_list(value)]


def dict_of(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def field(label: str, value: Any) -> str:
    text = str(value or "").strip()
    return f"{label}：{text}" if text else ""
