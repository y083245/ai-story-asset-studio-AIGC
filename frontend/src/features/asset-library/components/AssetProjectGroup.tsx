"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { AssetCardData, AssetLibraryTab } from "@/features/asset-library/types";
import type { AssetProjectGroup as AssetProjectGroupData } from "@/shared/api/image-assets";
import { AssetCategorySection } from "@/features/asset-library/components/AssetCategorySection";

interface AssetProjectGroupProps {
  project: AssetProjectGroupData;
  tab: AssetLibraryTab;
  selectedIds: string[];
  onToggleSelect: (assetId: string) => void;
  onPreview: (asset: AssetCardData) => void;
  onDelete: (asset: AssetCardData) => void;
  onRestore: (asset: AssetCardData) => void;
  onPermanentDelete: (asset: AssetCardData) => void;
}

export function AssetProjectGroup({
  project,
  tab,
  selectedIds,
  onToggleSelect,
  onPreview,
  onDelete,
  onRestore,
  onPermanentDelete,
}: AssetProjectGroupProps) {
  return (
    <section className="space-y-4 rounded-xl border border-neutral-800 bg-neutral-900/70 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-white">
          <Link href={`/projects/${project.project_id}`} className="hover:text-blue-300">
            {project.project_title}
          </Link>
        </h2>
        <Badge variant="outline" className="border-neutral-700 text-neutral-300">
          {project.project_status}
        </Badge>
        {project.is_project_in_trash ? <Badge variant="secondary">项目已在回收站</Badge> : null}
        <span className="text-xs text-neutral-500">{project.total} 张图片</span>
        <span className="text-xs text-neutral-500">
          最近生成：{new Date(project.latest_created_at).toLocaleString("zh-CN")}
        </span>
      </div>

      <div className="space-y-5">
        <AssetCategorySection
          title="角色"
          assets={project.categories.character}
          tab={tab}
          selectedIds={selectedIds}
          onToggleSelect={onToggleSelect}
          onPreview={onPreview}
          onDelete={onDelete}
          onRestore={onRestore}
          onPermanentDelete={onPermanentDelete}
        />
        <AssetCategorySection
          title="道具"
          assets={project.categories.prop}
          tab={tab}
          selectedIds={selectedIds}
          onToggleSelect={onToggleSelect}
          onPreview={onPreview}
          onDelete={onDelete}
          onRestore={onRestore}
          onPermanentDelete={onPermanentDelete}
        />
        <AssetCategorySection
          title="场景"
          assets={project.categories.scene}
          tab={tab}
          selectedIds={selectedIds}
          onToggleSelect={onToggleSelect}
          onPreview={onPreview}
          onDelete={onDelete}
          onRestore={onRestore}
          onPermanentDelete={onPermanentDelete}
        />
      </div>
    </section>
  );
}
