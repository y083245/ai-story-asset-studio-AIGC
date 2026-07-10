"use client";

import { useState } from "react";
import { AlertTriangle, Eye, ImageOff, RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AssetCardData, AssetLibraryTab } from "@/features/asset-library/types";
import { resolveAssetUrl } from "@/shared/api/asset-url";

interface AssetImageCardProps {
  asset: AssetCardData;
  tab: AssetLibraryTab;
  isSelected: boolean;
  onToggleSelect: (assetId: string) => void;
  onPreview: (asset: AssetCardData) => void;
  onDelete: (asset: AssetCardData) => void;
  onRestore: (asset: AssetCardData) => void;
  onPermanentDelete: (asset: AssetCardData) => void;
}

const CATEGORY_LABELS = {
  character: "角色",
  prop: "道具",
  scene: "场景",
} as const;

export function AssetImageCard({
  asset,
  tab,
  isSelected,
  onToggleSelect,
  onPreview,
  onDelete,
  onRestore,
  onPermanentDelete,
}: AssetImageCardProps) {
  const [imageFailed, setImageFailed] = useState(false);

  const remainingDays =
    "remaining_cleanup_days" in asset ? asset.remaining_cleanup_days : asset.remaining_retention_days;
  const isUrgent =
    ("remaining_cleanup_days" in asset && remainingDays < 7) ||
    ("is_expiring_soon" in asset && asset.is_expiring_soon);
  const displayTimestamp = "deleted_at" in asset && asset.deleted_at ? asset.deleted_at : asset.created_at;
  const imageUrl = resolveAssetUrl(asset.thumbnail_url) ?? resolveAssetUrl(asset.asset_url);

  return (
    <Card className="overflow-hidden border-neutral-800 bg-neutral-900 text-white">
      <div className="relative aspect-[4/3] border-b border-neutral-800 bg-neutral-950">
        {!imageFailed && imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={asset.display_name}
            className="h-full w-full object-cover"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-neutral-400">
            <ImageOff className="size-4" />
            <span>图片加载失败</span>
          </div>
        )}
        <label className="absolute left-2 top-2 flex items-center gap-2 rounded-md bg-black/60 px-2 py-1 text-xs text-white">
          <input
            type="checkbox"
            aria-label={`选择 ${asset.display_name}`}
            checked={isSelected}
            onChange={() => onToggleSelect(asset.asset_id)}
          />
          选择
        </label>
      </div>

      <CardContent className="space-y-3 p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{asset.display_name}</div>
            <div className="mt-1 text-xs text-neutral-400">
              {(asset.related_name || asset.related_id) && `${asset.related_name || "未命名对象"} / ${asset.related_id || "无 ID"}`}
            </div>
          </div>
          {isUrgent ? (
            <Badge variant="destructive" className="shrink-0">
              剩余 {remainingDays} 天
            </Badge>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className="border-neutral-700 text-neutral-200">
            {CATEGORY_LABELS[asset.category]}
          </Badge>
          <Badge variant="secondary" className="bg-neutral-800 text-neutral-200">
            {asset.asset_type_label}
          </Badge>
          {"can_restore" in asset && !asset.can_restore ? (
            <Badge variant="destructive">不可恢复</Badge>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-neutral-400">
          <div>
            <dt>项目</dt>
            <dd className="truncate text-neutral-200">{asset.project_title}</dd>
          </div>
          <div>
            <dt>模型</dt>
            <dd className="truncate text-neutral-200">{asset.model_name}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd className="text-neutral-200">{asset.status}</dd>
          </div>
          <div>
            <dt>质检</dt>
            <dd className="text-neutral-200">{asset.quality_status || "暂无"}</dd>
          </div>
          <div>
            <dt>{tab === "trash" ? "删除时间" : "生成时间"}</dt>
            <dd className="text-neutral-200">
              {new Date(displayTimestamp).toLocaleString("zh-CN")}
            </dd>
          </div>
          <div>
            <dt>{tab === "trash" ? "剩余时间" : "保留期"}</dt>
            <dd className="text-neutral-200">{remainingDays} 天</dd>
          </div>
        </dl>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="xs" onClick={() => onPreview(asset)} aria-label={`查看大图 ${asset.display_name}`}>
            <Eye className="size-3" />
            查看大图
          </Button>
          {tab === "library" ? (
            <Button variant="outline" size="xs" onClick={() => onDelete(asset)} aria-label={`删除${asset.display_name}`} className="border-red-900 text-red-300 hover:bg-red-950/40">
              <Trash2 className="size-3" />
              删除
            </Button>
          ) : (
            <>
              <Button variant="outline" size="xs" onClick={() => onRestore(asset)} aria-label={`恢复${asset.display_name}`}>
                <RotateCcw className="size-3" />
                恢复
              </Button>
              <Button variant="outline" size="xs" onClick={() => onPermanentDelete(asset)} aria-label={`永久删除${asset.display_name}`} className="border-red-900 text-red-300 hover:bg-red-950/40">
                <AlertTriangle className="size-3" />
                永久删除
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
