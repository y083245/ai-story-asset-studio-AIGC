"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AssetCardData, AssetLibraryTab } from "@/features/asset-library/types";
import type { AssetDateGroup as AssetDateGroupData } from "@/shared/api/image-assets";
import { AssetProjectGroup } from "@/features/asset-library/components/AssetProjectGroup";

interface AssetDateGroupProps {
  group: AssetDateGroupData;
  tab: AssetLibraryTab;
  selectedIds: string[];
  onToggleSelect: (assetId: string) => void;
  onPreview: (asset: AssetCardData) => void;
  onDelete: (asset: AssetCardData) => void;
  onRestore: (asset: AssetCardData) => void;
  onPermanentDelete: (asset: AssetCardData) => void;
}

export function AssetDateGroup(props: AssetDateGroupProps) {
  const { group, tab, selectedIds, onToggleSelect, onPreview, onDelete, onRestore, onPermanentDelete } = props;
  const [collapsed, setCollapsed] = useState(false);

  return (
    <section className="space-y-4">
      <Button
        variant="ghost"
        className="h-auto w-full justify-start rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-left"
        onClick={() => setCollapsed((value) => !value)}
      >
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
        <div className="ml-1">
          <div className="text-base font-semibold text-white">{group.date}</div>
          <div className="text-xs text-neutral-400">
            {group.total} 张图片 · {group.project_count} 个项目
          </div>
        </div>
      </Button>

      {collapsed ? null : (
        <div className="space-y-4">
          {group.projects.map((project) => (
            <AssetProjectGroup
              key={project.project_id}
              project={project}
              tab={tab}
              selectedIds={selectedIds}
              onToggleSelect={onToggleSelect}
              onPreview={onPreview}
              onDelete={onDelete}
              onRestore={onRestore}
              onPermanentDelete={onPermanentDelete}
            />
          ))}
        </div>
      )}
    </section>
  );
}
