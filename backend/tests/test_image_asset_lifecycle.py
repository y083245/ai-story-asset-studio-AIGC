from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.modules.image_asset.lifecycle import (
    CATEGORY_ORDER,
    CHARACTER_ASSET_TYPES,
    IMAGE_LIBRARY_TIMEZONE,
    IMAGE_TRASH_RETENTION_DAYS,
    PROP_ASSET_TYPES,
    SCENE_ASSET_TYPES,
    add_natural_months,
    archive_date,
    asset_category,
    compute_expires_at,
    compute_purge_after,
    effective_permanent_delete_at,
    is_expired,
    remaining_days,
)


@dataclass
class _AssetSnapshot:
    expires_at: datetime | None
    purge_after: datetime | None
    deleted_at: datetime | None = None


def test_add_natural_months_keeps_same_day_when_target_month_has_that_day() -> None:
    created_at = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)

    assert add_natural_months(created_at, 6) == datetime(2027, 1, 8, 11, 30, tzinfo=UTC)


def test_add_natural_months_uses_last_day_for_month_end() -> None:
    created_at = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)

    assert add_natural_months(created_at, 6) == datetime(2027, 2, 28, 9, 15, tzinfo=UTC)


def test_add_natural_months_handles_leap_year_target_month() -> None:
    created_at = datetime(2023, 8, 31, 18, 45, tzinfo=UTC)

    assert add_natural_months(created_at, 6) == datetime(2024, 2, 29, 18, 45, tzinfo=UTC)


def test_compute_expires_at_adds_six_natural_months() -> None:
    created_at = datetime(2026, 7, 8, 0, 0, tzinfo=UTC)

    assert compute_expires_at(created_at) == datetime(2027, 1, 8, 0, 0, tzinfo=UTC)


def test_compute_purge_after_adds_thirty_days() -> None:
    deleted_at = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)

    assert compute_purge_after(deleted_at) == deleted_at + timedelta(days=IMAGE_TRASH_RETENTION_DAYS)


@pytest.mark.parametrize(
    ("asset_type", "expected_category"),
    [
        ("character_bible_sheet", "character"),
        ("character_front", "character"),
        ("character_turnaround", "character"),
        ("character_expression", "character"),
        ("prop_product", "prop"),
        ("prop_usage", "prop"),
        ("scene_empty", "scene"),
        ("scene_with_atmosphere", "scene"),
    ],
)
def test_asset_category_maps_exact_supported_asset_types(asset_type: str, expected_category: str) -> None:
    assert asset_category(asset_type) == expected_category


def test_asset_category_rejects_unknown_asset_type() -> None:
    with pytest.raises(ValueError, match="Unsupported asset_type: storyboard_frame"):
        asset_category("storyboard_frame")


def test_archive_date_uses_asia_shanghai_timezone_by_default() -> None:
    created_at = datetime(2026, 7, 8, 18, 30, tzinfo=UTC)

    assert archive_date(created_at) == datetime(2026, 7, 9, 2, 30, tzinfo=ZoneInfo(IMAGE_LIBRARY_TIMEZONE)).date()


def test_remaining_days_returns_zero_for_past_deadline() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    deadline = now - timedelta(days=2)

    assert remaining_days(deadline, now) == 0


def test_effective_permanent_delete_at_prefers_earlier_deadline() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    asset = _AssetSnapshot(
        expires_at=now + timedelta(days=10),
        purge_after=now + timedelta(days=3),
        deleted_at=now,
    )

    assert effective_permanent_delete_at(asset) == now + timedelta(days=3)


def test_effective_permanent_delete_at_uses_expiration_for_active_asset() -> None:
    expires_at = datetime(2027, 1, 8, 12, 0, tzinfo=UTC)
    asset = _AssetSnapshot(expires_at=expires_at, purge_after=None, deleted_at=None)

    assert effective_permanent_delete_at(asset) == expires_at


def test_is_expired_uses_effective_delete_deadline() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    asset = _AssetSnapshot(
        expires_at=now + timedelta(days=10),
        purge_after=now - timedelta(seconds=1),
        deleted_at=now - timedelta(days=1),
    )

    assert is_expired(asset, now) is True


def test_module_constants_match_design_contract() -> None:
    assert IMAGE_TRASH_RETENTION_DAYS == 30
    assert IMAGE_LIBRARY_TIMEZONE == "Asia/Shanghai"
    assert {
        "character_bible_sheet",
        "character_front",
        "character_turnaround",
        "character_expression",
    } == CHARACTER_ASSET_TYPES
    assert {"prop_product", "prop_usage"} == PROP_ASSET_TYPES
    assert {"scene_empty", "scene_with_atmosphere"} == SCENE_ASSET_TYPES
    assert CATEGORY_ORDER == ("character", "prop", "scene")
