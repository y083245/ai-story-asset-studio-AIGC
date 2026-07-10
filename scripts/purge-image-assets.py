#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Purge expired image assets.")
    parser.add_argument("--dry-run", action="store_true", help="Count candidates without deleting data.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of assets to scan and purge.")
    return parser.parse_args()


async def _main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.db.session import async_session_factory
    from app.modules.image_asset.library_service import ImageAssetLibraryService
    from app.modules.storage.service import StorageService

    args = _parse_args()
    service = ImageAssetLibraryService(StorageService.create())

    async with async_session_factory() as session:
        result = await service.purge_expired_assets(
            session,
            limit=args.limit,
            dry_run=args.dry_run,
        )

    print(f"trash_expired_count={result.trash_expired_count}")
    print(f"retention_expired_count={result.retention_expired_count}")
    print(f"storage_failed_count={result.storage_failed_count}")
    print(f"deleted_count={result.deleted_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
