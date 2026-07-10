from __future__ import annotations

import calendar
import math
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

IMAGE_TRASH_RETENTION_DAYS = 30
IMAGE_LIBRARY_TIMEZONE = "Asia/Shanghai"

CHARACTER_ASSET_TYPES = {
    "character_bible_sheet",
    "character_front",
    "character_turnaround",
    "character_expression",
}
PROP_ASSET_TYPES = {"prop_product", "prop_usage"}
SCENE_ASSET_TYPES = {"scene_empty", "scene_with_atmosphere"}
CATEGORY_ORDER = ("character", "prop", "scene")

ImageAssetCategory = Literal["character", "prop", "scene"]


class AssetLifecycleRecord(Protocol):
    expires_at: datetime | None
    purge_after: datetime | None
    deleted_at: datetime | None


def add_natural_months(value: datetime, months: int) -> datetime:
    month_index = (value.month - 1) + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def compute_expires_at(created_at: datetime) -> datetime:
    return add_natural_months(created_at, 6)


def compute_purge_after(deleted_at: datetime) -> datetime:
    return deleted_at + timedelta(days=IMAGE_TRASH_RETENTION_DAYS)


def effective_permanent_delete_at(asset: AssetLifecycleRecord) -> datetime | None:
    deadlines: list[datetime] = []
    if asset.expires_at is not None:
        deadlines.append(asset.expires_at)
    if asset.deleted_at is not None and asset.purge_after is not None:
        deadlines.append(asset.purge_after)
    if not deadlines:
        return None
    return min(deadlines)


def asset_category(asset_type: str) -> ImageAssetCategory:
    if asset_type in CHARACTER_ASSET_TYPES:
        return "character"
    if asset_type in PROP_ASSET_TYPES:
        return "prop"
    if asset_type in SCENE_ASSET_TYPES:
        return "scene"
    raise ValueError(f"Unsupported asset_type: {asset_type}")


def archive_date(created_at: datetime, timezone_name: str = IMAGE_LIBRARY_TIMEZONE) -> date:
    return created_at.astimezone(ZoneInfo(timezone_name)).date()


def remaining_days(deadline: datetime, now: datetime) -> int:
    remaining_seconds = (deadline - now).total_seconds()
    if remaining_seconds <= 0:
        return 0
    return math.ceil(remaining_seconds / 86400)


def is_expired(asset: AssetLifecycleRecord, now: datetime) -> bool:
    effective_deadline = effective_permanent_delete_at(asset)
    if effective_deadline is None:
        return False
    return effective_deadline <= now
