"use client";

import { RotateCcw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AssetLibraryTab } from "@/features/asset-library/types";

interface AssetBulkActionBarProps {
  tab: AssetLibraryTab;
  selectedCount: number;
  onClear: () => void;
  onDelete: () => void;
  onRestore: () => void;
  onPermanentDelete: () => void;
}

export function AssetBulkActionBar({
  tab,
  selectedCount,
  onClear,
  onDelete,
  onRestore,
  onPermanentDelete,
}: AssetBulkActionBarProps) {
  if (selectedCount === 0) return null;

  return (
    <div className="sticky bottom-4 z-10 flex items-center justify-between rounded-xl border border-neutral-800 bg-neutral-950/95 px-4 py-3 backdrop-blur">
      <div className="text-sm text-neutral-300">已选择 {selectedCount} 张</div>
      <div className="flex items-center gap-2">
        {tab === "library" ? (
          <Button variant="outline" size="sm" onClick={onDelete}>
            <Trash2 className="size-3.5" />
            删除 {selectedCount} 张
          </Button>
        ) : (
          <>
            <Button variant="outline" size="sm" onClick={onRestore}>
              <RotateCcw className="size-3.5" />
              恢复 {selectedCount} 张
            </Button>
            <Button variant="outline" size="sm" className="border-red-900 text-red-300 hover:bg-red-950/40" onClick={onPermanentDelete}>
              <Trash2 className="size-3.5" />
              永久删除 {selectedCount} 张
            </Button>
          </>
        )}
        <Button variant="ghost" size="sm" onClick={onClear}>
          清空选择
        </Button>
      </div>
    </div>
  );
}
