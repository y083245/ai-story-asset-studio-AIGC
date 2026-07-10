"use client";

import type { AssetCardData, AssetLibraryTab } from "@/features/asset-library/types";
import { AssetImageCard } from "@/features/asset-library/components/AssetImageCard";

interface AssetCategorySectionProps {
  title: string;
  assets: AssetCardData[];
  tab: AssetLibraryTab;
  selectedIds: string[];
  onToggleSelect: (assetId: string) => void;
  onPreview: (asset: AssetCardData) => void;
  onDelete: (asset: AssetCardData) => void;
  onRestore: (asset: AssetCardData) => void;
  onPermanentDelete: (asset: AssetCardData) => void;
}

export function AssetCategorySection({
  title,
  assets,
  tab,
  selectedIds,
  onToggleSelect,
  onPreview,
  onDelete,
  onRestore,
  onPermanentDelete,
}: AssetCategorySectionProps) {
  if (assets.length === 0) return null;

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {assets.map((asset) => (
          <AssetImageCard
            key={asset.asset_id}
            asset={asset}
            tab={tab}
            isSelected={selectedIds.includes(asset.asset_id)}
            onToggleSelect={onToggleSelect}
            onPreview={onPreview}
            onDelete={onDelete}
            onRestore={onRestore}
            onPermanentDelete={onPermanentDelete}
          />
        ))}
      </div>
    </section>
  );
}
